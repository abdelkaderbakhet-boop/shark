# الملف: bot.py
import os
import time
import pandas as pd
import pandas_ta as ta
import requests
import numpy as np
from tvDatafeed import TvDatafeed, Interval
from sklearn.ensemble import RandomForestClassifier

# ==================== إعدادات القرش ====================
TELEGRAM_TOKEN = "8466875451:AAHXwDTX5Tww-oylqzOwVSTE_XoypRfRsrI"
CHAT_ID = "-1003552439018"
SYMBOL = "XAUUSD"
EXCHANGE = "FOREXCOM"
TIMEFRAME = Interval.in_15_minute 
VOTE_THRESHOLD = 6 

# ==================== دوال القرش ====================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
    except: pass

def get_data():
    tv = TvDatafeed()
    for _ in range(3):
        try:
            df = tv.get_hist(symbol=SYMBOL, exchange=EXCHANGE, interval=TIMEFRAME, n_bars=500)
            if df is not None and not df.empty: return df
        except: time.sleep(1)
    return None

def analyze_and_signal():
    print("🦈 Shark Bot Wake Up... Scanning XAUUSD...")
    
    df = get_data()
    if df is None: 
        print("❌ No Data Received")
        return

    # 1. تجهيز المؤشرات
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA200'] = ta.ema(df['close'], length=200)
    
    close = df['close'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    
    # ==========================================================
    # 2. حساب الأهداف (الشرط: الستوب والهدف لا يقلان عن 40 بيب)
    # ==========================================================
    # ملاحظة: في الذهب، تحرك 1 دولار في السعر = 10 بيب
    # إذن 40 بيب = 4.0 دولار في السعر

    # أولاً: حساب القيم بناء على ATR (تذبذب السوق)
    raw_sl = atr * 1.5       # الستوب الطبيعي
    raw_tp = raw_sl * 2.0    # الهدف الطبيعي (ضعف الستوب)

    # ثانياً: تطبيق الحد الأدنى (40 بيب / 4 دولار)
    sl_dist = max(raw_sl, 4.0)  # خذ الأكبر بين القيمة المحسوبة و 4.0
    tp_dist = max(raw_tp, 4.0)  # خذ الأكبر بين القيمة المحسوبة و 4.0

    # 3. نظام التصويت
    votes = {"BUY": 0, "SELL": 0}
    details = []

    # RSI
    rsi = df['RSI'].iloc[-1]
    if rsi < 30: votes["BUY"] += 1; details.append("RSI Oversold")
    elif rsi > 70: votes["SELL"] += 1; details.append("RSI Overbought")

    # Trend
    if close > df['EMA200'].iloc[-1]: votes["BUY"] += 1
    else: votes["SELL"] += 1

    # SMC
    try:
        if df['high'].iloc[-3] < df['low'].iloc[-1]: votes["BUY"] += 2; details.append("SMC Bullish")
        elif df['low'].iloc[-3] > df['high'].iloc[-1]: votes["SELL"] += 2; details.append("SMC Bearish")
    except: pass

    # AI Prediction
    try:
        data = df.copy()
        data['Target'] = (data['close'].shift(-1) > data['close']).astype(int)
        data.dropna(inplace=True)
        features = ['RSI', 'EMA200']
        X = data[features].iloc[:-1]; y = data['Target'].iloc[:-1]
        
        model = RandomForestClassifier(n_estimators=50, max_depth=3)
        model.fit(X, y)
        pred = model.predict(data[features].iloc[[-1]])[0]
        
        if pred == 1: votes["BUY"] += 2; details.append("AI: Up")
        else: votes["SELL"] += 2; details.append("AI: Down")
    except: pass

    # 4. اتخاذ القرار
    signal = None
    if votes["BUY"] >= VOTE_THRESHOLD: signal = "BUY"
    elif votes["SELL"] >= VOTE_THRESHOLD: signal = "SELL"

    print(f"📊 Votes -> Buy: {votes['BUY']} | Sell: {votes['SELL']}")

    if signal:
        if signal == "BUY":
            sl = close - sl_dist
            tp = close + tp_dist
            emoji = "🟢"
        else:
            sl = close + sl_dist
            tp = close - tp_dist
            emoji = "🔴"
        
        reasons_txt = ", ".join(details)
        
        # تنسيق الرسالة بوضوح
        msg = f"""
🦈 <b>Shark Bot Alert (GitHub)</b> 🦈
{emoji} <b>{signal} XAUUSD</b>
📥 <b>Price: {close:.2f}</b>

🎯 <b>TP: {tp:.2f}</b> (+{tp_dist*10:.0f} pips)
🛑 <b>SL: {sl:.2f}</b> (-{sl_dist*10:.0f} pips)

📊 <b>Reasons:</b> {reasons_txt}
"""
        send_telegram(msg)
        print("✅ Signal Sent to Telegram")
    else:
        print("💤 No Strong Signal Found.")

if __name__ == "__main__":
    analyze_and_signal()
