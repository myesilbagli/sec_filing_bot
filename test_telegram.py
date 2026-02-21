#!/usr/bin/env python3
"""
Send a test message to your Telegram chat. Run this to verify the bot is set up correctly.
Usage: python3 test_telegram.py
"""
import asyncio
import sys

# Load config (reads .env)
import config
from telegram_notifier import send_filing_alert


async def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Missing TELEGRAM_BOT_TOKEN in .env")
        print("  → Create a bot with @BotFather and paste the token in .env")
        sys.exit(1)
    if not config.TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_CHAT_ID in .env")
        print("  → Send a message to your bot, then open:")
        print("    https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates")
        print("  → Find \"chat\":{\"id\": 123456789} and put that number in .env")
        sys.exit(1)

    # Send a fake "filing" so we use the same format as real alerts
    test_filing = {
        "company_name": "Test Company (BAMSec Bot)",
        "form_type": "8-K",
        "filing_date": "2026-02-20",
        "description": "This is a test. Your Telegram bot is working.",
        "link": "https://www.sec.gov",
    }
    ok = await send_filing_alert(test_filing)
    if ok:
        print("Test message sent. Check Telegram.")
    else:
        print("Failed to send. Check token and chat_id.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
