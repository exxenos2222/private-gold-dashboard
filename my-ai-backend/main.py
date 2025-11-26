from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import pandas_ta as ta

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

# --- ฟังก์ชันดึงราคาปัจจุบัน (Real-time) ---
def get_current_price(symbol):
    try:
        # บังคับดู Spot Gold เท่านั้น
        target = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        df = yf.Ticker(target).history(period="1d", interval="1m")
        if not df.empty: return df['Close'].iloc[-1]
    except: pass
    return None

# --- [แก้ใหม่] ฟังก์ชันดึงข้อมูลแบบ "Spot Only" (ไม่เอา Futures) ---
def get_data_safe(symbol, interval, period):
    
    # กรณีเป็นทองคำ (Gold)
    if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
        target = "XAUUSD=X" # Spot Gold
        
        # 1. พยายามดึงตามที่ขอ (เช่น M15)
        try:
            df = yf.Ticker(target).history(period=period, interval=interval)
            if len(df) > 15: return df, f"{interval} (Spot)"
        except: pass
        
        # 2. ถ้า M15 ไม่มา -> ลอง M30 Spot (ยังดีกว่าไปใช้ Futures)
        if interval == "15m":
            print("⚠️ Spot M15 failed, trying M30 Spot...")
            try:
                df = yf.Ticker(target).history(period="5d", interval="30m")
                if len(df) > 15: return df, "M30 (Spot Backup)"
            except: pass

        # 3. ถ้าไม่ไหวจริง -> ใช้ H1 Spot (ชัวร์สุด)
        print("⚠️ Spot Intraday failed, using H1 Spot...")
        try:
            df = yf.Ticker(target).history(period="1mo", interval="60m")
            return df, "H1 (Spot Backup)"
        except: pass

    # กรณี Bitcoin หรืออื่นๆ
    else:
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if len(df) > 15: return df, interval
        except: pass
        
        # Fallback BTC
        try:
            df = yf.Ticker(symbol).history(period="1mo", interval="60m")
            return df, "H1 (Backup)"
        except: pass

    return pd.DataFrame(), "Error"

def analyze_dynamic(symbol: str, mode: str):
    try:
        # Config
        if mode == "scalping":
            req_int = "15m"; req_per = "5d"; sl_mult = 0.6; tp_mult = 1.2; tf_name = "M15 (ซิ่ง)"
        elif mode == "daytrade":
            req_int = "60m"; req_per = "1mo"; sl_mult = 1.5; tp_mult = 2.0; tf_name = "H1 (จบในวัน)"
        else: 
            req_int = "1d"; req_per = "1y"; sl_mult = 2.5; tp_mult = 3.5; tf_name = "D1 (ถือยาว)"

        # Get Data
        df, actual_tf_label = get_data_safe(symbol, req_int, req_per)
        
        if df.empty or len(df) < 10: return None 

        # Indicators
        last = df.iloc[-1]
        raw_price = last['Close']
        
        # Auto-Calibration (จูนราคา Spot ให้ตรงเป๊ะ)
        real_price = get_current_price(symbol)
        offset = 0
        is_calibrated = False
        
        if real_price and abs(real_price - raw_price) > 0.5:
            price = real_price
            offset = real_price - raw_price
            is_calibrated = True
        else:
            price = raw_price
        
        # Default Indicators
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

        if price > ema50: bull_score += 2; reasons.append("เหนือ EMA50")
        else: bear_score += 2; reasons.append("ใต้ EMA50")

        if rsi < 30: bull_score += 2; reasons.append("RSI Oversold")
        elif rsi > 70: bear_score += 2; reasons.append("RSI Overbought")

        buy_entry = price - atr
        sell_entry = price + atr
        
        try:
            df.ta.bbands(length=20, std=2, append=True)
            if 'BBL_20_2.0' in df.columns:
                bb_lower = df['BBL_20_2.0'].iloc[-1] + offset
                bb_upper = df['BBU_20_2.0'].iloc[-1] + offset
                
                if pd.notna(bb_lower) and pd.notna(bb_upper):
                    buy_entry = bb_lower
                    sell_entry = bb_upper
                    if price <= bb_lower: bull_score += 3; reasons.append("ชนขอบล่าง BB")
                    if price >= bb_upper: bear_score += 3; reasons.append("ชนขอบบน BB")
        except: pass

        # Verdict
        if bull_score > bear_score:
            bias = "BULLISH"
            action_rec = "🟢 เน้นฝั่ง BUY"
        elif bear_score > bull_score:
            bias = "BEARISH"
            action_rec = "🔴 เน้นฝั่ง SELL"
        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"

        if (price - buy_entry) > (atr * 5): buy_entry = price - atr
        if (sell_entry - price) > (atr * 5): sell_entry = price + atr

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
            "reasons": ", ".join(reasons[:3]),
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
            f"🎯 **แผนเทรด {data['symbol']}**\n"
            f"⚙️ ข้อมูล: {data['tf_name']}\n"
            f"💰 **ราคาปัจจุบัน: ${data['price']}**\n"
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