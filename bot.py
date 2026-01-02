import os
import time
import pandas as pd
import requests
import numpy as np
from tvDatafeed import TvDatafeed, Interval

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = "8466875451:AAHXwDTX5Tww-oylqzOwVSTE_XoypRfRsrI"
CHAT_ID = "-1003552439018"
SYMBOL = "XAUUSD"
EXCHANGE = "FOREXCOM"
VOTE_THRESHOLD = 5 

# ==================== مؤشرات يدوية ====================
def EMA(series, period): return series.ewm(span=period, adjust=False).mean()

def RSI(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def ATR(df, period=14):
    tr = pd.concat([df['high']-df['low'], 
                    (df['high']-df['close'].shift()).abs(), 
                    (df['low']-df['close'].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ==================== Telegram ====================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

# ==================== التحليل الفني ====================
def get_mtf_data(tv):
    try:
        df30 = tv.get_hist(SYMBOL, EXCHANGE, Interval.in_30_minute, n_bars=100)
        df15 = tv.get_hist(SYMBOL, EXCHANGE, Interval.in_15_minute, n_bars=100)
        df5  = tv.get_hist(SYMBOL, EXCHANGE, Interval.in_5_minute, n_bars=100)
        return df30, df15, df5
    except: return None, None, None

def analyze():
    tv = TvDatafeed()
    df30, df15, df5 = get_mtf_data(tv)
    if df5 is None or df30 is None: return False

    # 1. اتجاه فريم 30 دقيقة
    ema200_30 = EMA(df30['close'], 200).iloc[-1]
    close30 = df30['close'].iloc[-1]
    trend = "UP" if close30 > ema200_30 else "DOWN"

    # 2. فريم 15 دقيقة (SK System & SMC)
    high15 = df15['high'].rolling(50).max().iloc[-1]
    low15 = df15['low'].rolling(50).min().iloc[-1]
    fib_50 = low15 + (high15 - low15) * 0.50
    fib_61 = low15 + (high15 - low15) * 0.618
    close15 = df15['close'].iloc[-1]

    # 3. فريم 5 دقائق (Entry)
    rsi5 = RSI(df5['close']).iloc[-1]
    atr5 = ATR(df5).iloc[-1]
    close5 = df5['close'].iloc[-1]

    votes = 0
    reasons = []

    # حساب النقاط
    if trend == "UP":
        votes += 2; reasons.append("30m Trend Up")
    else:
        votes -= 2 # عقوبة للبيع في ترند صاعد والعكس

    if fib_61 <= close15 <= fib_50:
        votes += 2; reasons.append("15m Golden Zone")

    if df15['high'].iloc[-3] < df15['low'].iloc[-1]:
        votes += 2; reasons.append("15m SMC Imbalance")

    if rsi5 < 35:
        votes += 1; reasons.append("5m RSI Oversold")

    # اتخاذ القرار
    if votes >= VOTE_THRESHOLD:
        sl_val = max(atr5 * 2, 4.0)
        tp = close5 + (sl_val * 2)
        sl = close5 - sl_val
        msg = f"🦈 <b>توصية شراء (Shark Sniper)</b>\n💎 الذهب XAUUSD\n📥 الدخول: {close5:.2f}\n🎯 الهدف: {tp:.2f}\n🛑 الستوب: {sl:.2f}\n📊 القوة: {votes} أصوات\n🔍 الأسباب: {', '.join(reasons)}"
        send_telegram(msg)
        return True
    
    # منطق البيع (اختياري - معكوس)
    elif votes <= -VOTE_THRESHOLD:
        sl_val = max(atr5 * 2, 4.0)
        tp = close5 - (sl_val * 2)
        sl = close5 + sl_val
        msg = f"🦈 <b>توصية بيع (Shark Sniper)</b>\n💎 الذهب XAUUSD\n📥 الدخول: {close5:.2f}\n🎯 الهدف: {tp:.2f}\n🛑 الستوب: {sl:.2f}\n📊 القوة: {abs(votes)} أصوات"
        send_telegram(msg)
        return True

    return False

# ==================== التشغيل المستمر داخل الدورة ====================
if __name__ == "__main__":
    # يبدأ المسح بصمت دون إرسال رسالة ترحيب
    start_time = time.time()
    # يعمل لمدة 13 دقيقة ويفحص كل دقيقة واحدة
    while time.time() - start_time < 780: 
        try:
            signal_found = analyze()
            if signal_found:
                break # يتوقف بعد إرسال التوصية لتجنب تكرار نفس الصفقة
        except:
            pass
        time.sleep(60)
