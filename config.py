"""
Config for BAMSec Filing Bot.
Watchlist is driven by tickers: watchlist_tickers.txt is resolved to SEC CIKs
via SEC company_tickers.json (see ticker_to_cik.py).
"""
import os
from dotenv import load_dotenv

load_dotenv()

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "BAMSecFilingBot your@email.com")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# SEC CIKs to watch. Built from watchlist_tickers.txt (ticker -> CIK via SEC company_tickers.json).
# Edit watchlist_tickers.txt to add/remove tickers; CIKs are resolved at import time.
from ticker_to_cik import get_watchlist_ciks
WATCHLIST_CIKS = get_watchlist_ciks()

# Form types to alert on (SEC form type codes).
# 8-K = current report (material events, often redemption/call); 424B* = prospectus supplements; N-2 = CEF.
FORM_TYPES = {
    "8-K",
    "424B2",
    "424B3",
    "424B4",
    "424B5",
    "424B7",
    "N-2",
    "DEF 14A",
}

# How often to poll the SEC (minutes). Stay respectful of SEC rate limits.
POLL_INTERVAL_MINUTES = 5

# State file to remember last-seen filings and avoid duplicate alerts.
STATE_FILE = "bot_state.json"

# Only alert on filings from the last N days (avoids spamming old filings on first run).
MAX_FILING_AGE_DAYS = 7
