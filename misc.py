import asyncio
import datetime
import websockets
import json

now = datetime.datetime.now

async def hello(address,port):
    async with websockets.connect(f"ws://{address}:{port}") as websocket:
        greeting = await websocket.recv()
        print("< {}".format(greeting))


async def connect_websocket(stream_name):
    bitonic_address = f"wss://stream.binance.com:9443/ws/{stream_name}"
    async with websockets.connect(bitonic_address) as websocket:
        counter = 0
        while True:
            counter += 1
            message_str = await websocket.recv()
            message = json.loads(message_str)
            #date_time = int(str(message['E'])[:10])
            #print(datetime.datetime.utcfromtimestamp(date_time).strftime('%Y-%m-%d %H:%M:%S'))
            if counter > 10:
                websocket.close()
                break

async def get_candles(stream_name):
    bitonic_address = f"wss://stream.binance.com:9443/ws/{stream_name}"
    async with websockets.connect(bitonic_address) as websocket:
        counter = 0
        while True:
            counter += 1
            message_str = await websocket.recv()
            message = json.loads(message_str)
            print(message)
            #date_time = int(str(message['E'])[:10])
            #print(datetime.datetime.utcfromtimestamp(date_time).strftime('%Y-%m-%d %H:%M:%S'))


            if counter > 5:
                websocket.close()
                break
