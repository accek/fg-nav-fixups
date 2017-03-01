#!/usr/bin/env python

import gzip
import argparse
import os
import xml.etree.cElementTree as ElementTree
import sys

M_IN_FT = 3.280839895

COORD_DEG_EPS = 1/111000.0  # 1 meter along meridian
ELEV_M_EPS = 5.0
HDG_DEG_EPS = 0.1

parser = argparse.ArgumentParser(description=('Converts .ils.xml corrections '
	'to nav.dat overrides.'))
parser.add_argument('airports_dir',
                    help='Airports folder')
parser.add_argument('nav_dat',
                    help='nav.dat[.gz] file')
parser.add_argument('--rm-script', metavar='FILENAME',
					help='gen. rm script for redundant files')

args = parser.parse_args()

ils_data = {}
ils_filenames = []

for root, dirs, files in os.walk(args.airports_dir):
	for filename in files:
		if filename.endswith(".ils.xml"):
			path = os.path.join(root, filename)
			apt = os.path.basename(path).split('.')[0]
			ils_filenames.append(path)
			with open(path) as f:
				xml = ElementTree.parse(f)
				for rwy in xml.findall('runway'):
					for ils in rwy.findall('ils'):
						lon = float(ils.findtext('lon'))
						lat = float(ils.findtext('lat'))
						hdg = float(ils.findtext('hdg-deg'))
						elev = float(ils.findtext('elev-m'))
						rwy = ils.findtext('rwy')
						navid = ils.findtext('nav-id')

						ils_data[(apt, rwy)] = (lon, lat, hdg, elev, navid,
								filename)

used_keys = set()
used_filenames = set()

with gzip.GzipFile(args.nav_dat) as nav_file:
	for line in nav_file.readlines():
		line = line.rstrip()
		if not line.strip():
			continue
		tokens = line.strip().split()
		row_type = int(tokens[0])
		if row_type != 4:
			continue
		apt = tokens[8]
		rwy = tokens[-2]
		fixup = ils_data.get((apt, rwy), None)
		if fixup is None:
			continue
		used_keys.add((apt, rwy))

		lon, lat, hdg, elev, navid, filename = fixup
		dlon = float(tokens[2]) - lon
		dlat = float(tokens[1]) - lat
		delev = int(tokens[3]) / M_IN_FT - elev
		dhdg = float(tokens[6]) - hdg

		if abs(dlon) > COORD_DEG_EPS or abs(dlat) > COORD_DEG_EPS \
				or abs(delev) > ELEV_M_EPS or abs(dhdg) > HDG_DEG_EPS \
				or navid != tokens[7]:

			print >>sys.stderr, apt, rwy,
			if abs(dlon) > COORD_DEG_EPS or abs(dlat) > COORD_DEG_EPS:
				print >>sys.stderr, 'dlon', dlon, 'dlat', dlat,
			if abs(delev) > ELEV_M_EPS:
				print >>sys.stderr, 'delev', delev,
			if abs(dhdg) > HDG_DEG_EPS:
				print >>sys.stderr, 'dhdg', dhdg,
			if navid != tokens[7]:
				print >>sys.stderr, 'navids', navid, tokens[7],
			print >>sys.stderr

			tokens[1] = '% 012.8f' % lat
			tokens[2] = '% 013.8f' % lon
			tokens[3] = '%6d' % int(round(elev * M_IN_FT))
			tokens[6] = '%11.3f' % hdg
			tokens[7] = navid
			print ' '.join(tokens)

			used_filenames.add(filename)
		else:
			print >>sys.stderr, apt, rwy, 'NO DIFF'

for apt, rwy in set(ils_data.iterkeys()).difference(used_keys):
	print >>sys.stderr, apt, rwy, 'NO SUCH ILS'

if args.rm_script:
	with open(args.rm_script, 'w') as f:
		for filename in set(ils_filenames).difference(used_filenames):
			print >>f, 'git rm', filename
