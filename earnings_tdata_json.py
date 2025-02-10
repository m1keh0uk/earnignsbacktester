import requests
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os
import json

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

def fetch_earningcalls(symbol):
    file_path = os.path.join("data/earnings", f"{symbol}_earnings.json")
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
        return pd.DataFrame(data)
    else:
        raise FileNotFoundError(f"No earnings data file found for {symbol}.")

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
   
def return_on_earning(symbol, prices_df, frequency, holding_period):
    earnings_df = fetch_earningcalls(symbol)
    
    # Check if the DataFrame is empty or if the column does not exist
    if earnings_df.empty:
        raise ValueError(f"No data returned for {symbol}. Please check the data source.")
    if "reportedDate" not in earnings_df.columns:
        raise ValueError(f"'reportedDate' column is missing in the data for {symbol}.")

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
    number_of_shares = 100  # Random number for the sake of example
    trading_log = []

    for index, row in earnings_df.iterrows():
        prices_df.index = prices_df.index.normalize()
        reported_date = row["reportedDate"].normalize()

        if reported_date not in prices_df.index:
            print(f"Warning: Reported date {reported_date} not found in price data. Skipping.")
            continue
        report_time = row["reportTime"]

        # Adjust the starting date based on the report time
        if report_time == "post-market":
            start_date = reported_date + pd.Timedelta(days=1)
        else:
            start_date = reported_date

        trading_dates = []
        i = 0
        while len(trading_dates) < holding_period:
            try:
                next_date = get_next_trading_day(prices_df, start_date + pd.Timedelta(days=i))
                if next_date not in trading_dates:
                    trading_dates.append(next_date)
                i += 1
            except ValueError:
                print(f"Reached the end of the available data for {symbol} when looking for trading days.")
                break

        for trade_date in trading_dates:
            if trade_date not in prices_df.index:
                print(f"Warning: Trade date {trade_date} not found in price data. Skipping.")
                continue
            open_price = prices_df.loc[trade_date, "1. open"]
            close_price = prices_df.loc[trade_date, "4. close"]

            if row["beat"]:
                continue
                # pnl = number_of_shares * (close_price - open_price)
                # position = "long"
            else:
                # continue
                pnl = number_of_shares * (open_price - close_price)
                position = "short"
            # position = "long"
            # pnl = number_of_shares * (close_price - open_price)

            # pnl = number_of_shares * (open_price - close_price)
            # position = "short"
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
        #     pnl = number_of_shares * (close_price - open_price)
        #     position = "long"
            continue
        else:
            # continue
            pnl = number_of_shares * (open_price - close_price)
            position = "short"

        # pnl = number_of_shares * (close_price - open_price)
        # position = "long"

        # pnl = number_of_shares * (open_price - close_price)
        # position = "short"
        
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

def portfolio_return(df):
    grouped_df = df.groupby('dateExecuted').agg({'Amount Invested': 'sum', 'PnL': 'sum'}).reset_index()
    grouped_df['Return'] = grouped_df['PnL'] / grouped_df ['Amount Invested']
    grouped_df['Cumulative PnL'] = grouped_df['PnL'].cumsum()
    return grouped_df

def calculate_return(df):
    df['Amount Invested'] = pd.to_numeric(df['Amount Invested'], errors='coerce')
    total_invested = df['Amount Invested'].sum()
    alpha = df['PnL'].sum()
    returns = alpha / total_invested
    print(total_invested, alpha, returns)
    return returns

def calculate_sharpe_ratio(df, returns):
    risk_free_rate = 0.0
    std_dev = df['Return'].std()
    sharpe_ratio = (returns - risk_free_rate) / std_dev

    return sharpe_ratio

def calculate_max_drawdown(df):
    df['Cumulative Return'] = (df['Cumulative PnL'] / (df['Amount Invested'].cumsum()))
    max_drawdown = (df['Cumulative Return'].min() - df['Cumulative Return'].max()) / df['Cumulative Return'].max()
    return max_drawdown

def calculate_profit_per_contract(df, pnl, type, period):
    total_pnl = pnl['Cumulative PnL'].iloc[-1]
    number_of_contracts = len(df)
    if type == 'd':
        number_of_contracts /= period
    profit_per_contract = total_pnl / number_of_contracts
    return profit_per_contract

def plot_pnl(df):
    # Ensure 'dateExecuted' is a datetime type for proper plotting
    df['dateExecuted'] = pd.to_datetime(df['dateExecuted'])
    # Group by date and sum the 'Cumulative PnL'

    plt.figure(figsize=(12, 6))
    plt.plot(df['dateExecuted'], df['Cumulative PnL'], marker='o', linestyle='-', color='blue')
    plt.title("Cumulative P&L Over Time")
    plt.xlabel("Date")
    plt.ylabel("Cumulative P&L ($)")
    plt.grid(True)
    plt.show()

def append_to_csv(dataframe, filename):
    file_exists = os.path.isfile(filename)
    header = not file_exists or os.stat(filename).st_size == 0
    dataframe.to_csv(filename, mode='a', header=header, index=False)

if __name__ == "__main__":

    '''
    Adjust portfolio below by manually entering ticker. See data folder for avaible tickers.
    '''
    symbols = ["AAPl", "BLK", "CVX", "D", "DE", "LUV", "NFLX", "NKE", "PG", "WMT"]
    #holding_period_type = get_input_period()

    # if holding_period_type == "d":
    #     holding_period = int(input("Enter integer number of days:"))
    # if holding_period_type == "m":
    #     holding_period = int(input("Enter integer number of minutes:"))

    holding_period_type = 'd'
    for i in range(10):
        holding_period = i + 1
        all_pnl = []

        for symbol in symbols:
            prices_df = fetch_spot_from_h5(symbol, holding_period_type)
            trading_log = return_on_earning(symbol, prices_df, holding_period_type, holding_period)
            all_pnl.append(trading_log)

        combined_pnl = pd.concat(all_pnl)
        combined_pnl = calculate_cumulative_pnl(combined_pnl)
        portfolio_pnl = portfolio_return(combined_pnl)
        portfolio_pnl.to_csv("Portfolio_Return.csv", index=False)

        returns = calculate_return(portfolio_pnl)
        max_drawdown = calculate_max_drawdown(portfolio_pnl)
        profit_per_contract = calculate_profit_per_contract(combined_pnl, portfolio_pnl, holding_period_type, holding_period)
        sharpe_ratio = calculate_sharpe_ratio(portfolio_pnl, returns)

        print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")
        print(f"Profit Per Contract is: ${profit_per_contract:.2f}")
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
        print(f"Return: {returns:.5f}")

        #plot_pnl(portfolio_pnl)
        combined_pnl.to_csv("Combined_Portfolio_PnL.csv", index=False)

        analytics_df = pd.DataFrame([{
            "Holding Period": holding_period_type,
            "Period Length": holding_period,
            "Returns": returns,
            "Maximum Drawdown": max_drawdown,
            "Sharpe Ratio": sharpe_ratio,
            "Profit Per Contract": profit_per_contract
        }])

        # Append results to CSV
        append_to_csv(analytics_df, "Performance_Metrics.csv")