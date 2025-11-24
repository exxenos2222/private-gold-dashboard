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

# --- ฟังก์ชันช่วยดึงข้อมูล (พยายามดึงจนกว่าจะได้) ---
def get_reliable_data(symbol, preferred_interval, preferred_period):
    # ความพยายามครั้งที่ 1: ตามที่ขอมา
    df = yf.Ticker(symbol).history(period=preferred_period, interval=preferred_interval)
    if len(df) > 25: return df, preferred_interval

    # ความพยายามครั้งที่ 2: ถ้า M15 พัง ให้ลอง M30
    if preferred_interval == "15m":
        print(f"⚠️ M15 failed for {symbol}, trying M30...")
        df = yf.Ticker(symbol).history(period="5d", interval="30m")
        if len(df) > 25: return df, "M30 (Backup)"

    # ความพยายามครั้งที่ 3: ถ้ายังพัง ให้ใช้ H1 (เสถียรสุด)
    print(f"⚠️ Intraday failed for {symbol}, fallback to H1...")
    df = yf.Ticker(symbol).history(period="1mo", interval="60m")
    return df, "H1 (Backup)"

def analyze_dynamic(symbol: str, mode: str):
    try:
        # 1. ตั้งค่าพารามิเตอร์
        if mode == "scalping":
            req_interval = "15m"
            req_period = "5d"
            sl_mult = 0.6
            tp_mult = 1.2
            tf_label = "M15 (ซิ่ง)"
        elif mode == "daytrade":
            req_interval = "60m"
            req_period = "1mo"
            sl_mult = 1.5
            tp_mult = 2.0
            tf_label = "H1 (จบในวัน)"
        else: 
            req_interval = "1d"
            req_period = "1y"
            sl_mult = 2.5
            tp_mult = 3.5
            tf_label = "D1 (ถือยาว)"

        # 2. ดึงข้อมูลผ่านระบบ Fallback (กันเหนียว)
        df, actual_tf = get_reliable_data(symbol, req_interval, req_period)
        
        if df.empty or len(df) < 20: return None 

        # 3. คำนวณ Indicator
        df.ta.atr(length=14, append=True)
        
        # คำนวณ BB & Stoch (ใช้ได้ทุก Timeframe)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.stoch(append=True)
        df.ta.macd(append=True)
        df.ta.ema(length=50, append=True)
        df.ta.adx(append=True)

        last = df.iloc[-1]
        price = last['Close']
        
        # ถ้าค่าไหนหาไม่ได้ ให้ใช้ค่า Default
        atr = last['ATRr_14'] if pd.notna(last['ATRr_14']) else (price * 0.005)
        ema50 = last['EMA_50'] if pd.notna(last['EMA_50']) else price
        rsi = last['RSI_14'] if 'RSI_14' in last else 50
        
        bias = "SIDEWAY"
        reasons = []
        bull_score = 0
        bear_score = 0

        # ==========================================
        # 🧠 LOGIC: ตัดสินใจ (ใช้ Logic ผสมเพื่อให้รองรับทุก TF)
        # ==========================================
        
        # 1. ดูเทรนด์ (EMA)
        if price > ema50: bull_score += 2
        else: bear_score += 2

        # 2. ดู BB (ของถูก/แพง)
        if 'BBL_20_2.0' in last:
            bb_lower = last['BBL_20_2.0']
            bb_upper = last['BBU_20_2.0']
            if price <= bb_lower * 1.001: bull_score += 3; reasons.append("ราคาชนขอบล่าง (ของถูก)")
            if price >= bb_upper * 0.999: bear_score += 3; reasons.append("ราคาชนขอบบน (ของแพง)")
            
            buy_entry = bb_lower
            sell_entry = bb_upper
        else:
            buy_entry = price - atr
            sell_entry = price + atr

        # 3. ดู MACD (โมเมนตัม)
        if 'MACD_12_26_9' in last:
            if last['MACD_12_26_9'] > last['MACDs_12_26_9']: bull_score += 1
            else: bear_score += 1

        # --- สรุปผล ---
        if bull_score > bear_score:
            bias = "BULLISH"
            action_rec = "🟢 เน้นฝั่ง BUY"
        elif bear_score > bull_score:
            bias = "BEARISH"
            action_rec = "🔴 เน้นฝั่ง SELL"
        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"

        # ป้องกัน Entry ไกลเกิน (Dynamic Adjust)
        if (price - buy_entry) > (atr * 4): buy_entry = price - (atr * 1.5)
        if (sell_entry - price) > (atr * 4): sell_entry = price + (atr * 1.5)

        # คำนวณ SL/TP
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

        # เช็กว่ามีการเปลี่ยน Timeframe หรือไม่
        final_tf_name = tf_name
        if actual_tf != req_interval:
            final_tf_name = f"{tf_name} [ใช้ข้อมูล {actual_tf}]"

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": final_tf_name,
            "trend": bias,
            "action": action_rec,
            "reasons": ", ".join(reasons[:2]),
            "rsi": round(rsi, 2),
            "score": f"{bull_score}-{bear_score}",
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
        reply = (
            f"🏆 **สรุป: {data['action']}**\n"
            f"--------------------\n"
            f"🎯 **แผนเทรด {data['symbol']}**\n"
            f"⚙️ โหมด: {data['tf_name']}\n"
            f"📊 สถานะ: {data['trend']} (Score {data['score']})\n"
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
        return {"reply": "❌ ขออภัยครับ ตลาดปิดหรือข้อมูลมีปัญหาจริงๆ กรุณาลองใหม่ภายหลัง"}

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