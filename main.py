"""
BAMSec Filing Bot — poll SEC for watchlist filings and notify via Telegram.
"""

import json
import logging
import os
import time
from pathlib import Path

import config
from event_classifier import classify_event, get_phrases_for_event
from evidence_snippets import extract_snippets
from sec_archives import SecHttpClient
from sec_fetcher import fetch_all_watchlist_filings
from telegram_notifier import send_filing_alert_sync
from text_extract import extract_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_seen_accessions() -> set[str]:
    state_path = Path(config.STATE_FILE)
    if not state_path.exists():
        return set()
    try:
        with open(state_path) as f:
            data = json.load(f)
        return set(data.get("seen_accessions", []))
    except Exception:
        return set()


def save_seen_accessions(seen: set[str]) -> None:
    state_path = Path(config.STATE_FILE)
    cap = getattr(config, "MAX_SEEN_ACCESSIONS", 5000)
    to_save = list(seen)
    if len(to_save) > cap:
        to_save = to_save[-cap:]
    try:
        with open(state_path, "w") as f:
            json.dump({"seen_accessions": to_save}, f, indent=2)
    except Exception as e:
        log.warning("Could not save state: %s", e)


def run_once(seen: set[str]) -> set[str]:
    """Fetch filings, send alerts for new ones, return updated set of seen accession numbers."""
    log.info("Fetching filings for %s CIKs...", len(config.WATCHLIST_CIKS))
    filings = fetch_all_watchlist_filings()
    log.info("Got %s filings (after form filter).", len(filings))

    # Step 1 validation (RUN_ONCE): fetch first filing's primary doc and print first 300 chars.
    if os.environ.get("RUN_ONCE") == "1" and filings:
        f0 = filings[0]
        url = f0.get("primary_doc_url")
        if url:
            try:
                client = SecHttpClient(config.SEC_USER_AGENT, min_interval_s=0.25)
                content = client.get(url)
                text = extract_text(content, url)
                preview = (text[:300] + "...") if len(text) > 300 else text
                log.info("Step 1 validation - first 300 chars: %s", preview)
            except Exception as e:
                log.warning("Step 1 validation fetch failed: %s", e)

    sec_client = SecHttpClient(config.SEC_USER_AGENT, min_interval_s=0.25)
    for f in filings:
        acc = f.get("accession_number")
        if not acc or acc in seen:
            continue
        seen.add(acc)
        url = f.get("primary_doc_url")
        if url:
            try:
                content = sec_client.get(url)
                text = extract_text(content, url)
                event_type, confidence = classify_event(text)
                phrases = get_phrases_for_event(event_type)
                evidence = extract_snippets(text, phrases, window_chars=250, max_snippets=3, max_snippet_len=200)
                f["event_type"] = event_type
                f["confidence"] = confidence
                f["evidence_snippets"] = evidence
            except Exception as e:
                log.warning("Fetch/classify failed for %s: %s", acc, e)
                f["event_type"] = "GENERIC_NEWS"
                f["confidence"] = 0.2
                f["evidence_snippets"] = []
        else:
            f["event_type"] = "GENERIC_NEWS"
            f["confidence"] = 0.2
            f["evidence_snippets"] = []
        if send_filing_alert_sync(f):
            log.info("Alert sent: %s %s", f.get("company_name"), f.get("form_type"))
        else:
            log.warning("Failed to send Telegram alert for %s", acc)
    return seen


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Alerts will not be sent.")
    if not config.SEC_USER_AGENT or "your@email" in config.SEC_USER_AGENT:
        log.warning("Set SEC_USER_AGENT in .env (SEC requires a descriptive User-Agent).")

    seen = load_seen_accessions()
    log.info("Loaded %s seen accession(s) from %s (duplicates will be skipped).", len(seen), config.STATE_FILE)

    # Run once and exit (e.g. for GitHub Actions). No loop, no sleep.
    if os.environ.get("RUN_ONCE") == "1":
        seen = run_once(seen)
        save_seen_accessions(seen)
        return

    interval_sec = config.POLL_INTERVAL_MINUTES * 60
    log.info("Started. Polling every %s minutes. Ctrl+C to stop.", config.POLL_INTERVAL_MINUTES)
    while True:
        try:
            seen = run_once(seen)
            save_seen_accessions(seen)
        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break
        except Exception as e:
            log.exception("Poll error: %s", e)
        time.sleep(interval_sec)


if __name__ == "__main__":
    main()
