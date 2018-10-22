#! /usr/bin/env python3
# 
# **** bmwcdapi.py ****
# https://github.com/jupe76/bmwcdapi
#
# Query vehicle data from the BMW ConnectedDrive Website, i.e. for BMW i3
# Based on the excellent work by Sergej Mueller
# https://github.com/sergejmueller/battery.ebiene.de
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import json
import requests
import time
import urllib.parse
import re
import argparse
import xml.etree.ElementTree as etree  

# ADJUST HERE if OH is not running on "localhost:8080"
OPENHABIP = "localhost:8080"

# API Gateway
AUTH_API = 'https://customer.bmwgroup.com/gcdm/oauth/authenticate'
VEHICLE_API = 'https://www.bmw-connecteddrive.de/api/vehicle'

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:57.0) Gecko/20100101 Firefox/57.0"

class ConnectedDrive(object):

    def __init__(self):
        self.printall = False
        self.bmwUsername = self.ohGetValue("Bmw_Username").json()["label"]
        self.bmwPassword = self.ohGetValue("Bmw_Password").json()["label"]
        self.bmwVin = self.ohGetValue('Bmw_Vin').json()["label"].upper()
        self.accessToken = self.ohGetValue('Bmw_accessToken').json()["state"]
        self.tokenExpires = self.ohGetValue('Bmw_tokenExpires').json()["state"]

        if((self.tokenExpires == 'NULL') or (int(time.time()) >= int(self.tokenExpires))):
            self.generateCredentials()
        else:
            self.authenticated = True

    def generateCredentials(self):
        """
        If previous token has expired, create a new one.
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-agent": USER_AGENT
        }

        values = {'username' : self.bmwUsername,
            'password' : self.bmwPassword,
            'client_id' : 'dbf0a542-ebd1-4ff0-a9a7-55172fbfce35',
            'redirect_uri' : 'https://www.bmw-connecteddrive.com/app/default/static/external-dispatch.html',
            'response_type' : 'token',
            'scope' : 'authenticate_user fupo',
            'state' : 'eyJtYXJrZXQiOiJkZSIsImxhbmd1YWdlIjoiZGUiLCJkZXN0aW5hdGlvbiI6ImxhbmRpbmdQYWdlIn0',
            'locale' : 'DE-de'
        }

        data = urllib.parse.urlencode(values)
        r = requests.post(AUTH_API,  data=data, headers=headers,allow_redirects=False)
        #r.status_code will be 302

        # https://www.bmw-connecteddrive.com/app/default/static/external-dispatch.html?error=access_denied
        myPayLoad=r.headers['Location']
        if("error=access_denied" in myPayLoad):
            self.authenticated = False
        else:
            m = re.match(".*access_token=([\w\d]+).*token_type=(\w+).*expires_in=(\d+).*", myPayLoad )
            
            tokenType=(m.group(2))

            self.accessToken=(m.group(1))
            self.ohPutValue('Bmw_accessToken',self.accessToken)

            self.tokenExpires=int(time.time()) + int(m.group(3))
            self.ohPutValue('Bmw_tokenExpires',self.tokenExpires)

            self.authenticated = True
        return

    def ohPutValue(self, item, value):
        rc =requests.put('http://' + OPENHABIP + '/rest/items/'+ item +'/state', str(value))
        if(rc.status_code != 202):
            print("Warning: couldn't save item " + item + " to openHAB")

    def ohGetValue(self, item):
        return requests.get('http://' + OPENHABIP + '/rest/items/'+ item)

    def queryData(self):
        headers = {
            "Content-Type": "application/json",
            "User-agent": USER_AGENT,
            "Authorization" : "Bearer "+ self.accessToken
            }

        execStatusCode = 0 #ok
        r = requests.get(VEHICLE_API+'/dynamic/v1/'+self.bmwVin+'?offset=-60', headers=headers,allow_redirects=True)
        if (r.status_code== 200):
            map=r.json() ['attributesMap']
            #optional print all values
            if(self.printall==True):
                for k, v in map.items():
                    print(k, v)
            
            if('door_lock_state' in map):
                self.ohPutValue("Bmw_doorLockState",map['door_lock_state'])
            if('chargingLevelHv' in map):
                self.ohPutValue("Bmw_chargingLevelHv",map['chargingLevelHv'])
            if('beRemainingRangeElectric' in map):
                self.ohPutValue("Bmw_beRemainingRangeElectric",map["beRemainingRangeElectric"])
            if('mileage' in map):
                self.ohPutValue("Bmw_mileage",map["mileage"])
            if('beRemainingRangeFuel' in map):
                self.ohPutValue("Bmw_beRemainingRangeFuel",map["beRemainingRangeFuel"])
            if('updateTime_converted_date' in map):
                self.ohPutValue("Bmw_updateTimeConverted", map['updateTime_converted_date']+ " " + map['updateTime_converted_time'])
            if('chargingSystemStatus' in map):
                self.ohPutValue("Bmw_chargingSystemStatus", map['chargingSystemStatus'])
            if('remaining_fuel' in map):
                self.ohPutValue("Bmw_remainingFuel", map['remaining_fuel'])
            if('gps_lng' in map and 'gps_lat' in map):
                 self.ohPutValue("Bmw_positionLng", map['gps_lng'])
                 self.ohPutValue("Bmw_positionLat", map['gps_lat'])
        else :
            execStatusCode = 70 #errno ECOMM, Communication error on send

        r = requests.get(VEHICLE_API+'/navigation/v1/'+self.bmwVin, headers=headers,allow_redirects=True)
        if (r.status_code== 200):
            map=r.json()

            #optional print all values
            if(self.printall==True):
                for k, v in map.items():
                    print(k, v)

            if('socMax' in map):
                self.ohPutValue("Bmw_socMax",map['socMax'])
        else:
            execStatusCode = 70 #errno ECOMM, Communication error on send

        r = requests.get(VEHICLE_API+'/efficiency/v1/'+self.bmwVin, headers=headers,allow_redirects=True)
        if (r.status_code== 200):
            if(self.printall==True):
                for k, v in r.json().items():
                    print(k, v)

            #lastTripList
            myList=r.json() ["lastTripList"]
            for listItem in myList:
                if (listItem["name"] == "LASTTRIP_DELTA_KM"):
                    pass
                elif (listItem["name"] == "ACTUAL_DISTANCE_WITHOUT_CHARGING"):
                    pass
                elif (listItem["name"] == "AVERAGE_ELECTRIC_CONSUMPTION"):
                    self.ohPutValue("Bmw_lastTripAvgConsum", listItem["lastTrip"])
                elif (listItem["name"] == "AVERAGE_RECUPERATED_ENERGY_PER_100_KM"):
                    self.ohPutValue("Bmw_lastTripAvgRecup", listItem["lastTrip"])
                elif (listItem["name"] == "CUMULATED_ELECTRIC_DRIVEN_DISTANCE"):
                    pass
        else: execStatusCode = 70 #errno ECOMM, Communication error on send

        return execStatusCode

    def executeService(self,service):
        # lock doors:     RDL
        # unlock doors:   RDU
        # light signal:   RLF
        # sound horn:     RHB
        # climate:        RCN

        #https://www.bmw-connecteddrive.de/api/vehicle/remoteservices/v1/WBYxxxxxxxx123456/history

        # query execution status retries and interval time
        MAX_RETRIES = 9
        INTERVAL = 10 #secs

        print("executing service " + service)

        serviceCodes ={
            'climate' : 'RCN', 
            'lock': 'RDL', 
            'unlock' : 'RDU',
            'light' : 'RLF',
            'horn': 'RHB'}

        command = serviceCodes[service]
        headers = {
            "Content-Type": "application/json",
            "User-agent": USER_AGENT,
            "Authorization" : "Bearer "+ self.accessToken
            }

        #initalize vars
        execStatusCode=0
        remoteServiceStatus=""

        r = requests.post(VEHICLE_API+'/remoteservices/v1/'+self.bmwVin+'/'+command, headers=headers,allow_redirects=True)
        if (r.status_code!= 200):
            execStatusCode = 70 #errno ECOMM, Communication error on send

        #<remoteServiceStatus>DELIVERED_TO_VEHICLE</remoteServiceStatus>
        #<remoteServiceStatus>EXECUTED</remoteServiceStatus>
        #wait max. ((MAX_RETRIES +1) * INTERVAL) = 90 secs for execution 
        if(execStatusCode==0):
            for i in range(MAX_RETRIES):
                time.sleep(INTERVAL)
                r = requests.get(VEHICLE_API+'/remoteservices/v1/'+self.bmwVin+'/state/execution', headers=headers,allow_redirects=True)
                #print("status execstate " + str(r.status_code) + " " + r.text)
                root = etree.fromstring(r.text)
                remoteServiceStatus = root.find('remoteServiceStatus').text
                #print(remoteServiceStatus)
                if(remoteServiceStatus=='EXECUTED'):
                    execStatusCode= 0 #OK
                    break

        if(remoteServiceStatus!='EXECUTED'):
            execStatusCode = 62 #errno ETIME, Timer expired

        return execStatusCode

    def sendMessage(self,message):
        # Endpoint: https://www.bmw-connecteddrive.de/api/vehicle/myinfo/v1
        # Type: POST
        # Body:
        # {
        #   "vins": ["<VINNUMBER>"],
        #   "message": "CONTENT",
        #   "subject": "SUBJECT"
        # }

        headers = {
            "Content-Type": "application/json",
            "User-agent": USER_AGENT,
            "Authorization" : "Bearer "+ self.accessToken
            }

        #initalize vars
        execStatusCode=0

        values = {'vins' : [self.bmwVin],
                    'message' : message[1],
                    'subject' : message[0]
                    }
        r = requests.post(VEHICLE_API+'/myinfo/v1', data=json.dumps(values), headers=headers,allow_redirects=True)
        if (r.status_code!= 200):
            execStatusCode = 70 #errno ECOMM, Communication error on send

        return execStatusCode

def main():
    print("...running bmwcdapi.py")
    c = ConnectedDrive()

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--printall', action='store_true',
        help='print all values that were received')
    parser.add_argument('-e', '--execservice', dest='service', 
        choices=['climate', 'lock', 'unlock', 'light', 'horn'], 
        action='store', help='execute service like instant climate control')
    parser.add_argument('-s', '--sendmesg', nargs=2, dest='message',
        metavar=('subject','message'),
        action='store', help='send a message to the car')

    args = vars(parser.parse_args())

    if(args["printall"]==True):
        c.printall=True

    # dont query data and execute the service at the same time, takes too long
    if(args["service"] and c.authenticated == True):
        # execute service
        execStatusCode = c.executeService(args["service"])
    elif(args["message"] and c.authenticated == True):
        # snd message
        execStatusCode = c.sendMessage(args["message"])
    elif(c.authenticated == True):
        # else, query data
        execStatusCode = c.queryData()
    elif(c.authenticated == False):
        print("could not authenticate, user or password wrong?")
        #errno EACCES 13 Permission denied
        execStatusCode = 13
        
    #print("execStatusCode="+ str(execStatusCode) )
    return execStatusCode

if __name__ == '__main__':
    main()
