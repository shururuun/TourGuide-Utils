#!/usr/bin/env python3
import re
import sys
import argparse

# import quest db
from questdb import QUESTDB

# generate a set of QIDs in QUESTDB
VALID_QIDS = frozenset([
    qid for header, data in QUESTDB.items() for qid in data.keys()])

# generate a dict of quest refs
QUEST_BY_QID = {qid: info for (header, quest) in QUESTDB.items()
                for (qid, info) in quest.items()}

# valid races
RACES = {
    'Blood Elf',
    'Draenei',
    'Dwarf',
    'Gnome',
    'Human',
    'Night Elf',
    'Orc',
    'Tauren',
    'Troll',
    'Undead'
}

# valid classes
CLASSES = {
    'Druid',
    'Hunter',
    'Mage',
    'Paladin',
    'Priest',
    'Rogue',
    'Shaman',
    'Warlock',
    'Warrior'
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


# world area data from WorldMapArea.dbc
# https://wow.tools/dbc/?dbc=worldmaparea&build=1.13.0.28211#search=&page=1
# map names are taken from AreaTable.tbc
# https://wow.tools/dbc/?dbc=areatable&build=1.13.2.30979#search=&page=1
# tuple is: id, left, right, top, bottom
AREAS = {
    0: {'Alterac Mountains': (36, 783.3333, -2016.667, 1500.0, -366.6667),
        'Arathi Highlands': (45, -866.6666, -4466.667, -133.3333, -2533.333),
        'Azeroth': (0, 16000.0, -19199.9, 7466.6, -16000.0),
        'Badlands': (3, -2079.167, -4566.667, -5889.583, -7547.917),
        'Blasted Lands': (4, -1241.667, -4591.667, -10566.67, -12800.0),
        'Burning Steppes': (46, -266.6667, -3195.833, -7031.25, -8983.333),
        'Deadwind Pass': (41, -833.3333, -3333.333, -9866.666, -11533.33),
        'Dun Morogh': (1, 1802.083, -3122.917, -3877.083, -7160.417),
        'Duskwood': (10, 833.3333, -1866.667, -9716.666, -11516.67),
        'Eastern Plaguelands': (139, -2185.417, -6056.25, 3800.0, 1218.75),
        'Elwynn Forest': (12, 1535.417, -1935.417, -7939.583, -10254.17),
        'Hillsbrad Foothills': (267, 1066.667, -2133.333, 400.0, -1733.333),
        'The Hinterlands': (47, -1575.0, -5425.0, 1466.667, -1100.0),
        'Ironforge': (1537, -713.5914, -1504.216, -4569.241, -5096.846),
        'Loch Modan': (38, -1993.75, -4752.083, -4487.5, -6327.083),
        'Redridge Mountains': (44, -1570.833, -3741.667, -8575.0, -10022.92),
        'Searing Gorge': (51, -322.9167, -2554.167, -6100.0, -7587.5),
        'Silverpine Forest': (130, 3450.0, -750.0, 1666.667, -1133.333),
        'Stormwind City': (1519, 1380.971, 36.70063, -8278.851, -9175.205),
        'Stranglethorn Vale': (33, 2220.833, -4160.417, -11168.75, -15422.92),
        'Swamp of Sorrows': (8, -2222.917, -4516.667, -9620.833, -11150.0),
        'Tirisfal Glades': (85, 3033.333, -1485.417, 3837.5, 824.9999),
        'Undercity': (1497, 873.1926, -86.1824, 1877.945, 1237.841),
        'Western Plaguelands': (28, 416.6667, -3883.333, 3366.667, 500.0),
        'Westfall': (40, 3016.667, -483.3333, -9400.0, -11733.33),
        'Wetlands': (11, -389.5833, -4525.0, -2147.917, -4904.167)},
    1: {'Ashenvale': (331, 1700.0, -4066.667, 4672.917, 829.1666),
        'Aszhara': (16, -3277.083, -8347.916, 5341.667, 1960.417),
        'The Barrens': (17, 2622.917, -7510.417, 1612.5, -5143.75),
        'Darkshore': (148, 2941.667, -3608.333, 8333.333, 3966.667),
        'Darnassus': (1657, 2938.363, 1880.03, 10238.32, 9532.587),
        'Desolace': (405, 4233.333, -262.5, 452.0833, -2545.833),
        'Durotar': (14, -1962.5, -7250.0, 1808.333, -1716.667),
        'Dustwallow Marsh': (15, -974.9999, -6225.0, -2033.333, -5533.333),
        'Felwood': (361, 1641.667, -4108.333, 7133.333, 3300.0),
        'Feralas': (357, 5441.667, -1508.333, -2366.667, -7000.0),
        'Kalimdor': (0, 17066.6, -19733.21, 12799.9, -11733.3),
        'Moonglade': (493, -1381.25, -3689.583, 8491.666, 6952.083),
        'Mulgore': (215, 2047.917, -3089.583, -272.9167, -3697.917),
        'Orgrimmar': (1637, -3680.601, -5083.206, 2273.877, 1338.461),
        'Silithus': (1377, 2537.5, -945.834, -5958.334, -8281.25),
        'Stonetalon Mountains': (406, 3245.833, -1637.5, 2916.667, -339.5833),
        'Tanaris': (440, -218.75, -7118.75, -5875.0, -10475.0),
        'Teldrassil': (141, 3814.583, -1277.083, 11831.25, 8437.5),
        'Thousand Needles': (400, -433.3333, -4833.333, -3966.667, -6900.0),
        'Thunder Bluff': (1638, 516.6666, -527.0833, -849.9999, -1545.833),
        'Ungoro Crater': (490, 533.3333, -3166.667, -5966.667, -8433.333),
        'Winterspring': (618, -316.6667, -7416.667, 8533.333, 3800.0)}
}


# current file and line number
CURRENTFILE = None
CURRENTLINE = 0

# start zone and current zone
STARTZONE = None
CURRENTZONE = None

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
QID_STARTED = set()
QID_COMPLETED = set()


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
    for entry in arglist:
        if not entry.isdigit():
            error("AVAILABLE tag expects quest id numbers: '%s'" % entry)
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
    for entry in arglist:
        if not entry.isdigit():
            error("PRE tag expects quest id numbers: '%s'" % entry)
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
    outlist = []
    inplist = [x.strip().rstrip() for x in arg.split(',')]
    for entry in inplist:
        entry = entry.capitalize()
        if entry in CLASSES:
            outlist.append(entry)
        else:
            error("Ignoring unknown C tag parameter '%s'" % entry)
    if len(outlist):
        return {'C': ','.join(outlist)}
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
    for entry in inplist:
        try:
            x, y = entry.split(',', 1)
            x = float(x)
            y = float(y)
        except ValueError:
            error("Malformed M entry '%s'" % entry)
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
    for entry in inplist:
        if not entry.isdigit():
            error("L tag requires item id number: '%s'" % entry)
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
    for entry in arglist:
        if not entry.isdigit():
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


def error(errorstring, guidenote=True):
    """ print an error to stderr and note it in the output as comment """
    if CURRENTFILE:
        print('%s:%d: %s' % (CURRENTFILE, CURRENTLINE, errorstring),
              file=sys.stderr)
    else:
        print('line %s: %s' % (CURRENTLINE, errorstring), file=sys.stderr)
    if guidenote:
        print('; --- FIXME: %s' % errorstring)


def process_entry(guidestring):
    """ process a single line in the tourguide format """
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
    guide = [inlist.pop()]
    if guide[0][0] not in ACTIONS:
        error("Not a valid action: '%s'" % inlist[0][0])
        return
    if guide[0][1] != ' ':
        error("Line seems malformed: '%s'" % inlist[0])
        return

    # line isn't empty then
    LASTLINEEMPTY = False

    # parse each tag into a dictionary
    parsed = {}
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
            if qid not in VALID_QIDS:
                error("QID '%s' not found in list of valid QIDs" % parsed['QID'])
        except ValueError:
            error("QID '%s' could not be parsed" % parsed['QID'])

    # special handling for notes so they are always at the end
    note = None
    if 'N' in parsed:
        note = parsed['N']
        del parsed['N']

        # check for coordinates in note
        match = NOTE_COORD_RE.search(note)
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
            except ValueError as ex:
                pass

    # process ordered tags
    for tag in TAGORDER:
        if tag not in parsed:
            continue
        guide.append(tag)
        if not isinstance(parsed[tag], bool):
            guide.append(parsed[tag])
        del parsed[tag]

    # process remaining tags
    for tag in sorted(parsed):
        guide.append(tag)
        if not isinstance(parsed[tag], bool):
            guide.append(parsed[tag])

    # if note was set add it to the end
    if note:
        if note.endswith(' .'):
            note = note[:-2] + '.'
        guide.extend(['N', note])

    # record qid in sets
    if qid is not None:
        if guide[0][0] == 'A':
            if qid not in QID_STARTED:
                QID_STARTED.add(qid)
            else:
                error('QID %d already started in guide' % qid)
        elif guide[0][0] == 'T' or guide[0][0] == 't':
            if qid not in QID_COMPLETED:
                QID_COMPLETED.add(qid)
            else:
                error('QID %d already completed in guide' % qid)

    # print generated tourguide line
    print('|'.join(guide) + '|')


def set_zone(arg):
    """ set the active/default zone for the following tourguide entries """
    global STARTZONE, CURRENTZONE

    # filter string from argument
    zone = arg.strip().rstrip()
    if zone[0] == '"' or zone[0] == '\'' and zone[0] == zone[-1]:
        zone = zone[1:-1]

    # set zone
    CURRENTZONE = zone

    # set starting zone for the whole guide if not yet set
    if not STARTZONE:
        STARTZONE = zone
        print('Zone Start: %s' % zone, file=sys.stderr)
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
        process_entry(inputstring)
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


def print_quest_list(qids, file=sys.stdout):
    for qid in sorted(qids):
        if qid not in QUEST_BY_QID:
            print("Unknown quest %d" % qid, file=sys.stderr)
            sys.exit(0)
        print("%5d [%2d] %s" % (
            qid, QUEST_BY_QID[qid]['lvl'], QUEST_BY_QID[qid]['title']),
              file=file)


# -----------------------------------------------------------------------------


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'file', type=argparse.FileType('r'), nargs='*', default=[sys.stdin])
    parser.add_argument(
        '-z', '--zone', dest='header',
        help='Check QIDs in guide for QIDs in guide database')
    options = parser.parse_args()

    # check if header is known in quest db
    if options.header and options.header not in QUESTDB:
        print("ERROR: Zone/Header '%s' not known in Quest DB" % options.header,
              file=sys.stderr)

    for file in options.file:
        CURRENTFILE = file.name
        CURRENTLINE = 0
        print('--- %s ---' % CURRENTFILE, file=sys.stderr)
        for line in file:
            process_line(line)
        PROCESS = False

    if not FIRSTHEADER:
        print(']]', 'end)', sep='\n')

    print('%d quests started, %d quests completed' % (
        len(QID_STARTED), len(QID_COMPLETED)), file=sys.stderr)

    # check QIDs in quest db
    if options.header:
        check_qids = frozenset([qid for qid in QUESTDB[options.header].keys()])
        diff = check_qids.difference(QID_STARTED, QID_COMPLETED)
        if len(diff):
            print("Unhandled quests for zone/header '%s':" % options.header,
                  file=sys.stderr)
            print_quest_list(diff, file=sys.stderr)
        else:
            print("No unhandled quests for zone/header '%s'" % options.header,
                  file=sys.stderr)

