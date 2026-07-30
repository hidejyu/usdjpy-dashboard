import json, time, urllib.request
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "Mozilla/5.0"}
JST = timezone(timedelta(hours=9))

def fetch(url, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"FETCH_FAILED: {url} after {retries} attempts: {last_err}")

def load_bars(raw):
    result = raw["chart"]["result"][0]
    ts = result["timestamp"]
    q = result["indicators"]["quote"][0]
    rows = []
    for i in range(len(ts)):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if o is None or h is None or l is None or c is None:
            continue
        rows.append((ts[i], o, h, l, c))
    return rows

def sma(series, period):
    out = [None] * len(series)
    for i in range(period - 1, len(series)):
        out[i] = sum(series[i - period + 1:i + 1]) / period
    return out

def ema(series, period):
    out = [None] * len(series)
    k = 2 / (period + 1)
    for i, v in enumerate(series):
        out[i] = v if i == 0 else v * k + out[i - 1] * (1 - k)
    return out

def rsi(series, period=14):
    out = [None] * len(series)
    gains = [0.0] * len(series)
    losses = [0.0] * len(series)
    for i in range(1, len(series)):
        diff = series[i] - series[i - 1]
        gains[i] = max(diff, 0)
        losses[i] = max(-diff, 0)
    avg_gain = avg_loss = None
    for i in range(1, len(series)):
        if i < period:
            continue
        if i == period:
            avg_gain = sum(gains[1:period + 1]) / period
            avg_loss = sum(losses[1:period + 1]) / period
        else:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
    return out

def bollinger(series, period=20, mult=2):
    mid = sma(series, period)
    upper = [None] * len(series)
    lower = [None] * len(series)
    for i in range(period - 1, len(series)):
        window = series[i - period + 1:i + 1]
        mean = mid[i]
        var = sum((x - mean) ** 2 for x in window) / period
        sd = var ** 0.5
        upper[i] = mean + mult * sd
        lower[i] = mean - mult * sd
    return upper, mid, lower

def rolling_max(series, period):
    out = [None] * len(series)
    for i in range(period - 1, len(series)):
        out[i] = max(series[i - period + 1:i + 1])
    return out

def rolling_min(series, period):
    out = [None] * len(series)
    for i in range(period - 1, len(series)):
        out[i] = min(series[i - period + 1:i + 1])
    return out

def compute_indicators(rows):
    closes = [r[4] for r in rows]
    highs = [r[2] for r in rows]
    lows = [r[3] for r in rows]
    n = len(rows)
    sma5v = sma(closes, 5)
    sma20v = sma(closes, 20)
    sma50v = sma(closes, 50)
    sma200v = sma(closes, 200)
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd_line = [(ema12[i] - ema26[i]) for i in range(n)]
    signal_line = ema(macd_line, 9)
    macd_hist = [macd_line[i] - signal_line[i] for i in range(n)]
    rsi14 = rsi(closes, 14)
    bb_upper, bb_mid, bb_lower = bollinger(closes, 20, 2)
    res20 = rolling_max(highs, 20)
    sup20 = rolling_min(lows, 20)
    res60 = rolling_max(highs, 60)
    sup60 = rolling_min(lows, 60)
    return {
        "closes": closes, "sma5": sma5v, "sma20": sma20v, "sma50": sma50v, "sma200": sma200v,
        "macd_line": macd_line, "signal_line": signal_line, "macd_hist": macd_hist,
        "rsi14": rsi14, "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
        "res20": res20, "sup20": sup20, "res60": res60, "sup60": sup60,
    }

def fmt_label(ts, with_time):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M") if with_time else dt.strftime("%Y-%m-%d")

def build_timeframe(rows, window, with_time):
    ind = compute_indicators(rows)
    n = len(rows)
    lo = max(0, n - window)
    labels = [fmt_label(r[0], with_time) for r in rows[lo:]]
    opens = [r[1] for r in rows[lo:]]
    highs = [r[2] for r in rows[lo:]]
    lows = [r[3] for r in rows[lo:]]
    display = {
        "dates": labels, "opens": opens, "highs": highs, "lows": lows,
        "closes": ind["closes"][lo:],
        "sma20": ind["sma20"][lo:], "sma50": ind["sma50"][lo:], "sma200": ind["sma200"][lo:],
        "bb_upper": ind["bb_upper"][lo:], "bb_lower": ind["bb_lower"][lo:],
        "rsi14": ind["rsi14"][lo:],
        "macd_line": ind["macd_line"][lo:], "signal_line": ind["signal_line"][lo:], "macd_hist": ind["macd_hist"][lo:],
        "res20": ind["res20"][lo:], "sup20": ind["sup20"][lo:], "res60": ind["res60"][lo:], "sup60": ind["sup60"][lo:],
    }
    li = n - 1
    current = {
        "label": labels[-1], "close": ind["closes"][li],
        "sma20": ind["sma20"][li], "sma50": ind["sma50"][li], "sma200": ind["sma200"][li],
        "rsi14": ind["rsi14"][li], "macd": ind["macd_line"][li], "macd_signal": ind["signal_line"][li],
        "bb_upper": ind["bb_upper"][li], "bb_lower": ind["bb_lower"][li],
        "res20": ind["res20"][li], "sup20": ind["sup20"][li], "res60": ind["res60"][li], "sup60": ind["sup60"][li],
    }
    return {"display": display, "bar_count": n, "current": current}

def resample(rows, bucket_seconds):
    buckets = {}
    order = []
    for ts, o, h, l, c in rows:
        b = ts - (ts % bucket_seconds)
        if b not in buckets:
            buckets[b] = [o, h, l, c]
            order.append(b)
        else:
            cur = buckets[b]
            cur[1] = max(cur[1], h)
            cur[2] = min(cur[2], l)
            cur[3] = c
    order.sort()
    return [(b, buckets[b][0], buckets[b][1], buckets[b][2], buckets[b][3]) for b in order]

def forward_return(closes, i, horizon):
    if i + horizon >= len(closes):
        return None
    return (closes[i + horizon] - closes[i]) / closes[i] * 100

def backtest_one(closes, signal_list, horizons=(1, 5)):
    results = {}
    for h in horizons:
        wins = total = 0
        ret_sum = 0.0
        for idx, direction in signal_list:
            r = forward_return(closes, idx, h)
            if r is None:
                continue
            signed = r * direction
            total += 1
            ret_sum += signed
            if signed > 0:
                wins += 1
        results[h] = {
            "count": total,
            "win_rate": round(wins / total * 100, 1) if total else None,
            "avg_return_pct": round(ret_sum / total, 3) if total else None,
        }
    return results

def backtest_signals(closes, signal_list, horizons=(1, 5)):
    buy_list = [s for s in signal_list if s[1] == 1]
    sell_list = [s for s in signal_list if s[1] == -1]
    return {
        "combined": backtest_one(closes, signal_list, horizons),
        "buy": backtest_one(closes, buy_list, horizons),
        "sell": backtest_one(closes, sell_list, horizons),
        "buy_count": len(buy_list),
        "sell_count": len(sell_list),
    }

def pivot_lows(lo_series, w=5):
    out = []
    for i in range(w, len(lo_series) - w):
        window = lo_series[i - w:i + w + 1]
        if lo_series[i] == min(window) and window.count(lo_series[i]) == 1:
            out.append(i)
    return out

def pivot_highs(hi_series, w=5):
    out = []
    for i in range(w, len(hi_series) - w):
        window = hi_series[i - w:i + w + 1]
        if hi_series[i] == max(window) and window.count(hi_series[i]) == 1:
            out.append(i)
    return out

def detect_double_patterns(closes, highs, lows, n):
    piv_lo = pivot_lows(lows, 5)
    piv_hi = pivot_highs(highs, 5)
    double_signals = []
    CONFIRM_WINDOW = 30
    for a in range(len(piv_lo) - 1):
        i1 = piv_lo[a]
        for b in range(a + 1, len(piv_lo)):
            i2 = piv_lo[b]
            gap = i2 - i1
            if gap < 5:
                continue
            if gap > 80:
                break
            l1, l2 = lows[i1], lows[i2]
            if abs(l2 - l1) / l1 > 0.025:
                continue
            between_highs = [highs[k] for k in range(i1 + 1, i2)]
            if not between_highs:
                continue
            neckline = max(between_highs)
            if neckline < max(l1, l2) * 1.015:
                continue
            confirm_idx = None
            for k in range(i2 + 1, min(n, i2 + 1 + CONFIRM_WINDOW)):
                if closes[k] > neckline:
                    confirm_idx = k
                    break
            if confirm_idx is not None:
                double_signals.append((confirm_idx, 1))
            break
    for a in range(len(piv_hi) - 1):
        i1 = piv_hi[a]
        for b in range(a + 1, len(piv_hi)):
            i2 = piv_hi[b]
            gap = i2 - i1
            if gap < 5:
                continue
            if gap > 80:
                break
            h1, h2 = highs[i1], highs[i2]
            if abs(h2 - h1) / h1 > 0.025:
                continue
            between_lows = [lows[k] for k in range(i1 + 1, i2)]
            if not between_lows:
                continue
            neckline = min(between_lows)
            if neckline > min(h1, h2) * 0.985:
                continue
            confirm_idx = None
            for k in range(i2 + 1, min(n, i2 + 1 + CONFIRM_WINDOW)):
                if closes[k] < neckline:
                    confirm_idx = k
                    break
            if confirm_idx is not None:
                double_signals.append((confirm_idx, -1))
            break
    double_signals.sort(key=lambda s: s[0])
    return double_signals

# ---------------- fetch ----------------
raw_1d = fetch("https://query1.finance.yahoo.com/v8/finance/chart/JPY=X?range=10y&interval=1d")
raw_60m = fetch("https://query1.finance.yahoo.com/v8/finance/chart/JPY=X?range=730d&interval=60m")
raw_15m = fetch("https://query1.finance.yahoo.com/v8/finance/chart/JPY=X?range=60d&interval=15m")
raw_5m = fetch("https://query1.finance.yahoo.com/v8/finance/chart/JPY=X?range=60d&interval=5m")

daily_rows = load_bars(raw_1d)
h60_rows = load_bars(raw_60m)
m15_rows = load_bars(raw_15m)
m5_rows = load_bars(raw_5m)
h4_rows = resample(h60_rows, 4 * 3600)
h8_rows = resample(h60_rows, 8 * 3600)

if len(daily_rows) < 300 or len(h60_rows) < 100:
    raise SystemExit("FETCH_FAILED: insufficient bars, aborting to avoid publishing broken data")

timeframes = {
    "1d":  build_timeframe(daily_rows, 120, False),
    "8h":  build_timeframe(h8_rows, 120, True),
    "4h":  build_timeframe(h4_rows, 150, True),
    "1h":  build_timeframe(h60_rows, 150, True),
    "15m": build_timeframe(m15_rows, 200, True),
    "5m":  build_timeframe(m5_rows, 200, True),
}

# ---------------- daily analysis + backtest ----------------
dates = [fmt_label(r[0], False) for r in daily_rows]
opens = [r[1] for r in daily_rows]
highs = [r[2] for r in daily_rows]
lows = [r[3] for r in daily_rows]
closes = [r[4] for r in daily_rows]
raw_ts = [r[0] for r in daily_rows]
n = len(daily_rows)
ind = compute_indicators(daily_rows)
sma5, sma20, sma50, sma200 = ind["sma5"], ind["sma20"], ind["sma50"], ind["sma200"]
macd_line, signal_line, macd_hist = ind["macd_line"], ind["signal_line"], ind["macd_hist"]
rsi14 = ind["rsi14"]
bb_upper, bb_mid, bb_lower = ind["bb_upper"], ind["bb_mid"], ind["bb_lower"]
res20, sup20, res60, sup60 = ind["res20"], ind["sup20"], ind["res60"], ind["sup60"]

ma_signals = []
for i in range(1, n):
    if None in (sma5[i], sma20[i], sma5[i-1], sma20[i-1]):
        continue
    prev_diff = sma5[i-1] - sma20[i-1]
    cur_diff = sma5[i] - sma20[i]
    if prev_diff <= 0 and cur_diff > 0:
        ma_signals.append((i, 1))
    elif prev_diff >= 0 and cur_diff < 0:
        ma_signals.append((i, -1))

rsi_signals = []
for i in range(1, n):
    if rsi14[i] is None or rsi14[i-1] is None:
        continue
    if rsi14[i-1] >= 30 and rsi14[i] < 30:
        rsi_signals.append((i, 1))
    elif rsi14[i-1] <= 70 and rsi14[i] > 70:
        rsi_signals.append((i, -1))

macd_signals = []
for i in range(1, n):
    if None in (macd_line[i], signal_line[i], macd_line[i-1], signal_line[i-1]):
        continue
    prev_diff = macd_line[i-1] - signal_line[i-1]
    cur_diff = macd_line[i] - signal_line[i]
    if prev_diff <= 0 and cur_diff > 0:
        macd_signals.append((i, 1))
    elif prev_diff >= 0 and cur_diff < 0:
        macd_signals.append((i, -1))

bb_signals = []
for i in range(1, n):
    if bb_upper[i] is None or bb_lower[i] is None or bb_upper[i-1] is None or bb_lower[i-1] is None:
        continue
    if closes[i] <= bb_lower[i] and closes[i-1] > bb_lower[i-1]:
        bb_signals.append((i, 1))
    elif closes[i] >= bb_upper[i] and closes[i-1] < bb_upper[i-1]:
        bb_signals.append((i, -1))

double_signals = detect_double_patterns(closes, highs, lows, n)

# ---------- confluence: 2+ of {MA cross, RSI reversion, MACD cross, BB touch} agree same day ----------
by_day = {}
for name, sigs in [("ma", ma_signals), ("rsi", rsi_signals), ("macd", macd_signals), ("bb", bb_signals)]:
    for idx, d in sigs:
        by_day.setdefault(idx, {}).setdefault(d, []).append(name)
CONFLUENCE_LABELS = {"ma": "移動平均クロス", "rsi": "RSI逆張り", "macd": "MACDクロス", "bb": "ボリンジャータッチ"}
confluence_signals = []
confluence_detail = {}
for idx, dirs in by_day.items():
    for d, names in dirs.items():
        if len(names) >= 2:
            confluence_signals.append((idx, d))
            confluence_detail[(idx, d)] = names
confluence_signals.sort(key=lambda s: s[0])

latest_i = n - 1
latest_dt_utc = datetime.fromtimestamp(raw_ts[latest_i], tz=timezone.utc)
latest_dt_jst = latest_dt_utc.astimezone(JST)
current = {
    "date": dates[latest_i], "open": opens[latest_i], "high": highs[latest_i], "low": lows[latest_i], "close": closes[latest_i],
    "updated_at_jst": latest_dt_jst.strftime("%Y-%m-%d %H:%M"),
    "updated_at_utc": latest_dt_utc.strftime("%Y-%m-%d %H:%M"),
    "sma5": sma5[latest_i], "sma20": sma20[latest_i], "sma50": sma50[latest_i], "sma200": sma200[latest_i],
    "rsi14": rsi14[latest_i],
    "macd": macd_line[latest_i], "macd_signal": signal_line[latest_i], "macd_hist": macd_hist[latest_i],
    "bb_upper": bb_upper[latest_i], "bb_mid": bb_mid[latest_i], "bb_lower": bb_lower[latest_i],
    "res20": res20[latest_i], "sup20": sup20[latest_i], "res60": res60[latest_i], "sup60": sup60[latest_i],
}
prev_close = closes[latest_i - 1]
day_change = current["close"] - prev_close
day_change_pct = day_change / prev_close * 100

WINDOW = 120
lo = n - WINDOW
display = {
    "dates": dates[lo:], "opens": opens[lo:], "highs": highs[lo:], "lows": lows[lo:], "closes": closes[lo:],
    "sma20": sma20[lo:], "sma50": sma50[lo:], "sma200": sma200[lo:],
    "bb_upper": bb_upper[lo:], "bb_lower": bb_lower[lo:],
    "rsi14": rsi14[lo:],
    "macd_line": macd_line[lo:], "signal_line": signal_line[lo:], "macd_hist": macd_hist[lo:],
    "res20": res20[lo:], "sup20": sup20[lo:], "res60": res60[lo:], "sup60": sup60[lo:],
}

recent_pattern = None
for idx, direction in reversed(double_signals):
    if idx >= n - 15:
        recent_pattern = {"date": dates[idx], "type": "ダブルボトム(買い)" if direction == 1 else "ダブルトップ(売り)"}
        break

confluence_today = None
for direction in (1, -1):
    key = (latest_i, direction)
    if key in confluence_detail:
        confluence_today = {
            "direction": "買い" if direction == 1 else "売り",
            "matched": [CONFLUENCE_LABELS[nm] for nm in confluence_detail[key]],
        }
        break

output = {
    "display": display,
    "backtest": {
        "ma_cross_5_20": {"signals": len(ma_signals), **backtest_signals(closes, ma_signals)},
        "rsi_reversion_14": {"signals": len(rsi_signals), **backtest_signals(closes, rsi_signals)},
        "macd_cross": {"signals": len(macd_signals), **backtest_signals(closes, macd_signals)},
        "bollinger_touch": {"signals": len(bb_signals), **backtest_signals(closes, bb_signals)},
        "double_pattern": {"signals": len(double_signals), **backtest_signals(closes, double_signals)},
        "confluence_2plus": {"signals": len(confluence_signals), **backtest_signals(closes, confluence_signals)},
    },
    "recent_pattern": recent_pattern,
    "confluence_today": confluence_today,
    "current": current,
    "day_change": round(day_change, 3),
    "day_change_pct": round(day_change_pct, 3),
    "history_range": {"start": dates[0], "end": dates[-1], "n": n},
    "timeframes": timeframes,
}

try:
    with open("fundamentals.json", encoding="utf-8-sig") as f:
        output["fundamentals"] = json.load(f)
except FileNotFoundError:
    pass

def compute_trades(current_close):
    try:
        with open("trades.json", encoding="utf-8-sig") as f:
            raw_trades = json.load(f)
    except FileNotFoundError:
        raw_trades = []
    trades = []
    for t in raw_trades:
        direction = t.get("direction", "buy")
        entry_time = t.get("entry_time")
        entry_price = t.get("entry_price")
        exit_time = t.get("exit_time")
        exit_price = t.get("exit_price")
        qty = t.get("qty")
        lot = t.get("lot")
        if not entry_time or entry_price is None:
            continue
        sign = 1 if direction == "buy" else -1
        closed = bool(exit_time and exit_price is not None)
        mark_price = exit_price if closed else current_close
        pnl_pct = (mark_price - entry_price) / entry_price * 100 * sign
        pnl_jpy = None
        if qty:
            pnl_jpy = round((mark_price - entry_price) * qty * sign)
        trades.append({
            "direction": direction, "entry_time": entry_time, "entry_price": entry_price,
            "exit_time": exit_time, "exit_price": exit_price, "qty": qty, "lot": lot,
            "closed": closed, "pnl_pct": round(pnl_pct, 3), "pnl_jpy": pnl_jpy,
        })
    trades.sort(key=lambda t: t["entry_time"], reverse=True)
    return trades

output["trades"] = compute_trades(current["close"])
output["trades_edit_url"] = "https://github.com/hidejyu/usdjpy-dashboard/issues/new?template=new-trade.yml"

with open("template.html", encoding="utf-8") as f:
    template = f.read()

data_json = json.dumps(output, ensure_ascii=False)
final_html = template.replace("__DATA_JSON__", data_json)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(final_html)

print("OK current close:", current["close"], "date:", current["date"], "n_daily:", n)
