# Reads the portfolio from portfolio.csv, which is the file to edit when you buy a stock.
# Used by build_dashboard.py and log_prices.py.
#
# portfolio.csv has one row per stock:
#   ticker    Yahoo Finance symbol: RELIANCE.NS (NSE), 500325.BO (BSE), AAPL (US)
#   name      what to call it on the dashboard
#   shares    how many you bought (fractions allowed, e.g. 0.3059 for US shares)
#   buy_date  the day you bought it, as YYYY-MM-DD; the buy price is that day's opening price

import csv
import re
import sys
from datetime import date

INDEX = ("^NSEI", "Nifty 50")
FX = ("INR=X", "US dollar in rupees")   # converts US prices to rupees
STARTING_CAPITAL = 100000
CSV_FILE = "portfolio.csv"


def currency(ticker):
    """INR for Indian stocks, points for an index, USD for everything else."""
    if ticker.startswith("^"):
        return "points"
    if ticker.endswith((".NS", ".BO")) or ticker == FX[0]:
        return "INR"
    return "USD"


def load():
    """ticker -> {"name", "shares", "buy_date"}. Stops with a clear message on a bad row."""
    stocks, problems = {}, []
    with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            ticker = (row.get("ticker") or "").strip().upper()
            if not ticker:
                continue  # blank line
            name = (row.get("name") or "").strip() or ticker
            where = f"{CSV_FILE} line {line} ({ticker})"
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.&-]{0,19}", ticker):
                problems.append(f"{where}: the ticker should look like RELIANCE.NS, 500325.BO or AAPL.")
            if not re.fullmatch(r"[\w .&()'-]{1,40}", name):
                problems.append(f"{where}: keep the name to letters, numbers, spaces and . & ( ) ' - (40 characters at most).")
            try:
                shares = float(row.get("shares") or "")
                if shares <= 0:
                    raise ValueError
            except ValueError:
                problems.append(f"{where}: shares should be a number above 0, e.g. 10 or 0.5.")
                shares = 0
            buy_date = (row.get("buy_date") or "").strip()
            try:
                if date.fromisoformat(buy_date) > date.today():
                    problems.append(f"{where}: the buy date {buy_date} is in the future.")
            except ValueError:
                problems.append(f"{where}: the buy date should look like 2026-11-02 (year-month-day).")
            if ticker in stocks:
                problems.append(f"{where}: this ticker is listed twice. Add the shares together on one line.")
            stocks[ticker] = {"name": name, "shares": shares, "buy_date": buy_date}
    if problems:
        sys.exit("Please fix portfolio.csv:\n- " + "\n- ".join(problems))
    if not stocks:
        sys.exit("portfolio.csv has no stocks in it.")
    return stocks


PORTFOLIO = load()
# The first day anything was bought: where the portfolio chart and the price log start.
FIRST_BUY_DATE = min(s["buy_date"] for s in PORTFOLIO.values())
