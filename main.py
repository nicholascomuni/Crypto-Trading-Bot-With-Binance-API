import asyncio
import datetime
import websockets
import json
from cryptotrading import Crypto_bot

class Bot(Crypto_bot):
    def run(self):
        self.on_init()

    def on_init(self):
        tickers = ["BNBBTC,1m",
                   "BTCUSDT,1m",
                   "ETHBTC,1m"]

        self.subscribe_tickers(tickers)

        self.main_loop()

    def on_bar_close(self,bar):
        print("Ticker: {}\n
              Datetime: {}\n
              Opentime: {}\n
              Closetime: {}\n
              Interval: {}\n
              Open: {}\n
              Close: {}\n
              Closed: {}\n
              \n".format(bar['ticker'],
              bar["datetime"],
              bar['open_time'],
              bar['close_time'],
              bar['interval'],
              bar['open'],
              bar['close'],
              bar['closed']))


if __name__ == "__main__":
    bot = Bot()
    bot.run()
