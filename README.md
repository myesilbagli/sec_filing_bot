# BAMSec Filing Bot

Bot that watches **SEC filings** for US fixed income–relevant issuers (preferreds, closed-end funds) and pushes alerts to **Telegram**. Covers new filings, call/redemption news, and offerings (e.g. 8-K, 424B, N-2).

## What it does

- **Watchlist**: You define a list of issuers by SEC **CIK** (Central Index Key). Only filings from these issuers trigger alerts.
- **Form types**: 8-K (material events / calls), 424B* (prospectus supplements / offerings), N-2 (CEF), DEF 14A (proxy), etc.
- **Telegram**: Sends a short message per new filing with company name, form type, description, and link.

## Setup

1. **Clone / open this repo**

2. **Create a Telegram bot**
   - Message [@BotFather](https://t.me/BotFather) → `/newbot` → name it (e.g. "BAMSec Filings").
   - Copy the **bot token**.

3. **Get your Telegram chat ID**
   - Start a chat with your new bot (e.g. send "hi").
   - Open: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - In the JSON, find `"chat":{"id": 123456789}` — that number is your `TELEGRAM_CHAT_ID`.

4. **Env file**
   ```bash
   cp .env.example .env
   ```
   Edit `.env`: set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `SEC_USER_AGENT` (your firm name + email; SEC requires this).

5. **Install and run**
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

## Testing the Telegram bot

Before running the full bot, verify that Telegram is set up correctly.

**What you need:**

| Item | Where to get it |
|------|------------------|
| **Bot token** | [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token (e.g. `7123456789:AAH...`) |
| **Chat ID** | Send any message to your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser. In the JSON, find `"chat":{"id": 123456789}` — that number is your chat ID. |

**Steps:**

1. Create `.env` from the example and fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (and `SEC_USER_AGENT`).
2. Run the test script:
   ```bash
   python3 test_telegram.py
   ```
3. If it works, you’ll see “Test message sent. Check Telegram.” and a sample alert in the chat. If not, the script will print what’s missing (token or chat_id).

**Group chats:** To get alerts in a group, add the bot to the group, send a message in the group, then call `getUpdates` again — the `chat.id` for the group will be a negative number (e.g. `-1001234567890`). Use that as `TELEGRAM_CHAT_ID`.

## Running on GitHub Actions

You can run the bot on a schedule without a 24/7 server. The workflow is in [`.github/workflows/sec-filings.yml`](.github/workflows/sec-filings.yml).

**Secrets** (repo **Settings → Secrets and variables → Actions**): add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `SEC_USER_AGENT`. The workflow runs with `RUN_ONCE=1`, does one SEC poll, sends new filings to Telegram, then exits. State (already-seen accession numbers) is persisted via the Actions cache so you don’t get duplicate alerts across runs.

**Schedule:** 12:00–04:00 (next day) Turkish local time, weekdays. The cron expressions in the workflow are in UTC (Turkey is UTC+3). To run manually, open the **Actions** tab, select “SEC Filings Bot”, then **Run workflow**.

The bot polls the SEC every few minutes when run locally (see `POLL_INTERVAL_MINUTES` in `config.py`). On GitHub Actions it runs once per scheduled or manual trigger. Respect SEC rate limits (e.g. 10 req/s); the default interval is conservative.

## Config

- **Watchlist (tickers)**: The bot uses **`watchlist_tickers.txt`** as the source of truth — one ticker per line (e.g. `BAC`, `JPM`, `WFC`). At startup it resolves those tickers to SEC CIKs via the SEC’s [company_tickers.json](https://www.sec.gov/files/company_tickers.json), then polls filings for those CIKs. Edit `watchlist_tickers.txt` to add or remove tickers; no need to look up CIKs yourself.  
  Tickers that don’t appear in the SEC ticker list (e.g. some preferred or series symbols) are skipped and logged once at startup.  
  **Reference list of issuer names:** `watchlist_issuers.txt` (383 unique names) is still available for cross-reference; the live watchlist is ticker-based.
- **Form types**: Same file → `FORM_TYPES`. Add/remove form types (e.g. `8-K`, `424B2`, `424B3`, `N-2`).
- **Poll interval**: `POLL_INTERVAL_MINUTES` in `config.py`.

## Data source

Filings are pulled from the **SEC EDGAR** public APIs / feeds (no BamSEC API key required). If you use BamSEC in the office, you can still use this bot for alerts and open filings in BamSEC from the links.

## Disclaimer

Not legal or investment advice. For informational use only.
