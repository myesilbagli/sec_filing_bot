# How the SEC API is used (and rate limits)

## What we call

We use the **SEC’s public, unauthenticated JSON API** on `data.sec.gov` (no API key).

**Single endpoint we use:**

- **Submissions per company**  
  `GET https://data.sec.gov/submissions/CIK{cik}.json`  
  Example: `https://data.sec.gov/submissions/CIK000070458.json` (Apple)

**What it returns:** One JSON object per company with:

- Company name, tickers, SIC, etc.
- `filings.recent`: arrays of recent filings (form type, accession number, filing date, primary doc description, etc.)

**EDGAR “recent” structure:** `filings.recent` is **one row per filing**: parallel arrays (`form`, `accessionNumber`, `filingDate`, `primaryDocument`, …) aligned by index. The same issuer can have many rows (e.g. dozens of 424B2s for different note series). We treat each row as one filing and use `accession_number` as the unique key for “already seen.” When **digest mode** is on (`ALERT_DIGEST_BY_GROUP`), we group new filings by (issuer, form type, filing date) and send one Telegram message per group (e.g. “WFC — 424B2 · 2026-02-20 (5 filings): link1, link2, …”) to reduce message count and stay under Telegram rate limits.

We **do not** download full filing documents in digest mode; we use metadata and links only. Without digest, we fetch the primary document for classification and send one alert per filing.

**Required header:** SEC expects a descriptive `User-Agent` (who you are + contact). We send it from `config.SEC_USER_AGENT` (set in `.env`).

---

## How we send requests

1. **Main loop** (`main.py`) runs every `POLL_INTERVAL_MINUTES` (default 5).
2. **Each poll:** For every CIK in `WATCHLIST_CIKS`, we call `fetch_filings_for_cik(cik)`:
   - One `requests.get(url, headers=REQUIRED_HEADERS, timeout=30)` to  
     `https://data.sec.gov/submissions/CIK{cik}.json`
   - Parse JSON, filter by `FORM_TYPES` and `MAX_FILING_AGE_DAYS`, build filing dicts with link.
3. **Throttling:** After **each** company request we `time.sleep(0.2)` (see `sec_fetcher.py` → `fetch_all_watchlist_filings`). So we send at most **5 requests per second** (1 request every 0.2 s), which is under the SEC limit.

So:

- **How we send:** Plain HTTP GET with `requests`, one URL per watchlist company, with a 0.2 s delay between requests.
- **How often we poll:** Every 5 minutes (configurable). Within each poll we only send as many requests as there are CIKs, spaced by 0.2 s.

---

## SEC rate limits (official)

- **Limit:** **10 requests per second** for automated access to EDGAR (applies across your traffic; multiple IPs don’t get 10 each).
- **If you exceed:** SEC may temporarily block your IP until the rate drops.
- **Rules:** Declare a proper `User-Agent`; don’t crawl or hammer the site; only request what you need.

So we stay under 10/sec by doing at most 5 requests per second (0.2 s between each). With hundreds of CIKs you’d still be under 10/sec; you’d just take longer per poll (e.g. 100 CIKs × 0.2 s ≈ 20 seconds per cycle).

---

## Summary

| What | How |
|------|-----|
| **Endpoint** | `GET https://data.sec.gov/submissions/CIK{cik}.json` |
| **Auth** | None (public). Header: `User-Agent: <your name/email>` |
| **Our rate** | 1 request per CIK per poll, 0.2 s between requests ⇒ &lt; 10/sec |
| **Poll frequency** | Every 5 minutes (config) |
| **SEC limit** | 10 requests per second; declare User-Agent |
