"""
Build EDGAR Archives URLs for primary documents and fetch document bytes.
Throttles requests and retries on 429/5xx with exponential backoff.
"""

import time

import requests


def accession_no_dashes(accession: str) -> str:
    """Remove hyphens from accession number for URL path."""
    return (accession or "").replace("-", "")


def cik_to_int_str(cik: str) -> str:
    """Remove leading zeros and return CIK as string (e.g. '70858')."""
    try:
        return str(int(str(cik).strip()))
    except (ValueError, TypeError):
        return str(cik).strip().lstrip("0") or "0"


def build_primary_doc_url(cik: str, accession: str, primary_doc: str) -> str:
    """Build SEC EDGAR Archives URL for the primary document."""
    cik_int = cik_to_int_str(cik)
    acc = accession_no_dashes(accession)
    doc = (primary_doc or "").strip()
    if not acc or not doc:
        return ""
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{doc}"


class SecHttpClient:
    """
    HTTP client for SEC with throttle and retries.
    - Throttle: min_interval_s between requests.
    - Retries: on 429 or 5xx, exponential backoff, max 3 attempts total.
    """

    def __init__(self, user_agent: str, min_interval_s: float = 0.25) -> None:
        self._headers = {"User-Agent": user_agent}
        self._min_interval_s = min_interval_s
        self._last_request_time: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._min_interval_s:
            time.sleep(self._min_interval_s - elapsed)
        self._last_request_time = time.monotonic()

    def get(self, url: str, timeout: int = 30) -> bytes:
        """
        GET url and return response body as bytes.
        Throttles, then retries up to 3 times on 429 or 5xx with exponential backoff.
        """
        max_retries = 3
        for attempt in range(max_retries):
            self._throttle()
            try:
                r = requests.get(url, headers=self._headers, timeout=timeout)
                if r.status_code == 429 or (500 <= r.status_code < 600):
                    if attempt < max_retries - 1:
                        delay = (2 ** attempt) * 1.0  # 1s, 2s, 4s
                        time.sleep(delay)
                        continue
                r.raise_for_status()
                return r.content
            except requests.RequestException:
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 1.0
                    time.sleep(delay)
                    continue
                raise
        return b""  # unreachable if we raise
