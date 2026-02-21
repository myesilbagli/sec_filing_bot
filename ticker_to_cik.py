"""
Resolve ticker symbols to SEC CIKs using the SEC's company_tickers.json.
Used to build WATCHLIST_CIKS from watchlist_tickers.txt.
"""
import logging
import os
from pathlib import Path

import requests

LOG = logging.getLogger(__name__)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
WATCHLIST_TICKERS_FILE = Path(__file__).resolve().parent / "watchlist_tickers.txt"


def _sec_user_agent() -> str:
    """User-Agent for SEC requests (avoid importing config to prevent circular import)."""
    return os.getenv("SEC_USER_AGENT", "BAMSecFilingBot your@email.com")


def load_sec_ticker_map() -> dict[str, str]:
    """
    Fetch SEC company_tickers.json and return a map ticker_upper -> cik (string).
    """
    try:
        r = requests.get(
            SEC_TICKERS_URL,
            headers={"User-Agent": _sec_user_agent()},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        LOG.warning("Could not load SEC company tickers: %s", e)
        return {}

    # data is {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "..."}, ...}
    out = {}
    for entry in data.values():
        ticker = (entry.get("ticker") or "").strip().upper()
        cik = entry.get("cik_str")
        if ticker and cik is not None:
            out[ticker] = str(cik).strip()
    return out


def load_watchlist_tickers() -> set[str]:
    """Load ticker symbols from watchlist_tickers.txt (one per line, uppercase)."""
    path = WATCHLIST_TICKERS_FILE
    if not path.exists():
        return set()
    raw = path.read_text().strip()
    return {t.strip().upper() for t in raw.splitlines() if t.strip()}


def get_watchlist_ciks() -> set[str]:
    """
    Resolve watchlist_tickers.txt to SEC CIKs. Returns a set of CIK strings.
    Tickers not found in SEC data are skipped (and logged once).
    """
    tickers = load_watchlist_tickers()
    if not tickers:
        return set()

    sec_map = load_sec_ticker_map()
    ciks = set()
    for t in tickers:
        cik = sec_map.get(t)
        if cik:
            ciks.add(cik)
        else:
            LOG.debug("No SEC CIK for ticker %s", t)
    unresolved = tickers - {t for t in tickers if sec_map.get(t)}
    if unresolved:
        LOG.info("Tickers with no SEC CIK (skipped): %s", sorted(unresolved))
    return ciks
