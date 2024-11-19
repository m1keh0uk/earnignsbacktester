import requests
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from dotenv import load_dotenv
import os


load_dotenv()


API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

def fetch_earningcalls(symbol):
    params = {
        "function": "EARNINGS",
        "symbol": symbol,
        "apikey": API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    return pd.DataFrame(data["quarterlyEarnings"])

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

def return_on_earning(symbol):
    earnings_df = fetch_earningcalls(symbol)
    prices_df = fetch_spot(symbol)

    earnings_df["fiscalDateEnding"] = pd.to_datetime(earnings_df["fiscalDateEnding"])
    earnings_df["reportedDate"] = pd.to_datetime(earnings_df["reportedDate"])
    earnings_df["beat"] = earnings_df["reportedEPS"].astype(float) > earnings_df["estimatedEPS"].astype(float)

    earnings_df["Open"] = None
    earnings_df["Close"] = None
    earnings_df["Change (%)"] = None
  
    for index, row in earnings_df.iterrows():
        reported_date = row["reportedDate"]
        if row["reportTime"] != "pre-market":
            reported_date += pd.Timedelta(days=1)
        
        open_price = prices_df.loc[reported_date, "1. open"]
        close_price = prices_df.loc[reported_date, "4. close"]
        change = ((close_price - open_price) / open_price) * 100
        
        earnings_df.at[index, "Open"] = open_price
        earnings_df.at[index, "Close"] = close_price
        earnings_df.at[index, "Change (%)"] = change
    
    return earnings_df

        
            