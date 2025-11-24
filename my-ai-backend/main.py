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
        # --- [จุดที่จูน Logic] ปรับระยะ SL/TP ตามสไตล์การเล่น ---
        if mode == "scalping":
            # สายซิ่ง: ดู M15, SL แคบมาก (0.6 เท่าของความผันผวน), TP สั้น
            interval = "15m"
            period = "5d"
            sl_mult = 0.6   # <--- ปรับให้แคบลง (เดิม 1.5)
            tp_mult = 1.2   # เก็บสั้นๆ
            tf_name = "M15 (Scalping)"
        elif mode == "daytrade":
            # สายจบในวัน: ดู H1, SL มาตรฐาน (1.5 เท่า)
            interval = "60m"
            period = "1mo"
            sl_mult = 1.5
            tp_mult = 2.0
            tf_name = "H1 (Day Trade)"
        else: 
            # สายถือยาว: ดู Day, SL กว้าง (2.5 เท่า)
            interval = "1d"
            period = "1y"
            sl_mult = 2.5
            tp_mult = 3.5
            tf_name = "D1 (Swing Trade)"
        # -------------------------------------------------------

        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if len(df) < 50: return None

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

        recent_high = df['High'].tail(20).max()
        recent_low = df['Low'].tail(20).min()

        score = 0
        if price > ema50: score += 1
        if macd_line > macd_signal: score += 1
        if rsi > 50: score += 1

        bias = "SIDEWAY"
        if score >= 2: bias = "BULLISH (ขาขึ้น)"
        elif score <= 1: bias = "BEARISH (ขาลง)"

        # คำนวณจุดเข้า (Entry) ให้สมเหตุสมผลกับโหมด
        # Scalping: พยายามเข้าใกล้เส้น EMA หรือราคาปัจจุบันมากที่สุด (ไม่รอ Pivot ไกลๆ)
        if mode == "scalping":
            buy_entry = price if price > ema50 else ema50
            sell_entry = price if price < ema50 else ema50
        else:
            # Day/Swing: รอเข้าที่ Swing High/Low เดิม
            buy_entry = max(recent_low, ema50) if price > ema50 else recent_low
            if (price - buy_entry) > (atr * 2): buy_entry = price - (atr * 0.5)

            sell_entry = min(recent_high, ema50) if price < ema50 else recent_high
            if (sell_entry - price) > (atr * 2): sell_entry = price + (atr * 0.5)

        # คำนวณ SL/TP
        buy_sl = buy_entry - (atr * sl_mult)
        buy_tp = buy_entry + (atr * tp_mult)

        sell_sl = sell_entry + (atr * sl_mult)
        sell_tp = sell_entry - (atr * tp_mult)

        # คำนวณ Pips
        pips_scale = 10000 
        if "JPY" in symbol: pips_scale = 100
        if "XAU" in symbol or "GC=F" in symbol: pips_scale = 100 
        if "BTC" in symbol: pips_scale = 1

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

@app.post("/analyze_custom")
def analyze_custom(req: AnalysisRequest):
    symbol_map = {
        "GOLD": "GC=F", "BITCOIN": "BTC-USD",
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "JPY=X"
    }
    target = symbol_map.get(req.symbol.upper(), req.symbol.upper())
    
    data = analyze_dynamic(target, req.mode)
    
    if data:
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
        return {"reply": "❌ ข้อมูลไม่เพียงพอ"}

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