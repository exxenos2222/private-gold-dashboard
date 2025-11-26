from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests

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

# --- [NEW] สร้าง Session หลอกว่าเป็นคนเข้าเว็บ (กัน Yahoo บล็อก) ---
def get_ticker_safe(symbol):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return yf.Ticker(symbol, session=session)

def get_current_price(symbol):
    try:
        target = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        ticker = get_ticker_safe(target)
        df = ticker.history(period="1d", interval="1m")
        if not df.empty: return df['Close'].iloc[-1]
    except: pass
    return None

def get_data_safe(symbol, interval, period):
    # 1. Spot Gold (XAUUSD=X)
    if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
        try:
            ticker = get_ticker_safe("XAUUSD=X")
            df = ticker.history(period=period, interval=interval)
            if len(df) > 10: return df, f"{interval} (Spot)"
        except: pass
        
        # 2. Futures (GC=F)
        try:
            ticker = get_ticker_safe("GC=F")
            df = ticker.history(period=period, interval=interval)
            if len(df) > 10: return df, f"{interval} (Futures)"
        except: pass

    # 3. General (BTC)
    else:
        try:
            ticker = get_ticker_safe(symbol)
            df = ticker.history(period=period, interval=interval)
            if len(df) > 10: return df, interval
        except: pass

    # 4. Fallback H1
    print("⚠️ Fetch failed, using fallback H1...")
    try:
        fallback_sym = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        ticker = get_ticker_safe(fallback_sym)
        df = ticker.history(period="5d", interval="60m")
        return df, "H1 (Backup Data)"
    except:
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

        # Indicators (ใช้ try-except แยกแต่ละตัว)
        last = df.iloc[-1]
        price = last['Close']
        atr = price * 0.005; rsi = 50; ema50 = price

        try: 
            df.ta.atr(length=14, append=True)
            if pd.notna(df['ATRr_14'].iloc[-1]): atr = df['ATRr_14'].iloc[-1]
        except: pass

        try:
            df.ta.rsi(length=14, append=True)
            if pd.notna(df['RSI_14'].iloc[-1]): rsi = df['RSI_14'].iloc[-1]
        except: pass

        try:
            df.ta.ema(length=50, append=True)
            if pd.notna(df['EMA_50'].iloc[-1]): ema50 = df['EMA_50'].iloc[-1]
        except: pass

        # Auto-Calibration
        real_price = get_current_price(symbol)
        offset = 0
        is_calibrated = False
        if real_price and abs(real_price - price) > 0.5:
            offset = real_price - price
            price = real_price
            ema50 += offset # Adjust EMA too
            is_calibrated = True

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
        
        # BB Strategy
        try:
            df.ta.bbands(length=20, std=2, append=True)
            if 'BBL_20_2.0' in df.columns:
                bb_lower = df['BBL_20_2.0'].iloc[-1] + offset
                bb_upper = df['BBU_20_2.0'].iloc[-1] + offset
                if pd.notna(bb_lower):
                    buy_entry = bb_lower
                    sell_entry = bb_upper
                    if price <= bb_lower: bull_score += 3
                    if price >= bb_upper: bear_score += 3
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

        # Safety
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
        print(f"CRITICAL: {e}")
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
        return {"reply": "❌ ขออภัยครับ ข้อมูล Yahoo มีปัญหาชั่วคราว (ลองกดใหม่อีกครั้งใน 1 นาที)"}

@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    try:
        target = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
        ticker = get_ticker_safe(target)
        data = ticker.history(period="2d", interval="1h")
        if data.empty: return {"symbol": symbol, "price": 0, "change":0, "percent":0}
        price = data['Close'].iloc[-1]
        prev = data['Close'].iloc[0]
        change = price - prev
        percent = (change / prev) * 100
        return {"symbol": symbol, "price": round(price, 2), "change": round(change, 2), "percent": round(percent, 2)}
    except: return {"symbol": symbol, "price": 0}