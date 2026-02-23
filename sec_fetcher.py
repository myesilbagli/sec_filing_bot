"""
Fetch recent SEC filings for a list of issuers (CIKs) and form types.
Uses the official SEC data.sec.gov submissions API.
"""

import time
from datetime import datetime, timedelta
from typing import Any

import requests

import config
from sec_archives import build_primary_doc_url


SEC_BASE = "https://data.sec.gov/submissions"
# SEC requires a descriptive User-Agent (company name + contact).
REQUIRED_HEADERS = {"User-Agent": config.SEC_USER_AGENT}


def _normalize_cik(cik: str) -> str:
    """CIK as 10-digit zero-padded string for SEC URLs."""
    return str(cik).strip().zfill(10)


def _submissions_url(cik: str) -> str:
    return f"{SEC_BASE}/CIK{_normalize_cik(cik)}.json"


def fetch_filings_for_cik(cik: str) -> list[dict[str, Any]]:
    """
    Fetch recent filings for one issuer. Returns list of dicts with keys:
    accession_number, form_type, filing_date, description, link, company_name.
    """
    url = _submissions_url(cik)
    try:
        r = requests.get(url, headers=REQUIRED_HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return []  # skip this CIK on error; we'll log in main

    company_name = (data.get("name") or "").strip()
    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return []

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_doc = recent.get("primaryDocument", [])
    primary_desc = recent.get("primaryDocDescription", [])

    # Build accession without hyphens for link (SEC style). Path uses numeric CIK.
    try:
        cik_num = str(int(cik))
    except Exception:
        cik_num = cik
    def link_for(acc: str) -> str:
        no_dash = (acc or "").replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{no_dash}/{acc}-index.htm"

    try:
        cutoff = datetime.utcnow() - timedelta(days=config.MAX_FILING_AGE_DAYS)
    except Exception:
        cutoff = None

    results = []
    for i, form in enumerate(forms):
        if form not in config.FORM_TYPES:
            continue
        filing_date = dates[i] if i < len(dates) else ""
        if cutoff and filing_date:
            try:
                fd = datetime.strptime(filing_date, "%Y-%m-%d")
                if fd.replace(tzinfo=None) < cutoff:
                    continue
            except Exception:
                pass
        acc = accessions[i] if i < len(accessions) else ""
        desc = primary_desc[i] if i < len(primary_desc) else ""
        primary_doc_name = primary_doc[i] if i < len(primary_doc) else ""
        results.append({
            "accession_number": acc,
            "form_type": form,
            "filing_date": filing_date,
            "description": desc,
            "link": link_for(acc) if acc else "",
            "company_name": company_name,
            "primary_doc_url": build_primary_doc_url(cik, acc, primary_doc_name),
        })
    return results


def fetch_all_watchlist_filings() -> list[dict[str, Any]]:
    """
    Fetch recent filings for all watchlist CIKs, filtered by FORM_TYPES.
    Throttles requests to be nice to SEC (no more than 10/sec).
    """
    all_filings = []
    for cik in config.WATCHLIST_CIKS:
        filings = fetch_filings_for_cik(cik)
        try:
            cik_int_str = str(int(str(cik).strip()))
        except (ValueError, TypeError):
            cik_int_str = str(cik).strip().lstrip("0") or "0"
        ticker = config.CIK_TO_TICKER.get(cik_int_str, "")
        for f in filings:
            f["cik"] = _normalize_cik(cik)
            f["ticker"] = ticker
            all_filings.append(f)
        time.sleep(0.2)  # throttle
    return all_filings
