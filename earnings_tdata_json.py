import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
import numpy as np
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
    df = df[df.index >= '2019-01-01']

    return df

def L_s_strategy(row, open, close, number_of_shares):
    #long if beat, short if miss
    if row["beat"]:
        pnl = number_of_shares * (close - open)
        position = "long"
    else:
        pnl = number_of_shares * (open - close)
        position = "short"
    return position, pnl

def L_if_strategy(row, open, close, number_of_shares):
    #long if beat, pass if miss
    if row["beat"]:
        pnl = number_of_shares * (close - open)
        position = "long"
    else:
        pnl = 0
        position = "pass"
    return position, pnl

def L_strategy(row, open, close, number_of_shares):
    #Long every announcement
    pnl = number_of_shares * (close - open)
    position = "long"
    return position, pnl

def S_if_strategy(row, open, close, number_of_shares):
    #Short if miss, pass if beat
    if row["beat"]:
        pnl = 0
        position = "pass"
    else:
        pnl = number_of_shares * (open - close)
        position = "short"
    return position, pnl

def S_strategy(row, open, close, number_of_shares): 
    #Short every announcement
    pnl = number_of_shares * (open - close)
    position = "short"
    return position, pnl
   
def return_on_earning(symbol, prices_df, frequency, holding_period, strat):
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
        return process_earnings_d(earnings_df, prices_df, symbol, holding_period, strat)
    elif frequency == 'm':
        return process_earnings_m(earnings_df, prices_df, symbol, holding_period, strat)
    
def process_earnings_d(earnings_df, prices_df, symbol, holding_period, strat):
    portfolio_value = 100000 #intial investment
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
            number_of_shares = calculate_position_size(portfolio_value, open_price, 5)

            #set strategy here
            position, pnl = globals()[strat](row, open_price, close_price, number_of_shares)
            if position == "pass":
                continue
            
            if trade_date == trading_dates[0]:
                amount_invested = open_price * number_of_shares
            else:
                amount_invested = 0
                
            trading_dict = {
                "dateExecuted": trade_date,
                "Position": position,
                "Stock": symbol,
                "Open": f"${open_price:.2f}",
                "Close": f"${close_price:.2f}",
                "Amount Invested": amount_invested,
                "Change (%)": ((close_price - open_price) / open_price) * 100,
                "PnL": pnl
            }
            trading_log.append(trading_dict)

            
    return pd.DataFrame(trading_log)

def process_earnings_m(earnings_df, prices_df, symbol, holding_period, strat):
    portfolio_value = 100000 #intial investment
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
  
        try:
            trade_date = get_next_trading_day(prices_df, reported_date)
        except ValueError:
                print(f"Reached the end of the available data for {symbol} when looking for trading days.")
                break

        daily_rows = prices_df.loc[trade_date]
        open_price = daily_rows.iloc[0]['1. open']
        close_price = daily_rows.iloc[holding_period]['4. close'] #each row is a minute, take the first row, then count out the minutes
        number_of_shares = calculate_position_size(portfolio_value, open_price, 15) #last value = %of portfolio value invested each trade

        position, pnl = globals()[strat](row, open_price, close_price, number_of_shares)
        if position == "pass":
            continue
        
        trading_dict = {
            "dateExecuted": trade_date,
            "Position": position,
            "Stock": symbol,
            "Open": f"${open_price:.2f}",
            "Close": f"${close_price:.2f}",
            "Amount Invested": open_price * number_of_shares,
            "Change (%)": ((close_price - open_price) / open_price) * 100,
            "PnL": pnl
        }
        trading_log.append(trading_dict)
    
    return pd.DataFrame(trading_log)

def calculate_position_size(portfolio_value, stock_price, allocation_percentage):
    amount_to_invest = portfolio_value * (allocation_percentage / 100)  # Amount to invest
    position_size = amount_to_invest // stock_price  # Number of shares/contracts to buy
    return position_size

def calculate_cumulative_pnl(df):
    df = pd.DataFrame(df)
    df = df.sort_values(by='dateExecuted', ascending=True)
    df['Cumulative PnL'] = df['PnL'].cumsum()
    return df

def calculate_sharpe_ratio(df, type, period, trades):
    risk_free_rate = 0.0
    mean_daily_returns = df['Return'].mean()
    std_dev_daily_returns = df['Return'].std()
    daily_sharpe = (mean_daily_returns - risk_free_rate) / std_dev_daily_returns
    sharpe = (mean_daily_returns - risk_free_rate) * np.sqrt(252) / std_dev_daily_returns



    df['dateExecuted'] = pd.to_datetime(df['dateExecuted'])
    total_return = (df['Portfolio Value'].iloc[-1] - 100000) / 100000

    df['Year'] = df['dateExecuted'].dt.year
    df.sort_values('dateExecuted', inplace=True)

    yearly_data = df.groupby('Year').last()
    yearly_data.reset_index(inplace=True)
    yearly_data = yearly_data[['Year', 'Portfolio Value']]

    first_row = pd.DataFrame({'Year': [df['Year'].min() - 1], 'Portfolio Value': [100000]})
    yearly_data = pd.concat([first_row, yearly_data], ignore_index=True)
    
    yearly_data['Yearly Return'] = yearly_data['Portfolio Value'].pct_change()

     #anualized sharpe ratio

    print("Average daily portfolio returns:", mean_daily_returns * 100, "%")
    print("Daily standard deviation:", std_dev_daily_returns * 100, "%")
    print("Daily Sharpe:", daily_sharpe)
    print("Anual Sharpe:", sharpe)
    
    return yearly_data, sharpe, total_return

def calculate_max_drawdown(df):
    df['Rolling Max'] = df['Portfolio Value'].cummax()
    df['Drawdown'] = (df['Portfolio Value'] - df['Rolling Max']) / df['Rolling Max']
    
    # Find the maximum drawdown
    max_drawdown = df['Drawdown'].min()
    
    return max_drawdown

def calculate_profit_per_contract(df, pnl, type, period):
    total_pnl = pnl['Cumulative PnL'].iloc[-1]
    number_of_contracts = len(df)
    if type == 'd':
        number_of_contracts /= period
    profit_per_contract = total_pnl / number_of_contracts
    return profit_per_contract

def portfolio_return(df):
    initial_investment = 100000

    df['Amount Invested'] = pd.to_numeric(df['Amount Invested'], errors='coerce')
    df['PnL'] = pd.to_numeric(df['PnL'], errors='coerce')
    grouped_df = df.groupby('dateExecuted').agg({'Amount Invested': 'sum', 'PnL': 'sum'}).reset_index()

    grouped_df['Cumulative PnL'] = grouped_df['PnL'].cumsum()
    grouped_df['Portfolio Value'] = grouped_df['Cumulative PnL'] + initial_investment
    grouped_df['Return'] = grouped_df['Portfolio Value'].pct_change()
    return grouped_df

def market_beta(df):
    # Convert date column to datetime
    df['dateExecuted'] = pd.to_datetime(df['dateExecuted'])
    
    # Extract Year and Month
    df['YearMonth'] = df['dateExecuted'].dt.to_period('M')

    # Get min and max date
    min_date = df['dateExecuted'].min()
    max_date = df['dateExecuted'].max()

    # Aggregate portfolio data to monthly frequency (last value of each month)
    monthly_data = df.groupby('YearMonth').last()
    monthly_data['Monthly Return'] = monthly_data['Portfolio Value'].pct_change()
    monthly_data.reset_index(inplace=True)  # Reset index to merge later

    # Load and clean S&P 500 data
    sp = pd.read_csv("data/SnP.csv")
    sp['Date'] = pd.to_datetime(sp['Date'], format='%b-%y', errors='coerce')
    sp = sp.dropna(subset=['Date'])  # Drop invalid date rows

    # Filter S&P 500 data to match the portfolio time range
    sp = sp[(sp['Date'] >= min_date) & (sp['Date'] <= max_date)]

    # Convert dates to Year-Month format to align with `monthly_data`
    sp['YearMonth'] = sp['Date'].dt.to_period('M')

    # Convert 'Open' prices to numeric
    sp['Open'] = sp['Open'].replace(',', '', regex=True).astype(float)

    # Aggregate S&P data to monthly frequency (last value of each month)
    sp_monthly = sp.groupby('YearMonth').last()

    # Merge portfolio and S&P data on Year-Month
    merged_data = pd.merge(monthly_data, sp_monthly, on='YearMonth', suffixes=('_portfolio', '_sp'))

    # Independent variable (portfolio monthly return)
    X = sm.add_constant(merged_data['Monthly Return'])  # Add constant for OLS

    # Dependent variable (S&P 500 monthly return)
    merged_data['SP Return'] = merged_data['Open'].pct_change()
    Y = merged_data['SP Return']

    # Fit the model
    model = sm.OLS(Y[1:], X[1:]).fit()  # Remove first NaN row due to pct_change()
    beta = model.params['Monthly Return']

    return beta

def plot_pnl(df):
    min_date = df['dateExecuted'].min()
    max_date = df['dateExecuted'].max()
    df['dateExecuted'] = pd.to_datetime(df['dateExecuted'])

    sp = pd.read_csv("data/SnP.csv")
    sp['Date'] = pd.to_datetime(sp['Date'], format='%b-%y', errors='coerce')
    sp = sp.dropna(subset=['Date'])  # Drop invalid date rows
    sp = sp.sort_values(by='Date')
    sp['Open'] = sp['Open'].replace(',', '', regex=True).astype(float)

   
    sp = sp[(sp['Date'] >= min_date) & (sp['Date'] <= max_date)]  # Filter S&P 500 data to match the portfolio time range
    scale_fct = sp['Open'].iloc[0] / df['Portfolio Value'].iloc[0] # Help vizualize porfolio vs S&P by scaling starting point
   
    # print(sp)
    # Plotting both datasets
    plt.figure(figsize=(12, 6))  # Set the figure size
    plt.plot(df['dateExecuted'], df['Portfolio Value'], 
             marker='o', linestyle='-', markersize=4, label='Portfolio Value')  # Portfolio line plot with markers

    plt.plot(sp['Date'], sp['Open'] / scale_fct, 
             marker='', linestyle='-', color='red', label='S&P 500 Open')  # S&P 500 line plot

    plt.title('Portfolio Value and S&P 500 Over Time')  # Title of the graph
    plt.xlabel('Date')  # Label for the x-axis
    plt.ylabel('Value')  # Label for the y-axis
    plt.legend()  # Add a legend to distinguish the lines
    plt.grid(True)  # Add gridlines for better readability
    plt.gcf().autofmt_xdate()  # Rotate date labels for better readability
    plt.show()

def append_to_csv(dataframe, filename):
    file_exists = os.path.isfile(filename)
    header = not file_exists or os.stat(filename).st_size == 0
    dataframe.to_csv(filename, mode='a', header=header, index=False)

if __name__ == "__main__":

    '''
    Adjust portfolio below by manually entering ticker. See data folder for available tickers.
    '''
    # symbols = ["AAPL", "BLK", "CVX", "D", "DE", "LUV", "NFLX", "NKE", "PG", "WMT", "AMZN", "MSFT", "BAC", "JPM", "V", "MA", "INTC", "AMD", "CSCO", "PFE", "GILD", "ADBE", "DIS", "IBM", "ORCL", "XOM", "BA"]
    symbols = ["AAPL", "ABT", "ADBE", "AMD", "AMZN", "AXP", "BA", "BAC", "BLK", "CAT", "CFG","CRWD", "CSCO", "CVX", "D", "DD", "DE", "DIS", "GILD", "GOOGL","GS", "IBM", "INTC", "JNJ", "JPM", "LMT", "LUV", "MA", "MRK", "MSFT", "NEE", "NEM", "NFLX", "NKE", "ORCL", "PFE", "PG", "RHP", "SBUX", "SO", "SPG", "TGT", "TM", "V", "WMT", "WYNN", "XOM"]

    #holding_period_type = get_input_period()

    # if holding_period_type == "d":
    #     holding_period = int(input("Enter integer number of days:"))
    # if holding_period_type == "m":
    #     holding_period = int(input("Enter integer number of minutes:"))
    
    strategies = ['L_s_strategy', 'L_if_strategy', 'L_strategy', 'S_if_strategy', 'S_strategy']
    # strategies = ['S_if_strategy']
    holding_types = ['d', 'm']
    for holding_period_type in holding_types: #run for days and minutes
        if holding_period_type == 'd':
            length = 31
        else:
            length = 28
        for strat in strategies:   #loop through each strategy
            for i in range(length): #run each strategy for every interval 1-30 days/ 1-20 min then up to 1hr by 5 min
                if holding_period_type == 'm' and i > 19: #start counting by 5 after 20 min
                    holding_period = (i-20)*5 + 20
                else:
                    holding_period = i + 1
            # holding_period = 1
                all_pnl = []

                for symbol in symbols:
                    prices_df = fetch_spot_from_h5(symbol, holding_period_type) #read in price data
                    trading_log = return_on_earning(symbol, prices_df, holding_period_type, holding_period, strat) #make trades based on strategy
                    all_pnl.append(trading_log) #log every trade across all tickers

                combined_pnl = pd.concat(all_pnl)
                combined_pnl = calculate_cumulative_pnl(combined_pnl) #sort by date/track cumallative returns
                portfolio_pnl = portfolio_return(combined_pnl) #group by day
                portfolio_pnl.to_csv("Portfolio_Return.csv", index=False)

                max_drawdown = calculate_max_drawdown(portfolio_pnl)
                profit_per_contract = calculate_profit_per_contract(combined_pnl, portfolio_pnl, holding_period_type, holding_period)
                yearly, sharpe, returns = calculate_sharpe_ratio(portfolio_pnl, holding_period_type, holding_period, combined_pnl)
                beta = market_beta(portfolio_pnl)

                yearly.to_csv("yearly.csv")

                print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")
                print(f"Profit Per Contract is: ${profit_per_contract:.2f}")
                print(f"Sharpe Ratio: {sharpe:.2f}")
                print(f"Return: {returns * 100:.5f}%")
                print(f"Beta: {beta:.5f}")

                combined_pnl.to_csv("Combined_Portfolio_PnL.csv", index=False)
                
                analytics_df = pd.DataFrame([{
                    "Strategy": strat,
                    "Holding Period": holding_period_type,
                    "Period Length": holding_period,
                    "Returns": returns,
                    "Maximum Drawdown": max_drawdown,
                    "Sharpe Ratio": sharpe,
                    "Profit Per Contract": profit_per_contract,
                    "Portfolio Beta": beta
                }])

                append_to_csv(analytics_df, "Performance_Metrics.csv") # Append results to CSV

                # plot_pnl(portfolio_pnl)