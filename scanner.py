import os
import requests
import yfinance as yf
import pandas as pd

# ==========================================
# TELEGRAM CONFIG
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_telegram(message):

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=20
        )
    except Exception as e:
        print(f"Telegram Error: {e}")


# ==========================================
# NIFTY 50 STOCK LIST
# ==========================================

stocks = [
    "ADANIENT.NS",
    "ADANIPORTS.NS",
    "APOLLOHOSP.NS",
    "ASIANPAINT.NS",
    "AXISBANK.NS",
    "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS",
    "BAJAJFINSV.NS",
    "BEL.NS",
    "BHARTIARTL.NS",
    "BPCL.NS",
    "BRITANNIA.NS",
    "CIPLA.NS",
    "COALINDIA.NS",
    "DRREDDY.NS",
    "EICHERMOT.NS",
    "GRASIM.NS",
    "HCLTECH.NS",
    "HDFCBANK.NS",
    "HDFCLIFE.NS",
    "HEROMOTOCO.NS",
    "HINDALCO.NS",
    "HINDUNILVR.NS",
    "ICICIBANK.NS",
    "INDUSINDBK.NS",
    "INFY.NS",
    "ITC.NS",
    "JIOFIN.NS",
    "JSWSTEEL.NS",
    "KOTAKBANK.NS",
    "LT.NS",
    "M&M.NS",
    "MARUTI.NS",
    "NESTLEIND.NS",
    "NTPC.NS",
    "ONGC.NS",
    "POWERGRID.NS",
    "RELIANCE.NS",
    "SBILIFE.NS",
    "SBIN.NS",
    "SHRIRAMFIN.NS",
    "SUNPHARMA.NS",
    "TATACONSUM.NS",
    "TATAMOTORS.NS",
    "TATASTEEL.NS",
    "TCS.NS",
    "TECHM.NS",
    "TITAN.NS",
    "ULTRACEMCO.NS",
    "WIPRO.NS"
]


# ==========================================
# HELPER FUNCTION
# ==========================================

def clean_series(x):
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0]
    return x


# ==========================================
# RSI
# ==========================================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ==========================================
# MARKET TREND
# ==========================================

def market_trend():

    df = yf.download(
        "^NSEI",
        period="6mo",
        interval="1d",
        progress=False
    )

    close = clean_series(df["Close"]).astype(float)

    ema20 = close.ewm(span=20).mean()

    last_close = float(close.iloc[-1])
    last_ema = float(ema20.iloc[-1])

    return "BULL" if last_close > last_ema else "BEAR"


# ==========================================
# STOCK SCORING
# ==========================================

def score_stock(symbol, regime):

    df = yf.download(
        symbol,
        period="1mo",
        interval="1h",
        progress=False
    )

    if len(df) < 30:
        return None

    close = clean_series(df["Close"]).astype(float)

    ema20 = close.ewm(span=20).mean()
    rsi_val = rsi(close)

    last_close = float(close.iloc[-1])
    last_ema = float(ema20.iloc[-1])
    last_rsi = float(rsi_val.iloc[-1])

    score = 0

    if last_close > last_ema:
        score += 30

    if 50 < last_rsi < 70:
        score += 25

    if regime == "BULL":
        score += 20

    return {
        "stock": symbol,
        "score": score,
        "price": round(last_close, 2),
        "rsi": round(last_rsi, 2)
    }


# ==========================================
# OPTIONS SIGNAL
# ==========================================

def options_signal(regime):

    df = yf.download(
        "^NSEI",
        period="5d",
        interval="15m",
        progress=False
    )

    close = clean_series(df["Close"]).astype(float)

    rsi_val = rsi(close)

    last_rsi = float(rsi_val.iloc[-1])
    last_close = float(close.iloc[-1])

    strike = round(last_close / 50) * 50

    if regime == "BULL" and last_rsi > 60:
        return f"BUY NIFTY CALL {strike}"

    if regime == "BEAR" and last_rsi < 40:
        return f"BUY NIFTY PUT {strike}"

    return "NO TRADE"


# ==========================================
# MAIN
# ==========================================

def main():

    print("Starting NIFTY Scanner...")

    regime = market_trend()

    results = []

    for stock in stocks:

        try:

            result = score_stock(stock, regime)

            if result:
                results.append(result)

            print(f"Scanned: {stock}")

        except Exception as e:

            print(f"Error in {stock}: {e}")

    if not results:

        send_telegram("Scanner failed. No results found.")
        return

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    top3 = results[:3]

    signal = options_signal(regime)

    message = f"📊 NIFTY 50 QUANT SCANNER\n\n"

    message += f"Market Regime: {regime}\n\n"

    message += "🏆 TOP 3 STOCKS\n\n"

    for stock in top3:

        message += (
            f"📈 {stock['stock']}\n"
            f"Score: {stock['score']}\n"
            f"Price: ₹{stock['price']}\n"
            f"RSI: {stock['rsi']}\n\n"
        )

    message += f"🎯 OPTION SIGNAL\n{signal}\n\n"

    message += (
        "⚠️ Risk Rules\n"
        "Max Loss: ₹180\n"
        "Risk Per Trade: ₹60"
    )

    print(message)

    send_telegram(message)


if __name__ == "__main__":
    main()
