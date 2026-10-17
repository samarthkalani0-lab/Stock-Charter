# Python Stock Price Charter
# Downloads daily prices for each stock, works out a 50-day moving average,
# and saves one chart per stock showing both lines.

import os                          # lets us create a folder for the charts
import pandas as pd                # table library yfinance uses; we need it for dates
import yfinance as yf              # free library that downloads prices from Yahoo Finance
import matplotlib.pyplot as plt    # library for drawing charts

# 1. The stocks to chart. Indian NSE stocks end in ".NS" (BSE stocks end in ".BO").
#    US stocks such as Apple have no suffix. These are the stocks from my mock portfolio (project 1).
STOCKS = {
    "AAPL": "Apple",
    "ETERNAL.NS": "Eternal (Zomato)",
    "RELIANCE.NS": "Reliance Industries",
    "ANGELONE.NS": "Angel One",
    "INFY.NS": "Infosys",
    "LICI.NS": "LIC",
    "ADANIPORTS.NS": "Adani Ports",
    "HDFCBANK.NS": "HDFC Bank",
    "SBIN.NS": "State Bank of India",
    "DOMS.NS": "DOMS Industries",
    "IOC.NS": "Indian Oil Corporation",
    "^NSEI": "Nifty 50 index",
}

PERIOD = "1y"              # how much history to download: "6mo", "1y", "2y", "5y" ...
MA_DAYS = 50               # length of the moving average, in trading days
BUY_DATE = "2026-08-05"    # the day I bought the mock portfolio, marked on every chart
OUTPUT_FOLDER = "charts"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)   # make the charts folder if it isn't there yet

for ticker, name in STOCKS.items():
    # 2. Download daily prices. The result is a table with one row per trading day.
    data = yf.download(ticker, period=PERIOD, auto_adjust=True, progress=False)

    if data.empty:
        print(f"No data for {ticker} - check the ticker symbol.")
        continue

    # 3. Keep only the closing price, one number per day.
    close = data["Close"].squeeze()

    # 4. The 50-day moving average: for each day, the average of the last 50 closing prices.
    #    It smooths out daily ups and downs so the overall trend is easier to see.
    moving_avg = close.rolling(window=MA_DAYS).mean()

    # 5. Draw both lines on one chart.
    plt.figure(figsize=(11, 5))
    plt.plot(close.index, close, label="Daily closing price", color="#1f77b4", linewidth=1.2)
    plt.plot(moving_avg.index, moving_avg, label=f"{MA_DAYS}-day moving average",
             color="#ff7f0e", linewidth=2)
    plt.axvline(pd.Timestamp(BUY_DATE), color="grey", linestyle="--", label="Portfolio bought")
    plt.title(f"{name} ({ticker}) - last {PERIOD}")
    plt.xlabel("Date")
    if ticker.startswith("^"):
        plt.ylabel("Index points")
    elif ticker.endswith(".NS") or ticker.endswith(".BO"):
        plt.ylabel("Price (Rs)")
    else:
        plt.ylabel("Price (US$)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()

    # 6. Save the chart as a picture file, then close it to free memory.
    filename = ticker.replace("^", "").replace(".", "_") + ".png"
    plt.savefig(os.path.join(OUTPUT_FOLDER, filename), dpi=120)
    plt.close()

    # 7. Print a one-line summary: is the price above or below its moving average?
    last_price = close.iloc[-1]
    last_ma = moving_avg.iloc[-1]
    trend = "ABOVE" if last_price > last_ma else "BELOW"
    print(f"{name:28s} last close {last_price:10.2f}   50-day avg {last_ma:10.2f}   "
          f"price is {trend} its average  -> {filename}")

print(f"\nDone. Charts saved in the '{OUTPUT_FOLDER}' folder.")
