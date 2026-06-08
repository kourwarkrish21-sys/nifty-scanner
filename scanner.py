import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CAPITAL = 100000
RISK_PERCENT = 1.0

stocks = [
    "ADANIENT.NS","ADANIPORTS.NS","APOLLOHOSP.NS","ASIANPAINT.NS",
    "AXISBANK.NS","BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS",
    "BEL.NS","BHARTIARTL.NS","BPCL.NS","BRITANNIA.NS","CIPLA.NS",
    "COALINDIA.NS","DRREDDY.NS","EICHERMOT.NS","ETERNAL.NS","GRASIM.NS",
    "HCLTECH.NS","HDFCBANK.NS","HDFCLIFE.NS","HEROMOTOCO.NS","HINDALCO.NS",
    "HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","ITC.NS",
    "JIOFIN.NS","JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","M&M.NS","MARUTI.NS",
    "NESTLEIND.NS","NTPC.NS","ONGC.NS","POWERGRID.NS","RELIANCE.NS",
    "SBILIFE.NS","SBIN.NS","SHRIRAMFIN.NS","SUNPHARMA.NS","TATACONSUM.NS",
    "TATAMOTORS.NS","TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS","TRENT.NS"
]

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing Telegram credentials")
        return
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": message},
        timeout=20
    )

def clean_series(x):
    return x.iloc[:, 0] if isinstance(x, pd.DataFrame) else x

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    rs = gain.rolling(period).mean() / loss.rolling(period).mean()
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    high = clean_series(df["High"]).astype(float)
    low = clean_series(df["Low"]).astype(float)
    close = clean_series(df["Close"]).astype(float)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def macd(close):
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    m = ema12 - ema26
    sig = m.ewm(span=9).mean()
    return m, sig

def market_trend():
    n = yf.download("^NSEI", period="6mo", interval="1d", progress=False)
    c = clean_series(n["Close"]).astype(float)
    return "BULL" if c.iloc[-1] > c.ewm(span=20).mean().iloc[-1] else "BEAR"

def options_signal(regime):
    n = yf.download("^NSEI", period="5d", interval="15m", progress=False)
    c = clean_series(n["Close"]).astype(float)
    strike = round(float(c.iloc[-1]) / 50) * 50
    rv = float(rsi(c).iloc[-1])
    if regime == "BULL" and rv > 60:
        return f"BUY NIFTY CALL {strike}"
    if regime == "BEAR" and rv < 40:
        return f"BUY NIFTY PUT {strike}"
    return "NO TRADE"

def bullish_engulfing(df):
    o = clean_series(df["Open"]).astype(float)
    c = clean_series(df["Close"]).astype(float)
    if len(c) < 2:
        return False
    return c.iloc[-2] < o.iloc[-2] and c.iloc[-1] > o.iloc[-1] and c.iloc[-1] > o.iloc[-2] and o.iloc[-1] < c.iloc[-2]

def hammer(df):
    o = float(clean_series(df["Open"]).iloc[-1])
    c = float(clean_series(df["Close"]).iloc[-1])
    h = float(clean_series(df["High"]).iloc[-1])
    l = float(clean_series(df["Low"]).iloc[-1])
    body = abs(c-o)
    lower = min(c,o)-l
    upper = h-max(c,o)
    return lower > body*2 and upper < body

def score_stock(symbol, nifty_return):
    try:
        df = yf.download(symbol, period="1mo", interval="1h", progress=False)
        if len(df) < 60:
            return None

        close = clean_series(df["Close"]).astype(float)
        vol = clean_series(df["Volume"]).astype(float)

        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()

        score = 0

        if close.iloc[-1] > ema20.iloc[-1]: score += 20
        if ema20.iloc[-1] > ema50.iloc[-1]: score += 15

        r = float(rsi(close).iloc[-1])
        if 55 < r < 70: score += 20

        avg_vol = float(vol.tail(20).mean())
        rvol = float(vol.iloc[-1] / avg_vol) if avg_vol else 0
        if rvol > 1.5: score += 15

        stock_return = float(close.iloc[-1] / close.iloc[-20] - 1)
        if stock_return > nifty_return: score += 25

        typical = (clean_series(df["High"]) + clean_series(df["Low"]) + clean_series(df["Close"])) / 3
        vwap = ((typical * vol).cumsum() / vol.cumsum()).iloc[-1]
        above_vwap = close.iloc[-1] > vwap
        if above_vwap: score += 15

        m, sig = macd(close)
        macd_bull = m.iloc[-1] > sig.iloc[-1]
        if macd_bull: score += 20

        breakout = close.iloc[-1] > clean_series(df["High"]).tail(21).iloc[:-1].max()
        if breakout: score += 25

        pattern = "None"
        if bullish_engulfing(df):
            pattern = "Bullish Engulfing"
            score += 15
        elif hammer(df):
            pattern = "Hammer"
            score += 10

        a = float(atr(df).iloc[-1])

        return {
            "stock": symbol,
            "score": score,
            "price": round(float(close.iloc[-1]),2),
            "rsi": round(r,2),
            "atr": round(a,2),
            "rvol": round(rvol,2),
            "vwap": above_vwap,
            "macd": macd_bull,
            "breakout": breakout,
            "pattern": pattern
        }
    except Exception as e:
        print(symbol, e)
        return None

def main():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    regime = market_trend()

    nifty = yf.download("^NSEI", period="1mo", interval="1d", progress=False)
    nc = clean_series(nifty["Close"]).astype(float)
    nifty_price = round(float(nc.iloc[-1]),2)
    nifty_return = float(nc.iloc[-1] / nc.iloc[-20] - 1)

    results = [r for s in stocks if (r := score_stock(s, nifty_return))]
    results.sort(key=lambda x: x["score"], reverse=True)
    top5 = results[:5]

    msg = f"📊 NIFTY QUANT SCANNER\n🕒 {now.strftime('%d-%m-%Y %I:%M:%S %p IST')}\n\n"
    msg += f"NIFTY: {nifty_price}\nMarket: {regime}\n\n🏆 TOP 5 STOCKS\n\n"

    for i, s in enumerate(top5, 1):
        risk_amt = CAPITAL * (RISK_PERCENT / 100)
        sl = round(s["price"] - s["atr"], 2)
        target = round(s["price"] + (2 * s["atr"]), 2)
        qty = max(1, int(risk_amt / max(s["price"] - sl, 0.01)))

        msg += (
            f"{i}. {s['stock']}\n"
            f"Score: {s['score']}\n"
            f"Price: ₹{s['price']}\n"
            f"RSI: {s['rsi']}\n"
            f"RVOL: {s['rvol']}x\n"
            f"VWAP: {'Above ✅' if s['vwap'] else 'Below ❌'}\n"
            f"MACD: {'Bullish ✅' if s['macd'] else 'Bearish ❌'}\n"
            f"Breakout: {'YES 🔥' if s['breakout'] else 'NO'}\n"
            f"Pattern: {s['pattern']}\n\n"
            f"Entry: ₹{s['price']}\nSL: ₹{sl}\nTarget: ₹{target}\n"
            f"Quantity: {qty}\n\n-----------------\n\n"
        )

    msg += "🎯 OPTION SIGNAL\n" + options_signal(regime)
    send_telegram(msg)

if __name__ == "__main__":
    main()
