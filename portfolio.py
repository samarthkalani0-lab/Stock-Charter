# The mock portfolio from project 1, shared by build_dashboard.py and log_prices.py.
# To track a different set of stocks, change it here only.

# ticker -> (name, shares bought). Shares come from the spreadsheet; each stock got Rs 9,000.
PORTFOLIO = {
    "AAPL": ("Apple", 0.3059),
    "ETERNAL.NS": ("Eternal (Zomato)", 28),
    "RELIANCE.NS": ("Reliance Industries", 6),
    "ANGELONE.NS": ("Angel One", 29),
    "INFY.NS": ("Infosys", 7),
    "LICI.NS": ("LIC", 23),
    "ADANIPORTS.NS": ("Adani Ports", 5),
    "HDFCBANK.NS": ("HDFC Bank", 12),
    "SBIN.NS": ("State Bank of India", 8),
    "DOMS.NS": ("DOMS Industries", 3),
    "IOC.NS": ("Indian Oil Corporation", 62),
}
INDEX = ("^NSEI", "Nifty 50")
FX = ("INR=X", "US dollar in rupees")   # used to convert Apple's price to rupees
STARTING_CAPITAL = 100000
BUY_DATE = "2026-08-05"
