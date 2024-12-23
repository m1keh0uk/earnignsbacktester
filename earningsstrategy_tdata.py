import requests
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os

load_dotenv()

H5_FILE_PATH = "data/AAPL.h5"  # Path to the .h5 file, hardcodded for Apple

def get_next_trading_day(prices_df, reported_date):
    max_date = prices_df.index.max()  # Get the maximum date in the prices DataFrame
    while reported_date not in prices_df.index:
        reported_date += pd.Timedelta(days=1)
        if reported_date > max_date:  # Stop if reported_date exceeds the available data range
            raise ValueError(f"Exceeded available dates in prices data. Last date in data: {max_date}")
    return reported_date

def calculate_cumulative_pnl(df):
    df = df.sort_values(by='reportedDate', ascending=True)
    df['Cumulative PnL'] = df['PnL'].cumsum()
    return df

def calculate_sharpe(df):
    std = df["change (%)"].std()
    mean = df["Change (%)"].std()
    return

def fetch_earningcalls():
    API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
    BASE_URL = "https://www.alphavantage.co/query"

    params = {
        "function": "EARNINGS",
        "symbol": "AAPL",
        "apikey": API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    return pd.DataFrame(data["quarterlyEarnings"])

def fetch_spot_from_h5():
    """Fetch stock data from the .h5 file."""
    df = pd.read_hdf("data/AAPL.h5")
    # Rename columns to match with API
    df.rename(columns={
        "open": "1. open",
        "close": "4. close",
        "high": "2. high",
        "low": "3. low"
    }, inplace=True)

    return df
   
def return_on_earning():
    earnings_df = fetch_earningcalls()
    prices_df = fetch_spot_from_h5()

    # Convert reportedDate to datetime and filter data
    earnings_df["reportedDate"] = pd.to_datetime(earnings_df["reportedDate"], errors="coerce")
    earnings_df = earnings_df[earnings_df["reportedDate"] >= pd.Timestamp('2018-01-01')]
    earnings_df = earnings_df.dropna(subset=["reportedDate"])

    # check reportedDate is within the range of prices data
    max_price_date = prices_df.index.max()
    earnings_df = earnings_df[earnings_df["reportedDate"] <= max_price_date]
    if earnings_df.empty:
        raise ValueError("No valid earnings data within the range of available price data.")

    # Additional processing
    earnings_df["fiscalDateEnding"] = pd.to_datetime(earnings_df["fiscalDateEnding"], errors="coerce")
    earnings_df["reportedEPS"] = pd.to_numeric(earnings_df["reportedEPS"].replace("None", pd.NA), errors='coerce')
    earnings_df["estimatedEPS"] = pd.to_numeric(earnings_df["estimatedEPS"].replace("None", pd.NA), errors='coerce')
    earnings_df["beat"] = earnings_df["reportedEPS"] > earnings_df["estimatedEPS"]
    earnings_df["Open"] = None
    earnings_df["Close"] = None
    earnings_df["Change (%)"] = None
    earnings_df["PnL"] = None

    number_of_shares = 100

    for index, row in earnings_df.iterrows():
        prices_df.index = prices_df.index.normalize()
        reported_date = row["reportedDate"].normalize()
        if reported_date not in prices_df.index:
            print(f"Warning: Reported date {reported_date} not found in price data. Skipping.")
            continue
        report_time = row["reportTime"]

        if report_time == "pre-market":
            current_close_date = get_next_trading_day(prices_df, reported_date)
            open = prices_df.loc[current_close_date, "1. open"]
            close = prices_df.loc[current_close_date, "4. close"]
        else:  # For post-market
            current_close_date = get_next_trading_day(prices_df, reported_date)
            next_close_date = get_next_trading_day(prices_df, reported_date + pd.Timedelta(days=1))
            open = prices_df.loc[next_close_date, "1. open"]
            close = prices_df.loc[next_close_date, "4. close"]

        # Calculate PnL based on s/l after earnings
        if row["beat"]: # short
            pnl = number_of_shares * (close - open) 
        else:  # long
            pnl = number_of_shares * (open - close)

        earnings_df.at[index, "Open"] = open
        earnings_df.at[index, "Close"] = close
        earnings_df.at[index, "Change (%)"] = ((close - open) / open) * 100
        earnings_df.at[index, "PnL"] = pnl

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

def plot_pnl(df):
    plt.figure(figsize=(12, 6))
    plt.plot(df['reportedDate'], df['Cumulative PnL'], marker='o', linestyle='-', color='blue')
    plt.title("Cumulative P&L Over Time")
    plt.xlabel("Date")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    symbol = "AAPL"  # Hardcoded symbol

    results = return_on_earning()
    results_with_cumulative_pnl = calculate_cumulative_pnl(results)
    sharp = calculate_sharpe(results_with_cumulative_pnl)
    plot_pnl(results_with_cumulative_pnl)

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    print(results_with_cumulative_pnl)
    results_with_cumulative_pnl.to_csv("Cumulative_PnL_Output.csv", index=False)



   
