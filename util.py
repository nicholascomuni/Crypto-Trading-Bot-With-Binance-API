import datetime
import json

def unixparser(unix):
    return datetime.datetime.utcfromtimestamp(int(str(unix)[:10])).strftime('%Y-%m-%d %H:%M:%S')

def load_keys():
    with open("keys.json",'rb') as file:
        return json.load(file)
