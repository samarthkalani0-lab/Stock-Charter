# Builds the data for the interactive dashboard (dashboard/index.html).
# Downloads prices for every stock in the mock portfolio, works out the 50-day
# moving average and a few simple measures for each one, and writes it all
# straight into dashboard/index.html, so the page is one file that works anywhere.

import json
import re
import sys
from datetime import date

import pandas as pd
import yfinance as yf

from portfolio import BUY_DATE, FX, INDEX, PORTFOLIO, STARTING_CAPITAL

MA_DAYS = 50
PAGE = "dashboard/index.html"


def download(ticker):
    """Daily open and close prices for the last 18 months (extra history so the
    50-day average already exists at the start of the 1-year chart)."""
    data = yf.download(ticker, period="18mo", auto_adjust=True, progress=False)
    if data.empty:
        sys.exit(f"No prices came back for {ticker}. Yahoo Finance may be down, or the ticker "
                 "has changed. Nothing was updated; try again later.")
    data.columns = data.columns.get_level_values(0)   # flatten yfinance's two-level column names
    return data[["Open", "Close"]].dropna()


def analyse(prices):
    """Simple measures for one stock, all from its closing prices."""
    close = prices["Close"]
    ma = close.rolling(MA_DAYS).mean()
    since_buy = close[close.index >= BUY_DATE]
    buy_price = float(prices.loc[prices.index >= BUY_DATE, "Open"].iloc[0])   # Day 1 opening price

    # The most recent day the price crossed its 50-day average.
    above = (close > ma)[ma.notna()]
    crossed = above.ne(above.shift()) & above.shift().notna()
    last_cross = above[crossed].index[-1] if crossed.any() else None

    # The low point after the highest price since buying (biggest fall from a peak).
    drawdown = (since_buy / since_buy.cummax() - 1).min()

    return {
        "buyPrice": round(buy_price, 2),
        "last": round(float(close.iloc[-1]), 2),
        "ma": round(float(ma.iloc[-1]), 2),
        "returnPct": round((close.iloc[-1] / buy_price - 1) * 100, 2),
        "gapPct": round((close.iloc[-1] / ma.iloc[-1] - 1) * 100, 2),
        # How much the 50-day average itself moved over the last 20 trading days.
        "maSlopePct": round((ma.iloc[-1] / ma.iloc[-21] - 1) * 100, 2),
        "lastCross": {"date": str(last_cross.date()), "up": bool(above[last_cross])} if last_cross is not None else None,
        "highSinceBuy": round(float(since_buy.max()), 2),
        "lowSinceBuy": round(float(since_buy.min()), 2),
        "drawdownPct": round(float(drawdown) * 100, 2),
        # Typical daily move: the standard deviation of daily % changes.
        "dailyMovePct": round(float(since_buy.pct_change().std() * 100), 2),
        # One entry per trading day since buying: was the price above its average?
        "aboveSinceBuy": [bool(x) for x in (close > ma)[close.index >= BUY_DATE]],
    }


def series(prices):
    """Last year of daily closes and moving averages, as [date, close, ma] rows."""
    close = prices["Close"]
    ma = close.rolling(MA_DAYS).mean()
    cutoff = close.index[-1] - pd.DateOffset(years=1)
    rows = []
    for day in close.index[close.index >= cutoff]:
        rows.append([str(day.date()), round(float(close[day]), 2),
                     round(float(ma[day]), 2) if pd.notna(ma[day]) else None])
    return rows


stocks = []
closes = {}
for ticker, (name, shares) in PORTFOLIO.items():
    prices = download(ticker)
    closes[ticker] = prices["Close"]
    stocks.append({"ticker": ticker, "name": name, "shares": shares,
                   "currency": "USD" if ticker == "AAPL" else "INR",
                   **analyse(prices), "series": series(prices)})
    print(f"{name:26s} return since buying {stocks[-1]['returnPct']:+6.2f}%")

nifty_prices = download(INDEX[0])
nifty = {"ticker": INDEX[0], "name": INDEX[1], "currency": "points",
         **analyse(nifty_prices), "series": series(nifty_prices)}

# Portfolio value in rupees on each NSE trading day since buying.
# Apple is priced in dollars, so it is converted with that day's USD/INR rate.
usd_inr = download(FX[0])["Close"]
days = nifty_prices.index[nifty_prices.index >= BUY_DATE]
table = pd.DataFrame(closes).reindex(days.union(pd.DatetimeIndex(usd_inr.index))).ffill().reindex(days)
table["AAPL"] = table["AAPL"] * usd_inr.reindex(table.index, method="ffill")

cost = sum(s["buyPrice"] * s["shares"] for s in stocks if s["currency"] == "INR")
aapl = next(s for s in stocks if s["ticker"] == "AAPL")
cost += aapl["buyPrice"] * aapl["shares"] * float(usd_inr[usd_inr.index >= BUY_DATE].iloc[0])
cash = STARTING_CAPITAL - cost

shares = pd.Series({t: s for t, (_, s) in PORTFOLIO.items()})
value = (table[shares.index] * shares).sum(axis=1) + cash
nifty_open = float(nifty_prices.loc[days[0], "Open"])
portfolio = [[str(d.date()), round(float(v), 2), round(float(nifty_prices.loc[d, "Close"] / nifty_open * STARTING_CAPITAL), 2)]
             for d, v in value.items()]

data = {
    "generated": str(date.today()),
    "buyDate": BUY_DATE,
    "maDays": MA_DAYS,
    "startingCapital": STARTING_CAPITAL,
    "cash": round(cash, 2),
    # [date, portfolio value, what Rs 1,00,000 in the Nifty 50 would be worth]
    "portfolio": portfolio,
    "stocks": stocks,
    "nifty": nifty,
}

# Put the data inside the page, between its <script id="portfolio-data"> tags,
# replacing whatever data was there from the last run.
with open(PAGE, encoding="utf-8") as f:
    page = f.read()
block = '<script id="portfolio-data">\nwindow.PORTFOLIO_DATA = ' + json.dumps(data) + ';\n</script>'
page, found = re.subn(r'<script id="portfolio-data">.*?</script>', lambda _: block, page, count=1, flags=re.S)
if not found:
    sys.exit(f'Couldn\'t find <script id="portfolio-data"> in {PAGE}, so nothing was updated. '
             "Put that tag back exactly as it was.")
with open(PAGE, "w", encoding="utf-8") as f:
    f.write(page)

print(f"\nPortfolio value today: Rs {portfolio[-1][1]:,.0f}   Same money in the Nifty 50: Rs {portfolio[-1][2]:,.0f}")
print(f"Updated {PAGE}. Open it in a browser to see the dashboard.")
