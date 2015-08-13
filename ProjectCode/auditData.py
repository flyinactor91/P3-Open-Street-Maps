#!/usr/bin/python3

##--Michael duPont
##--auditData.py
##--Contains a series of functions used to iterparse and audit the osm xml file
##--and create the value cleaning function for the JSON and Mongo port

import xml.etree.cElementTree as ET
from pprint import pprint
import re , sys

auditSet = set()
auditDict = {}
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

#Returns True if item contains only lowercase alpha characters
def isalphalower(item):
	return item.isalpha() and item.islower()

#Returns True if item contains only lowercase characters,
#no problem characters, and colon characters equal to numCol
def islowercolon(item , numCol=1):
	return item.islower() and item.count(':') == numCol \
	and not bool(problemchars.search(item))


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


#Creates a set of all valid tags
#Ex: auditTags(child)
def auditTags(element):
	keyVal = element.get('k')
	if isalphalower(keyVal) or islowercolon(keyVal):
		if keyVal in auditDict: auditDict[keyVal] += 1
		else: auditDict[keyVal] = 1

#Creates a count of addr subkeys
#Ex: auditAddr(element)
def auditAddr(element):
	keyVal = element.get('k')
	if keyVal.startswith('addr:'):
		if keyVal in auditDict: auditDict[keyVal] += 1
		else: auditDict[keyVal] = 1

#Creates a set of unexpected street end elements
#Ex: auditStreetTypes(element)
expectedStreetEnds = ['Street','Road','Lane','Drive','Plaza','Way','Avenue', \
				      'Boulevard','Trail','Circle','Court','Parkway','Place']
def auditStreetTypes(element):
	if element.get('k') == 'addr:street':
		itemVal = element.get('v')
		lastItem = itemVal.split(' ')[-1]
		if lastItem in streetReplacements: lastItem = streetReplacements[lastItem]
		if lastItem not in expectedStreetEnds:
			if lastItem in auditDict: auditDict[lastItem].add(itemVal)
			else: auditDict[lastItem] = set([itemVal])

#Creates a dict of the various capitalizations for a given name key
#Ex: auditName(child)
def auditName(element):
	if element.get('k') == 'name':
		itemVal = element.get('v')
		if itemVal.lower() in auditDict: auditDict[itemVal.lower()].add(itemVal)
		else: auditDict[itemVal.lower()] = set([itemVal])

#Creates a set of keyvals for a target key
#Ex: auditKeyValSet(element , 'religion')
def auditKeyValSet(element , target):
	keyVal = element.get('k')
	if keyVal == target:
		auditSet.add(cleanVal(keyVal , element.get('v')))

#Creates a count of itemvals for a target key
#Ex: auditKeyVal(child , 'addr:state')
def auditKeyVal(element , target):
	keyVal = element.get('k')
	if keyVal == target:
		itemVal = str(cleanVal(keyVal , element.get('v')))
		if itemVal in auditDict: auditDict[itemVal] += 1
		else: auditDict[itemVal] = 1

#Creates a count of keys whose itemval is in targets
#Ex: auditValues(child , ['null','none','true','false'])
def auditValues(element , targets):
	val = element.get('v').lower()
	if val in targets:
		if val in auditDict: auditDict[val] += 1
		else: auditDict[val] = 1

#Create a set of keys that match a target value
#Ex: auditValuesSet(child , 'none')
def auditValuesSet(element , targetVal):
	val = element.get('v').lower()
	if val == targetVal:
		auditSet.add(element.get('k'))

def main(filename):
	for _, element in ET.iterparse(filename):
		if element.tag in ['node','way']:
			#for item in element.attrib:
				#auditSet.add(item)
			for child in element.iter('tag'):
				auditTags(child)
				#auditAddr(child)
				#auditStreetTypes(child)
				#auditKeyValSet(child , 'addr:state')
				#auditKeyVal(child , 'operator')
				#auditValues(child , ['null','none','true','false'])
				#auditValuesSet(child , 'none')
				#auditName(child)
	print('Audit Results')
	if auditSet: pprint(auditSet)
	elif auditDict: pprint(auditDict)
	#These two lines are only for auditName
	#Only print out sets where there are different name capitalizations
	#for item in auditDict:
	#	if len(auditDict[item]) > 1: print(auditDict[item])

if __name__ == "__main__":
	main('orlandomap.osm')