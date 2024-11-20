import requests
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from dotenv import load_dotenv
import os
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"
print(API_KEY)

def get_next_trading_day(prices_df, reported_date):
    while reported_date not in prices_df.index:
        reported_date += pd.Timedelta(days=1)
    return reported_date

def fetch_spot(symbol):
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "apikey": API_KEY,
        "outputsize": "full"
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()["Time Series (Daily)"]
    df = pd.DataFrame.from_dict(data, orient="index", dtype="float")
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df


def fetch_earningcalls(symbol):
    params = {
        "function": "EARNINGS",
        "symbol": symbol,
        "apikey": API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    return pd.DataFrame(data["quarterlyEarnings"])

fetch_earningcalls("AAPL")
fetch_spot("AAPL")
