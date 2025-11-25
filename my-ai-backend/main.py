from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    symbol: str
    mode: str 

# --- Helper Functions ---
def get_current_price(symbol):
    try:
        target = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        df = yf.Ticker(target).history(period="1d", interval="1m")
        if not df.empty: return df['Close'].iloc[-1]
    except: pass
    return None

def get_data_safe(symbol, interval, period):
    # Spot -> Futures -> Fallback Logic (เหมือนเดิม)
    if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
        try:
            df = yf.Ticker("XAUUSD=X").history(period=period, interval=interval)
            if len(df) > 15: return df, f"{interval} (Spot)"
        except: pass
        try:
            df = yf.Ticker("GC=F").history(period=period, interval=interval)
            if len(df) > 15: return df, f"{interval} (Futures)"
        except: pass
    else:
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if len(df) > 15: return df, interval
        except: pass

    try:
        fallback_sym = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        df = yf.Ticker(fallback_sym).history(period="1mo", interval="60m")
        return df, "H1 (Backup)"
    except:
        return pd.DataFrame(), "Error"

# --- [NEW] ฟังก์ชันคำนวณ Fibonacci ---
def get_fibonacci_levels(df):
    # หาจุดสูงสุด/ต่ำสุด ในรอบ 50 แท่งล่าสุด
    high_price = df['High'].tail(50).max()
    low_price = df['Low'].tail(50).min()
    diff = high_price - low_price
    
    # ขาขึ้น (Retracement)
    fibo_618_up = high_price - (diff * 0.618)
    fibo_500_up = high_price - (diff * 0.5)
    
    # ขาลง (Retracement)
    fibo_618_down = low_price + (diff * 0.618)
    fibo_500_down = low_price + (diff * 0.5)
    
    return {
        "high": high_price, "low": low_price,
        "buy_zone": [fibo_618_up, fibo_500_up], # โซนรอย่อซื้อ
        "sell_zone": [fibo_618_down, fibo_500_down] # โซนรอเด้งขาย
    }

# --- [NEW] ฟังก์ชันหาแท่งเทียนกลับตัว (Pattern) ---
def check_candlestick_pattern(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Engulfing (กลืนกิน)
    bullish_engulfing = (prev['Close'] < prev['Open']) and (last['Close'] > last['Open']) and (last['Close'] > prev['Open']) and (last['Open'] < prev['Close'])
    bearish_engulfing = (prev['Close'] > prev['Open']) and (last['Close'] < last['Open']) and (last['Close'] < prev['Open']) and (last['Open'] > prev['Close'])
    
    # Hammer / Shooting Star (หางยาว)
    body = abs(last['Close'] - last['Open'])
    upper_wick = last['High'] - max(last['Close'], last['Open'])
    lower_wick = min(last['Close'], last['Open']) - last['Low']
    
    hammer = lower_wick > (body * 2) and upper_wick < body # หางล่างยาว (ดันขึ้น)
    shooting_star = upper_wick > (body * 2) and lower_wick < body # หางบนยาว (ตบลง)
    
    if bullish_engulfing: return "Bullish Engulfing (กลืนกินขาขึ้น)"
    if bearish_engulfing: return "Bearish Engulfing (กลืนกินขาลง)"
    if hammer: return "Hammer (แรงซื้อดันกลับ)"
    if shooting_star: return "Shooting Star (แรงขายตบสวน)"
    
    return None

def analyze_dynamic(symbol: str, mode: str):
    try:
        if mode == "scalping":
            req_int = "15m"; req_per = "5d"; sl_mult = 0.6; tp_mult = 1.5; tf_name = "M15 (Sniper)"
        elif mode == "daytrade":
            req_int = "60m"; req_per = "1mo"; sl_mult = 1.5; tp_mult = 2.0; tf_name = "H1 (Day Trade)"
        else: 
            req_int = "1d"; req_per = "1y"; sl_mult = 2.5; tp_mult = 3.5; tf_name = "D1 (Swing)"

        df, actual_tf_label = get_data_safe(symbol, req_int, req_per)
        if df.empty or len(df) < 20: return None 

        last = df.iloc[-1]
        raw_price = last['Close']
        
        # Calibration
        real_price = get_current_price(symbol)
        offset = 0
        is_calibrated = False
        if real_price and abs(real_price - raw_price) > 0.5:
            price = real_price
            offset = real_price - raw_price
            is_calibrated = True
        else:
            price = raw_price
        
        # Basic Indicators
        atr = price * 0.005; rsi = 50; ema50 = price
        try: 
            df.ta.atr(length=14, append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.ema(length=50, append=True)
            if pd.notna(df['ATRr_14'].iloc[-1]): atr = df['ATRr_14'].iloc[-1]
            if pd.notna(df['RSI_14'].iloc[-1]): rsi = df['RSI_14'].iloc[-1]
            if pd.notna(df['EMA_50'].iloc[-1]): ema50 = df['EMA_50'].iloc[-1] + offset
        except: pass

        # --- Scoring System ---
        bull_score = 0
        bear_score = 0
        reasons = []

        # 1. Trend
        if price > ema50: bull_score += 2
        else: bear_score += 2

        # 2. Fibonacci Logic (จุดเข้าคมๆ)
        fibo = get_fibonacci_levels(df)
        # ปรับ Offset ให้ Fibo
        fibo_buy_zone = [x + offset for x in fibo['buy_zone']]
        fibo_sell_zone = [x + offset for x in fibo['sell_zone']]

        # 3. Candlestick Pattern (ตัวคอนเฟิร์ม)
        pattern = check_candlestick_pattern(df)
        if pattern:
            reasons.append(f"Pattern: {pattern}")
            if "Bullish" in pattern or "Hammer" in pattern: bull_score += 2
            if "Bearish" in pattern or "Shooting" in pattern: bear_score += 2

        # 4. RSI Logic
        if rsi < 30: bull_score += 1; reasons.append("RSI Oversold")
        if rsi > 70: bear_score += 1; reasons.append("RSI Overbought")

        # --- Decision & Entry ---
        
        # ขาขึ้น: หาจังหวะย่อซื้อที่ Fibo 61.8%
        if bull_score > bear_score:
            bias = "BULLISH"
            action_rec = "🟢 เน้นฝั่ง BUY"
            # Entry ที่ Fibo 61.8% ของชุดขาขึ้น
            buy_entry = fibo_buy_zone[0] 
            # ถ้า Fibo ไกลไป ให้ใช้ EMA50 ช่วย
            if price - buy_entry > atr * 3: buy_entry = ema50
            
            # ถ้ากราฟเกิด Pattern กลับตัว ให้เข้าเลย!
            if pattern and ("Bullish" in pattern or "Hammer" in pattern):
                buy_entry = price
                reasons.append("เข้าตาม Pattern กลับตัว")

            sell_entry = price + (atr * 2) # ตั้งหลอกไว้ไกลๆ

        # ขาลง: หาจังหวะเด้งขายที่ Fibo 61.8%
        elif bear_score > bull_score:
            bias = "BEARISH"
            action_rec = "🔴 เน้นฝั่ง SELL"
            # Entry ที่ Fibo 61.8% ของชุดขาลง
            sell_entry = fibo_sell_zone[0]
            if sell_entry - price > atr * 3: sell_entry = ema50

            if pattern and ("Bearish" in pattern or "Shooting" in pattern):
                sell_entry = price
                reasons.append("เข้าตาม Pattern กลับตัว")

            buy_entry = price - (atr * 2)

        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"
            buy_entry = price - atr
            sell_entry = price + atr

        # Safety Adjust
        if buy_entry >= price: buy_entry = price - (atr * 0.2)
        if sell_entry <= price: sell_entry = price + (atr * 0.2)

        # Setup
        buy_sl = buy_entry - (atr * sl_mult)
        buy_tp = buy_entry + (atr * tp_mult)
        sell_sl = sell_entry + (atr * sl_mult)
        sell_tp = sell_entry - (atr * tp_mult)

        pips_scale = 10000 
        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol: pips_scale = 100 
        if "BTC" in symbol: pips_scale = 1

        final_tf_name = actual_tf_label
        if is_calibrated: final_tf_name += " ⚡(Live)"

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": final_tf_name,
            "trend": bias,
            "action": action_rec,
            "reasons": ", ".join(reasons[:3]), # เอาเหตุผลเด็ดๆ 3 ข้อ
            "rsi": round(rsi, 2),
            "score": f"{bull_score}-{bear_score}",
            "buy_setup": {"entry": round(buy_entry, 2), "sl": round(buy_sl, 2), "tp": round(buy_tp, 2), "pips": int((buy_entry - buy_sl) * pips_scale)},
            "sell_setup": {"entry": round(sell_entry, 2), "sl": round(sell_sl, 2), "tp": round(sell_tp, 2), "pips": int((sell_sl - sell_entry) * pips_scale)}
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

@app.post("/analyze_custom")
def analyze_custom(req: AnalysisRequest):
    target = req.symbol
    data = analyze_dynamic(target, req.mode)
    
    if data:
        reply = (
            f"🏆 **สรุป: {data['action']}**\n"
            f"--------------------\n"
            f"🎯 **แผนเทรด {data['symbol']} (Sniper)**\n"
            f"⚙️ ข้อมูล: {data['tf_name']}\n"
            f"💰 **ราคา: ${data['price']}**\n"
            f"📊 สถานะ: {data['trend']} (RSI: {data['rsi']})\n"
            f"💡 เหตุผล: {data['reasons']}\n"
            f"--------------------\n"
            f"🟢 **BUY Limit**\n"
            f"   • เข้า: {data['buy_setup']['entry']}\n"
            f"   • ⛔ SL: {data['buy_setup']['sl']} (~{data['buy_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['buy_setup']['tp']}\n"
            f"--------------------\n"
            f"🔴 **SELL Limit**\n"
            f"   • เข้า: {data['sell_setup']['entry']}\n"
            f"   • ⛔ SL: {data['sell_setup']['sl']} (~{data['sell_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['sell_setup']['tp']}"
        )
        return {"reply": reply}
    else:
        return {"reply": "❌ ข้อมูลไม่พร้อมใช้งาน กรุณาลองใหม่"}

@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    try:
        target = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        ticker = yf.Ticker(target)
        data = ticker.history(period="2d", interval="1h")
        if data.empty: return {"symbol": symbol, "price": 0, "change":0, "percent":0}
        price = data['Close'].iloc[-1]
        prev = data['Close'].iloc[0]
        change = price - prev
        percent = (change / prev) * 100
        return {"symbol": symbol, "price": round(price, 2), "change": round(change, 2), "percent": round(percent, 2)}
    except: return {"symbol": symbol, "price": 0}