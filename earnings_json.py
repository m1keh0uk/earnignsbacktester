import pandas as pd
import matplotlib.pyplot as plt
import os
import json

API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

def get_next_trading_day(prices_df, reported_date):
    while reported_date not in prices_df.index:
        reported_date += pd.Timedelta(days=1)
    return reported_date

def fetch_earningcalls(symbol):
    file_path = os.path.join("data/earnings", f"{symbol}_earnings.pkl")
    if os.path.exists(file_path):
        return pd.read_pickle(file_path)
    else:
        raise FileNotFoundError(f"No earnings data file found for {symbol}.")

def fetch_spot(symbol):
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "apikey": API_KEY,
        "outputsize": "full"
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    df = pd.DataFrame.from_dict(data["Time Series (Daily)"], orient="index", dtype="float")
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df

def return_on_earning(symbol):
    earnings_df = fetch_earningcalls(symbol)
    prices_df = fetch_spot(symbol)

    # dates
    earnings_df["fiscalDateEnding"] = pd.to_datetime(earnings_df["fiscalDateEnding"])
    earnings_df["reportedDate"] = pd.to_datetime(earnings_df["reportedDate"])

    # Handle missing EPS values
    earnings_df["reportedEPS"] = earnings_df["reportedEPS"].replace("None", pd.NA)
    earnings_df["estimatedEPS"] = earnings_df["estimatedEPS"].replace("None", pd.NA)
    earnings_df = earnings_df.dropna(subset=["reportedEPS", "estimatedEPS"])

    earnings_df = earnings_df[earnings_df["reportedDate"] >= "2000-01-01"]

    earnings_df["reportedEPS"] = earnings_df["reportedEPS"].astype(float)
    earnings_df["estimatedEPS"] = earnings_df["estimatedEPS"].astype(float)

    # Add a column for beats
    earnings_df["beat"] = earnings_df["reportedEPS"] > earnings_df["estimatedEPS"]

    earnings_df["Open"] = None
    earnings_df["Close"] = None
    earnings_df["Return (%)"] = None

    for index, row in earnings_df.iterrows():
        reported_date = row["reportedDate"]
        report_time = row["reportTime"]

        if report_time == "pre-market":
            # pre-market: Compare previous close to current close
            previous_close_date = reported_date - pd.Timedelta(days=1)
            previous_close_date = get_next_trading_day(prices_df, previous_close_date)
            current_close_date = get_next_trading_day(prices_df, reported_date)

            previous_close = prices_df.loc[previous_close_date, "4. close"]
            current_close = prices_df.loc[current_close_date, "4. close"]

            change = ((current_close - previous_close) / previous_close) * 100

        else:
            # post-market: Compare current close to next day's close
            current_close_date = get_next_trading_day(prices_df, reported_date)
            next_close_date = get_next_trading_day(prices_df, reported_date + pd.Timedelta(days=1))

            current_close = prices_df.loc[current_close_date, "4. close"]
            next_close = prices_df.loc[next_close_date, "4. close"]

            change = ((next_close - current_close) / current_close) * 100

        earnings_df.at[index, "Open"] = prices_df.loc[current_close_date, "1. open"]
        earnings_df.at[index, "Close"] = current_close
        earnings_df.at[index, "Change (%)"] = change

    return earnings_df

        
def visualize_results(earnings_df, symbol):
    plt.close('all')

    beat_true = earnings_df[earnings_df["beat"] == True]["Change (%)"].dropna()
    beat_false = earnings_df[earnings_df["beat"] == False]["Change (%)"].dropna()

    print(f"\nBeats Earnings: \n\tAverage Return = {beat_true.mean():.2f}%\n\tStandard Deviation = {beat_true.std():.2f}%\n")
    print(f"Misses Earnings: \n\tAverage Return = {beat_false.mean():.2f}%\n\tStandard Deviation = {beat_false.std():.2f}%")

    plt.figure(figsize=(12, 6))
    plt.hist(beat_true, bins=20, alpha=0.7, label="Earnings Beat (True)", color="green", edgecolor="black")
    plt.hist(beat_false, bins=20, alpha=0.7, label="Earnings Beat (False)", color="red", edgecolor="black")
    plt.title(f"Distribution of Returns Day After Earnings for {symbol}")
    plt.xlabel("Change (%)")
    plt.ylabel("Frequency")
    plt.legend()
    plt.grid(axis="y", alpha=0.75)
    plt.show()

if __name__ == "__main__":
    symbol = input("Enter ticker: ").strip().upper()

    results = return_on_earning(symbol)
    visualize_results(results, symbol)
