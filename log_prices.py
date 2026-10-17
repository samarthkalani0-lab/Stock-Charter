# Daily price log: adds each trading day's opening and closing price for every stock
# in portfolio.csv (plus the Nifty 50 and the USD/INR rate) to data/prices.csv.
#
# Safe to run as often as you like. Each run re-checks the last 10 days and fills in
# anything missing, so a skipped day (computer off, Yahoo down) catches up by itself.
# A stock you've just added to portfolio.csv gets its whole history since its buy date.
#
# Prices are the real traded prices, not adjusted for later dividends or splits, so a
# day's row never changes once it's logged.

import os
import sys
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from portfolio import FIRST_BUY_DATE, FX, INDEX, PORTFOLIO, currency

LOG = os.path.join("data", "prices.csv")
COLUMNS = ["date", "ticker", "name", "open", "close", "currency"]
RECHECK_DAYS = 10

# ticker -> (name, the earliest day we want in the log)
TRACKED = {t: (s["name"], s["buy_date"]) for t, s in PORTFOLIO.items()}
TRACKED[INDEX[0]] = (INDEX[1], FIRST_BUY_DATE)
TRACKED[FX[0]] = (FX[1], FIRST_BUY_DATE)

if os.path.exists(LOG):
    log = pd.read_csv(LOG, dtype={"date": str})
else:
    log = pd.DataFrame(columns=COLUMNS)
first_logged = log.groupby("ticker")["date"].min().to_dict()
last_logged = log.groupby("ticker")["date"].max().to_dict()

new_rows, failed = [], []
for ticker, (name, wanted_from) in TRACKED.items():
    if first_logged.get(ticker, "9999") <= wanted_from:
        # Already logged back to the day we need: re-check from a few days before the
        # last entry, which also fills any gap if the job didn't run for a while.
        start = (date.fromisoformat(last_logged[ticker]) - timedelta(days=RECHECK_DAYS)).isoformat()
    else:
        # A new stock, or an earlier buy date: fetch everything from that day.
        start = wanted_from
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

# A ticker that has never returned any prices is almost certainly mistyped: fail loudly
# (GitHub emails you when the daily job fails). Others are probably a brief Yahoo hiccup.
never_seen = [t for t in failed if t not in first_logged]
retry = [t for t in failed if t in first_logged]
if retry:
    print("No data this time for: " + ", ".join(retry) + ". They'll be retried on the next run.")
if never_seen:
    sys.exit("Yahoo Finance has no prices for: " + ", ".join(never_seen) + ". Check the ticker in "
             "portfolio.csv against finance.yahoo.com (Indian stocks end in .NS or .BO).")
