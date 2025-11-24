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

# --- ฟังก์ชันดึงข้อมูลทองคำแบบ "Spot First" (เอา Spot ขึ้นก่อน) ---
def get_gold_data_smart(interval, period):
    # 1. ลองดึง Spot Gold (XAUUSD=X) ก่อน <-- พระเอกของเรา
    print(f"🔄 Trying Gold Spot (XAUUSD=X) {interval}...")
    df = yf.Ticker("XAUUSD=X").history(period=period, interval=interval)
    
    if len(df) > 25:
        return df, f"{interval} (Spot)"
    
    # 2. ถ้า Spot พัง ค่อยไปลอง Futures (GC=F)
    print(f"⚠️ Spot failed, switching to Futures (GC=F)...")
    df = yf.Ticker("GC=F").history(period=period, interval=interval)
    
    if len(df) > 25:
        return df, f"{interval} (Futures)"
        
    # 3. ถ้าพังหมด ใช้ H1 Spot มาแทน
    print(f"❌ All M15 failed, fallback to H1...")
    df = yf.Ticker("XAUUSD=X").history(period="1mo", interval="60m")
    return df, "H1 (Emergency)"

def analyze_dynamic(symbol: str, mode: str):
    try:
        # 1. Config
        if mode == "scalping":
            req_int = "15m"; req_per = "5d"
            sl_mult = 0.6; tp_mult = 1.2
            tf_name = "M15 (Scalping)"
        elif mode == "daytrade":
            req_int = "60m"; req_per = "1mo"
            sl_mult = 1.5; tp_mult = 2.0
            tf_name = "H1 (Day Trade)"
        else: 
            req_int = "1d"; req_per = "1y"
            sl_mult = 2.5; tp_mult = 3.5
            tf_name = "D1 (Swing)"

        # 2. Get Data
        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
            df, actual_tf_label = get_gold_data_smart(req_int, req_per)
        else:
            # Bitcoin
            df = yf.Ticker(symbol).history(period=req_per, interval=req_int)
            actual_tf_label = req_int
            if len(df) < 25: 
                df = yf.Ticker(symbol).history(period="1mo", interval="60m")
                actual_tf_label = "H1 (Backup)"

        if df.empty: return None

        # 3. Indicators
        try:
            df.ta.atr(length=14, append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.ema(length=50, append=True)
            df.ta.bbands(length=20, std=2, append=True)
            df.ta.macd(append=True)
        except: pass

        last = df.iloc[-1]
        price = last['Close']
        
        atr = last['ATRr_14'] if 'ATRr_14' in last and pd.notna(last['ATRr_14']) else (price * 0.005)
        rsi = last['RSI_14'] if 'RSI_14' in last and pd.notna(last['RSI_14']) else 50
        ema50 = last['EMA_50'] if 'EMA_50' in last and pd.notna(last['EMA_50']) else price

        # 4. Scoring
        bull_score = 0
        bear_score = 0
        reasons = []

        # Trend
        if price > ema50: bull_score += 2; reasons.append("ราคา > EMA50")
        else: bear_score += 2; reasons.append("ราคา < EMA50")

        # BB Entry
        if 'BBL_20_2.0' in last and pd.notna(last['BBL_20_2.0']):
            bb_lower = last['BBL_20_2.0']
            bb_upper = last['BBU_20_2.0']
            if price <= bb_lower * 1.001: bull_score += 3; reasons.append("ชนขอบล่าง BB")
            if price >= bb_upper * 0.999: bear_score += 3; reasons.append("ชนขอบบน BB")
            
            buy_entry = bb_lower
            sell_entry = bb_upper
        else:
            buy_entry = price - (atr * 0.5)
            sell_entry = price + (atr * 0.5)

        # RSI
        if rsi < 30: bull_score += 1; reasons.append("RSI Oversold")
        if rsi > 70: bear_score += 1; reasons.append("RSI Overbought")

        # 5. Verdict
        if bull_score > bear_score:
            bias = "BULLISH"
            action_rec = "🟢 เน้นฝั่ง BUY"
        elif bear_score > bull_score:
            bias = "BEARISH"
            action_rec = "🔴 เน้นฝั่ง SELL"
        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"

        # Dynamic Entry Adjust
        if (price - buy_entry) > (atr * 3): buy_entry = price - (atr * 1.0)
        if (sell_entry - price) > (atr * 3): sell_entry = price + (atr * 1.0)

        # SL/TP Calculation
        buy_sl = buy_entry - (atr * sl_mult)
        buy_tp = buy_entry + (atr * tp_mult)
        sell_sl = sell_entry + (atr * sl_mult)
        sell_tp = sell_entry - (atr * tp_mult)

        pips_scale = 10000 
        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol: pips_scale = 100 
        if "BTC" in symbol: pips_scale = 1

        buy_pips = int((buy_entry - buy_sl) * pips_scale)
        sell_pips = int((sell_sl - sell_entry) * pips_scale)

        display_tf = tf_name
        if "Futures" in actual_tf_label: display_tf += " [Futures]"
        elif "Backup" in actual_tf_label or "Emergency" in actual_tf_label: display_tf = "H1 (Backup Data)"

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": display_tf,
            "trend": bias,
            "action": action_rec,
            "reasons": ", ".join(reasons),
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
    target = req.symbol # รับ GOLD หรือ BITCOIN มาตรงๆ เลย แล้วไปจัดการใน analyze_dynamic
    
    data = analyze_dynamic(target, req.mode)
    
    if data:
        reply = (
            f"🏆 **สรุป: {data['action']}**\n"
            f"--------------------\n"
            f"🎯 **แผนเทรด {data['symbol']}**\n"
            f"⚙️ โหมด: {data['tf_name']}\n"
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
        return {"reply": "❌ ระบบ Data ขัดข้อง กรุณาลองใหม่อีกครั้ง"}

@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    # Dashboard ใช้ Spot Gold เสมอ
    target = "XAUUSD=X" if "GC=F" in symbol or "GOLD" in symbol else symbol
    try:
        ticker = yf.Ticker(target)
        data = ticker.history(period="2d", interval="1h")
        if data.empty: return {"symbol": symbol, "price": 0, "change":0, "percent":0}
        price = data['Close'].iloc[-1]
        prev = data['Close'].iloc[0]
        change = price - prev
        percent = (change / prev) * 100
        return {"symbol": symbol, "price": round(price, 2), "change": round(change, 2), "percent": round(percent, 2)}
    except: return {"symbol": symbol, "price": 0}