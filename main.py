"""
BAMSec Filing Bot — poll SEC for watchlist filings and notify via Telegram.
"""

import json
import logging
import os
import time
from pathlib import Path

import config
from sec_fetcher import fetch_all_watchlist_filings
from telegram_notifier import send_filing_alert_sync

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
    try:
        with open(state_path, "w") as f:
            json.dump({"seen_accessions": list(seen)}, f, indent=2)
    except Exception as e:
        log.warning("Could not save state: %s", e)


def run_once(seen: set[str]) -> set[str]:
    """Fetch filings, send alerts for new ones, return updated set of seen accession numbers."""
    log.info("Fetching filings for %s CIKs...", len(config.WATCHLIST_CIKS))
    filings = fetch_all_watchlist_filings()
    log.info("Got %s filings (after form filter).", len(filings))

    for f in filings:
        acc = f.get("accession_number")
        if not acc or acc in seen:
            continue
        seen.add(acc)
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
