from util import unixparser

class Bar():
    def __init__(self,ticker:"ticker",opentime:"opentime",closetime:"closetime",open:"open",close:"close",interval:"interval",volume:"volume"):
        self.ticker = ticker
        self.opentime = unixparser(opentime)
        self.closetime = unixparser(closetime)
        self.open = open
        self.close = close
        self.volume = volume
        self.interval = interval

    def __str__(self):
        return "Ticker:          {}\nOpen:            {}\nClose:           {}\nOpentime:        {}\nClosetime:       {}\nVolume:          {}\nInterval:        {}\n".format(self.ticker,self.open,self.close,self.opentime,self.closetime,self.volume,self.interval)
