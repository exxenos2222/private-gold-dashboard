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
        # --- 1. กำหนดกลยุทธ์ตามโหมด (Strategy Selector) ---
        if mode == "scalping":
            # Strategy: Mean Reversion (BB + Stoch) -> ซิ่ง M15
            interval = "15m"
            period = "5d"
            sl_mult = 0.8   # SL แคบ (เข้าเร็วออกเร็ว)
            tp_mult = 1.5
            tf_name = "M15 (Sniper BB+Stoch)"
            
        elif mode == "daytrade":
            # Strategy: Momentum Trend (MACD + EMA Cross) -> จบในวัน H1
            interval = "60m"
            period = "1mo"
            sl_mult = 1.5   # SL ปานกลาง
            tp_mult = 2.0
            tf_name = "H1 (Day Trend MACD)"
            
        else: # swing
            # Strategy: Major Trend (Golden Cross + ADX) -> ถือยาว D1
            interval = "1d"
            period = "2y"   # ดึงยาวเพื่อหา EMA200
            sl_mult = 2.5   # SL กว้างกันสะบัด
            tp_mult = 4.0   # กินคำโต
            tf_name = "D1 (Big Swing Trend)"

        # --- 2. ดึงข้อมูล ---
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if len(df) < 200: return None 

        # --- 3. คำนวณ Indicator พื้นฐาน ---
        df.ta.atr(length=14, append=True)
        last = df.iloc[-1]
        price = last['Close']
        atr = last['ATRr_14']
        
        bias = "SIDEWAY"
        reasons = []
        bull_score = 0
        bear_score = 0

        # ==========================================
        # 🧠 LOGIC 1: SCALPING (M15) -> เน้น BB + Stoch
        # ==========================================
        if mode == "scalping":
            df.ta.bbands(length=20, std=2, append=True)
            df.ta.stoch(append=True) # Stochastic
            
            last = df.iloc[-1]
            bb_lower = last['BBL_20_2.0']
            bb_upper = last['BBU_20_2.0']
            stoch_k = last['STOCHk_14_3_3']
            
            # Logic: ราคาชนขอบ + Stoch กลับตัว
            if price <= bb_lower * 1.001 and stoch_k < 25:
                bull_score += 5 # สัญญาณชัดมาก (Oversold)
                reasons.append("ราคาชนขอบล่าง BB + Stoch Oversold")
            elif price >= bb_upper * 0.999 and stoch_k > 75:
                bear_score += 5 # สัญญาณชัดมาก (Overbought)
                reasons.append("ราคาชนขอบบน BB + Stoch Overbought")
            else:
                # ถ้าไม่ชนขอบ ดูโมเมนตัมย่อย
                if stoch_k < 20: bull_score += 2
                if stoch_k > 80: bear_score += 2

            # จุดเข้า: ขอบ BB
            buy_entry = bb_lower
            sell_entry = bb_upper

        # ==========================================
        # 🧠 LOGIC 2: DAY TRADE (H1) -> เน้น MACD + EMA
        # ==========================================
        elif mode == "daytrade":
            df.ta.macd(append=True)
            df.ta.ema(length=20, append=True)
            df.ta.ema(length=50, append=True)
            
            last = df.iloc[-1]
            macd = last['MACD_12_26_9']
            signal = last['MACDs_12_26_9']
            ema20 = last['EMA_20']
            ema50 = last['EMA_50']
            
            # Logic: MACD ตัดขึ้น + ราคาอยู่เหนือ EMA
            if macd > signal:
                bull_score += 2
                reasons.append("MACD ตัดขึ้น (Momentum มา)")
            else:
                bear_score += 2
                reasons.append("MACD ตัดลง (Momentum หมด)")
                
            if ema20 > ema50:
                bull_score += 3
                reasons.append("EMA 20 ตัด 50 ขึ้น (Golden Cross เล็ก)")
            else:
                bear_score += 3
                reasons.append("EMA 20 ตัด 50 ลง (Dead Cross เล็ก)")

            # จุดเข้า: เส้น EMA20 (รอย่อ)
            buy_entry = ema20
            sell_entry = ema20

        # ==========================================
        # 🧠 LOGIC 3: SWING TRADE (D1) -> เน้น EMA200 + ADX
        # ==========================================
        else: 
            df.ta.adx(append=True)
            df.ta.ema(length=50, append=True)
            df.ta.ema(length=200, append=True)
            
            last = df.iloc[-1]
            adx = last['ADX_14']
            ema50 = last['EMA_50']
            ema200 = last['EMA_200']
            
            # Logic: ต้องมีเทรนด์ชัดเจน (ADX > 25) และดูโครงสร้างใหญ่
            if adx > 25:
                reasons.append(f"เทรนด์แข็งแรง (ADX {round(adx,1)})")
                if ema50 > ema200:
                    bull_score += 5
                    reasons.append("Golden Cross (EMA50 > EMA200)")
                else:
                    bear_score += 5
                    reasons.append("Dead Cross (EMA50 < EMA200)")
            else:
                reasons.append("ADX ต่ำ (ตลาดไซด์เวย์)")
            
            # จุดเข้า: EMA50 หรือ EMA200
            buy_entry = ema50 if price > ema50 else ema200
            sell_entry = ema50 if price < ema50 else ema200

        # --- 4. สรุปผล (Verdict) ---
        if bull_score > bear_score: bias = "BULLISH (ขาขึ้น)"
        elif bear_score > bull_score: bias = "BEARISH (ขาลง)"
        
        # ป้องกัน Entry ไกลเกินความจริง (Dynamic Adjust)
        if (price - buy_entry) > (atr * 3): buy_entry = price - (atr * 1.0)
        if (sell_entry - price) > (atr * 3): sell_entry = price + (atr * 1.0)

        # คำนวณ SL/TP
        buy_sl = buy_entry - (atr * sl_mult)
        buy_tp = buy_entry + (atr * tp_mult)
        sell_sl = sell_entry + (atr * sl_mult)
        sell_tp = sell_entry - (atr * tp_mult)

        # Pips Scale Correction (ทอง $1 = 100 จุด)
        pips_scale = 10000 
        if "JPY" in symbol: pips_scale = 100
        if "XAU" in symbol or "GC=F" in symbol: pips_scale = 100 
        if "BTC" in symbol: pips_scale = 1

        buy_pips = int((buy_entry - buy_sl) * pips_scale)
        sell_pips = int((sell_sl - sell_entry) * pips_scale)

        # RSI สำหรับโชว์ (ทั่วไป)
        rsi_show = round(last['RSI_14'], 2) if 'RSI_14' in last else 0

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": tf_name,
            "trend": bias,
            "reasons": ", ".join(reasons),
            "rsi": rsi_show,
            "buy_setup": {"entry": round(buy_entry, 2), "sl": round(buy_sl, 2), "tp": round(buy_tp, 2), "pips": buy_pips},
            "sell_setup": {"entry": round(sell_entry, 2), "sl": round(sell_sl, 2), "tp": round(sell_tp, 2), "pips": sell_pips}
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

@app.post("/analyze_custom")
def analyze_custom(req: AnalysisRequest):
    # --- จำกัดแค่ Gold & Bitcoin ตามคำขอ ---
    symbol_map = {
        "GOLD": "GC=F", 
        "BITCOIN": "BTC-USD"
    }
    target = symbol_map.get(req.symbol.upper(), req.symbol.upper())
    
    data = analyze_dynamic(target, req.mode)
    
    if data:
        # เลือกโชว์แผนหลักตาม Score
        main_trend_icon = "🟢" if "BULLISH" in data['trend'] else "🔴" if "BEARISH" in data['trend'] else "⚠️"
        
        reply = (
            f"🧠 **AI Pro (3-Brain Logic): {data['symbol']}**\n"
            f"⚙️ กลยุทธ์: {data['tf_name']}\n"
            f"--------------------\n"
            f"{main_trend_icon} **แนวโน้ม: {data['trend']}**\n"
            f"💡 เหตุผล: {data['reasons']}\n"
            f"--------------------\n"
            f"🟢 **แผน BUY Limit**\n"
            f"   • เข้า: {data['buy_setup']['entry']}\n"
            f"   • ⛔ SL: {data['buy_setup']['sl']} (~{data['buy_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['buy_setup']['tp']}\n"
            f"--------------------\n"
            f"🔴 **แผน SELL Limit**\n"
            f"   • เข้า: {data['sell_setup']['entry']}\n"
            f"   • ⛔ SL: {data['sell_setup']['sl']} (~{data['sell_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['sell_setup']['tp']}"
        )
        return {"reply": reply}
    else:
        return {"reply": "❌ ข้อมูลไม่เพียงพอ หรือตลาดปิดครับ"}

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