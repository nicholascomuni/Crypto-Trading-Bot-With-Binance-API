import hmac
import hashlib
import binascii
import requests
import datetime
import time
import json
from util import *
from classes import *
from dateutil.parser import parse

rest_endpoint = "https://api.binance.com"

def create_sha256_signature(key, message):
    message = message.encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest().upper()


def signed_request(endpoint,query,keys):

    url = rest_endpoint + endpoint
    timestamp = int(time.time())*1000
    query = query + f"&recvWindow=3000&timestamp={timestamp}"
    signature = create_sha256_signature(keys['skey'], query)
    url = url + "?" + query + "&signature=" + signature

    response = requests.get(url,headers={"X-MBX-APIKEY":keys['key']}).json()
    return response

def public_request(endpoint,query):
    url = rest_endpoint + endpoint + "?" + query
    response = requests.get(url)
    return response

def get_historical_data(ticker,interval,start=False,end=False):


    endpoint = "/api/v1/klines"
    if start and end:
        startTime = int(time.mktime(parse(start).timetuple())*1000)
        endTime = int(time.mktime(parse(end).timetuple())*1000)

        query = f"symbol={ticker}&interval={interval}&startTime={startTime}&endTime={endTime}"
    else:
        query = f"symbol={ticker}&interval={interval}"

    response = public_request(endpoint,query).json()
    return [{"ticker":ticker,"open":i[1],"close":i[4],"opentime":i[0],"closetime":i[6],"interval":interval,"volume":i[5]} for i in response]

#keys = load_keys()
#response = signed_request("/api/v3/account",f"",keys)

data = get_historical_data("BTCUSDT","1m","01-02-2018","01-28-2018")


for i in data:
    print(i)
