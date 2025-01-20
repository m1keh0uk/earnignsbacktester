import requests
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os

load_dotenv()

def get_next_trading_day(prices_df, reported_date):
    max_date = prices_df.index.max()  # Get the maximum date in the prices DataFrame
    while reported_date not in prices_df.index:
        reported_date += pd.Timedelta(days=1)
        if reported_date > max_date:  # Stop if reported_date exceeds the available data range
            raise ValueError(f"Exceeded available dates in prices data. Last date in data: {max_date}")
    return reported_date

def calculate_cumulative_pnl(df):
    df = pd.DataFrame(df)
    df = df.sort_values(by='dateExecuted', ascending=True)
    df['Cumulative PnL'] = df['PnL'].cumsum()
    return df

def calculate_sharpe(df):
    std = df["change (%)"].std()
    mean = df["Change (%)"].std()
    return

def fetch_earningcalls(symbol, API_KEY):
    BASE_URL = "https://www.alphavantage.co/query"

    params = {
        "function": "EARNINGS",
        "symbol": symbol,
        "apikey": API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    return pd.DataFrame(data["quarterlyEarnings"])

def fetch_spot_from_h5(symbol):
    #Fetch stock data from the .h5 file
    df = pd.read_hdf(f"data/{symbol}.h5")
    # Rename columns to match with API
    df.rename(columns={
        "open": "1. open",
        "close": "4. close",
        "high": "2. high",
        "low": "3. low"
    }, inplace=True)

    df.index = pd.to_datetime(df.index)
    df = df[df.index >= '2018-01-01']

    return df
   
def return_on_earning(symbol, API_KEY, prices_df):
    earnings_df = fetch_earningcalls(symbol, API_KEY)
    earnings_df["reportedDate"] = pd.to_datetime(earnings_df["reportedDate"], errors="coerce")
    earnings_df = earnings_df.dropna(subset=["reportedDate"])
    earnings_df = earnings_df[earnings_df["reportedDate"].isin(prices_df.index)]
    earnings_df["fiscalDateEnding"] = pd.to_datetime(earnings_df["fiscalDateEnding"], errors="coerce")
    earnings_df["reportedEPS"] = pd.to_numeric(earnings_df["reportedEPS"].replace("None", pd.NA), errors='coerce')
    earnings_df["estimatedEPS"] = pd.to_numeric(earnings_df["estimatedEPS"].replace("None", pd.NA), errors='coerce')
    earnings_df["beat"] = earnings_df["reportedEPS"] > earnings_df["estimatedEPS"]
    
    return process_earnings(earnings_df, prices_df, symbol)
   
def process_earnings(earnings_df, prices_df, symbol):
    number_of_shares = 100

    trading_log = []

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
            date_executed = current_close_date
        else:  # For post-market
            current_close_date = get_next_trading_day(prices_df, reported_date)
            next_close_date = get_next_trading_day(prices_df, reported_date + pd.Timedelta(days=1))
            open = prices_df.loc[next_close_date, "1. open"]
            close = prices_df.loc[next_close_date, "4. close"]
            date_executed = next_close_date

        # Calculate PnL based on s/l after earnings
        if row["beat"]: # long
            pnl = number_of_shares * (close - open) 
            position = "long"
        else:  # short
            pnl = number_of_shares * (open - close)
            position = "short"

        trading_dict = {
        "dateExecuted": date_executed,
        "Position": position,
        "Stock": symbol,
        "Open": open,
        "Close": close,
        "Change (%)": ((close - open) / open) * 100,
        "PnL": pnl
        }
        trading_log.append(trading_dict)
    
    return pd.DataFrame(trading_log)

import pandas as pd

def calculate_sharpe_ratio(df, risk_free_rate=0.01):

    df['Previous Cumulative PnL'] = df['Cumulative PnL'].shift(1)
    df['Daily Return'] = df['PnL'] / df['Previous Cumulative PnL'].replace(0, 1)  # avoid division by zero

    if df.iloc[0]['Previous Cumulative PnL'] == 0:
        df.at[0, 'Daily Return'] = df.iloc[0]['PnL'] / df.iloc[0]['Cumulative PnL'] if df.iloc[0]['Cumulative PnL'] != 0 else 0
    
    average_daily_return = df['Daily Return'].mean()
    daily_return_std_dev = df['Daily Return'].std()
    annualized_return = average_daily_return * 252  # Assuming 252 trading days in a year
    annualized_std_dev = daily_return_std_dev * (252**0.5)
    sharpe_ratio = (annualized_return - risk_free_rate) / annualized_std_dev

    return sharpe_ratio

def calculate_max_drawdown(df):
    cumulative_max = df['Cumulative PnL'].cummax()
    drawdowns = (df['Cumulative PnL'] - cumulative_max) / cumulative_max
    max_drawdown = drawdowns.min()
    return max_drawdown

def calculate_profit_per_contract(df):
    total_pnl = df['PnL'].sum()
    number_of_contracts = len(df)
    profit_per_contract = total_pnl / number_of_contracts if number_of_contracts else 0
    return profit_per_contract

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
    plt.plot(df['dateExecuted'], df['Cumulative PnL'], marker='o', linestyle='-', color='blue')
    plt.title("Cumulative P&L Over Time")
    plt.xlabel("Date")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
    symbols = ["AAPL","BLK", "NFLX", "NKE", "WMT"] #adjust portfolio here. Manually change stocks
    
    all_pnl = []
    for symbol in symbols:
        prices_df = fetch_spot_from_h5(symbol)
        trading_log = return_on_earning(symbol, API_KEY, prices_df)
        all_pnl.append(trading_log)

    combined_pnl = pd.concat(all_pnl)
    combined_pnl = calculate_cumulative_pnl(combined_pnl)

    max_drawdown = calculate_max_drawdown(combined_pnl)
    profit_per_contract = calculate_profit_per_contract(combined_pnl)
    sharpe_ratio = calculate_sharpe_ratio(combined_pnl)
    
    print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")
    print(f"Profit Per Contract is: ${profit_per_contract:.2f}")
    print(f"Sharpe Ratio: ${sharpe_ratio:.2f}")
    
    plot_pnl(combined_pnl)
    combined_pnl.to_csv("Combined_Portfolio_PnL.csv", index=False)
    


   
