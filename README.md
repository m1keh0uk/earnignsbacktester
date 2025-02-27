# Evaluating Investment Strategies Following Quarterly Earnings Announcements
Michael Houk

## 1. Objective

I analyzed five years of price data and quarterly earnings announcements to identify a viable investment strategy based on whether companies exceeded or missed their earnings expectations.

## 2. Research Question

How effective of a strategy is shorting a stock when the company misses earnings and buying the stock when it beats earnings? What time horizons is this viable for?

## 3. Data

The historical price data I used, for both daily and minute levels, were proprietary datasets provided by Avi Thacker. Earnings announcement data was collected from the Alpha Vantage API. To test these strategies, I created a portfolio of 50 random companies.

## 4. Procedure


To test this main strategy, going short when a company reports earnings lower than expected and going long when earnings beat expectations, I compared it to four other control strategies. Below is the total list of strategies that were compared, and the label I’ve assigned to each:

Shorting on earnings miss, buying long on earnings beat (L_S)
Shorting on every earnings announcement (S)
Shorting on every earnings miss (S_if)
Buying long on every earnings announcement (L)
Buying long on every earnings beat (L_if)

Each of these strategies was analyzed on minute and day holding periods. The minute holding periods were 1 through 55 minutes (5-minute steps), and the days were 1 to 31 days. This means that for each strategy, the appropriate position was held for that amount of time following the earnings announcement.

The starting date of the trade was determined by the time of the announcement. If the earrings were reported post-market hours, the trade was initiated on the next available trading day. If earnings were pre-market hours, the trade was initiated that day. 


## 5. Execution

I created a backtesting framework in Python to track portfolio success for each of the 5 strategies. I used the Pandas library for data manipulation and visualization. The code is available at this repository: https://github.com/m1keh0uk/earnignsbacktester.git 

The program takes the selected tickers, fetches the earnings reports, and then executes the selected strategy for the selected holding period. The trades are compiled in a trading log, reporting the PnL and return of each individual trade. This trading log is then compiled, grouped by each day, to analyze the total portfolio PnL and return for each day. From this data set, the Sharpe Ratio, Max Drawdown, Profit Per Contract, and cumulative PnL are calculated. The monthly strategies returns are regressed on the S&P 500 returns to calculate beta. The cumulative PnL is then graphed. The performance metrics previously mentioned are stored, along with the strategy and holding period. After collecting data on all 5 strategies across all holding periods, I sorted the data and compared which strategy was most successful.

