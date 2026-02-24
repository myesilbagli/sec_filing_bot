"""
One-shot Telegram feedback processor for GitHub Actions.
Reads getUpdates, processes callback_query (Correct / Wrong / Not relevant),
appends to feedback_labels.jsonl, updates feedback_offset.txt.
Run from repo root: python scripts/process_telegram_feedback.py
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Run from repo root so config and event_classifier are importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import requests

import config
from event_classifier import (
    ALL_EVENT_TYPES,
    NOT_RELEVANT,
    event_type_display_name,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

TELEGRAM_BASE = "https://api.telegram.org/bot"


def _load_offset(offset_path: Path) -> int:
    if not offset_path.exists():
        return 0
    try:
        return int(offset_path.read_text().strip())
    except (ValueError, OSError):
        return 0


def _save_offset(offset_path: Path, value: int) -> None:
    offset_path.write_text(str(value) + "\n")


def _seen_update_ids(feedback_path: Path) -> set[int]:
    seen: set[int] = set()
    if not feedback_path.exists():
        return seen
    for line in feedback_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            uid = obj.get("update_id")
            if uid is not None:
                seen.add(int(uid))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return seen


def _append_feedback(feedback_path: Path, row: dict) -> None:
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    with open(feedback_path, "a") as f:
        f.write(json.dumps(row) + "\n")


def _get_updates(token: str, offset: int, timeout: int = 5) -> list[dict]:
    url = f"{TELEGRAM_BASE}{token}/getUpdates"
    r = requests.get(url, params={"offset": offset, "timeout": timeout}, timeout=timeout + 5)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        return []
    return data.get("result", [])


def _answer_callback(token: str, callback_query_id: str, text: str | None = None) -> None:
    url = f"{TELEGRAM_BASE}{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
    requests.post(url, json=payload, timeout=10)


def _send_message(token: str, chat_id: str, text: str, reply_markup: dict | None = None) -> None:
    url = f"{TELEGRAM_BASE}{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload, timeout=10)


def _build_event_type_keyboard(accession: str, suggested: str) -> dict:
    """Inline keyboard for 'Which event type?' - set:ACC:SUGGESTED:EVENT per button."""
    row: list[dict] = []
    keyboard: list[list[dict]] = []
    for ev in ALL_EVENT_TYPES:
        label = event_type_display_name(ev)
        cb = f"set:{accession}:{suggested}:{ev}"
        if len(cb) > 64:
            continue
        row.append({"text": label, "callback_data": cb})
        if len(row) >= 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return {"inline_keyboard": keyboard}


def process_updates(
    token: str,
    chat_id: str,
    feedback_path: Path,
    offset_path: Path,
) -> None:
    seen = _seen_update_ids(feedback_path)
    last_offset = _load_offset(offset_path)
    updates = _get_updates(token, last_offset)
    if not updates:
        return
    max_update_id = last_offset - 1
    new_rows: list[dict] = []
    for upd in updates:
        uid = upd.get("update_id")
        if uid is not None:
            max_update_id = max(max_update_id, uid)
        cq = upd.get("callback_query")
        if not cq:
            continue
        if str(cq.get("message", {}).get("chat", {}).get("id")) != str(chat_id):
            continue
        cq_id = cq.get("id")
        data_str = (cq.get("data") or "").strip()
        if not data_str or not cq_id:
            continue
        # Idempotency: skip if we already have this update_id
        if uid is not None and uid in seen:
            _answer_callback(token, cq_id)
            continue
        parts = data_str.split(":", 3)
        prefix = parts[0] if parts else ""
        now_iso = datetime.now(timezone.utc).isoformat()
        if prefix == "ok" and len(parts) >= 3:
            acc, suggested = parts[1], parts[2]
            row = {
                "update_id": uid,
                "accession_number": acc,
                "suggested_event_type": suggested,
                "corrected_event_type": None,
                "created_at": now_iso,
            }
            new_rows.append(row)
            seen.add(uid)
            _answer_callback(token, cq_id, "Thanks, marked as correct.")
        elif prefix == "wrong" and len(parts) >= 3:
            acc, suggested = parts[1], parts[2]
            _answer_callback(token, cq_id)
            _send_message(
                token,
                chat_id,
                "Which event type?",
                reply_markup=_build_event_type_keyboard(acc, suggested),
            )
            if uid is not None:
                seen.add(uid)
        elif prefix == "set" and len(parts) >= 4:
            acc, suggested, correct = parts[1], parts[2], parts[3]
            row = {
                "update_id": uid,
                "accession_number": acc,
                "suggested_event_type": suggested,
                "corrected_event_type": correct,
                "created_at": now_iso,
            }
            new_rows.append(row)
            seen.add(uid)
            _answer_callback(token, cq_id, f"Thanks, recorded as {event_type_display_name(correct)}.")
        elif prefix == "irrelevant" and len(parts) >= 3:
            acc, suggested = parts[1], parts[2]
            row = {
                "update_id": uid,
                "accession_number": acc,
                "suggested_event_type": suggested,
                "corrected_event_type": NOT_RELEVANT,
                "created_at": now_iso,
            }
            new_rows.append(row)
            seen.add(uid)
            _answer_callback(token, cq_id, "Thanks, marked as not relevant.")
        else:
            _answer_callback(token, cq_id)
    for row in new_rows:
        _append_feedback(feedback_path, row)
    if updates:
        _save_offset(offset_path, max_update_id + 1)
        log.info("Processed %s update(s), appended %s feedback row(s).", len(updates), len(new_rows))


def main() -> int:
    token = (config.TELEGRAM_BOT_TOKEN or "").strip()
    chat_id = (config.TELEGRAM_CHAT_ID or "").strip()
    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Skipping.")
        return 0
    feedback_file = getattr(config, "FEEDBACK_FILE", "feedback_labels.jsonl")
    offset_file = getattr(config, "FEEDBACK_OFFSET_FILE", "feedback_offset.txt")
    feedback_path = _REPO_ROOT / feedback_file
    offset_path = _REPO_ROOT / offset_file
    try:
        process_updates(token, chat_id, feedback_path, offset_path)
    except Exception as e:
        log.exception("Feedback processing failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
