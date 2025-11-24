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
        # --- 1. กำหนดกลยุทธ์ ---
        if mode == "scalping":
            interval = "15m"
            period = "5d"  # <--- [แก้ไข] ลดเหลือ 5 วัน (Yahoo ส่งข้อมูล M15 ได้สูงสุดแค่นี้แบบเสถียร)
            sl_mult = 0.8
            tp_mult = 1.5
            tf_name = "M15 (Sniper Scalp)"
            
        elif mode == "daytrade":
            interval = "60m"
            period = "1mo"
            sl_mult = 1.5
            tp_mult = 2.0
            tf_name = "H1 (Day Trend)"
            
        else: 
            interval = "1d"
            period = "2y"
            sl_mult = 2.5
            tp_mult = 4.0
            tf_name = "D1 (Big Swing)"

        # --- 2. ดึงข้อมูล ---
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        
        # ลดเกณฑ์ลงอีกเผื่อข้อมูลมาน้อยจริงๆ
        if len(df) < 15: return None 

        # --- 3. คำนวณ Indicator ---
        df.ta.atr(length=14, append=True)
        last = df.iloc[-1]
        price = last['Close']
        
        atr = last['ATRr_14'] if pd.notna(last['ATRr_14']) else (price * 0.01)
        
        bias = "SIDEWAY"
        reasons = []
        bull_score = 0
        bear_score = 0

        # ==========================================
        # 🧠 LOGIC 1: SCALPING (M15)
        # ==========================================
        if mode == "scalping":
            df.ta.bbands(length=20, std=2, append=True)
            df.ta.stoch(append=True)
            
            last = df.iloc[-1]
            
            # Check Data Availability
            if 'BBL_20_2.0' not in last or pd.isna(last['BBL_20_2.0']):
                return None # ถ้าคำนวณ BB ไม่ได้ ให้จบเลย

            bb_lower = last['BBL_20_2.0']
            bb_upper = last['BBU_20_2.0']
            stoch_k = last['STOCHk_14_3_3'] if 'STOCHk_14_3_3' in last else 50
            
            if price <= bb_lower * 1.001:
                bull_score += 5; reasons.append("ราคาชนขอบล่าง BB")
            elif price >= bb_upper * 0.999:
                bear_score += 5; reasons.append("ราคาชนขอบบน BB")
            
            if stoch_k < 20: bull_score += 2; reasons.append("Stoch Oversold")
            if stoch_k > 80: bear_score += 2; reasons.append("Stoch Overbought")

            buy_entry = bb_lower
            sell_entry = bb_upper

        # ==========================================
        # 🧠 LOGIC 2: DAY TRADE (H1)
        # ==========================================
        elif mode == "daytrade":
            df.ta.macd(append=True)
            df.ta.ema(length=20, append=True)
            df.ta.ema(length=50, append=True)
            
            last = df.iloc[-1]
            macd = last['MACD_12_26_9'] if 'MACD_12_26_9' in last else 0
            signal = last['MACDs_12_26_9'] if 'MACDs_12_26_9' in last else 0
            ema20 = last['EMA_20'] if 'EMA_20' in last else price
            ema50 = last['EMA_50'] if 'EMA_50' in last else price
            
            if macd > signal: bull_score += 2; reasons.append("MACD ตัดขึ้น")
            else: bear_score += 2; reasons.append("MACD ตัดลง")
                
            if ema20 > ema50: bull_score += 3; reasons.append("EMA 20>50")
            else: bear_score += 3; reasons.append("EMA 20<50")

            buy_entry = ema20
            sell_entry = ema20

        # ==========================================
        # 🧠 LOGIC 3: SWING TRADE (D1)
        # ==========================================
        else: 
            df.ta.adx(append=True)
            df.ta.ema(length=50, append=True)
            df.ta.ema(length=200, append=True)
            
            last = df.iloc[-1]
            adx = last['ADX_14'] if 'ADX_14' in last else 0
            ema50 = last['EMA_50'] if 'EMA_50' in last else price
            ema200 = last['EMA_200'] if 'EMA_200' in last else price
            
            if adx > 25:
                reasons.append(f"เทรนด์แข็ง (ADX {round(adx)})")
                if ema50 > ema200: bull_score += 5; reasons.append("Golden Cross")
                else: bear_score += 5; reasons.append("Dead Cross")
            else:
                reasons.append("ADX ต่ำ")
            
            buy_entry = ema50 if price > ema50 else ema200
            sell_entry = ema50 if price < ema50 else ema200

        # --- 4. สรุปผล ---
        if bull_score > bear_score: 
            bias = "BULLISH (ขาขึ้น)"
            action_rec = "🟢 เน้นฝั่ง BUY"
        elif bear_score > bull_score: 
            bias = "BEARISH (ขาลง)"
            action_rec = "🔴 เน้นฝั่ง SELL"
        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"
        
        # Dynamic Adjust (ป้องกัน Entry ไกลเกิน)
        if (price - buy_entry) > (atr * 3): buy_entry = price - (atr * 1.0)
        if (sell_entry - price) > (atr * 3): sell_entry = price + (atr * 1.0)

        buy_sl = buy_entry - (atr * sl_mult)
        buy_tp = buy_entry + (atr * tp_mult)
        sell_sl = sell_entry + (atr * sl_mult)
        sell_tp = sell_entry - (atr * tp_mult)

        pips_scale = 10000 
        if "JPY" in symbol: pips_scale = 100
        if "XAU" in symbol or "GC=F" in symbol: pips_scale = 100 
        if "BTC" in symbol: pips_scale = 1

        buy_pips = int((buy_entry - buy_sl) * pips_scale)
        sell_pips = int((sell_sl - sell_entry) * pips_scale)

        rsi_show = round(last['RSI_14'], 2) if 'RSI_14' in last else 0

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": tf_name,
            "trend": bias,
            "action": action_rec,
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
    symbol_map = { "GOLD": "GC=F", "BITCOIN": "BTC-USD" }
    target = symbol_map.get(req.symbol.upper(), req.symbol.upper())
    
    data = analyze_dynamic(target, req.mode)
    
    if data:
        main_trend_icon = "🟢" if "BULLISH" in data['trend'] else "🔴" if "BEARISH" in data['trend'] else "⚠️"
        
        reply = (
            f"🧠 **AI Pro (3-Brain): {data['symbol']}**\n"
            f"⚙️ โหมด: {data['tf_name']}\n"
            f"--------------------\n"
            f"{main_trend_icon} **แนวโน้ม: {data['trend']}**\n"
            f"💡 เหตุผล: {data['reasons']}\n"
            f"--------------------\n"
            f"🟢 **แผน BUY Limit (รับ)**\n"
            f"   • เข้า: {data['buy_setup']['entry']}\n"
            f"   • ⛔ SL: {data['buy_setup']['sl']} (~{data['buy_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['buy_setup']['tp']}\n"
            f"--------------------\n"
            f"🔴 **แผน SELL Limit (ต้าน)**\n"
            f"   • เข้า: {data['sell_setup']['entry']}\n"
            f"   • ⛔ SL: {data['sell_setup']['sl']} (~{data['sell_setup']['pips']} จุด)\n"
            f"   • ✅ TP: {data['sell_setup']['tp']}"
        )
        return {"reply": reply}
    else:
        return {"reply": "⚠️ ข้อมูลไม่เพียงพอ (ตลาดปิด หรือ M15 data ขาดช่วง ลองกดใหม่อีกครั้ง)"}

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