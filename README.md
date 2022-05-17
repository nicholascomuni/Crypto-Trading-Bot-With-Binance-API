<br/>
<div align="center">
  <h1 align="center">Crypto Trading Bot Using Binance APIs</h1>
</div>


<!-- ABOUT THE PROJECT -->
## About The Project

The main goal of this project is to build a complete algotrading module on top of Binance API. Binance provides us a very robust api, with REST and WebSocket streams. We are gonna use both, WebSocket streams to get real-time data, and REST specially historical data.

You can check the complete Binance API docs <a href="https://binance-docs.github.io/apidocs">HERE</a>.

This project is still under development. 

### Built With

* [Python](https://www.python.org/)
* [Websockets](https://websockets.readthedocs.io/en/stable/)
* [Asyncio](https://docs.python.org/3/library/asyncio.html)
* [Binance API](https://binance-docs.github.io/apidocs)

## Usage
First you will need to install the dependencies:

```pip install -r requirements.txt```

### Web Socket Hello World
Run:

```python main.py```

You will get:

```
Ticker: BNBBTC
Datetime: 2022-05-17 13:42:06
Opentime: 2022-05-17 13:41:00
Closetime: 2022-05-17 13:41:59
Interval: 1m
Open: 0.01011800
Close: 0.01011400
Closed: True
...
```

Check the main.py file to understand what is going on. Its very simple, you will find some useful methods:


<b>on_init</b>

On_init is a method which will run right after you instanciate your Crypto_bot class. Its usefull to subscribe tickers, load historical data and other things that you need to do once and before you run the bot.

```
def on_init(self):
        tickers = ["BNBBTC,1m",
                   "BTCUSDT,1m",
                   "ETHBTC,1m"]

        self.subscribe_tickers(tickers)

        self.main_loop()
```


<b>on_bar_close</b>

This event is called whenever a a bar of a ticker you subscribed is closed. You can use it to update your indicators, make orders and apply your trading strategies. 
```
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
```


### Rest Hello World
Run:

```python rest.py```

You will get:

```
{'ticker': 'BTCUSDT', 'open': '13520.32000000', 'close': '13491.76000000', 'opentime': 1514862000000, 'closetime': 1514862059999, 'interval': '1m', 'volume': '10.60982400'}
```

Hello World function inside rest.py:

```
def Hello_World():
    data = get_historical_data("BTCUSDT","1m","01-02-2018","01-28-2018")
```