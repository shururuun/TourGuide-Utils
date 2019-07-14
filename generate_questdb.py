#!/usr/bin/env python3
import re
import sys
import math
import pprint
import MySQLdb
import argparse

# prettyprinter
PP = pprint.PrettyPrinter(indent=4)

# database connection cursor for querying information
DBC = None

# QUESTS from Quest Database
QUESTS = {}


def read_quests():
    global DBC, QUESTS

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
        INNER JOIN quest_template_addon AS qa ON qt.ID = qa.ID""")
    if num <= 1:
        print("ERROR: No results while querying quests", file=sys.stderr)
        sys.exit(1)
    for entry in DBC.fetchall():
        QUESTS[entry[0]] = {
            'name': entry[1],
            'sort': entry[5],
            'info': entry[6],
            'lvls': (entry[2], entry[3], entry[4]),
            'link': (entry[7], entry[8], entry[9], entry[10]),
            'reqs': (entry[12], entry[13]),
            'diff': entry[11]
        }


def parse_args():
    global DBC
    parser = argparse.ArgumentParser()

    # command line arguments for database connection
    database = parser.add_argument_group('database')
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

    # open database connection and create the cursor
    try:
        dbconnection = MySQLdb.connect(
            db=opts.dbname, user=opts.dbuser, passwd=opts.dbpass)
    except MySQLdb.OperationalError as oe:
        print("ERROR: Could not connect to database %s" % opts.dbname,
              '       %s' % repr(oe), sep='\n', file=sys.stderr)
        sys.exit(1)
    DBC = dbconnection.cursor()

    # return parsed options
    return opts


if __name__ == '__main__':

    # parse command line arguments
    options = parse_args()

    # query quest database
    read_quests()

    # generate output
    print("QUESTS =", PP.pformat(QUESTS))

