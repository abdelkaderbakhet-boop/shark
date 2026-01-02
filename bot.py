import os
import time
import pandas as pd
import requests
import numpy as np
from tvDatafeed import TvDatafeed, Interval
from sklearn.ensemble import RandomForestClassifier

# ==================== الإعدادات ====================
TELEGRAM_TOKEN = "8466875451:AAHXwDTX5Tww-oylqzOwVSTE_XoypRfRsrI"
CHAT_ID = "-1003552439018"
SYMBOL = "XAUUSD"
EXCHANGE = "FOREXCOM"
VOTE_THRESHOLD = 5 # رفعنا العتبة قليلاً لأننا نستخدم 3 فريمات (دقة أعلى)

# ==================== مؤشرات يدوية ====================
def EMA(series, period): return series.ewm(span=period, adjust=False).mean()
def RSI(series, period=14):
    delta = series.diff(); gain = delta.where(delta > 0, 0.0); loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean(); avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def ATR(df, period=14):
    tr = pd.concat([df['high']-df['low'], (df['high']-df['close'].shift()).abs(), (df['low']-df['close'].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ==================== Telegram ====================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

# ==================== Logic ====================
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
    if df5 is None or df30 is None: return

    # --- تحليل فريم 30 دقيقة (الاتجاه العام) ---
    ema200_30 = EMA(df30['close'], 200).iloc[-1]
    close30 = df30['close'].iloc[-1]
    trend = "UP" if close30 > ema200_30 else "DOWN"

    # --- تحليل فريم 15 دقيقة (مناطق SK/SMC) ---
    high15 = df15['high'].rolling(50).max().iloc[-1]
    low15 = df15['low'].rolling(50).min().iloc[-1]
    fib_50 = low15 + (high15 - low15) * 0.50
    fib_61 = low15 + (high15 - low15) * 0.618
    close15 = df15['close'].iloc[-1]

    # --- تحليل فريم 5 دقائق (الدخول اللحظي) ---
    rsi5 = RSI(df5['close']).iloc[-1]
    atr5 = ATR(df5).iloc[-1]
    close5 = df5['close'].iloc[-1]

    votes = 0
    reasons = []

    # 1. قوة الترند (30د)
    if trend == "UP": votes += 2; reasons.append("30m Trend Up")
    else: votes -= 2 # عقوبة للبيع في ترند صاعد

    # 2. منطقة SK (15د)
    if fib_61 <= close15 <= fib_50:
        votes += 2; reasons.append("15m Golden Zone")

    # 3. RSI (5د)
    if rsi5 < 35: votes += 1; reasons.append("5m RSI Low")
    elif rsi5 > 65: votes -= 1

    # 4. SMC Imbalance (15د)
    if df15['high'].iloc[-3] < df15['low'].iloc[-1]:
        votes += 2; reasons.append("15m SMC Imbalance")

    print(f"[{time.strftime('%H:%M:%S')}] Price: {close5} | Votes: {votes}")

    if votes >= VOTE_THRESHOLD:
        sl = close5 - max(atr5 * 2, 4.0)
        tp = close5 + (max(atr5 * 2, 4.0) * 2)
        msg = f"🦈 <b>توصية شراء قوية</b>\n💎 الذهب XAUUSD\n📥 الدخول: {close5:.2f}\n🎯 الهدف: {tp:.2f}\n🛑 الستوب: {sl:.2f}\n📊 القوة: {votes} أصوات\n🔍 الأسباب: {', '.join(reasons)}"
        send_telegram(msg)
        return True # لمنع التكرار في نفس الدورة
    return False

# ==================== التشغيل المستمر (كل دقيقة) ====================
if __name__ == "__main__":
    send_telegram("🟢 <b>القرش استيقظ الآن!</b>\nجاري فحص الذهب كل دقيقة للفريمات (5, 15, 30)... 🔍")
    
    # حلقة تكرار لمدة 13 دقيقة (لتغطية وقت الـ 15 دقيقة في GitHub)
    start_time = time.time()
    while time.time() - start_time < 780: # 780 ثانية = 13 دقيقة
        try:
            found = analyze()
            if found: break # إذا أرسل توصية، يتوقف وينتظر الدورة القادمة
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(60) # انتظر دقيقة واحدة
