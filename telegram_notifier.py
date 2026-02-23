"""
Send SEC filing alerts to Telegram.
"""

import asyncio
from typing import Any

import config
from event_classifier import event_type_display_name, GENERIC_NEWS


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


async def send_filing_alert(filing: dict[str, Any]) -> bool:
    """Send a single filing alert to the configured Telegram chat. Returns True on success."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        text = format_filing_alert(filing)
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except Exception:
        return False


def send_filing_alert_sync(filing: dict[str, Any]) -> bool:
    """Synchronous wrapper for send_filing_alert."""
    return asyncio.run(send_filing_alert(filing))
