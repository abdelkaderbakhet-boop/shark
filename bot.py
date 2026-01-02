import os
import time
import pandas as pd
import requests
import numpy as np
from tvDatafeed import TvDatafeed, Interval
from sklearn.ensemble import RandomForestClassifier

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "PUT_YOUR_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "PUT_YOUR_CHAT_ID_HERE")

SYMBOL = "XAUUSD"
EXCHANGE = "FOREXCOM"
TIMEFRAME = Interval.in_15_minute
VOTE_THRESHOLD = 6

# ==================== مؤشرات يدوية (بدون pandas-ta) ====================

def EMA(series, period):
    return series.ewm(span=period, adjust=False).mean()

def RSI(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def ATR(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ==================== Telegram ====================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

# ==================== Data ====================

def get_data():
    tv = TvDatafeed()
    for _ in range(3):
        try:
            df = tv.get_hist(
                symbol=SYMBOL,
                exchange=EXCHANGE,
                interval=TIMEFRAME,
                n_bars=500
            )
            if df is not None and not df.empty:
                return df
        except:
            time.sleep(1)
    return None

# ==================== Logic ====================

def analyze_and_signal():
    print("🦈 Shark Bot Running...")

    df = get_data()
    if df is None:
        print("❌ No data")
        return

    df['ATR'] = ATR(df)
    df['RSI'] = RSI(df['close'])
    df['EMA200'] = EMA(df['close'], 200)

    df.dropna(inplace=True)

    close = df['close'].iloc[-1]
    atr = df['ATR'].iloc[-1]

    sl_dist = max(atr * 1.5, 4.0)
    tp_dist = sl_dist * 2

    votes = {"BUY": 0, "SELL": 0}
    reasons = []

    # RSI
    rsi = df['RSI'].iloc[-1]
    if rsi < 30:
        votes["BUY"] += 1
        reasons.append("RSI Oversold")
    elif rsi > 70:
        votes["SELL"] += 1
        reasons.append("RSI Overbought")

    # Trend
    if close > df['EMA200'].iloc[-1]:
        votes["BUY"] += 1
        reasons.append("Above EMA200")
    else:
        votes["SELL"] += 1
        reasons.append("Below EMA200")

    # Simple SMC
    try:
        if df['high'].iloc[-3] < df['low'].iloc[-1]:
            votes["BUY"] += 2
            reasons.append("Bullish Imbalance")
        elif df['low'].iloc[-3] > df['high'].iloc[-1]:
            votes["SELL"] += 2
            reasons.append("Bearish Imbalance")
    except:
        pass

    # AI
    try:
        data = df.copy()
        data['Target'] = (data['close'].shift(-1) > data['close']).astype(int)
        data.dropna(inplace=True)

        X = data[['RSI', 'EMA200']]
        y = data['Target']

        model = RandomForestClassifier(n_estimators=50, max_depth=3)
        model.fit(X[:-1], y[:-1])
        pred = model.predict(X.iloc[[-1]])[0]

        if pred == 1:
            votes["BUY"] += 2
            reasons.append("AI Bullish")
        else:
            votes["SELL"] += 2
            reasons.append("AI Bearish")
    except:
        pass

    print(f"Votes -> BUY: {votes['BUY']} | SELL: {votes['SELL']}")

    signal = None
    if votes["BUY"] >= VOTE_THRESHOLD:
        signal = "BUY"
    elif votes["SELL"] >= VOTE_THRESHOLD:
        signal = "SELL"

    if not signal:
        print("No signal")
        return

    if signal == "BUY":
        sl = close - sl_dist
        tp = close + tp_dist
        emoji = "🟢"
    else:
        sl = close + sl_dist
        tp = close - tp_dist
        emoji = "🔴"

    msg = f"""
🦈 <b>Shark Bot Alert</b>
{emoji} <b>{signal} XAUUSD</b>

📥 Price: {close:.2f}
🎯 TP: {tp:.2f}
🛑 SL: {sl:.2f}

📊 Reasons:
{", ".join(reasons)}
"""

    send_telegram(msg)
    print("✅ Signal sent")

# ==================== Run ====================

if __name__ == "__main__":
    analyze_and_signal()
