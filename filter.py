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

# valid zones
ZONES = {
    'Ashenvale',
    'Durotar',
    'Feralas',
    'Moonglade',
    'Mulgore',
    'Orgrimmar',
    'Silverpine Forest',
    'Stonetalon Mountains',
    'Stranglethorn Vale',
    'The Barrens',
    'Thunder Bluff',
    'Tirisfal Glades',
    'Undercity'
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
        if arg not in ZONES:
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

