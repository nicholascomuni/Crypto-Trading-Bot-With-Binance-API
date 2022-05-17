from util import *
import asyncio
import datetime
import websockets
import json


class Crypto_bot:
    def __init__(self):
        self.subscribed_tickers_streams = []
        self.functions = []
        self.loop = asyncio.get_event_loop()

    def subscribe_tickers(self,tickers_timeframes):
        streams = []
        for raw in tickers_timeframes:
            ticker,tf = raw.lower().split(",")
            streams.append(f"{ticker}@kline_{tf}")
        self.subscribed_tickers_streams = streams
        print(streams)
        self.loop.run_until_complete(self.multiple_bar_close_event(self.subscribed_tickers_streams))


    async def bar_signal_event(self,stream_name):
        bitonic_address = f"wss://stream.binance.com:9443/{stream_name}" # /ws
        #print(f"connecting to {bitonic_address}")
        print(bitonic_address)
        async with websockets.connect(bitonic_address) as websocket:
            print("DPS")
            #print(f"{bitonic_address} connected")
            counter = 0
            while True:
                counter += 1
                message_str = await websocket.recv()
                raw_bar = json.loads(message_str)
                if raw_bar['k']['x']:
                    bar = {"ticker":raw_bar['s'],
                           "interval":raw_bar['k']['i'],
                           "datetime": unixparser(raw_bar['E']),
                           "open": raw_bar['k']['o'],
                           "close": raw_bar['k']['c'],
                           "high": raw_bar['k']['h'],
                           "low": raw_bar['k']['l'],
                           "open_time": unixparser(raw_bar['k']['t']),
                           "close_time": unixparser(raw_bar['k']['T']),
                           "closed": raw_bar['k']["x"]
                           }
                    self.on_bar_close(bar)

    async def bar_close_event(self,stream_name):
        bitonic_address = f"wss://stream.binance.com:9443/ws/{stream_name}" # /ws
        #print(f"connecting to {bitonic_address}")
        async with websockets.connect(bitonic_address) as websocket:
            #print(f"{bitonic_address} connected")
            counter = 0
            while True:
                counter += 1
                message_str = await websocket.recv()
                raw_bar = json.loads(message_str)
                print(raw_bar)
                if raw_bar['k']['x']:
                    bar = {"ticker":raw_bar['s'],
                           "interval":raw_bar['k']['i'],
                           "datetime": unixparser(raw_bar['E']),
                           "open": raw_bar['k']['o'],
                           "close": raw_bar['k']['c'],
                           "high": raw_bar['k']['h'],
                           "low": raw_bar['k']['l'],
                           "open_time": unixparser(raw_bar['k']['t']),
                           "close_time": unixparser(raw_bar['k']['T']),
                           "closed": raw_bar['k']["x"]
                           }
                    self.on_bar_close(bar)

    async def multiple_bar_close_event(self,streams_name):
        streams = ""
        for stream in streams_name:
            streams = streams + stream + "/"

        bitonic_address = f"wss://stream.binance.com:9443/stream?streams={streams}" # /ws
        print(bitonic_address)
        bitonic_address = bitonic_address[:-1]
        print(bitonic_address)
        async with websockets.connect(bitonic_address) as websocket:
            counter = 0
            while True:
                counter += 1
                message_str = await websocket.recv()
                raw = json.loads(message_str)

                data = raw['data']


                if data['k']['x']:
                    bar = {"ticker":data['s'],
                           "interval":data['k']['i'],
                           "datetime": unixparser(data['E']),
                           "open": data['k']['o'],
                           "close": data['k']['c'],
                           "high": data['k']['h'],
                           "low": data['k']['l'],
                           "open_time": unixparser(data['k']['t']),
                           "close_time": unixparser(data['k']['T']),
                           "closed": data['k']["x"]
                           }
                    self.on_bar_close(bar)

    def main_loop(self):
        pass
