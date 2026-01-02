import os
import time
import pandas as pd
import requests
import numpy as np
from tvDatafeed import TvDatafeed, Interval
from sklearn.ensemble import RandomForestClassifier

# ==================== الإعدادات ====================
# نصيحة: ضع التوكن هنا مباشرة بين العلامات "" إذا كنت لا تعرف استخدام Secrets
TELEGRAM_TOKEN = "8466875451:AAHXwDTX5Tww-oylqzOwVSTE_XoypRfRsrI"
CHAT_ID = "-1003552439018"

SYMBOL = "XAUUSD"
EXCHANGE = "FOREXCOM"
TIMEFRAME = Interval.in_15_minute
VOTE_THRESHOLD = 4  # تم تقليلها من 6 إلى 4 لزيادة الفرص المحققة

# ==================== مؤشرات يدوية ====================

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
        r = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
        return r.json()
    except Exception as e:
        print("Telegram Error:", e)

# ==================== Data ====================

def get_data():
    tv = TvDatafeed()
    for _ in range(3):
        try:
            df = tv.get_hist(symbol=SYMBOL, exchange=EXCHANGE, interval=TIMEFRAME, n_bars=500)
            if df is not None and not df.empty:
                return df
        except:
            time.sleep(1)
    return None

# ==================== Logic ====================

def analyze_and_signal():
    print("🦈 Shark Bot Running Analysis...")

    df = get_data()
    if df is None:
        print("❌ No data received from TradingView")
        return

    # حساب المؤشرات
    df['ATR'] = ATR(df)
    df['RSI'] = RSI(df['close'])
    df['EMA200'] = EMA(df['close'], 200)
    
    # استراتيجية SK System (Golden Zone 50-61.8)
    df['high_50'] = df['high'].rolling(50).max()
    df['low_50'] = df['low'].rolling(50).min()

    df.dropna(inplace=True)

    close = df['close'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    rsi_val = df['RSI'].iloc[-1]
    ema200_val = df['EMA200'].iloc[-1]

    # حساب الأهداف (الحد الأدنى 40 بيب = 4 دولار في الذهب)
    sl_dist = max(atr * 1.5, 4.0)
    tp_dist = max(sl_dist * 2.0, 4.0)

    votes = {"BUY": 0, "SELL": 0}
    reasons = []

    # 1. RSI (1 point)
    if rsi_val < 30:
        votes["BUY"] += 1; reasons.append("RSI Oversold")
    elif rsi_val > 70:
        votes["SELL"] += 1; reasons.append("RSI Overbought")

    # 2. Trend (1 point)
    if close > ema200_val:
        votes["BUY"] += 1; reasons.append("Trend Bullish")
    else:
        votes["SELL"] += 1; reasons.append("Trend Bearish")

    # 3. Simple SMC (2 points)
    if df['high'].iloc[-3] < df['low'].iloc[-1]:
        votes["BUY"] += 2; reasons.append("SMC Bullish Imbalance")
    elif df['low'].iloc[-3] > df['high'].iloc[-1]:
        votes["SELL"] += 2; reasons.append("SMC Bearish Imbalance")

    # 4. SK System - Golden Zone (2 points)
    hi = df['high_50'].iloc[-1]
    lo = df['low_50'].iloc[-1]
    fib_50 = lo + (hi - lo) * 0.50
    fib_61 = lo + (hi - lo) * 0.618
    
    if fib_61 <= close <= fib_50:
        if close > ema200_val:
            votes["BUY"] += 2; reasons.append("SK Golden Zone (Buy)")
        else:
            votes["SELL"] += 2; reasons.append("SK Golden Zone (Sell)")

    # 5. AI Prediction (2 points)
    try:
        data = df.copy()
        data['Target'] = (data['close'].shift(-1) > data['close']).astype(int)
        X = data[['RSI', 'EMA200']].iloc[:-1]
        y = data['Target'].iloc[:-1]
        model = RandomForestClassifier(n_estimators=50, max_depth=3)
        model.fit(X, y)
        pred = model.predict(df[['RSI', 'EMA200']].iloc[[-1]])[0]
        if pred == 1:
            votes["BUY"] += 2; reasons.append("AI Prediction Bullish")
        else:
            votes["SELL"] += 2; reasons.append("AI Prediction Bearish")
    except: pass

    print(f"📊 Votes -> BUY: {votes['BUY']} | SELL: {votes['SELL']}")

    signal = None
    if votes["BUY"] >= VOTE_THRESHOLD:
        signal = "BUY"
    elif votes["SELL"] >= VOTE_THRESHOLD:
        signal = "SELL"

    if not signal:
        print("💤 No signal: Threshold not reached.")
        return

    # حساب المستويات
    if signal == "BUY":
        sl = close - sl_dist
        tp = close + tp_dist
        emoji = "🟢"
    else:
        sl = close + sl_dist
        tp = close - tp_dist
        emoji = "🔴"

    msg = f"""
🦈 <b>هجوم القرش - Shark Alert</b>
{emoji} <b>{signal} XAUUSD</b>

📥 سعر الدخول: {close:.2f}
🎯 الهدف (TP): {tp:.2f}
🛑 الستوب (SL): {sl:.2f}

📊 أسباب القوة:
{", ".join(reasons)}
(قوة الإشارة: {votes[signal]} أصوات)
"""

    result = send_telegram(msg)
    if result and result.get("ok"):
        print("✅ Signal sent to Telegram successfully!")
    else:
        print("❌ Failed to send Telegram message. Check Token/ChatID.")

if __name__ == "__main__":
    analyze_and_signal()
