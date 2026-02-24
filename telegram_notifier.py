"""
Send SEC filing alerts to Telegram.
"""

import asyncio
import logging
import time
from typing import Any

import config
from event_classifier import event_type_display_name, GENERIC_NEWS

log = logging.getLogger(__name__)

# Telegram message length limit (characters).
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def build_feedback_keyboard(filing: dict[str, Any]) -> "InlineKeyboardMarkup":
    """Build inline keyboard with Correct / Wrong / Not relevant for a single-filing alert."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    accession = (filing.get("accession_number") or "").strip()
    suggested = (filing.get("event_type") or GENERIC_NEWS).strip()
    if not accession or not suggested:
        return InlineKeyboardMarkup([])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Correct", callback_data=f"ok:{accession}:{suggested}"),
            InlineKeyboardButton("Wrong", callback_data=f"wrong:{accession}:{suggested}"),
            InlineKeyboardButton("Not relevant", callback_data=f"irrelevant:{accession}:{suggested}"),
        ],
    ])


def _confidence_label(confidence: float) -> str:
    if confidence > 0.6:
        return "high"
    if confidence > 0.35:
        return "medium"
    return "low"


def format_filing_alert(filing: dict[str, Any]) -> str:
    """
    Strict template: header (ticker + event type), filing facts, 2-4 evidence bullets, links, confidence.
    Fallback: if event_type missing or GENERIC_NEWS, use 'Filing' and omit/shorten evidence.
    """
    ticker = (filing.get("ticker") or "").strip().upper() or "—"
    event_type = filing.get("event_type") or GENERIC_NEWS
    display = event_type_display_name(event_type)
    form = filing.get("form_type") or ""
    date = filing.get("filing_date") or ""
    evidence = filing.get("evidence_snippets") or []
    link = filing.get("link") or ""
    primary_url = filing.get("primary_doc_url") or ""
    confidence = float(filing.get("confidence", 0.2))

    lines = [
        f"<b>{ticker} — {display}</b>",
        f"{form} · {date}",
    ]
    if evidence:
        for snip in evidence[:4]:
            escaped = snip.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"• {escaped}")
    if link:
        lines.append(link)
    if primary_url and primary_url != link:
        lines.append(primary_url)
    lines.append(f"Confidence: {_confidence_label(confidence)}")
    return "\n".join(lines)


def format_digest_alert(filings: list[dict[str, Any]]) -> str:
    """
    One message per (cik, form_type, filing_date) group: title line plus bullet list.
    Each bullet shows SEC description when present, then link.
    filings: list of filing dicts with same company_name, form_type, filing_date; each has link, description, accession_number.
    """
    if not filings:
        return ""
    first = filings[0]
    company = (first.get("company_name") or "").strip() or "—"
    form = first.get("form_type") or ""
    date = first.get("filing_date") or ""
    n = len(filings)
    title = f"<b>{company} — {form} · {date}</b> ({n} filing{'s' if n != 1 else ''})"
    lines = [title]
    for f in filings:
        link = f.get("link") or ""
        desc = (f.get("description") or "").strip()
        if desc:
            escaped = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            line = f"• {escaped}"
            if link:
                line += f" — {link}"
            lines.append(line)
        elif link:
            lines.append(f"• {link}")
    return "\n".join(lines)


# Backoff seconds when Telegram returns 429 (up to 3 retries).
_TELEGRAM_429_BACKOFF = [30, 60, 90]


def _is_429(e: BaseException) -> bool:
    s = str(e).lower()
    return "429" in s or "too many requests" in s or "retry after" in s


async def _send_message(text: str, reply_markup: Any = None) -> bool:
    """Send one message to the configured chat. Retries on 429 with backoff. Returns True on success."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    from telegram import Bot
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    last_exc = None
    kwargs = dict(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    for attempt in range(1 + len(_TELEGRAM_429_BACKOFF)):
        try:
            await bot.send_message(**kwargs)
            return True
        except Exception as e:
            last_exc = e
            if attempt < len(_TELEGRAM_429_BACKOFF) and _is_429(e):
                wait = _TELEGRAM_429_BACKOFF[attempt]
                log.warning("Telegram 429, retrying in %s s (attempt %s)", wait, attempt + 1)
                await asyncio.sleep(wait)
            else:
                raise
    if last_exc:
        raise last_exc
    return False


async def send_filing_alert(filing: dict[str, Any]) -> bool:
    """Send a single filing alert with Correct / Wrong / Not relevant buttons. Returns True on success."""
    text = format_filing_alert(filing)
    keyboard = build_feedback_keyboard(filing)
    return await _send_message(text, reply_markup=keyboard)


async def send_digest_alert(filings: list[dict[str, Any]]) -> bool:
    """Send one or more digest messages for a group of filings. Splits if over Telegram's 4096-char limit."""
    if not filings:
        return True
    text = format_digest_alert(filings)
    if len(text) <= TELEGRAM_MAX_MESSAGE_LENGTH:
        return await _send_message(text)
    # Split into chunks: build lines and send in batches under the limit.
    first = filings[0]
    company = (first.get("company_name") or "").strip() or "—"
    form = first.get("form_type") or ""
    date = first.get("filing_date") or ""
    n = len(filings)
    title = f"<b>{company} — {form} · {date}</b> ({n} filing{'s' if n != 1 else ''})"
    lines = [title]
    for f in filings:
        link = f.get("link") or ""
        desc = (f.get("description") or "").strip()
        if desc:
            escaped = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            line = f"• {escaped}"
            if link:
                line += f" — {link}"
            lines.append(line)
        elif link:
            lines.append(f"• {link}")
    max_line = TELEGRAM_MAX_MESSAGE_LENGTH - 20  # leave room for "(continued)" etc.
    chunk: list[str] = []
    for line in lines:
        if len(line) > max_line:
            line = line[: max_line - 1] + "…"
        trial = chunk + [line]
        trial_text = "\n".join(trial)
        if chunk and len(trial_text) > TELEGRAM_MAX_MESSAGE_LENGTH:
            if await _send_message("\n".join(chunk)) is False:
                return False
            chunk = ["<i>(continued)</i>", line]
        else:
            chunk = trial
    if chunk:
        return await _send_message("\n".join(chunk))
    return True


def _apply_delay() -> None:
    delay = getattr(config, "TELEGRAM_SEND_DELAY_SEC", 0) or 0
    if delay > 0:
        time.sleep(delay)


def send_filing_alert_sync(filing: dict[str, Any]) -> bool:
    """Synchronous wrapper for send_filing_alert. Applies configured delay before send."""
    _apply_delay()
    return asyncio.run(send_filing_alert(filing))


def send_digest_alert_sync(filings: list[dict[str, Any]]) -> bool:
    """Synchronous wrapper for send_digest_alert. Applies configured delay before send."""
    _apply_delay()
    return asyncio.run(send_digest_alert(filings))
