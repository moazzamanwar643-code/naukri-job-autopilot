# 5-minute Binance Spot crypto signals to Telegram

This scanner is **read-only**. It never places trades, requests Binance API keys, or handles funds.

It runs automatically with GitHub Actions on the **public** `naukri-job-autopilot` repository, separately from the Android/Naukri code. GitHub's schedule is best-effort, so a run may be delayed or skipped.

## Setup on mobile (about 3 steps)

1. In Telegram, open **@BotFather**, send `/newbot`, complete its steps, save your bot's token privately. Open your newly created bot and send `/start`.
2. Obtain your numeric Telegram private-chat ID. One way: while logged into Telegram, message **@userinfobot** with `/start` to see your account's numeric ID. Never give that helper bot your bot token. For direct messages to your new bot, the numeric private chat ID is normally your user ID.
3. In this GitHub repository, go to **Settings → Secrets and variables → Actions → New repository secret**. Add **TELEGRAM_BOT_TOKEN** with the full token; add **TELEGRAM_CHAT_ID** with your numeric ID. Keep both in Secrets, NOT source files or screenshots.

Go to **Actions → Crypto Scanner (5m + Telegram) → Run workflow → test_telegram**. Telegram should receive a connection-test message. Then run **scan** once to see a manual summary even if no setup qualifies. The schedule runs automatically after setup.

The GitHub Actions workflow is at `.github/workflows/crypto-scanner.yml`. Scanner code is `crypto_scanner/scanner.py`.

## Scanner logic

- Universe: Binance Spot **USDT** pairs with 24h USDT quote volume above **2 million**, excluding stablecoin bases and leveraged-token suffixes. Checks up to the **150 most liquid qualifying** pairs to limit latency; change `MAX_SYMBOLS` in the workflow (up to 220).
- **Intraday 1–2 hour** signals: 1H trend, 15M RSI6 (40–65 and rising), 15M StochRSI, MACD momentum, EMA7/25, 15M volume >= MA5, and 5M breakout, EMA cross, or support retest.
- **4H swing** signals: Daily RSI6 <75 and StochRSI K <80; completed 4H RSI6, StochRSI, MACD, EMA and volume checks. Evaluates at the start of a newly closed 4H candle window.
- `STRONG BUY SETUP`: confirmed confluence and a valid risk plan. `EARLY WATCH`: candidate not yet a buy recommendation.
- Uses **completed** candles only, and declines stale prices or stops outside planned range. Any qualifying signal sends a Telegram message. No message for a normal scheduled scan when no setup qualifies.
- On Strong setups, estimates entry reference, structural stop, TP1 at 1.5R, TP2 at 2.5R and spot size using a **maximum 50% allocation** and **1% account-equity planned loss** (including an illustrative 0.2% round-trip fee). The calculations use the last configured balance, so adjust `ACCOUNT_USDT` whenever it changes. These are price-based candidate levels, not guaranteed fills. Verify spot minimum order quantity/notional, spread, fees, current price and market context yourself.

## Limits and cost

- Public repositories with standard GitHub-hosted runners receive free GitHub Actions compute under current GitHub rules. A **private** repository has monthly minute limits; a 5-minute schedule can exhaust the free allowance.
- GitHub Actions supports a minimum 5-minute cron but **not** reliably exact 5-minute execution. Busy periods can delay or drop jobs.
- In public repositories, GitHub can disable scheduled workflows after **60 days without repository activity**. Re-enable in Actions if needed.
- Alerts are **best effort** and can repeat during persistent conditions. The monitor has no continuous memory between runs.
- Binance public market endpoints can be unavailable due to location/network restrictions or rate limiting. Check Actions run logs if no messages arrive. No live brokerage/trading authorization is needed.

## Change the settings

Edit the `env:` section of `.github/workflows/crypto-scanner.yml`:

- `ACCOUNT_USDT: "86.31"` = last stated total spot account balance, not a live wallet balance.
- `MAX_SYMBOLS: "150"` = top qualifying symbols per scan.
- `MAX_WORKERS: "12"` = maximum simultaneous symbol analyses.

To stop alerts, open **Actions → Crypto Scanner → … → Disable workflow** (or remove the two Telegram secrets).

## Testing

Run locally with Python 3.12+:

```bash
python -m unittest discover -s crypto_scanner -p "test_*.py"
```

No external Python packages are required.

**Warning:** Cryptocurrency is highly volatile. Indicators do not predict pumps reliably. Early Watch is not a buy signal, stop losses may slip, and losses can exceed planned limits.
