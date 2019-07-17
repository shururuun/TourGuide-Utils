#!/usr/bin/env python3
import sys
import math
import pprint
import argparse
import MySQLdb

# prettyprinter
PP = pprint.PrettyPrinter(indent=4)

# database connection cursor for querying information
DBC = None


def display_creature(name, zone=None):
    """ display creature location """
    global DBC

    num = DBC.execute(
        """SELECT ct.entry, ct.name, c.map, c.position_x, c.position_y
        FROM creature_template AS ct
            INNER JOIN creature AS c ON ct.entry = c.id
        WHERE ct.name LIKE %s""", ('%%%s%%' % name,))
    if num > 0:
        for entry in DBC.fetchall():
            c1 = get_thott_coords(entry[2], entry[3], entry[4])
            if c1 is not None:
                print("{0:5d} {1:30s} |M|{2:.2f},{3:.2f}|Z|{4:s}|".format(
                    entry[0], entry[1],
                    c1[0] + 0.005, c1[1] + 0.005, c1[2]))
            if zone is not None:
                c2 = get_thott_coords(entry[2], entry[3], entry[4], zone)
                if c2 is not None and c2 != c1:
                    print("{0:5d} {1:30s} |M|{2:.2f},{3:.2f}|Z|{4:s}|".format(
                        entry[0], entry[1],
                        c2[0] + 0.005, c2[1] + 0.005, c2[2]))


def get_thott_coords(map, posX, posY, zone=None):
    """ convert world coordinates to thottbot coordinates """

    # bail early if map is not in AREAS
    if map not in AREAS:
        return None

    # record best match
    area = None
    tmap = None
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
        if area is None or tmap == 0 or (zinfo[0] > 0 and tdist > tD):
            area = zname
            tmap = zinfo[0]
            thottX = tX
            thottY = tY
            tdist = tD

    # return either best match or none
    if area is not None:
        return thottX, thottY, area
    else:
        return None


def parse_args():
    """ parse command line arguments """
    global QID_RACES, QID_CLASSES

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'name', metavar='NAME', nargs='+')
    parser.add_argument(
        '-z', '--zone', dest='zone', metavar='ZONE',
        help='To zone')

    # database connection
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

    # import information
    global QUESTXP, AREAS, AREATABLE
    from filter_info_pre import QUESTXP
    from filter_info_pre import AREAS
    from filter_info_pre import AREATABLE

    # return parsed options
    return opts


# -----------------------------------------------------------------------------


if __name__ == '__main__':

    # parse command line arguments
    options = parse_args()

    zone = None
    if options.zone:
        for map, zones in AREAS.items():
            if options.zone in zones:
                zone = options.zone

    # read each file from command line
    for name in options.name:
        display_creature(name, zone)
