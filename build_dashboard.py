# Builds the data for the interactive dashboard (dashboard/index.html).
# Downloads prices for every stock in portfolio.csv, works out the 50-day moving
# average and a few simple measures for each one, and writes it all straight into
# dashboard/index.html, so the page is one file that works anywhere.

import json
import re
import sys
from datetime import date

import pandas as pd
import yfinance as yf

from portfolio import FIRST_BUY_DATE, FX, INDEX, PORTFOLIO, STARTING_CAPITAL, currency

MA_DAYS = 50
PAGE = "dashboard/index.html"
# Enough history for the 1-year chart and for the 50-day average on the first buy date.
HISTORY_START = min(pd.Timestamp(FIRST_BUY_DATE) - pd.Timedelta(days=100),
                    pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y-%m-%d")


def download(ticker):
    """Daily open and close prices from HISTORY_START to today."""
    data = yf.download(ticker, start=HISTORY_START, auto_adjust=True, progress=False)
    if data.empty:
        sys.exit(f"No prices came back for {ticker}. Check the ticker in portfolio.csv against "
                 "finance.yahoo.com, or try again later if Yahoo Finance is down. Nothing was updated.")
    data.columns = data.columns.get_level_values(0)   # flatten yfinance's two-level column names
    return data[["Open", "Close"]].dropna()


def first_day_from(index, day):
    """The first trading day on or after `day` (the buy date may be a holiday)."""
    later = index[index >= pd.Timestamp(day)]
    if later.empty:
        sys.exit(f"There are no prices yet on or after {day}. If you bought today, the "
                 "dashboard will include it after the market's first day of trading.")
    return later[0]


def analyse(prices, buy_date):
    """Simple measures for one stock, all from its closing prices."""
    close = prices["Close"]
    ma = close.rolling(MA_DAYS).mean()
    bought_on = first_day_from(prices.index, buy_date)
    since_buy = close[close.index >= bought_on]
    buy_price = float(prices.loc[bought_on, "Open"])   # opening price on the day you bought

    # The most recent day the price crossed its 50-day average.
    above = (close > ma)[ma.notna()]
    crossed = above.ne(above.shift()) & above.shift().notna()
    last_cross = above[crossed].index[-1] if crossed.any() else None

    # The low point after the highest price since buying (biggest fall from a peak).
    drawdown = (since_buy / since_buy.cummax() - 1).min()

    return {
        "buyDate": str(bought_on.date()),
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
        # Typical daily move: the standard deviation of daily % changes (0 on the first day).
        "dailyMovePct": round(float(since_buy.pct_change().std() * 100), 2) if len(since_buy) > 2 else 0,
        # One entry per trading day since buying: was the price above its average?
        "aboveSinceBuy": [bool(x) for x in (close > ma)[close.index >= bought_on]],
    }


def series(prices):
    """Last year of daily closes and moving averages, as [date, close, ma] rows."""
    close = prices["Close"]
    ma = close.rolling(MA_DAYS).mean()
    cutoff = close.index[-1] - pd.DateOffset(years=1)
    return [[str(day.date()), round(float(close[day]), 2),
             round(float(ma[day]), 2) if pd.notna(ma[day]) else None]
            for day in close.index[close.index >= cutoff]]


nifty_prices = download(INDEX[0])
usd_inr = download(FX[0])["Close"]
nifty_open = nifty_prices["Open"]


def asof(prices, day):
    """The latest value on or before `day` (or the first one, if `day` is earlier)."""
    earlier = prices[prices.index <= day]
    return float(earlier.iloc[-1] if len(earlier) else prices.iloc[0])


stocks, closes = [], {}
for ticker, holding in PORTFOLIO.items():
    prices = download(ticker)
    cur = currency(ticker)
    s = {"ticker": ticker, "name": holding["name"], "shares": holding["shares"], "currency": cur,
         **analyse(prices, holding["buy_date"]), "series": series(prices)}
    bought_on = pd.Timestamp(s["buyDate"])
    # What the purchase cost in rupees (US prices converted at that day's exchange rate).
    s["costInr"] = round(s["buyPrice"] * s["shares"] * (asof(usd_inr, bought_on) if cur == "USD" else 1), 2)
    # The Nifty 50's change over the same period, so each stock is compared fairly.
    nifty_from = float(nifty_open.loc[first_day_from(nifty_open.index, s["buyDate"])])
    s["niftyPct"] = round((float(nifty_prices["Close"].iloc[-1]) / nifty_from - 1) * 100, 2)
    closes[ticker] = prices["Close"] * (usd_inr.reindex(prices.index, method="ffill").bfill() if cur == "USD" else 1)
    stocks.append(s)
    print(f"{s['name']:26s} return since buying {s['returnPct']:+6.2f}%")

nifty = {"ticker": INDEX[0], "name": INDEX[1], "currency": "points",
         **analyse(nifty_prices, FIRST_BUY_DATE), "series": series(nifty_prices)}

# Portfolio value in rupees on each NSE trading day since the first purchase.
# Before a stock is bought, its money is still cash; from its buy date on, it's shares.
# The comparison puts each purchase's rupees into the Nifty 50 on the same day instead.
days = nifty_prices.index[nifty_prices.index >= pd.Timestamp(FIRST_BUY_DATE)]
# Stocks trade on different calendars (US vs India), so carry each last price forward.
frame = pd.DataFrame(closes)
table = frame.reindex(frame.index.union(days)).ffill().reindex(days)
portfolio = []
for d in days:
    value = nifty_value = STARTING_CAPITAL
    for s in stocks:
        if pd.Timestamp(s["buyDate"]) <= d:
            value += s["shares"] * float(table.loc[d, s["ticker"]]) - s["costInr"]
            start = float(nifty_open.loc[first_day_from(nifty_open.index, s["buyDate"])])
            nifty_value += s["costInr"] * (float(nifty_prices.loc[d, "Close"]) / start - 1)
    portfolio.append([str(d.date()), round(value, 2), round(nifty_value, 2)])

invested = sum(s["costInr"] for s in stocks)
cash = STARTING_CAPITAL - invested
if cash < 0:
    print(f"Note: the stocks cost Rs {invested:,.0f}, more than the Rs {STARTING_CAPITAL:,} starting "
          "capital, so cash shows as negative.")

data = {
    "generated": str(date.today()),
    "buyDate": FIRST_BUY_DATE,
    "maDays": MA_DAYS,
    "startingCapital": STARTING_CAPITAL,
    "cash": round(cash, 2),
    # [date, portfolio value, the same purchases made in the Nifty 50 instead]
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
