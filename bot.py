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
VOTE_THRESHOLD = 5 # القوة المطلوبة لإرسال التوصية

# ==================== مؤشرات فنية يدوية (لضمان الاستقرار) ====================

def EMA(series, period):
    return series.ewm(span=period, adjust=False).mean()

def RSI(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def ATR(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ==================== وظائف البوت ====================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def get_data(tv):
    try:
        # سحب الفريمات الثلاثة
        d30 = tv.get_hist(SYMBOL, EXCHANGE, Interval.in_30_minute, n_bars=150)
        d15 = tv.get_hist(SYMBOL, EXCHANGE, Interval.in_15_minute, n_bars=150)
        d5  = tv.get_hist(SYMBOL, EXCHANGE, Interval.in_5_minute, n_bars=150)
        return d30, d15, d5
    except:
        return None, None, None

def run_analysis():
    tv = TvDatafeed()
    df30, df15, df5 = get_data(tv)
    
    if df5 is None or df30 is None:
        print("❌ فشل الاتصال بمزود البيانات")
        return False

    # --- تحليل فريم 30 دقيقة (الاتجاه) ---
    ema200_30 = EMA(df30['close'], 200).iloc[-1]
    close30 = df30['close'].iloc[-1]
    trend = "UP" if close30 > ema200_30 else "DOWN"

    # --- تحليل فريم 15 دقيقة (SK & SMC) ---
    high15 = df15['high'].rolling(50).max().iloc[-1]
    low15 = df15['low'].rolling(50).min().iloc[-1]
    fib_50 = low15 + (high15 - low15) * 0.50
    fib_61 = low15 + (high15 - low15) * 0.618
    close15 = df15['close'].iloc[-1]

    # --- تحليل فريم 5 دقائق (الدخول) ---
    rsi5 = RSI(df5['close']).iloc[-1]
    atr5 = ATR(df5).iloc[-1]
    close5 = df5['close'].iloc[-1]

    buy_votes = 0
    sell_votes = 0
    reasons = []

    # منطق الشراء
    if trend == "UP": buy_votes += 2; reasons.append("الاتجاه العام صاعد (30m)")
    if fib_61 <= close15 <= fib_50 and trend == "UP": buy_votes += 2; reasons.append("منطقة SK الذهبية (15m)")
    if df15['high'].iloc[-3] < df15['low'].iloc[-1]: buy_votes += 2; reasons.append("فجوة سيولة SMC (15m)")
    if rsi5 < 35: buy_votes += 1; reasons.append("تشبع بيعي لحظي (5m)")

    # منطق البيع
    if trend == "DOWN": sell_votes += 2; reasons.append("الاتجاه العام هابط (30m)")
    if fib_61 <= close15 <= fib_50 and trend == "DOWN": sell_votes += 2; reasons.append("منطقة SK بيعية (15m)")
    if df15['low'].iloc[-3] > df15['high'].iloc[-1]: sell_votes += 2; reasons.append("فجوة هبوطية SMC (15m)")
    if rsi5 > 65: sell_votes += 1; reasons.append("تشبع شرائي لحظي (5m)")

    # طباعة للحالة في كونسول جيت هاب (للمراقبة فقط)
    current_time = time.strftime('%H:%M:%S')
    print(f"🕒 {current_time} | Price: {close5:.2f} | Trend: {trend} | B: {buy_votes} S: {sell_votes}")

    # إرسال التوصية
    if buy_votes >= VOTE_THRESHOLD:
        sl_dist = max(atr5 * 2, 4.0) # ضمان 40 بيب كحد أدنى
        tp = close5 + (sl_dist * 2)
        sl = close5 - sl_dist
        msg = f"🦈 <b>توصية شراء (Shark Sniper)</b>\n💎 الذهب XAUUSD\n📥 الدخول: {close5:.2f}\n🎯 الهدف: {tp:.2f}\n🛑 الستوب: {sl:.2f}\n📊 القوة: {buy_votes} أصوات\n🔍 الأسباب: {', '.join(reasons)}"
        send_telegram(msg)
        return True

    elif sell_votes >= VOTE_THRESHOLD:
        sl_dist = max(atr5 * 2, 4.0)
        tp = close5 - (sl_dist * 2)
        sl = close5 + sl_dist
        msg = f"🦈 <b>توصية بيع (Shark Sniper)</b>\n💎 الذهب XAUUSD\n📥 الدخول: {close5:.2f}\n🎯 الهدف: {tp:.2f}\n🛑 الستوب: {sl:.2f}\n📊 القوة: {sell_votes} أصوات\n🔍 الأسباب: {', '.join(reasons)}"
        send_telegram(msg)
        return True

    return False

# ==================== التشغيل اللحظي ====================

if __name__ == "__main__":
    start_time = time.time()
    # يعمل لمدة 13 دقيقة (يفحص كل 60 ثانية)
    while time.time() - start_time < 780:
        try:
            found = run_analysis()
            if found: 
                # التوقف بعد إرسال التوصية لمنع التكرار في نفس الدورة
                break 
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(60)
