#!/usr/bin/env python3
import re
import sys
import math
import pprint
import argparse

# prettyprinter
PP = pprint.PrettyPrinter(indent=4)

# valid races
RACES = {
    'Human': 1,
    'Orc': 2,
    'Dwarf': 4,
    'Night Elf': 8,
    'Undead': 16,
    'Tauren': 32,
    'Gnome': 64,
    'Troll': 128,
    'Goblin': 256,
    'Blood Elf': 512,
    'Draenei': 1024
}
RACES_ALLIANCE = 1 + 4 + 8 + 64 + 1024
RACES_HORDE = 2 + 16 + 32 + 128 + 512

# valid classes
CLASSES = {
    'Warrior': 1,
    'Paladin': 2,
    'Hunter': 4,
    'Rogue': 8,
    'Priest': 16,
    'Death Knight': 32,
    'Shaman': 64,
    'Mage': 128,
    'Warlock': 256,
    'Monk': 512,
    'Druid': 1024,
    'Demon Hunter': 2048
}

# valid actions
ACTIONS = {
    'A': "Accept",
    'C': "Complete",
    'T': "Turn in",
    't': "Turn in when complete",
    'K': "Kill",
    'R': "Run to",
    'H': "Hearth to",
    'h': "Set hearth to",
    'F': "Fly to",
    'f': "Get flight path for",
    'M': "Make",
    'N': "Note",
    'B': "Buy",
    'b': "Take Boat or Zeppelin",
    'U': "Use",
    'L': "Level",
    'l': "Loot",
    'r': "Repair/Restock",
    'D': "Done",
    'J': "Jump",
    'P': "Take portal",
    "!": "Declare",
    "$": "Treasure",
    "=": "Train",
    ";": "Comment"
}

# quest dict - either filled by import or by database query
QUESTS = {}

# expansion max quest ID
MAX_QID_BY_EXPANSION = {
    0:  9665
}

# current file and line number
CURRENTFILE = None
CURRENTLINE = 0

# start zone and current zone
STARTZONE = None
CURRENTZONE = None

# last known location if tracking
LASTLOCATION = (None, None, None)

# header of first guide processed
HEADER = []

# processing state
PROCESS = False
FIRSTHEADER = True
LASTLINEEMPTY = False

# output tag ordering
TAGORDER = [
    'QID', 'ACTIVE', 'AVAILABLE', 'PRE', 'C', 'R', 'LVL', 'P',
    'QO', 'QG', 'T', 'L', 'U', 'RANK',
    'M', 'Z', 'CS', 'CC', 'CN',
    'O', 'S', 'US', 'NC', 'NA'
]

# compiled regular expression for coordinates in step note
NOTE_COORD_RE = re.compile(r"\(\s*(\d+|\d+\.\d+)\s*,\s*(\d+|\d+\.\d+)\s*\)")

# sets of started quests and completed quests
QID_STARTED = []
QID_COMPLETED = []

# dict of AREAS to track
QID_AREAS = {}

# filter QID lists by races/classes
QID_RACES = 0
QID_CLASSES = 0

# database connection cursor for querying information
DBC = None


# -----------------------------------------------------------------------------


def tag_qid(arg):
    """ process QID tag """
    if not arg.isdigit() or arg == '*':
        error("PRE tag expects QID numbers: '%s'" % arg)
    return {'QID': arg}


def tag_active(arg):
    """ process ACTIVE tag """
    if arg.startswith('-') and len(arg) > 1:
        if not arg[1:].isdigit():
            error("ACTIVE tag expects a quest id number: '%s'" % arg)
    else:
        if not arg.isdigit():
            error("ACTIVE tag expects quest id number: '%s'" % arg)
    return {'ACTIVE': arg}


def tag_available(arg):
    """ process AVAILABLE tag """
    if arg.find('^') > 0:
        arglist = arg.split('^')
    elif arg.find('&') > 0:
        arglist = arg.split('&')
    else:
        if not arg.isdigit():
            error("AVAILABLE tag expects quest id numbers: '%s'" % arg)
        return {'AVAILABLE': arg}

    # if it was a list check every entry
    for arg in arglist:
        if not arg.isdigit():
            error("AVAILABLE tag expects quest id numbers: '%s'" % arg)
            break


def tag_pre(arg):
    """ process pre tag """
    # PRE tag can be split into a list by semicolon or plus sign
    if arg.find(';') > 0:
        arglist = arg.split(';')
    elif arg.find('+') > 0:
        arglist = arg.split('+')
    else:
        if not arg.isdigit():
            error("PRE tag expects quest id numbers: '%s'" % arg)
        return {'PRE': arg}

    # if it was a list check every entry
    for arg in arglist:
        if not arg.isdigit():
            error("PRE tag expects quest id numbers: '%s'" % arg)
            break
    return {'PRE': arg}


def tag_n(arg):
    """ process N tag """
    if len(arg):
        return {'N': arg}
    else:
        error("Empty N tag", guidenote=False)


def tag_p(arg):
    """ process P tag """
    if len(arg):
        return {'P': arg}
    else:
        error("Empty P tag")


def tag_c(arg):
    """ process C tag """
    outist = []
    inplist = [x.strip().rstrip() for x in arg.split(',')]
    for inp in inplist:
        inp = inp.capitalize()
        if inp in CLASSES:
            outist.append(inp)
        else:
            error("Ignoring unknown C tag parameter '%s'" % inp)
    if len(outist):
        return {'C': ','.join(outist)}
    else:
        error("Resulting C tag empty")


def tag_r(arg):
    """ process R tag """
    outlist = []
    inplist = [x.strip().rstrip() for x in arg.split(',')]
    for entry in inplist:
        negate = ''
        if entry.startswith('-'):
            negate = '-'
            entry = entry[1:]
        entry = entry.title()
        if entry in RACES:
            outlist.append(negate + entry)
        else:
            error("Ignoring unknown R tag parameter '%s'" % entry)
    if len(outlist):
        return {'R': ','.join(outlist)}
    else:
        error("Resulting R tag empty")


def tag_lvl(arg):
    """ process QID tag """
    if arg.startswith('-') and len(arg) > 1:
        if not arg[1:].isdigit():
            error("LVL tag expects a number: '%s'" % arg)
    else:
        if not arg.isdigit():
            error("LVL tag expects a number: '%s'" % arg)
    return {'LVL': arg}


def tag_rank(arg):
    """ process RANK tag """
    if not arg.isdigit():
        error("RANK tag expects a number: '%s'" % arg)
    return {'RANK': arg}


def tag_m(arg):
    """ process M tag """
    reslist = []
    inplist = [x.strip().rstrip() for x in arg.split(';')]
    for inp in inplist:
        try:
            x, y = inp.split(',', 1)
            x = float(x)
            y = float(y)
        except ValueError:
            error("Malformed M entry '%s'" % inp)
            continue
        reslist.append("{0:.2f},{1:.2f}".format(x, y))
    if len(reslist):
        return {'M': ';'.join(reslist)}


def tag_z(arg):
    """ process Z tag """
    if len(arg):
        if arg not in AREAS[0] and arg not in AREAS[1]:
            error("Zone '%s' not in list of valid zones" % arg)
        return {'Z': arg}
    else:
        error("Empty Z tag")
        return {}


def tag_q(arg):
    """ process Q tag """
    if len(arg):
        error('Tag Q unsupported but copied')
        return {'Q': arg}
    else:
        error("Empty Q tag")
        return {}


def tag_l(arg):
    """ process L tag """
    inplist = arg.strip().rstrip().split(' ', 1)
    for inp in inplist:
        if not inp.isdigit():
            error("L tag requires item id number: '%s'" % inp)
    return {'L': ' '.join(inplist)}


def tag_u(arg):
    """ process U tag """
    arg = arg.strip().rstrip()
    if not arg.isdigit():
        error("U tag requires item id number: '%s'" % arg)
    return {'U': arg}


def tag_qo(arg):
    """ process QO tag """

    if len(arg) == 0:
        error("Empty QO tag")
        return

    arglist = [x.strip().rstrip() for x in arg.split(';')]
    allint = True
    for inp in arglist:
        if not inp.isdigit():
            allint = False

    if not allint:
        error("Convert QO tag '%s' to number" % arg)
    return {'QO': ';'.join(arglist)}


def tag_t(arg):
    """ process T tag """
    if len(arg):
        return {'T': arg}
    else:
        error("Empty T tag removed, check")


def tag_cs():
    """ process CS tag """
    return {'CS': True}


def tag_cc():
    """ process CC tag """
    return {'CC': True}


def tag_cn():
    """ process CN tag """
    return {'CN': True}


def tag_o():
    """ process O tag """
    return {'O': True}


def tag_s():
    """ process S tag """
    return {'S': True}


def tag_us():
    """ process US tag """
    return {'US': True}


def tag_nc():
    """ process US tag """
    return {'NC': True}


def tag_na():
    """ process US tag """
    return {'NA': True}


# -----------------------------------------------------------------------------


def dbupdate_A(parsed):
    """ update A action from database information """
    global DBC

    # get qid from QID or ACTIVE tag, convert to int
    qid = None
    if 'QID' in parsed:
        qid = parsed['QID']
    elif 'AVAILABLE' in parsed:
        qid = parsed['AVAILABLE']
    try:
        qid = int(qid)
    except ValueError:
        return

    # retrieve quest information
    quest = get_quest_info(qid)
    if quest is None:
        return

    # check 1: quest is offered by an NPC
    num = DBC.execute(
        """SELECT ct.name, c.map, c.position_x, c.position_y
        FROM quest_template AS qt
            INNER JOIN creature_queststarter AS cq ON qt.ID = cq.quest
            INNER JOIN creature_template AS ct ON cq.id = ct.entry
            INNER JOIN creature AS c ON cq.id = c.id
        WHERE qt.ID = %s""", (qid,))
    if num > 0:
        dbupdate_at_location(parsed, dbresult=DBC.fetchall())
        return

    # check 2: quest is offered by an gameobject
    num = DBC.execute(
        """SELECT gt.name, g.map, g.position_x, g.position_y
        FROM quest_template AS qt
            INNER JOIN gameobject_queststarter AS gq ON qt.ID = gq.quest
            INNER JOIN gameobject_template AS gt ON gq.id = gt.entry
            INNER JOIN gameobject AS g ON gt.entry = g.id
        WHERE qt.ID = %s""", (qid, ))
    if num > 0:
        dbupdate_at_location(parsed, dbresult=DBC.fetchall())
        return

    # check 3: quest is offered by an item in the inventory
    num = DBC.execute(
        """SELECT it.name, it.entry
        FROM quest_template AS qt
            INNER JOIN item_template AS it ON qt.ID = it.startquest
        WHERE it.startquest = %s""", (qid, ))
    if num > 0:
        # if there are multiple results use the one with the higher id
        # this is only the case with items 6766 and 20310
        dbresult = DBC.fetchall()
        for result in sorted(dbresult, key=lambda x: -x[1]):
            update_parsed_entry(parsed, 'N', 'From ' + result[0])
            update_parsed_entry(parsed, 'O', True)
            update_parsed_entry(parsed, 'U', str(result[1]))
            return

    # something is not quite right when the qid exists but there is no starter
    error("QID %d: '%s' found, but no quest starter found in database" % (
        qid, quest['name']))


def dbupdate_T(parsed):
    """ update T action from database information """
    global DBC

    # get qid from QID tag
    if 'QID' not in parsed:
        return
    try:
        qid = int(parsed['QID'])
    except ValueError:
        return

    # retrieve quest information
    quest = get_quest_info(qid)
    if quest is None:
        return

    # check 1: quest ends at an NPC
    num = DBC.execute(
        """SELECT ct.name, c.map, c.position_x, c.position_y
        FROM quest_template AS qt
            INNER JOIN creature_questender AS cq ON qt.ID = cq.quest
            INNER JOIN creature_template AS ct ON cq.id = ct.entry
            INNER JOIN creature AS c ON cq.id = c.id
        WHERE qt.ID = %s""", (qid,))
    if num > 0:
        dbupdate_at_location(parsed, dbresult=DBC.fetchall())
        return

    # check 2: quest ends at an gameobject
    num = DBC.execute(
        """SELECT gt.name, g.map, g.position_x, g.position_y
        FROM quest_template AS qt
            INNER JOIN gameobject_questender AS gq ON qt.ID = gq.quest
            INNER JOIN gameobject_template AS gt ON gq.id = gt.entry
            INNER JOIN gameobject AS g ON gt.entry = g.id
        WHERE qt.ID = %s""", (qid, ))
    if num > 0:
        dbupdate_at_location(parsed, dbresult=DBC.fetchall())
        return

    # something is not quite right when the qid exists but there is no starter
    error("QID %d: '%s' found, but no quest ender found in database" % (
        qid, quest['name']))


def dbupdate_F(parsed):
    """ update F action from database information """
    global DBC, LASTLOCATION

    # we need a LASTLOCATION set
    # TODO: maybe infer location from startzone/currentzone
    if LASTLOCATION[0] is None:
        error("F tag, but unknown last location")
        return

    # look up all flight masters on current map
    num = DBC.execute(
        """SELECT ct.name, c.map, c.position_x, c.position_y
        FROM creature_template AS ct
        INNER JOIN creature AS c on ct.entry = c.id
        WHERE ct.npcflag & 8192 AND c.map = %s""", (LASTLOCATION[0],)
    )
    if num == 0:
        error("%s tag, but No flight masters found on map %d" % (
            parsed['ACTION'], LASTLOCATION[0]))
        return

    # sort database result by distance from current location
    dbres = list(DBC.fetchall())
    if len(dbres) > 1:
        dbres.sort(
            key=lambda pos: float('inf') if LASTLOCATION[0] != pos[1] else
            math.sqrt((LASTLOCATION[1] - pos[2]) ** 2 + (
                    LASTLOCATION[2] - pos[3]) ** 2))

    # find coordinates for current zone or set zone first
    zone = CURRENTZONE
    if 'Z' in parsed:
        zone = parsed['Z']
    coords = get_thott_coords(dbres[0][1], dbres[0][2], dbres[0][3], zone)
    if coords is None:
        coords = get_thott_coords(dbres[0][1], dbres[0][2], dbres[0][3])
    if coords is not None:
        coordstr = "{0:.2f},{1:.2f}".format(coords[0] + 0.005,
                                            coords[1] + 0.005)

    # update coordinates
    if coords is not None:
        update_parsed_entry(parsed, 'Z', coords[2])
        update_parsed_entry(parsed, 'M', coordstr)

    # update note
    if 'N' not in parsed or parsed['N'].find(dbres[0][0]) < 0:
        update_parsed_entry(parsed, 'N', 'At %s.' % dbres[0][0])


def dbupdate_f(parsed):
    dbupdate_F(parsed)


# -----------------------------------------------------------------------------


def dbupdate_at_location(parsed, dbresult):
    """ update A or T step TourGuide entry with location information """
    global LASTLOCATION

    # re-order result list if we have more than one result to nearest result
    if len(dbresult) > 1 and LASTLOCATION[0] is not None:
        # results on different maps are infinite distance
        dbresult = list(dbresult)
        dbresult.sort(
            key=lambda pos: float('inf') if LASTLOCATION[0] != pos[0] else
            math.sqrt((LASTLOCATION[1] - pos[1]) ** 2 + (
                    LASTLOCATION[2] - pos[2]) ** 2))

    # special processing on the first database result
    first = True
    if dbresult is not None:
        for se in dbresult:

            # get coordinates
            coords = None
            coordstr = ''
            if all(v is not None for v in [se[1], se[2], se[3]]):
                zone = CURRENTZONE
                if 'Z' in parsed:
                    zone = parsed['Z']
                coords = get_thott_coords(se[1], se[2], se[3], zone)
                if coords is None:
                    coords = get_thott_coords(se[1], se[2], se[3])
                if coords is not None:
                    coordstr = "{0:.2f},{1:.2f}".format(coords[0] + 0.005,
                                                        coords[1] + 0.005)

            # update note if it does not contain name
            note = None
            if parsed['ACTION'] in ('A', 'T', 't'):
                if ('N' not in parsed) or \
                        ('N' in parsed and parsed['N'].find(se[0]) < 0):
                    note = '%s %s.' % (
                        'From' if parsed['ACTION'] == 'A' else 'To', se[0])

            # if first match proceed naturally
            if first:
                first = False
                if note is not None:
                    update_parsed_entry(parsed, 'N', note)
                if coords is not None:
                    update_parsed_entry(parsed, 'Z', coords[2])
                    update_parsed_entry(parsed, 'M', coordstr)

                # also note location as last known location
                LASTLOCATION = (se[1], se[2], se[3])

            else:
                src = parsed.copy()
                if note is not None:
                    src['N'] = note
                if coords is not None:
                    src['Z'] = coords[2]
                    src['M'] = coordstr
                print('; ALT: ' + generate_tourguide(src), file=sys.stderr)
                print('; ALT: ' + generate_tourguide(src))


def update_from_quest(parsed, quest):
    """ update TourGuide entry from quest information """

    # update information from quest: PRE/ACTIVE on A steps
    if parsed['ACTION'] == 'A':
        # update required pre/active quests
        pre = quest['link'][0]
        if pre > 0:
            update_parsed_entry(parsed, 'PRE', str(pre))
        if pre < 0:
            update_parsed_entry(parsed, 'ACTIVE', str(-pre))

        # update required races
        reqrace = quest['reqs'][0]
        if reqrace != 0 and reqrace not in (RACES_ALLIANCE, RACES_HORDE):
            racelist = []
            for race, bit in RACES.items():
                if bit & reqrace:
                    racelist.append(race)
            if len(racelist):
                update_parsed_entry(parsed, 'R', ','.join(sorted(racelist)))

        # update required classes
        reqclass = quest['reqs'][1]
        if reqclass != 0:
            classlist = []
            for cls, bit in CLASSES.items():
                if bit & reqclass:
                    classlist.append(cls)
            if len(classlist):
                update_parsed_entry(parsed, 'C', ','.join(sorted(classlist)))

    # update title from quest for quest-related steps
    if parsed['ACTION'] in ('A', 'T', 't', 'C'):
        update_parsed_entry(parsed, 'TITLE', quest['name'])


# -----------------------------------------------------------------------------


def error(errorstring, guidenote=True):
    """ print an error to stderr and note it in the output as comment """
    if CURRENTFILE:
        print('%s:%d: %s' % (CURRENTFILE, CURRENTLINE, errorstring),
              file=sys.stderr)
    else:
        print('line %s: %s' % (CURRENTLINE, errorstring), file=sys.stderr)
    if guidenote:
        print('; --- FIXME: %s' % errorstring)


def get_thott_coords(map, posX, posY, zone=None):
    """ convert world coordinates to thottbot coordinates """

    # bail early if map is not in AREAS
    if map not in AREAS:
        return None

    # record best match
    area = None
    thottX = None
    thottY = None
    tdist = 71.0

    # iterate through all areas in the map
    for zname, zinfo in AREAS[map].items():

        # check if the coordinates fall inside mapping boundaries
        if not zinfo[1] >= posY >= zinfo[2] or not zinfo[3] >= posX >= zinfo[4]:
            continue

        # calculate thottbot coordinates and distance from center (50,50)
        tX = (posY - zinfo[1]) / (zinfo[2] - zinfo[1]) * 100
        tY = (posX - zinfo[3]) / (zinfo[4] - zinfo[3]) * 100
        tD = math.sqrt((50.0 - tX) ** 2 + (50.0 - tY) ** 2)

        # return coordinates if zone was explicitly requested
        if zone is not None and zone == zname:
            return tX, tY, zname

        # hack to find correct zone in the overlapping area list:
        # we use the area with thottbot coordinates closest to the center
        # except for the global zones with an id of zero (Azeroth, Kalimdor)
        if area is None or (zinfo[0] > 0 and tdist > tD):
            area = zname
            thottX = tX
            thottY = tY
            tdist = tD

    # return either best match or none
    if area is not None:
        return thottX, thottY, area
    else:
        return None


def update_parsed_entry(parsed, key, val):
    """ update a single entry in the parsed TourGuide entry """
    if key in parsed:
        if parsed[key] != val:
            error("Updated %s from '%s' to '%s'" % (key, parsed[key], val))
            parsed[key] = val
    else:
        parsed[key] = val


def generate_tourguide(parsed):
    """ generate a TourGuide entry """

    # copy the parsed dict
    src = parsed.copy()
    action = src['ACTION']
    del src['ACTION']

    # note is a special case
    note = None
    if 'N' in src:
        note = src['N']
        del src['N']
        if note.endswith(' .'):
            note = note[:-2] + '.'

    # create action step as first entry in result list
    if 'TITLE' not in src:
        res = [action + ' Unknown']
    else:
        res = [action + ' ' + src['TITLE']]
        del src['TITLE']

    # process ordered tags
    for tag in TAGORDER:
        if tag not in src:
            continue
        res.append(tag)
        if not isinstance(src[tag], bool):
            res.append(src[tag])
        del src[tag]

    # process remaining tags
    for tag in sorted(src):
        res.append(tag)
        if not isinstance(src[tag], bool):
            res.append(src[tag])

    # add note to end if it was set
    if note:
        res.extend(['N', note])

    # return TourGuide string
    return '|'.join(res) + '|'


def process_tourguide(guidestring):
    """ process a single line in the TourGuide format """
    global CURRENTLINE, LASTLINEEMPTY, NOTE_COORD_RE
    global QID_STARTED, QID_COMPLETED

    # split line into arguments, remove whitespaces and reverse for easy pop()
    inlist = [x.strip().rstrip() for x in guidestring.split('|')]
    inlist.reverse()

    # continue if line is empty
    if len(inlist) == 1 and len(inlist[0]) == 0:
        print()
        LASTLINEEMPTY = True
        return

    # retrieve the subject of the guide entry and check if its valid
    action = inlist.pop()
    if action[0] not in ACTIONS:
        error("Not a valid action: '%s'" % action[0])
        return
    if action[1] != ' ':
        error("Line seems malformed: '%s'" % action[0])
        return
    parsed = {'ACTION': action[0], 'TITLE': action[2:]}

    # parse each tag into a dictionary
    LASTLINEEMPTY = False
    while len(inlist):
        tag = inlist.pop()

        # check if tag is empty
        if len(tag) == 0:
            continue

        # check if we have a parser function for this tag
        func = 'tag_' + tag.lower()
        if func not in globals():
            error("Unknown tag '%s'" % tag)
            continue
        func = globals()[func]

        # check if the parser function expects an argument
        if func.__code__.co_argcount > 0:
            if not len(inlist):
                error("Tag '%s' expects a parameter" % tag)
                continue
            res = func(inlist.pop())
        else:
            res = func()
        if isinstance(res, dict):
            for key in res:
                if key in parsed:
                    error("Tag '%s' defined more than once" % key)
                else:
                    parsed[key] = res[key]

    #  special handling for zone transitions
    if 'Z' not in parsed and CURRENTZONE != STARTZONE:
        parsed['Z'] = CURRENTZONE

    # check if the QID is in the set of valid quest ids
    qid = None
    if 'QID' in parsed:
        try:
            qid = int(parsed['QID'])
        except ValueError:
            error("QID '%s' could not be parsed" % parsed['QID'])

        # get quest information from database
        quest = get_quest_info(qid)
        if quest is None:
            error("QID '%s' not found in list of valid QIDs" % parsed['QID'])
        else:
            update_from_quest(parsed, quest)

    # special handling for notes so they are always at the end
    if 'N' in parsed:
        # check for coordinates in note
        match = NOTE_COORD_RE.search(parsed['N'])
        if match:
            try:
                x, y = match.groups()
                x = float(x)
                y = float(y)
                coords = "{0:.2f},{1:.2f}".format(x, y)
                if 'M' in parsed and parsed['M'] != coords:
                    error(("Differing Coords found in N tag: "
                           "{0:.2f},{1:.2f}").format(x, y))
                else:
                    parsed['M'] = coords
                    error("Coords found in N tag, using: %s" % parsed['M'])
            except ValueError:
                pass

    # if we update from database information depends on action type
    if DBC is not None:
        func = 'dbupdate_' + parsed['ACTION']
        if func in globals():
            func = globals()[func]
            func(parsed)

    # record qid in sets
    if qid is not None:
        if parsed['ACTION'] == 'A':
            if qid not in QID_STARTED:
                QID_STARTED.append(qid)
            else:
                error('QID %d already started in guide' % qid)
        elif parsed['ACTION'] == 'T' or parsed['ACTION'] == 't':
            if qid not in QID_COMPLETED:
                QID_COMPLETED.append(qid)
            else:
                error('QID %d already completed in guide' % qid)

    # print generated TourGuide entry
    print(generate_tourguide(parsed))


def set_zone(arg):
    """ set the active/default zone for the following tourguide entries """
    global STARTZONE, CURRENTZONE, LASTLOCATION

    # filter string from argument
    zone = arg.strip().rstrip()
    if zone[0] == '"' or zone[0] == '\'' and zone[0] == zone[-1]:
        zone = zone[1:-1]

    # find zone in AREAS dict
    map = None
    area = None
    for id, arealist in AREAS.items():
        if zone in arealist:
            map = id
            area = arealist[zone]
            break
    if area is None:
        print("Zone '%s' not found" % zone, file=sys.stderr)
        sys.exit(0)

    # set zone
    CURRENTZONE = zone

    # set starting zone for the whole guide if not yet set
    if not STARTZONE:
        STARTZONE = zone
        LASTLOCATION = (map, (area[4] - area[3]) / 2, (area[2] - area[1]) / 2)
        print('Zone Start: %s (%d, %f, %f)' % (
            zone, map, LASTLOCATION[1], LASTLOCATION[2]), file=sys.stderr)
    else:
        print('Zone Change: %s' % zone, file=sys.stderr)


def process_start():
    """ start processing of tourguide entries in input """
    global PROCESS, HEADER, FIRSTHEADER

    PROCESS = True
    if FIRSTHEADER:
        FIRSTHEADER = False
        HEADER.append(line)
        print(*HEADER, sep='\n')
    elif not LASTLINEEMPTY:
        print()
    if CURRENTFILE:
        print('; === %s ===' % CURRENTFILE)


def process_line(inputstring):
    """ process a line in the input """
    global PROCESS, HEADER, FIRSTHEADER, CURRENTLINE

    CURRENTLINE += 1
    inputstring = inputstring.rstrip()
    if not PROCESS and inputstring.startswith(
            'WoWPro:GuideSteps') and inputstring.endswith('[['):
        process_start()
    elif not PROCESS and inputstring.startswith(
            'return') and inputstring.endswith('[['):
        process_start()
    elif inputstring.startswith(']]'):
        PROCESS = False
    elif PROCESS:
        process_tourguide(inputstring)
    else:
        HEADER.append(inputstring)

        # new guide format
        left = inputstring.find('WoWPro:RegisterGuide(')
        right = inputstring.find(')')
        if 0 < left < right and right > 0:
            args = inputstring[left + 21:right].split(',')
            if len(args) > 2:
                set_zone(args[2])
            else:
                error("Could not get zone info: '%s'" % inputstring,
                      guidenote=False)

        # old guide format (WotLK)
        left = inputstring.find('WoWPro_Leveling:RegisterGuide(')
        right = inputstring.find(')')
        if 0 <= left < right and right > 0:
            args = inputstring[left + 30:right].split(',')
            if len(args) > 1:
                set_zone(args[1])
            else:
                error("Could not get zone info: '%s'" % inputstring,
                      guidenote=False)


def print_quest_list(qids, stream=sys.stdout):
    for qid in sorted(qids):
        quest = get_quest_info(qid)
        if quest is None:
            print("%5d [??] Unknown quest" % qid, file=stream)
            continue
        print("%5d [%2d] %s" % (
            qid, quest['lvls'][0], quest['name']),
              file=stream)


def print_quest_xp():
    """ print XP report of all turned in quests """

    if len(QID_COMPLETED) == 0:
        return

    sumxp = 0
    for qid in QID_COMPLETED:
        quest = get_quest_info(qid)
        if quest is None:
            continue
        lvl = quest['lvls'][0]
        xp = 0
        if quest['reqs'][1] == 0:
            if lvl > 0 and quest['diff'] < 8:
                xp =  QUESTXP[lvl][quest['diff']]
                sumxp += xp
        print("%5d [%2d] %6d %s" % (
            qid, lvl, xp, quest['name']),
              file=sys.stderr)

    print("           ------", file=sys.stderr)
    print("           %6d" % sumxp, file=sys.stderr)


def print_quest_tracking():
    """ print report of untracked quests """
    global DBC, QID_AREAS, QID_RACES, QID_CLASSES

    # populate quest lists
    if DBC is not None:
        # query database for earch QID_AREA entry
        for area in QID_AREAS.keys():
            num = DBC.execute(
                """SELECT qt.id
                FROM quest_template as qt
                    INNER JOIN quest_template_addon AS qa ON qt.ID = qa.ID
                WHERE qt.QuestSortID = %s
                    AND
                        (%s = 0 OR qt.AllowableRaces = 0 
                            OR qt.AllowableRaces & %s)
                    AND
                        (%s = 0 OR qa.AllowableClasses = 0
                            OR qa.AllowableClasses & %s)""",
                (area, QID_RACES, QID_RACES, QID_CLASSES, QID_CLASSES))
            if num == 0:
                continue
            for res in DBC.fetchall():
                QID_AREAS[area].add(res[0])
    else:
        # look in QUESTS database for each quest in QID_AREAS
        for qid, quest in QUESTS.items():
            sort = quest['sort']
            if sort in QID_AREAS:
                # implement race filter if enabled
                if QID_RACES != 0 and \
                        quest['reqs'][0] != 0 and \
                        quest['reqs'][0] & QID_RACES == 0:
                   continue
                QID_AREAS[sort].add(qid)

    # process earch area
    for area, allquests in QID_AREAS.items():
        diff = allquests.difference(set(QID_STARTED), set(QID_COMPLETED))
        if len(diff):
            print("\nUnhandled quests for '%s':" % AREATABLE[area][0],
                  file=sys.stderr)
            print_quest_list(diff, stream=sys.stderr)


def get_quest_info(qid):
    """ get quest information, either from database or static import """
    global DBC

    # static import
    if DBC is None:
        global QUESTS
        if qid in QUESTS:
            return QUESTS[qid]
        else:
            return None

    # use cache of quest information from the database
    global QUESTS_CACHE
    if 'QUESTS_CACHE' not in globals():
        QUESTS_CACHE = {}
    if qid in QUESTS_CACHE:
        return QUESTS_CACHE[qid]

    # retrieve information from database
    num = DBC.execute("""
        SELECT
            qt.ID,
            qt.LogTitle,
            qt.QuestLevel,
            qt.MinLevel,
            qa.MaxLevel,
            qt.QuestSortID,
            qt.QuestInfoID,
            qa.PrevQuestID,
            qa.NextQuestID,
            qa.ExclusiveGroup,
            qt.RewardNextQuest,
            qt.RewardXPDifficulty,
            qt.AllowableRaces,
            qa.AllowableClasses
        FROM quest_template AS qt
        INNER JOIN quest_template_addon AS qa ON qt.ID = qa.ID
        WHERE qt.ID = %s""", (qid,))
    if num != 1:
        return None
    entry = DBC.fetchone()
    QUESTS_CACHE[qid] = {
            'name': entry[1],
            'sort': entry[5],
            'info': entry[6],
            'lvls': (entry[2], entry[3], entry[4]),
            'link': (entry[7], entry[8], entry[9], entry[10]),
            'reqs': (entry[12], entry[13]),
            'diff': entry[11]
        }
    return QUESTS_CACHE[qid]


def parse_args():
    """ parse command line arguments """
    global QID_RACES, QID_CLASSES

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'file', type=argparse.FileType('r'), nargs='*', default=[sys.stdin])
    parser.add_argument(
        '-z', '--zone', dest='header',
        help='Check QIDs in guide for QIDs in guide database')
    parser.add_argument(
        '-A', '--alliance', dest='alliance', action='store_true',
        help='Filter quests to available for Alliance')
    parser.add_argument(
        '-H', '--horde', dest='horde', action='store_true',
        help='Filter quests to available for Horde')

    # database connection
    database = parser.add_argument_group('database')
    database.add_argument(
        '-d', '--database', dest='database', action='store_true',
        help='Enable querying AzerothCore style MySQL database')
    database.add_argument(
        '--dbname', dest='dbname', metavar='DATABASE', default='acore_world',
        help='Name of database (default: %(default)s)')
    database.add_argument(
        '-u', '--dbuser', dest='dbuser', metavar='USERNAME', default='reader',
        help='User for database access (default: %(default)s)')
    database.add_argument(
        '-p', '--dbpass', dest='dbpass', metavar='PASSWORD', default='reader',
        help='Password for database access (default: %(default)s)')
    opts = parser.parse_args()

    # check alliance/horde filters
    if opts.alliance and opts.horde:
        print("ERROR: Can't filter by Alliance and Horde at the same time.",
              file=sys.stderr)
        sys.exit(1)
    if opts.alliance:
        QID_RACES = RACES_ALLIANCE
    if opts.horde:
        QID_RACES = RACES_HORDE

    # establish database connection?
    if opts.database:
        # import MySQL module
        try:
            import MySQLdb
        except ImportError as ie:
            print("ERROR: Database querying enabled but can't import MySQLdb",
                  '       %s' % repr(ie), sep='\n', file=sys.stderr)
            sys.exit(1)
        try:
            dbconnection = MySQLdb.connect(
                db=opts.dbname, user=opts.dbuser, passwd=opts.dbpass)
        except MySQLdb.OperationalError as oe:
            print("ERROR: Could not connect to database %s" % opts.dbname,
                  '       %s' % repr(oe), sep='\n', file=sys.stderr)
            sys.exit(1)

        # create a cursor to use for database connections
        global DBC
        DBC = dbconnection.cursor()
    else:
        # TODO: make this pre- and post-Cataclysm dependant
        global QUESTS
        try:
            from filter_questdb_pre import QUESTS
        except ImportError:
            print("ERROR: Could not read questdb_pre.py", file=sys.stderr)
            sys.exit(1)

    # import information
    # TODO: make this pre- and post-Cataclysm dependant
    global QUESTXP, AREAS, AREATABLE
    from filter_info_pre import QUESTXP
    from filter_info_pre import AREAS
    from filter_info_pre import AREATABLE

    # if a quest log header is set check if it is known in the AREATABLE
    if opts.header:
        global QID_AREAS
        headers = opts.header.split(',')
        for header in headers:
            header = header.strip().rstrip()
            area = None
            for areaid, info in AREATABLE.items():
                if info[0] == header:
                    area = areaid
                    break
            if area is None:
                print("ERROR: Zone/Header '%s' unknown in AreaTable" % header,
                      file=sys.stderr)
                sys.exit(0)
            QID_AREAS[area] = set()

    # return parsed options
    return opts


# -----------------------------------------------------------------------------


if __name__ == '__main__':

    # parse command line arguments
    options = parse_args()

    # read each file from command line
    for file in options.file:
        CURRENTFILE = file.name
        CURRENTLINE = 0
        print('--- %s ---' % CURRENTFILE, file=sys.stderr)
        for line in file:
            process_line(line)
        PROCESS = False

    if not FIRSTHEADER:
        print(']]', 'end)', sep='\n')

    print_quest_xp()
    print('%d quests started, %d quests completed' % (
        len(QID_STARTED), len(QID_COMPLETED)), file=sys.stderr)

    # check QIDs in quest db
    if options.header:
        print_quest_tracking()
