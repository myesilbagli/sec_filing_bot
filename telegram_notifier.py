"""
Send SEC filing alerts to Telegram.
"""

import asyncio
from typing import Any

import config


def _format_filing_message(filing: dict[str, Any]) -> str:
    company = filing.get("company_name") or "Unknown"
    form = filing.get("form_type") or ""
    date = filing.get("filing_date") or ""
    desc = (filing.get("description") or "").strip()
    link = filing.get("link") or ""
    lines = [
        f"📄 <b>{form}</b> — {company}",
        f"📅 {date}",
    ]
    if desc:
        lines.append(f"📋 {desc}")
    if link:
        lines.append(link)
    return "\n".join(lines)


async def send_filing_alert(filing: dict[str, Any]) -> bool:
    """Send a single filing alert to the configured Telegram chat. Returns True on success."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        text = _format_filing_message(filing)
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
