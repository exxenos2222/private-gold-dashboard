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

def analyze_dynamic(symbol: str, mode: str):
    try:
        # 1. ตั้งค่าพารามิเตอร์ (จูนความแม่นยำ)
        if mode == "scalping":
            interval = "15m"
            period = "5d"
            sl_mult = 0.6   # SL แคบ (300-500 จุด)
            tp_mult = 1.2   # เก็บสั้น
            tf_name = "M15 (Scalping)"
            lookback = 12   # ย้อนหลัง 12 แท่ง (3 ชม.)
        elif mode == "daytrade":
            interval = "60m"
            period = "1mo"
            sl_mult = 1.5   # SL กลาง (800-1500 จุด)
            tp_mult = 2.0   # R:R 1:2
            tf_name = "H1 (Day Trade)"
            lookback = 24   # ย้อนหลัง 24 แท่ง (1 วัน)
        else: # swing
            interval = "1d"
            period = "1y"
            sl_mult = 2.5   # SL กว้าง (2000+ จุด)
            tp_mult = 3.0   # R:R 1:3
            tf_name = "D1 (Swing Trade)"
            lookback = 10   # ย้อนหลัง 10 แท่ง (2 สัปดาห์)

        # 2. ดึงข้อมูล
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if len(df) < 50: return None

        # 3. คำนวณ Indicator
        df.ta.rsi(length=14, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.atr(length=14, append=True)

        last = df.iloc[-1]
        price = last['Close']
        rsi = last['RSI_14']
        ema50 = last['EMA_50']
        atr = last['ATRr_14']

        # 4. หาแนวรับ/แนวต้าน (Support & Resistance)
        # ใช้ High/Low ย้อนหลังตาม Lookback ที่ตั้งไว้
        recent_high = df['High'].tail(lookback).max()
        recent_low = df['Low'].tail(lookback).min()

        # 5. Scoring (ดูเทรนด์)
        bias = "SIDEWAY"
        if price > ema50: bias = "BULLISH (ขาขึ้น)"
        elif price < ema50: bias = "BEARISH (ขาลง)"

        # 6. คำนวณจุดเข้า (Entry Logic)
        
        # --- PLAN A: BUY LIMIT (รอซื้อที่แนวรับ) ---
        # รับที่ Low เดิม หรือ EMA50 (แล้วแต่ว่าอะไรใกล้ราคากว่ากัน)
        if price > ema50:
            buy_entry = max(recent_low, ema50) # ขาขึ้น รับที่ EMA หรือ Low
        else:
            buy_entry = recent_low # ขาลง รอรับที่ Low ต่ำสุดเลย (ปลอดภัย)
            
        # ป้องกัน Entry ไกลเกินไป (Dynamic Adjust)
        if (price - buy_entry) > (atr * 4): buy_entry = price - (atr * 2)

        buy_sl = buy_entry - (atr * sl_mult)
        buy_tp = buy_entry + (atr * tp_mult)

        # --- PLAN B: SELL LIMIT (รอขายที่แนวต้าน) ---
        # ขายที่ High เดิม หรือ EMA50
        if price < ema50:
            sell_entry = min(recent_high, ema50) # ขาลง ขายที่ EMA หรือ High
        else:
            sell_entry = recent_high # ขาขึ้น รอขายที่ High สูงสุด (Counter Trend)

        # ป้องกัน Entry ไกลเกินไป
        if (sell_entry - price) > (atr * 4): sell_entry = price + (atr * 2)

        sell_sl = sell_entry + (atr * sl_mult)
        sell_tp = sell_entry - (atr * tp_mult)

        # 7. คำนวณ Pips (ทองคำ)
        pips_scale = 10000 
        if "JPY" in symbol: pips_scale = 100
        if "XAU" in symbol or "GC=F" in symbol: pips_scale = 100 
        if "BTC" in symbol: pips_scale = 1

        buy_sl_pips = int((buy_entry - buy_sl) * pips_scale)
        sell_sl_pips = int((sell_sl - sell_entry) * pips_scale)

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": tf_name,
            "trend": bias,
            "rsi": round(rsi, 2),
            "buy_setup": {
                "entry": round(buy_entry, 2), 
                "sl": round(buy_sl, 2), 
                "tp": round(buy_tp, 2),
                "pips": buy_sl_pips
            },
            "sell_setup": {
                "entry": round(sell_entry, 2), 
                "sl": round(sell_sl, 2), 
                "tp": round(sell_tp, 2),
                "pips": sell_sl_pips
            }
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

@app.post("/analyze_custom")
def analyze_custom(req: AnalysisRequest):
    symbol_map = {
        "GOLD": "GC=F", "BITCOIN": "BTC-USD",
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X"
    }
    target = symbol_map.get(req.symbol.upper(), req.symbol.upper())
    
    data = analyze_dynamic(target, req.mode)
    
    if data:
        # --- สร้างข้อความตอบกลับแบบ 2 แผน (Dual Plan) ---
        reply = (
            f"🎯 **แผนเทรดคู่: {data['symbol']}**\n"
            f"⏱️ โหมด: {data['tf_name']}\n"
            f"--------------------\n"
            f"📊 **สถานะตลาด**\n"
            f"➤ ราคา: {data['price']}\n"
            f"➤ แนวโน้ม: {data['trend']} (RSI: {data['rsi']})\n"
            f"--------------------\n"
            f"🟢 **แผนย่อซื้อ (BUY Limit)**\n"
            f"   • เข้า: {data['buy_setup']['entry']}\n"
            f"   • ⛔ SL: {data['buy_setup']['sl']}\n"
            f"   • ✅ TP: {data['buy_setup']['tp']}\n"
            f"   *(SL: ~{data['buy_setup']['pips']} จุด)*\n"
            f"--------------------\n"
            f"🔴 **แผนเด้งขาย (SELL Limit)**\n"
            f"   • เข้า: {data['sell_setup']['entry']}\n"
            f"   • ⛔ SL: {data['sell_setup']['sl']}\n"
            f"   • ✅ TP: {data['sell_setup']['tp']}\n"
            f"   *(SL: ~{data['sell_setup']['pips']} จุด)*"
        )
        return {"reply": reply}
    else:
        return {"reply": "❌ ไม่สามารถวิเคราะห์ข้อมูลได้ในขณะนี้ครับ"}

@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="2d", interval="1h")
        if data.empty: return {"symbol": symbol, "price": 0, "change":0, "percent":0}
        price = data['Close'].iloc[-1]
        prev = data['Close'].iloc[0]
        change = price - prev
        percent = (change / prev) * 100
        return {"symbol": symbol, "price": round(price, 2), "change": round(change, 2), "percent": round(percent, 2)}
    except: return {"symbol": symbol, "price": 0}