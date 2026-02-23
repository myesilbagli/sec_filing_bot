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
from telegram_notifier import send_digest_alert_sync, send_filing_alert_sync
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


def _group_by_cik_form_date(filings: list[dict]) -> list[list[dict]]:
    """Group filings by (cik, form_type, filing_date). Return list of groups, each group a list of filing dicts."""
    from collections import defaultdict
    groups_map: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for f in filings:
        key = (f.get("cik") or "", f.get("form_type") or "", f.get("filing_date") or "")
        groups_map[key].append(f)
    # Order by date desc, then cik, so most recent first.
    sorted_keys = sorted(
        groups_map.keys(),
        key=lambda k: (k[2], k[0]),
        reverse=True,
    )
    return [groups_map[k] for k in sorted_keys]


def run_once(seen: set[str]) -> set[str]:
    """Fetch filings, send alerts for new ones, return updated set of seen accession numbers."""
    log.info("Fetching filings for %s CIKs...", len(config.WATCHLIST_CIKS))
    filings = fetch_all_watchlist_filings()
    log.info("Got %s filings (after form filter).", len(filings))

    # Filter to new accessions only.
    new_filings = [f for f in filings if f.get("accession_number") and f["accession_number"] not in seen]

    digest_mode = getattr(config, "ALERT_DIGEST_BY_GROUP", True)
    max_per_run = getattr(config, "MAX_NEW_ALERTS_PER_RUN", None)

    if digest_mode and new_filings:
        # Group by (cik, form_type, filing_date); one message per group (Option A: no primary-doc fetch).
        groups = _group_by_cik_form_date(new_filings)
        if max_per_run is not None:
            groups = groups[:max_per_run]
        for group in groups:
            if send_digest_alert_sync(group):
                for f in group:
                    acc = f.get("accession_number")
                    if acc:
                        seen.add(acc)
                log.info(
                    "Digest sent: %s %s (%s filing(s))",
                    group[0].get("company_name"),
                    group[0].get("form_type"),
                    len(group),
                )
            else:
                log.warning("Failed to send digest for %s %s", group[0].get("company_name"), group[0].get("form_type"))
        return seen

    # Non-digest: fetch primary doc, classify, send one alert per filing.
    if max_per_run is not None:
        new_filings = new_filings[:max_per_run]

    # Step 1 validation (RUN_ONCE): fetch first filing's primary doc and print first 300 chars.
    if os.environ.get("RUN_ONCE") == "1" and new_filings:
        f0 = new_filings[0]
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
    for f in new_filings:
        acc = f.get("accession_number")
        if not acc:
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
