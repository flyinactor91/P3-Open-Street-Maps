#!/usr/bin/python3

##--Michael duPont
##--createjsonmongo.py
##--This file iterparses the osm xml file and uses the value cleaning function to fix
##--mistakes before creating the json file or creating the mongo osm.orangecounty db

import xml.etree.cElementTree as ET
from pprint import pprint
import json , re

dataList = []
node = {}
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
streetReplacements = {'St':'Street','St.':'Street','Ave':'Avenue', \
					  'Blvd':'Boulevard','Cir':'Circle','blvd.':'Boulevard', \
					  'Rd':'Road','Dr':'Drive'}

#Cleans values on a key basis
streetReplacements = {'St':'Street','St.':'Street','Ave':'Avenue','Blvd':'Boulevard', \
					  'Cir':'Circle','blvd.':'Boulevard','Rd':'Road','Dr':'Drive'}
nameReplacements = {"chili's":"Chili's",'fairwinds credit union':'Fairwinds Credit Union', \
					'gamestop':'GameStop','freezone street':'FreeZone Street', \
					'preston street':'Preston Street','7-eleven':'7-Eleven','atm':'Atm', \
					'doubletree':'DoubleTree','alta Westgate Drive':'Alta Westgate Drive', \
					'bp':'BP','aldi':'ALDI', \
					'stoneybrook fitness center':'Stoneybrook Fitness Center'}
operReplacements = {'chase bank na':'Chase','city of orlando':'City of Orlando', \
					'disney parks':'Disney Parks and Resorts', \
					'disney parks and reosrt':'Disney Parks and Resorts', \
					'fdot':'Florida Department of Transportation', \
					'suncoast energys':'Suncoast Energys', \
					'seaworld parks & entertainment':'SeaWorld Parks and Entertainment'}
def cleanVal(key , val):
	val = val.replace('_' , ' ')
	#Fix for itemvals where the majority are lowercase
	if key in ['cuisine','denomination','leisure','shop']: return val.lower()
	elif key in ['routes','sidewalk']: return val.split(';')
	#Replace 'pri' with 'private' for 'access' key
	elif key == 'access' and val == 'pri': return 'private'
	#Fix city capitalization
	elif key == 'addr:city':
		split = val.split(' ')
		for i in range(len(split)): split[i] = split[i].capitalize()
		return ' '.join(split)
	elif key == 'addr:state' and val != 'Florida': return 'Florida'
	#Fix street name shortenings
	elif key == 'addr:street':
		split = val.split(' ')
		if split[-1] in streetReplacements: split[-1] = streetReplacements[split[-1]]
		return ' '.join(split)
	#Strip "FL" header and sub-code from zip code numbers
	elif key == 'addr:postcode': return val.strip('FL ').split('-')[0]
	elif key == 'brand':
		if val == '7-11': return '7-Eleven'
		elif val == 'Edwin Watts Golf Shops': return 'Edwin Watts'
		else: return val
	elif key == 'name' and val.lower() in nameReplacements: return nameReplacements[val.lower()]
	elif key == 'oneway':
		if val == '1': return 'yes'
		elif val == '-1': return 'no'
		else: return val
	elif key == 'operator' and val.lower() in operReplacements: return operReplacements[val.lower()]
	#Standardize phone number format
	elif key == 'phone':
		if val[:2] == '1-': val = val[2:]
		for char in ['+1',' ','-','.','(',')','+']: val = val.replace(char , '')
		if val[:2] == '18': return '+1 1-{0}-{1}-{2}'.format(val[1:4] , val[4:7] , val[7:])
		return '+1 {0}-{1}-{2}'.format(val[:3] , val[3:6] , val[6:])
	elif key == 'railway':
		if val == 'emergancy platform': return 'emergency platform'
		elif val == 'monorial': return 'monorail'
		else: return val
	elif key == 'sport':
		if val == 'beachvolleyball': return 'beach volleyball'
		elif val == 'minigolf': return 'miniature golf'
		else: return val
	elif key == 'width': return val.strip('ft')
	else: return val

#Returns True if item contains only lowercase alpha characters
def isalphalower(item):
	return item.isalpha() and item.islower()

#Returns True if item contains only lowercase characters,
#no problem characters, and colon characters equal to numCol
def islowercolon(item , numCol=1):
	return item.islower() and item.count(':') == numCol \
	and not bool(problemchars.search(item))

#Split a key with known subkey replacing keys as necessary
keyReplacement = {'addr':'address'}
def splitKey(key):
	split = key.split(':')
	if split[0] in keyReplacement: split[0] = keyReplacement[split[0]]
	return split[0] , split[1]

#Set value for key in node. Handles edge cases
def setValue(key , newVal , subKey=None):
	global node
	if not newVal: print(key , newVal , subKey)
	if subKey:
		if key in node:
			#If key collision, set key val to dict with new and old values
			if type(node[key]) != dict:
				oldVal = node[key]
				node[key] = {key:oldVal , subKey:newVal}
			else: node[key][subKey] = newVal
		else: node[key] = {subKey:newVal}
	else: node[key] = newVal

def postCheck():
	if 'address' in node:
		if 'county' not in node['address']: node['address']['county'] = 'Orange'
		if 'state' not in node['address']: node['address']['state'] = 'Florida'
		if 'country' not in node['address']: node['address']['country'] = 'US'

def processElement(element):
	global node
	node = {}
	#Parse elements attributes. Attribs are split id, pos, and created
	for item in element.attrib:
		if item == 'id': node['_id'] = element.attrib[item]
		elif item in ['lat','lon']:
			if 'pos' in node: node['pos'][item] = element.attrib[item]
			else: node['pos'] = {item:element.attrib[item]}
		else:
			if 'created' in node: node['created'][item] = element.attrib[item]
			else: node['created'] = {item:element.attrib[item]}
	#Iterate over child tag elements
	for tag in element.iter('tag'):
		keyVal = tag.get('k')
		if isalphalower(keyVal): setValue(keyVal , cleanVal(keyVal , tag.get('v')))
		elif islowercolon(keyVal):
			split = keyVal.split(':')
			setValue(split[0] , cleanVal(keyVal , tag.get('v')) , split[1])
	postCheck()
	return node

#Set to True when creating MongoDB, False for JSON file
makeDB = True
def main(fileIn , fileOut):
	if makeDB:
		from pymongo import MongoClient
		client = MongoClient("mongodb://localhost:27017")
		db = client.osm
	#Iterparse node and way elements
	for _, element in ET.iterparse(fileIn):
		if element.tag in ['node','way']:
			curNode = processElement(element)
			curNode['type'] = element.tag
			if makeDB: db.orangecounty.insert(curNode)
			else: dataList.append(curNode)
	#Save dataList out as JSON
	if not makeDB:
		with open(fileOut , 'w') as fout: fout.write(json.dumps(dataList))

if __name__ == "__main__":
	main('orlandomap.osm' , 'orlandomap.json')