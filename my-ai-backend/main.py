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

# --- ฟังก์ชันดึงราคา Real-time ---
def get_current_price(symbol):
    try:
        target = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        df = yf.Ticker(target).history(period="1d", interval="1m")
        if not df.empty: return df['Close'].iloc[-1]
    except: pass
    return None

def get_data_safe(symbol, interval, period):
    # Logic การดึงข้อมูลเดิม (Spot -> Futures -> Fallback)
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

# --- [NEW] ฟังก์ชันหา Order Block (SMC) ---
def find_order_blocks(df):
    # หา Bullish OB (แท่งแดงสุดท้าย ก่อนเขียวใหญ่)
    bullish_ob = None
    bearish_ob = None
    
    # วนลูปย้อนหลัง 20 แท่งล่าสุด
    for i in range(len(df)-2, len(df)-20, -1):
        curr = df.iloc[i]
        next_candle = df.iloc[i+1]
        body_size = abs(curr['Close'] - curr['Open'])
        next_body = abs(next_candle['Close'] - next_candle['Open'])
        avg_body = abs(df['Close'] - df['Open']).mean()

        # Bullish OB Logic: แท่งแดง -> ตามด้วยเขียวพุ่งแรง (Engulfing)
        if curr['Close'] < curr['Open']: # แท่งแดง
            if next_candle['Close'] > next_candle['Open']: # แท่งถัดไปเขียว
                if next_body > (avg_body * 1.5) and next_candle['Close'] > curr['Open']: 
                    # เจอแล้ว! รายใหญ่เข้าซื้อตรงนี้
                    bullish_ob = curr['High'] # ใช้ราคา High ของแท่ง OB เป็นจุดเข้า
                    break
    
    # Bearish OB Logic: แท่งเขียว -> ตามด้วยแดงทุบแรง
    for i in range(len(df)-2, len(df)-20, -1):
        curr = df.iloc[i]
        next_candle = df.iloc[i+1]
        body_size = abs(curr['Close'] - curr['Open'])
        next_body = abs(next_candle['Close'] - next_candle['Open'])
        avg_body = abs(df['Close'] - df['Open']).mean()

        if curr['Close'] > curr['Open']: # แท่งเขียว
            if next_candle['Close'] < next_candle['Open']: # แท่งถัดไปแดง
                if next_body > (avg_body * 1.5) and next_candle['Close'] < curr['Open']:
                    # เจอแล้ว! รายใหญ่ทุบตรงนี้
                    bearish_ob = curr['Low'] # ใช้ราคา Low ของแท่ง OB เป็นจุดเข้า
                    break
                    
    return bullish_ob, bearish_ob

def analyze_dynamic(symbol: str, mode: str):
    try:
        if mode == "scalping":
            req_int = "15m"; req_per = "5d"; sl_mult = 0.6; tp_mult = 1.5; tf_name = "M15 (SMC Scalp)"
        elif mode == "daytrade":
            req_int = "60m"; req_per = "1mo"; sl_mult = 1.5; tp_mult = 2.0; tf_name = "H1 (SMC Day)"
        else: 
            req_int = "1d"; req_per = "1y"; sl_mult = 2.5; tp_mult = 3.5; tf_name = "D1 (SMC Swing)"

        df, actual_tf_label = get_data_safe(symbol, req_int, req_per)
        if df.empty or len(df) < 10: return None 

        last = df.iloc[-1]
        raw_price = last['Close']
        
        real_price = get_current_price(symbol)
        if real_price and abs(real_price - raw_price) > 0.5:
            price = real_price
            offset = real_price - raw_price
            is_calibrated = True
        else:
            price = raw_price
            offset = 0
            is_calibrated = False
        
        atr = price * 0.005
        rsi = 50
        ema50 = price
        
        try: 
            df.ta.atr(length=14, append=True)
            if pd.notna(df['ATRr_14'].iloc[-1]): atr = df['ATRr_14'].iloc[-1]
            
            df.ta.rsi(length=14, append=True)
            if pd.notna(df['RSI_14'].iloc[-1]): rsi = df['RSI_14'].iloc[-1]
            
            df.ta.ema(length=50, append=True)
            if pd.notna(df['EMA_50'].iloc[-1]): ema50 = df['EMA_50'].iloc[-1] + offset
        except: pass

        # Scoring
        bull_score = 0
        bear_score = 0
        reasons = []

        if price > ema50: bull_score += 2; reasons.append("Trend ขาขึ้น")
        else: bear_score += 2; reasons.append("Trend ขาลง")

        if rsi < 30: bull_score += 1; reasons.append("RSI Oversold")
        elif rsi > 70: bear_score += 1; reasons.append("RSI Overbought")

        # --- [SMC INTEGRATION] ใช้ Order Block เป็นจุดเข้าหลัก ---
        ob_buy, ob_sell = find_order_blocks(df)
        
        # ปรับ Offset ให้ Order Block ด้วย
        if ob_buy: ob_buy += offset
        if ob_sell: ob_sell += offset

        # คำนวณจุดเข้า (Prioritize SMC)
        # ถ้าเจอ OB ให้ใช้ OB ถ้าไม่เจอให้ใช้ Logic เดิม (EMA/BB)
        if ob_buy and price > ob_buy: 
            buy_entry = ob_buy
            bull_score += 2 # ให้คะแนนเพิ่มเพราะมีฐานแน่น
            reasons.append("เจอ Bullish Order Block (แนวรับรายใหญ่)")
        else:
            buy_entry = price - (atr * 0.8) # Fallback

        if ob_sell and price < ob_sell: 
            sell_entry = ob_sell
            bear_score += 2
            reasons.append("เจอ Bearish Order Block (แนวต้านรายใหญ่)")
        else:
            sell_entry = price + (atr * 0.8) # Fallback

        # Verdict
        if bull_score > bear_score:
            bias = "BULLISH"
            action_rec = "🟢 เน้นฝั่ง BUY (ตามรายใหญ่)"
        elif bear_score > bull_score:
            bias = "BEARISH"
            action_rec = "🔴 เน้นฝั่ง SELL (ตามรายใหญ่)"
        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"

        # Safety
        if (price - buy_entry) > (atr * 5): buy_entry = price - atr
        if (sell_entry - price) > (atr * 5): sell_entry = price + atr

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
            "reasons": ", ".join(reasons[:2]),
            "rsi": round(rsi, 2),
            "score": f"{bull_score}-{bear_score}",
            "buy_setup": {"entry": round(buy_entry, 2), "sl": round(buy_sl, 2), "tp": round(buy_tp, 2), "pips": int((buy_entry - buy_sl) * pips_scale)},
            "sell_setup": {"entry": round(sell_entry, 2), "sl": round(sell_sl, 2), "tp": round(sell_tp, 2), "pips": int((sell_sl - sell_entry) * pips_scale)}
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return None

@app.post("/analyze_custom")
def analyze_custom(req: AnalysisRequest):
    target = req.symbol
    data = analyze_dynamic(target, req.mode)
    
    if data:
        reply = (
            f"🏆 **สรุป: {data['action']}**\n"
            f"--------------------\n"
            f"🎯 **แผนเทรด {data['symbol']} (SMC)**\n"
            f"⚙️ ข้อมูล: {data['tf_name']}\n"
            f"💰 **ราคา: ${data['price']}**\n"
            f"📊 สถานะ: {data['trend']} | {data['reasons']}\n"
            f"--------------------\n"
            f"🟢 **BUY Limit (รอที่ OB)**\n"
            f"   • เข้า: {data['buy_setup']['entry']}\n"
            f"   • ⛔ SL: {data['buy_setup']['sl']} (~{data['buy_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['buy_setup']['tp']}\n"
            f"--------------------\n"
            f"🔴 **SELL Limit (รอที่ OB)**\n"
            f"   • เข้า: {data['sell_setup']['entry']}\n"
            f"   • ⛔ SL: {data['sell_setup']['sl']} (~{data['sell_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['sell_setup']['tp']}"
        )
        return {"reply": reply}
    else:
        return {"reply": "❌ ข้อมูลไม่พร้อมใช้งาน"}

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