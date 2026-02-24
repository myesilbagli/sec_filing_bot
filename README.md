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
   Create a `.env` file in the project root with:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `SEC_USER_AGENT` (your name or bot name + email; SEC requires this).

5. **Virtual environment and run** (recommended on macOS/Homebrew to avoid “externally managed” pip errors)
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```
   To run again later: `source .venv/bin/activate` then `python main.py`.

**No duplicate alerts:** The bot stores already-seen filing accession numbers in **`bot_state.json`** (in the project root). On each run it loads this file, skips any filing already in it, and saves the updated list after sending new alerts. So after the first run (which may send many messages for recent filings), restarts will only send alerts for filings that appeared since the last run. You’ll see a log line like `Loaded N seen accession(s) from bot_state.json` at startup.

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

### Push and enable automatic runs

1. **Create a repo on GitHub** (e.g. `BAMSec-Filing-Bot`) and push your code:
   ```bash
   git init
   git remote add origin https://github.com/YOUR_USERNAME/BAMSec-Filing-Bot.git
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git push -u origin main
   ```
   Your `.env` and `bot_state.json` are in `.gitignore`, so they will **not** be pushed (secrets stay local).

2. **Add secrets** in the repo: **Settings → Secrets and variables → Actions → New repository secret**. Create:
   - `TELEGRAM_BOT_TOKEN` — your bot token from BotFather  
   - `TELEGRAM_CHAT_ID` — your chat ID (number from getUpdates)  
   - `SEC_USER_AGENT` — e.g. `BAMSecFilingBot your@email.com` (SEC requires a descriptive User-Agent)

3. **Runs:** The workflow runs on the schedule below. To run it once now: **Actions** tab → select **SEC Filings Bot** → **Run workflow** → **Run workflow**.

*(Secrets are set in step 2 above.)* The workflow runs with `RUN_ONCE=1`, does one SEC poll, sends new filings to Telegram, then exits. State is stored in the Actions cache so you don’t get duplicate alerts across runs.

**Schedule:** 12:00–04:00 (next day) Turkish local time, weekdays. The cron expressions in the workflow are in UTC (Turkey is UTC+3). To run manually, open the **Actions** tab, select “SEC Filings Bot”, then **Run workflow**.

The bot polls the SEC every few minutes when run locally (see `POLL_INTERVAL_MINUTES` in `config.py`). On GitHub Actions it runs once per scheduled or manual trigger. Respect SEC rate limits (e.g. 10 req/s); the default interval is conservative.

**Telegram feedback (single-filing mode):** When using single-filing alerts (digest off), each message includes **Correct** / **Wrong** / **Not relevant** buttons so you can confirm or correct the event type. Feedback is collected by the [Telegram Feedback Listener](.github/workflows/telegram-feedback-listener.yml) workflow, which runs every 10 minutes and commits new feedback to `feedback_labels.jsonl` and `feedback_offset.txt` in the repo. No always-on PC or VPS is required. You can tune the schedule after testing.

## Config

- **Watchlist (tickers)**: The bot uses two lists, merged at startup:
  - **`watchlist_preferred_tickers.txt`** — preferred stocks (one ticker per line).
  - **`watchlist_cef_tickers.txt`** — closed-end funds (one ticker per line).
  Both are resolved to SEC CIKs via [company_tickers.json](https://www.sec.gov/files/company_tickers.json); filings for any of these CIKs trigger alerts. Edit either file to add or remove tickers. Tickers not found in the SEC list are skipped and logged once at startup.  
  **Reference:** `watchlist_issuers.txt` for issuer names; the live watchlist is ticker-based (preferreds + CEFs).
- **Form types**: Same file → `FORM_TYPES`. Add/remove form types (e.g. `8-K`, `424B2`, `424B3`, `N-2`).
- **Poll interval**: `POLL_INTERVAL_MINUTES` in `config.py`.

## Data source

Filings are pulled from the **SEC EDGAR** public APIs / feeds (no BamSEC API key required). If you use BamSEC in the office, you can still use this bot for alerts and open filings in BamSEC from the links.

## Disclaimer

Not legal or investment advice. For informational use only.
