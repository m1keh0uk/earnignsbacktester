import requests
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os

load_dotenv()

def get_input_period():
    print("Select the holding period for the strategy:")
    print("1: Minutes")
    print("2: Days")
    choice = input("Enter your choice (1-4): ")
    periods = {
        '1': 'm',
        '2': 'd',
    }
    return periods.get(choice, 'd')

def get_next_trading_day(prices_df, reported_date):
    max_date = prices_df.index.max()  # Get the maximum date in the prices DataFrame
    while reported_date not in prices_df.index or reported_date.weekday() > 4:  # Skip weekends (Monday=0, Sunday=6)
        reported_date += pd.Timedelta(days=1)
        if reported_date > max_date:  # Stop if reported_date exceeds the available data range
            raise ValueError(f"Exceeded available dates in prices data. Last date in data: {max_date}")
            return "break"
    return reported_date

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

def fetch_spot_from_h5(symbol, period):
    #Fetch stock data from the .h5 file
    if period == "m":
        data_frequency = "minute"
    else:
        data_frequency = "daily"
    df = pd.read_hdf(f"data/{data_frequency}/{symbol}.h5")
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
   
def return_on_earning(symbol, API_KEY, prices_df, frequency, holding_period):
    earnings_df = fetch_earningcalls(symbol, API_KEY)
    earnings_df["reportedDate"] = pd.to_datetime(earnings_df["reportedDate"], errors="coerce")
    earnings_df.dropna(subset=["reportedDate"], inplace=True)

    # Adjust this line to account for minute-level data
    if frequency == 'm':
        # Normalize the price data index to just dates for comparison
        normalized_dates = prices_df.index.normalize()
        # Check if the normalized date is in the normalized index
        earnings_df = earnings_df[earnings_df["reportedDate"].dt.normalize().isin(normalized_dates)]
    else:
        earnings_df = earnings_df[earnings_df["reportedDate"].isin(prices_df.index)]

    earnings_df["fiscalDateEnding"] = pd.to_datetime(earnings_df["fiscalDateEnding"], errors="coerce")
    earnings_df["reportedEPS"] = pd.to_numeric(earnings_df["reportedEPS"].replace("None", pd.NA), errors='coerce')
    earnings_df["estimatedEPS"] = pd.to_numeric(earnings_df["estimatedEPS"].replace("None", pd.NA), errors='coerce')
    earnings_df["beat"] = earnings_df["reportedEPS"] > earnings_df["estimatedEPS"]
    
    if frequency =='d':
        return process_earnings_d(earnings_df, prices_df, symbol, holding_period)
    elif frequency == 'm':
        return process_earnings_m(earnings_df, prices_df, symbol, holding_period)
    
def process_earnings_d(earnings_df, prices_df, symbol, holding_period):
    number_of_shares = 100 #random number
    trading_log = []
    for index, row in earnings_df.iterrows():
        prices_df.index = prices_df.index.normalize()
        reported_date = row["reportedDate"].normalize()

        trading_dates = []

        if reported_date not in prices_df.index:
            print(f"Warning: Reported date {reported_date} not found in price data. Skipping.")
            continue
        report_time = row["reportTime"]

        if report_time == "post-market":
            reported_date = reported_date + pd.Timedelta(days=1)

        i = 0
        while len(trading_dates) < holding_period:
            next_date = get_next_trading_day(prices_df, reported_date + pd.Timedelta(days=i))
            if next_date not in trading_dates:
                trading_dates.append(next_date)
            i += 1
  
        for date in trading_dates:
            if date not in prices_df.index:
                continue
            open_price = prices_df.loc[date, "1. open"]
            close_price = prices_df.loc[date, "4. close"]

            if row["beat"]:
                pnl = number_of_shares * (close_price - open_price)
                position = "long"
            else:
                pnl = number_of_shares * (open_price - close_price)
                position = "short"
            
            trading_dict = {
                "dateExecuted": date,
                "Position": position,
                "Stock": symbol,
                "Open": f"${open_price:.2f}",
                "Close": f"${close_price:.2f}",
                "Amount Invested": open_price * 100,
                "Change (%)": ((close_price - open_price) / open_price) * 100,
                "PnL": pnl
            }
            trading_log.append(trading_dict)

    return pd.DataFrame(trading_log)

def process_earnings_m(earnings_df, prices_df, symbol, holding_period):
   
    trading_log = []
    for index, row in earnings_df.iterrows():
        prices_df.index = prices_df.index.normalize()
        reported_date = row["reportedDate"].normalize()
        if reported_date not in prices_df.index:
            print(f"Warning: Reported date {reported_date} not found in price data. Skipping.")
            continue
        report_time = row["reportTime"]

        if report_time == "post-market":
            reported_date = reported_date + pd.Timedelta(days=1)
  
        trade_date = get_next_trading_day(prices_df, reported_date)

        daily_rows = prices_df.loc[trade_date]
        open_price = daily_rows.iloc[0]['1. open']
        close_price = daily_rows.iloc[holding_period]['4. close'] #each row is a minute, take the first row, then count out the minutes
        number_of_shares = 100 #random number

        if row["beat"]:
            pnl = number_of_shares * (close_price - open_price)
            position = "long"
        else:
            pnl = number_of_shares * (open_price - close_price)
            position = "short"
        
        trading_dict = {
            "dateExecuted": trade_date,
            "Position": position,
            "Stock": symbol,
            "Open": f"${open_price:.2f}",
            "Close": f"${close_price:.2f}",
            "Amount Invested": open_price * 100,
            "Change (%)": ((close_price - open_price) / open_price) * 100,
            "PnL": pnl
        }
        trading_log.append(trading_dict)
    
    return pd.DataFrame(trading_log)

def calculate_cumulative_pnl(df):
    df = pd.DataFrame(df)
    df = df.sort_values(by='dateExecuted', ascending=True)
    df['Cumulative PnL'] = df['PnL'].cumsum()
    return df

def calculate_return(df):
    df['Amount Invested'] = pd.to_numeric(df['Amount Invested'], errors='coerce')
    return df['Cumulative Pnl'].iloc[-1]/df['Amount Invested'].sum

def calculate_sharpe_ratio(df, risk_free_rate=0.01):
    df['Daily Return'] = df['PnL'] / df['Amount Invested'].replace(0, 1)
    
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
    '''
    Adjust portfolio below by manually entering ticker. For minute strategy, only avaible 
    tickers are WMT and AAPL (size constraint). See data folder for avaible tickers.
    '''
    
    symbols = ["WMT", "AAPL"] 
                    
    holding_period_type = get_input_period()
    if holding_period_type == "d":
        holding_period = int(input("Enter integer number of days:"))
    if holding_period_type == "m":
        holding_period = int(input("Enter integer number of minutes:"))

    all_pnl = []
    

    for symbol in symbols:
        prices_df = fetch_spot_from_h5(symbol, holding_period_type)
        trading_log = return_on_earning(symbol, API_KEY, prices_df, holding_period_type, holding_period)
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
    


   
