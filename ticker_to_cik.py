"""
Resolve ticker symbols to SEC CIKs using the SEC's company_tickers.json.
Watchlist = preferreds (watchlist_preferred_tickers.txt) + CEFs (watchlist_cef_tickers.txt).
"""
import logging
import os
from pathlib import Path

import requests

LOG = logging.getLogger(__name__)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
WATCHLIST_PREFERRED_TICKERS_FILE = Path(__file__).resolve().parent / "watchlist_preferred_tickers.txt"
WATCHLIST_CEF_TICKERS_FILE = Path(__file__).resolve().parent / "watchlist_cef_tickers.txt"


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


def _load_tickers_from_file(path: Path) -> set[str]:
    """Load ticker symbols from a file (one per line, uppercase)."""
    if not path.exists():
        return set()
    raw = path.read_text().strip()
    return {t.strip().upper() for t in raw.splitlines() if t.strip()}


def load_preferred_tickers() -> set[str]:
    """Load preferred stock tickers from watchlist_preferred_tickers.txt."""
    return _load_tickers_from_file(WATCHLIST_PREFERRED_TICKERS_FILE)


def load_cef_tickers() -> set[str]:
    """Load closed-end fund tickers from watchlist_cef_tickers.txt."""
    return _load_tickers_from_file(WATCHLIST_CEF_TICKERS_FILE)


def load_all_watchlist_tickers() -> set[str]:
    """Combined watchlist: preferreds + CEFs (no duplicates)."""
    return load_preferred_tickers() | load_cef_tickers()


def get_watchlist_ciks() -> set[str]:
    """
    Resolve preferred + CEF tickers to SEC CIKs. Returns a set of CIK strings.
    Tickers not found in SEC data are skipped (and logged once).
    """
    tickers = load_all_watchlist_tickers()
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


def get_cik_to_ticker() -> dict[str, str]:
    """
    Return a map CIK (normalized, no leading zeros) -> ticker for watchlist companies.
    Keys match str(int(cik)) so sec_fetcher can look up by normalized CIK.
    Uses preferred + CEF ticker lists.
    """
    tickers = load_all_watchlist_tickers()
    if not tickers:
        return {}

    sec_map = load_sec_ticker_map()
    out = {}
    for t in tickers:
        cik = sec_map.get(t)
        if cik is not None:
            cik_str = str(int(str(cik).strip()))
            out[cik_str] = t
    return out
