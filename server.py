import asyncio
import datetime
import websockets
import json
from cryptotrading import Crypto_bot

class Bot(Crypto_bot):
    def run(self):
        self.on_init()

    def on_init(self):
        tickers = ["BNBBTC,1m","BTCUSDT,1m","ETHBTC,1m"]

        self.subscribe_tickers(tickers)

        self.main_loop()

    def on_bar_close(self,bar):
        print("Ticker: {}\nDatetime: {}\nOpentime: {}\nClosetime: {}\nInterval: {}\nOpen: {}\nClose: {}\nClosed: {}\n\n".format(bar['ticker'],bar["datetime"],bar['open_time'],bar['close_time'],bar['interval'],bar['open'],bar['close'],bar['closed']))




bot = Bot()
bot.run()
rest_endpoint = "https://api.binance.com"
t = "/api/v1/ping"
api_key = ""
secret_key = ""
