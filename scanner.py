import os
import requests
import yfinance as yf
import pandas as pd

from datetime import datetime, time
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ----------------------------------
# TELEGRAM
# ----------------------------------

def send_telegram(message):

    if not BOT_TOKEN or not CHAT_ID:
        print("Missing Telegram credentials")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

# ----------------------------------
# NIFTY 50 STOCKS
# ----------------------------------

stocks = [
    "ADANIENT.NS","ADANIPORTS.NS","APOLLOHOSP.NS","ASIANPAINT.NS",
    "AXISBANK.NS","BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS",
    "BEL.NS","BHARTIARTL.NS","BPCL.NS","BRITANNIA.NS",
    "CIPLA.NS","COALINDIA.NS","DRREDDY.NS","EICHERMOT.NS",
    "ETERNAL.NS","GRASIM.NS","HCLTECH.NS","HDFCBANK.NS",
    "HDFCLIFE.NS","HEROMOTOCO.NS","HINDALCO.NS","HINDUNILVR.NS",
    "ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","ITC.NS",
    "JIOFIN.NS","JSWSTEEL.NS","KOTAKBANK.NS","LT.NS",
    "M&M.NS","MARUTI.NS","NESTLEIND.NS","NTPC.NS",
    "ONGC.NS","POWERGRID.NS","RELIANCE.NS","SBILIFE.NS",
    "SBIN.NS","SHRIRAMFIN.NS","SUNPHARMA.NS","TATACONSUM.NS",
    "TATAMOTORS.NS","TATASTEEL.NS","TCS.NS","TECHM.NS",
    "TITAN.NS","TRENT.NS"
]

# ----------------------------------
# SAFE SERIES
# ----------------------------------

def clean_series(x):
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0]
    return x

# ----------------------------------
# RSI
# ----------------------------------

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))

# ----------------------------------
# MARKET REGIME
# ----------------------------------

def market_trend():

    nifty = yf.download(
        "^NSEI",
        period="6mo",
        interval="1d",
        progress=False
    )

    close = clean_series(nifty["Close"]).astype(float)

    ema20 = close.ewm(span=20).mean()

    if float(close.iloc[-1]) > float(ema20.iloc[-1]):
        return "BULL"

    return "BEAR"

# ----------------------------------
# OPTION SIGNAL
# ----------------------------------

def options_signal(regime):

    nifty = yf.download(
        "^NSEI",
        period="5d",
        interval="15m",
        progress=False
    )

    close = clean_series(nifty["Close"]).astype(float)

    last_close = float(close.iloc[-1])

    r = rsi(close)

    last_rsi = float(r.iloc[-1])

    strike = round(last_close / 50) * 50

    if regime == "BULL" and last_rsi > 60:
        return f"BUY NIFTY CALL {strike}"

    if regime == "BEAR" and last_rsi < 40:
        return f"BUY NIFTY PUT {strike}"

    return "NO TRADE"

# ----------------------------------
# SCORE STOCK
# ----------------------------------

def score_stock(symbol, regime, nifty_return):

    try:

        df = yf.download(
            symbol,
            period="1mo",
            interval="1h",
            progress=False
        )

        if len(df) < 30:
            return None

        close = clean_series(df["Close"]).astype(float)
        volume = clean_series(df["Volume"]).astype(float)

        ema20 = close.ewm(span=20).mean()

        score = 0

        if float(close.iloc[-1]) > float(ema20.iloc[-1]):
            score += 30

        stock_rsi = float(rsi(close).iloc[-1])

        if 55 < stock_rsi < 70:
            score += 20

        avg_vol = float(volume.tail(20).mean())

        if float(volume.iloc[-1]) > avg_vol * 1.5:
            score += 25

        stock_return = (
            float(close.iloc[-1]) /
            float(close.iloc[-20]) - 1
        )

        if stock_return > nifty_return:
            score += 25

        return {
            "stock": symbol,
            "score": score,
            "price": round(float(close.iloc[-1]), 2),
            "rsi": round(stock_rsi, 2)
        }

    except Exception as e:
        print(symbol, e)
        return None

# ----------------------------------
# MAIN
# ----------------------------------

def main():

    india_now = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    current_time = india_now.time()

    if current_time < time(9, 15) or current_time > time(15, 30):
        print("Outside market hours")
        return

    regime = market_trend()

    nifty = yf.download(
        "^NSEI",
        period="1mo",
        interval="1d",
        progress=False
    )

    nifty_close = clean_series(
        nifty["Close"]
    ).astype(float)

    nifty_price = round(
        float(nifty_close.iloc[-1]),
        2
    )

    nifty_return = (
        float(nifty_close.iloc[-1]) /
        float(nifty_close.iloc[-20]) - 1
    )

    results = []

    for stock in stocks:

        result = score_stock(
            stock,
            regime,
            nifty_return
        )

        if result:
            results.append(result)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    top5 = results[:5]

    signal = options_signal(regime)

    if signal == "NO TRADE":
        print("No signal")
        return

    timestamp = india_now.strftime(
        "%d-%m-%Y %I:%M:%S %p IST"
    )

    msg = (
        f"📊 NIFTY QUANT SCANNER\n"
        f"🕒 {timestamp}\n\n"
    )

    msg += f"NIFTY: {nifty_price}\n"
    msg += f"Market: {regime}\n\n"

    msg += "🏆 TOP 5 STOCKS\n\n"

    for i, s in enumerate(top5, start=1):

        entry = s["price"]

        sl = round(
            entry * 0.99,
            2
        )

        target = round(
            entry + ((entry - sl) * 2),
            2
        )

        msg += (
            f"{i}. {s['stock']}\n"
            f"Score: {s['score']}\n"
            f"Price: ₹{s['price']}\n"
            f"RSI: {s['rsi']}\n\n"
            f"Entry: ₹{entry}\n"
            f"SL: ₹{sl}\n"
            f"Target: ₹{target}\n"
            f"R:R = 1:2\n\n"
        )

    msg += "🎯 OPTION SIGNAL\n"
    msg += f"{signal}"

    send_telegram(msg)

if __name__ == "__main__":
    main()
