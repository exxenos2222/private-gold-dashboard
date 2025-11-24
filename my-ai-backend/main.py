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

# รับค่าแบบละเอียดขึ้น (ชื่อเหรียญ + โหมด)
class AnalysisRequest(BaseModel):
    symbol: str
    mode: str # "scalping", "daytrade", "swing"

# --- สมอง AI ปรับเปลี่ยนได้ (Dynamic Logic) ---
def analyze_dynamic(symbol: str, mode: str):
    try:
        # 1. ตั้งค่าพารามิเตอร์ตามโหมดที่เลือก
        if mode == "scalping":
            interval = "15m"
            period = "5d"
            sl_mult = 1.5  # SL แคบ
            tp_mult = 2.0
            tf_name = "M15 (ซิ่ง)"
        elif mode == "daytrade":
            interval = "60m"
            period = "1mo"
            sl_mult = 2.0  # SL กลาง
            tp_mult = 2.5
            tf_name = "H1 (จบในวัน)"
        else: # swing
            interval = "1d"
            period = "1y"
            sl_mult = 3.0  # SL กว้าง (กันสะบัด)
            tp_mult = 3.0
            tf_name = "D1 (ถือยาว)"

        # 2. ดึงข้อมูล
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if len(df) < 50: return None

        # 3. คำนวณ Indicator
        df.ta.rsi(length=14, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.macd(append=True)
        df.ta.atr(length=14, append=True)

        last = df.iloc[-1]
        price = last['Close']
        rsi = last['RSI_14']
        ema50 = last['EMA_50']
        atr = last['ATRr_14']
        macd_line = last['MACD_12_26_9']
        macd_signal = last['MACDs_12_26_9']

        # 4. หาจุดเข้า (Dynamic Entry)
        # หาราคา High/Low ในช่วง 20 แท่งล่าสุดเพื่อเป็นแนวรับต้านระยะสั้น
        recent_high = df['High'].tail(20).max()
        recent_low = df['Low'].tail(20).min()

        # 5. Scoring
        score = 0
        if price > ema50: score += 1
        if macd_line > macd_signal: score += 1
        if rsi > 50: score += 1

        bias = "SIDEWAY"
        if score >= 2: bias = "BULLISH (ขาขึ้น)"
        elif score <= 1: bias = "BEARISH (ขาลง)"

        # 6. คำนวณ Setup ตามโหมด
        buy_entry = max(recent_low, ema50) if price > ema50 else recent_low
        # ปรับจุดเข้าให้ใกล้ปัจจุบันถ้ามันไกลไป
        if (price - buy_entry) > (atr * 3): buy_entry = price - atr

        buy_sl = buy_entry - (atr * sl_mult)
        buy_tp = buy_entry + (atr * tp_mult)

        sell_entry = min(recent_high, ema50) if price < ema50 else recent_high
        if (sell_entry - price) > (atr * 3): sell_entry = price + atr

        sell_sl = sell_entry + (atr * sl_mult)
        sell_tp = sell_entry - (atr * tp_mult)

        # แปลงระยะเป็นจุด (Pips) โดยประมาณ
        pips_scale = 100 if "JPY" in symbol else 10000
        if "XAU" in symbol or "GC=F" in symbol: pips_scale = 10 # ทองคำ
        if "BTC" in symbol: pips_scale = 1 # คริปโต

        sl_pips = int((buy_entry - buy_sl) * pips_scale)

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": tf_name,
            "trend": bias,
            "rsi": round(rsi, 2),
            "sl_pips": abs(sl_pips),
            "buy_setup": {"entry": round(buy_entry, 2), "sl": round(buy_sl, 2), "tp": round(buy_tp, 2)},
            "sell_setup": {"entry": round(sell_entry, 2), "sl": round(sell_sl, 2), "tp": round(sell_tp, 2)}
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

# API ใหม่: รับทั้งชื่อและโหมด
@app.post("/analyze_custom")
def analyze_custom(req: AnalysisRequest):
    # แปลงชื่อให้ตรงกับ Yahoo Finance
    symbol_map = {
        "GOLD": "GC=F", "BITCOIN": "BTC-USD",
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X"
    }
    target = symbol_map.get(req.symbol.upper(), req.symbol.upper())
    
    data = analyze_dynamic(target, req.mode)
    
    if data:
        # เลือกโชว์แผนเดียวตามเทรนด์
        plan_text = ""
        if "BULLISH" in data['trend']:
            plan_text = (
                f"🟢 **แนะนำฝั่ง BUY**\n"
                f"   • เข้า: {data['buy_setup']['entry']}\n"
                f"   • ⛔ SL: {data['buy_setup']['sl']}\n"
                f"   • ✅ TP: {data['buy_setup']['tp']}"
            )
        else:
            plan_text = (
                f"🔴 **แนะนำฝั่ง SELL**\n"
                f"   • เข้า: {data['sell_setup']['entry']}\n"
                f"   • ⛔ SL: {data['sell_setup']['sl']}\n"
                f"   • ✅ TP: {data['sell_setup']['tp']}"
            )

        reply = (
            f"🎯 **แผนเทรด: {data['symbol']}**\n"
            f"⏱️ โหมด: {data['tf_name']}\n"
            f"--------------------\n"
            f"➤ ราคา: {data['price']}\n"
            f"➤ สถานะ: {data['trend']} (RSI: {data['rsi']})\n"
            f"--------------------\n"
            f"{plan_text}\n"
            f"--------------------\n"
            f"*(ระยะ SL ประมาณ {data['sl_pips']} จุด)*"
        )
        return {"reply": reply}
    else:
        return {"reply": "❌ ไม่สามารถดึงข้อมูลได้ หรือข้อมูลไม่พอครับ"}

# API เก่า (สำหรับ Dashboard หน้าแรก)
@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    # โค้ดดึงราคาง่ายๆ สำหรับ Ticker Bar
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