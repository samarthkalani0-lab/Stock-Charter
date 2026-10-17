# Daily price log: adds each trading day's opening and closing price for every stock
# in the portfolio (plus the Nifty 50 and the USD/INR rate) to data/prices.csv.
#
# Safe to run as often as you like. Each run re-checks the last 10 days and fills in
# anything missing, so a skipped day (computer off, Yahoo down) catches up by itself.
# The first run fills in everything since the buy date.
#
# Prices are the real traded prices, not adjusted for later dividends or splits, so a
# day's row never changes once it's logged.

import os
import sys
from datetime import timedelta

import pandas as pd
import yfinance as yf

from portfolio import BUY_DATE, FX, INDEX, PORTFOLIO

LOG = os.path.join("data", "prices.csv")
COLUMNS = ["date", "ticker", "name", "open", "close", "currency"]
RECHECK_DAYS = 10

TRACKED = {t: name for t, (name, _) in PORTFOLIO.items()}
TRACKED[INDEX[0]] = INDEX[1]
TRACKED[FX[0]] = FX[1]


def currency(ticker):
    if ticker.startswith("^"):
        return "points"
    if ticker.endswith(".NS") or ticker.endswith(".BO") or ticker == FX[0]:
        return "INR"
    return "USD"


# Start from the buy date the first time, otherwise a few days before the last entry.
if os.path.exists(LOG):
    log = pd.read_csv(LOG, dtype={"date": str})
    start = (pd.Timestamp(log["date"].max()) - timedelta(days=RECHECK_DAYS)).strftime("%Y-%m-%d")
else:
    log = pd.DataFrame(columns=COLUMNS)
    start = BUY_DATE

new_rows, failed = [], []
for ticker, name in TRACKED.items():
    data = yf.download(ticker, start=start, auto_adjust=False, progress=False)
    if data.empty:
        failed.append(ticker)
        continue
    data.columns = data.columns.get_level_values(0)   # flatten yfinance's two-level column names
    digits = 4 if ticker == FX[0] else 2
    for day, row in data[["Open", "Close"]].dropna().iterrows():
        new_rows.append([day.strftime("%Y-%m-%d"), ticker, name,
                         round(float(row["Open"]), digits), round(float(row["Close"]), digits), currency(ticker)])

if len(failed) == len(TRACKED):
    sys.exit("No prices came back for any stock. Yahoo Finance may be down; nothing was changed.")

before = len(log)
fresh = pd.DataFrame(new_rows, columns=COLUMNS)
# Newer downloads replace older rows for the same day (Yahoo sometimes corrects a price late).
log = (pd.concat([log, fresh]) if before else fresh) \
    .drop_duplicates(subset=["date", "ticker"], keep="last") \
    .sort_values(["date", "ticker"])

os.makedirs("data", exist_ok=True)
log.to_csv(LOG, index=False)

print(f"{LOG}: {len(log) - before} new rows, {len(log)} in total, latest day {log['date'].max()}.")
if failed:
    print("No data this time for: " + ", ".join(failed) + ". They'll be retried on the next run.")
