"""Binance Spot signal scanner. Read-only market data; NEVER places orders."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from statistics import mean
from zoneinfo import ZoneInfo

API_BASES = ("https://data-api.binance.vision", "https://api.binance.com")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
ACCOUNT = float(os.getenv("ACCOUNT_USDT", "86.31"))
MAX_COINS = max(10, min(220, int(os.getenv("MAX_SYMBOLS", "150"))))
MAX_WORKERS = max(1, min(16, int(os.getenv("MAX_WORKERS", "12"))))
MIN_VOL = 2_000_000
IST = ZoneInfo("Asia/Kolkata")
STABLES = {"USDC", "USDP", "TUSD", "FDUSD", "DAI", "USDD", "USDE", "PYUSD", "RLUSD", "USD1", "BUSD", "EUR", "EURC"}
LEVER_SUFFIX = ("UP", "DOWN", "BULL", "BEAR", "3L", "3S", "5L", "5S")
UA = "Mozilla/5.0 (compatible; spot-signal-monitor/1.0)"


def get_json(endpoint: str, params: dict | None = None):
    query = "?" + urllib.parse.urlencode(params) if params else ""
    last_exc = None
    for base in API_BASES:
        for attempt in range(3):
            try:
                request = urllib.request.Request(base + endpoint + query, headers={"User-Agent": UA})
                with urllib.request.urlopen(request, timeout=14) as res:
                    return json.load(res)
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in (418, 429, 500, 502, 503, 504):
                    time.sleep(min(2 ** attempt, 4))
                    continue
                break
            except (TimeoutError, OSError, ValueError) as exc:
                last_exc = exc
                time.sleep(min(2 ** attempt, 4))
    raise RuntimeError(f"Binance {endpoint} unavailable: {last_exc}")


def send_message(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as GitHub Actions secrets.")
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    payload = json.dumps({"chat_id": CHAT_ID, "text": text[:4000], "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        response = json.load(r)
    if not response.get("ok"):
        raise RuntimeError("Telegram rejected the message")
    print("Telegram message delivered")


def ema(series: list[float], period: int) -> list[float]:
    alpha = 2 / (period + 1)
    output = [series[0]]
    for price in series[1:]:
        output.append(alpha * price + (1 - alpha) * output[-1])
    return output


def rsi(series: list[float], period: int = 6) -> list[float | None]:
    values = [None] * len(series)
    if len(series) <= period:
        return values
    moves = [series[i] - series[i - 1] for i in range(1, len(series))]
    gain = sum(max(m, 0) for m in moves[:period]) / period
    loss = sum(max(-m, 0) for m in moves[:period]) / period
    for i in range(period, len(series)):
        if i > period:
            change = moves[i - 1]
            gain = (gain * (period - 1) + max(change, 0)) / period
            loss = (loss * (period - 1) + max(-change, 0)) / period
        values[i] = (100 * gain / (gain + loss)) if (gain + loss) else 50.0
    return values


def stoch_rsi(series: list[float]):
    rs = rsi(series, 14)
    raw = [None] * len(series)
    for i in range(27, len(series)):
        lookback = rs[i - 13:i + 1]
        if any(x is None for x in lookback):
            continue
        low, high = min(lookback), max(lookback)
        raw[i] = 100 * (rs[i] - low) / (high - low) if high > low else 50.0

    def sma3(a):
        output = [None] * len(a)
        for i in range(2, len(a)):
            window = a[i - 2:i + 1]
            if all(v is not None for v in window):
                output[i] = mean(window)
        return output

    k = sma3(raw)
    return k, sma3(k)


def indicators(rows):
    # Binance returns the open/incomplete current candle as the final item.
    # Only use candles whose close time is strictly in the past.
    now_ms = int(time.time() * 1000)
    closed = [x for x in rows if int(x[6]) < now_ms - 1000]
    if len(closed) < 110:
        raise ValueError("Insufficient closed candles")
    closes = [float(x[4]) for x in closed]
    highs = [float(x[2]) for x in closed]
    lows = [float(x[3]) for x in closed]
    vols = [float(x[5]) for x in closed]
    k, d = stoch_rsi(closes)
    e12, e26 = ema(closes, 12), ema(closes, 26)
    macd = [a - b for a, b in zip(e12, e26)]
    signal = ema(macd, 9)
    return {
        "c": closes, "h": highs, "l": lows, "v": vols,
        "e7": ema(closes, 7), "e25": ema(closes, 25), "e99": ema(closes, 99),
        "r6": rsi(closes, 6), "k": k, "d": d,
        "macd": macd, "hist": [a - b for a, b in zip(macd, signal)],
        "close_ms": int(closed[-1][6]) + 1,
    }


def klines(symbol, interval):
    return indicators(get_json("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": 145}))


def universe():
    meta = get_json("/api/v3/exchangeInfo")
    ticks = get_json("/api/v3/ticker/24hr")
    allowed = set()
    for item in meta["symbols"]:
        base = item.get("baseAsset", "")
        if (item.get("status") == "TRADING" and item.get("quoteAsset") == "USDT"
                and item.get("isSpotTradingAllowed", True) and base not in STABLES
                and not base.endswith(LEVER_SUFFIX)):
            allowed.add(item["symbol"])
    ranked = []
    for tick in ticks:
        sym = tick.get("symbol", "")
        if sym in allowed:
            vol = float(tick.get("quoteVolume", 0))
            if vol >= MIN_VOL:
                ranked.append((sym, vol, float(tick["lastPrice"])))
    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked[:MAX_COINS], len(ranked)


def evaluate_intraday(symbol, volume, last_price):
    h1 = klines(symbol, "1h")
    m15 = klines(symbol, "15m")
    m5 = klines(symbol, "5m")
    trend = h1["c"][-1] > h1["e25"][-1] and h1["e25"][-1] > h1["e25"][-3]
    rsi_ok = 40 <= m15["r6"][-1] <= 65 and m15["r6"][-1] > m15["r6"][-2]
    stoch_ok = (m15["k"][-1] is not None and m15["d"][-1] is not None
                and m15["k"][-1] < 65 and m15["k"][-1] > m15["d"][-1]
                and m15["k"][-1] > m15["k"][-2])
    macd_ok = (m15["hist"][-1] > m15["hist"][-2]
               and (m15["hist"][-2] <= 0 or m15["hist"][-1] > 0))
    ema_ok = (m15["e7"][-1] > m15["e25"][-1]
              or (m15["c"][-2] <= m15["e25"][-2] and m15["c"][-1] > m15["e25"][-1]))
    vol_ok = m15["v"][-1] >= mean(m15["v"][-6:-1])
    breakout = m5["c"][-1] > max(m5["h"][-5:-1]) and m5["v"][-1] >= mean(m5["v"][-6:-1]) * 1.15
    ema_cross = m5["e7"][-2] <= m5["e25"][-2] and m5["e7"][-1] > m5["e25"][-1]
    retest = (m5["l"][-1] <= m5["e25"][-1] * 1.004
              and m5["c"][-1] > m5["e25"][-1] and m5["c"][-1] > m5["c"][-2]
              and m5["v"][-1] >= mean(m5["v"][-6:-1]))
    trigger = breakout or ema_cross or retest
    score = sum((trend, rsi_ok, stoch_ok, macd_ok, ema_ok, vol_ok, trigger))
    if trend and rsi_ok and macd_ok and ema_ok and vol_ok and trigger and score >= 6:
        status = "STRONG BUY SETUP"
    elif trend and rsi_ok and (stoch_ok or macd_ok) and score >= 4:
        status = "EARLY WATCH"
    else:
        return None
    # Early Watch is emitted only once per newly closed 15m candle.
    if status == "EARLY WATCH" and time.time() * 1000 - m15["close_ms"] > 6 * 60_000:
        return None
    entry = m5["c"][-1]
    # Do not alert on a stale quoted price or a trade that has run away.
    if abs(last_price - entry) / entry > 0.015:
        return None
    stop = min(m5["l"][-7:]) * 0.998
    plan = trade_plan(entry, stop, status == "STRONG BUY SETUP")
    if plan is None and status == "STRONG BUY SETUP":
        return None
    reasons = [name for name, ok in (
        ("1H trend", trend), ("15m RSI6", rsi_ok), ("StochRSI", stoch_ok),
        ("MACD", macd_ok), ("EMA", ema_ok), ("Volume", vol_ok), ("5m trigger", trigger)) if ok]
    return {
        "symbol": symbol, "status": status, "score": score, "volume": volume,
        "price": entry, "time": m5["close_ms"], "rsi": m15["r6"][-1],
        "stoch": m15["k"][-1], "volume_ratio": m15["v"][-1] / max(mean(m15["v"][-6:-1]), 1e-12),
        "hist": m15["hist"][-1], "reason": ", ".join(reasons), "plan": plan, "kind": "INTRADAY 1-2H",
    }


def evaluate_swing(symbol, volume, last_price):
    day = klines(symbol, "1d")
    h4 = klines(symbol, "4h")
    if (day["r6"][-1] >= 75 or day["k"][-1] is None or day["k"][-1] >= 80):
        return None
    rsi_ok = 40 <= h4["r6"][-1] <= 65 and h4["r6"][-1] > h4["r6"][-2]
    stoch_ok = (h4["k"][-1] is not None and h4["d"][-1] is not None
                and h4["k"][-1] < 60 and h4["k"][-1] > h4["d"][-1]
                and h4["k"][-1] > h4["k"][-2])
    macd_ok = h4["hist"][-1] > h4["hist"][-2] and (h4["hist"][-2] <= 0 or h4["hist"][-1] > 0)
    ema_ok = (h4["e7"][-1] > h4["e25"][-1]
              or h4["c"][-2] <= h4["e25"][-2] < h4["c"][-1])
    vol_ok = h4["v"][-1] >= mean(h4["v"][-6:-1])
    score = sum((rsi_ok, stoch_ok, macd_ok, ema_ok, vol_ok))
    if rsi_ok and macd_ok and ema_ok and vol_ok and score >= 4:
        status = "STRONG BUY SETUP"
    elif rsi_ok and (stoch_ok or macd_ok) and score >= 3:
        status = "EARLY WATCH"
    else:
        return None
    entry = h4["c"][-1]
    if abs(last_price - entry) / entry > 0.03:
        return None
    stop = min(h4["l"][-5:]) * 0.998
    plan = trade_plan(entry, stop, status == "STRONG BUY SETUP")
    if plan is None and status == "STRONG BUY SETUP":
        return None
    reasons = [name for name, ok in (
        ("4H RSI6", rsi_ok), ("StochRSI", stoch_ok), ("MACD", macd_ok),
        ("EMA", ema_ok), ("Volume", vol_ok), ("Daily above EMA99", day["c"][-1] > day["e99"][-1])) if ok]
    return {
        "symbol": symbol, "status": status, "score": score,
        "volume": volume, "price": entry, "time": h4["close_ms"],
        "rsi": h4["r6"][-1], "stoch": h4["k"][-1],
        "volume_ratio": h4["v"][-1] / max(mean(h4["v"][-6:-1]), 1e-12),
        "hist": h4["hist"][-1], "reason": ", ".join(reasons),
        "plan": plan, "kind": "SWING 4H",
    }


def trade_plan(entry, stop, active):
    if entry <= 0 or stop >= entry or stop <= 0:
        return None
    stop_pct = (entry - stop) / entry
    if stop_pct < 0.004 or stop_pct > 0.07:
        return None
    # Approximate 0.2% round-trip fees; actual fees/slippage vary.
    allocation = min(ACCOUNT * 0.50, ACCOUNT * 0.01 / (stop_pct + 0.002))
    if allocation < 5:
        return None
    risk = entry - stop
    return {
        "stop": stop, "tp1": entry + 1.5 * risk, "tp2": entry + 2.5 * risk,
        "allocation": allocation, "qty": allocation / entry,
        "maxloss": allocation * (stop_pct + 0.002), "stop_pct": stop_pct,
    }


def fmt_num(n):
    return f"{n:.8f}".rstrip("0").rstrip(".") if n < 0.1 else f"{n:.5f}".rstrip("0").rstrip(".")


def format_alert(candidate):
    when = dt.datetime.fromtimestamp(candidate["time"] / 1000, IST).strftime("%d %b %H:%M IST")
    st = candidate["stoch"]
    lines = [
        f"{candidate['kind']} | {candidate['status']}",
        f"{candidate['symbol']} | Last closed: {when}",
        f"Entry reference: {fmt_num(candidate['price'])} USDT",
        f"24h volume: {candidate['volume'] / 1_000_000:.1f}m USDT",
        f"RSI6: {candidate['rsi']:.1f} | Stoch K: {st:.1f}" if st is not None else f"RSI6: {candidate['rsi']:.1f}",
        f"Volume / MA5: {candidate['volume_ratio']:.2f}x | Score: {candidate['score']}",
        "Checks: " + candidate["reason"],
    ]
    p = candidate["plan"]
    if p and candidate["status"] == "STRONG BUY SETUP":
        lines.extend([
            f"Stop: {fmt_num(p['stop'])} ({p['stop_pct'] * 100:.2f}% below entry)",
            f"TP1: {fmt_num(p['tp1'])} (1.5R) | TP2: {fmt_num(p['tp2'])} (2.5R)",
            f"Suggested max spot size: {p['allocation']:.2f} USDT ({fmt_num(p['qty'])} coins)",
            f"Estimated max planned loss incl. 0.2% fees: {p['maxloss']:.2f} USDT",
            "Check current price, spread and minimum order size before considering an entry.",
        ])
    else:
        lines.append("EARLY WATCH only. Wait for confirmed entry; no buy recommendation.")
    lines.append("Signal, not a guarantee. No trades are placed.")
    return "\n".join(lines)


def run():
    if "--test-telegram" in sys.argv:
        send_message("Crypto scanner: Telegram connection successful. Test only, no trade signal.")
        return
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID GitHub secrets")
    coins, eligible = universe()
    if not coins:
        raise RuntimeError("No qualifying Binance Spot USDT symbols; check API/connectivity.")
    print(f"Eligible: {eligible} | scanning top {len(coins)} by USDT turnover")
    # Scan 4h only immediately after a completed 4h candle, not every 5m.
    now = dt.datetime.now(dt.timezone.utc)
    swing_due = now.hour % 4 == 0 and now.minute < 6
    all_alerts = []
    failures = 0
    jobs = [("INTRADAY", evaluate_intraday)]
    if swing_due:
        jobs.append(("SWING", evaluate_swing))
    for label, fn in jobs:
        matches = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_map = {pool.submit(fn, sym, vol, price): sym for sym, vol, price in coins}
            for future in concurrent.futures.as_completed(future_map):
                try:
                    result = future.result()
                    if result:
                        matches.append(result)
                except Exception as exc:
                    failures += 1
                    print(f"{label}: {future_map[future]}: {exc}", file=sys.stderr)
        matches.sort(key=lambda x: (x["status"] == "STRONG BUY SETUP", x["score"], x["volume"]), reverse=True)
        strong = [v for v in matches if v["status"] == "STRONG BUY SETUP"]
        early = [v for v in matches if v["status"] == "EARLY WATCH"]
        print(f"{label}: {len(strong)} strong, {len(early)} early")
        all_alerts.extend(strong[:2] if strong else early[:2])
    if failures >= len(coins):
        raise RuntimeError(f"Major market data failure: {failures} symbol errors")
    for item in all_alerts:
        send_message(format_alert(item))
    if "--manual" in sys.argv and not all_alerts:
        send_message(f"Scanner ran successfully. {len(coins)} liquid Binance Spot pairs checked; no qualifying setup. {dt.datetime.now(IST):%d %b %H:%M IST}")
    print(f"Done. Sent {len(all_alerts)} alert(s). Symbol fetch errors: {failures}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"SCANNER ERROR: {exc}", file=sys.stderr)
        raise
