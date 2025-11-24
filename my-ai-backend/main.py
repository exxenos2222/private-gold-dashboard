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

class ChatMessage(BaseModel):
    message: str

# --- สมอง AI รุ่นอัปเกรด (Smart Filter + Trading Plan) ---
def analyze_logic(symbol: str):
    try:
        # 1. ดึงข้อมูล (1 ปี)
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", interval="1d")
        
        if len(df) < 50: return None

        # 2. คำนวณ Indicator
        df.ta.rsi(length=14, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.macd(append=True)
        df.ta.adx(append=True)

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = last['Close']
        rsi = last['RSI_14']
        ema50 = last['EMA_50']
        adx = last['ADX_14']
        
        # MACD
        macd_line = last['MACD_12_26_9']
        macd_signal = last['MACDs_12_26_9']

        # 3. คำนวณ Pivot Points (เอามาทำ Buy/Sell Limit)
        pp = (prev['High'] + prev['Low'] + prev['Close']) / 3
        r1 = (2 * pp) - prev['Low']
        s1 = (2 * pp) - prev['High']

        # 4. Logic การตัดสินใจ
        trend = "UP 🟢" if price > ema50 else "DOWN 🔴"
        
        trend_strength = "Weak (ไซด์เวย์)"
        if adx > 25: trend_strength = "Strong (แรง)"
        if adx > 50: trend_strength = "Very Strong (แรงจัด)"

        suggestion = "WAIT (รอดูท่าที)"
        
        if price > ema50: # ขาขึ้น
            if macd_line > macd_signal and rsi < 70:
                suggestion = "BUY SIGNAL (ตามน้ำ) 🚀"
            elif rsi > 70:
                suggestion = "ระวังแรงขาย (Overbought) ⚠️"
            elif adx < 20:
                suggestion = "ตลาดนิ่ง ระวังโดนหลอก"
        else: # ขาลง
            if macd_line < macd_signal and rsi > 30:
                suggestion = "SELL SIGNAL (ทุบ) 📉"
            elif rsi < 30:
                suggestion = "ระวังเด้งสวน (Oversold) ⚠️"
            elif adx < 20:
                suggestion = "ตลาดนิ่ง ระวังโดนหลอก"

        change = price - prev['Close']
        percent = (change / prev['Close']) * 100

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change, 2),
            "percent": round(percent, 2),
            "trend": trend,
            "strength": trend_strength,
            "rsi": round(rsi, 2),
            "macd": "Bullish" if macd_line > macd_signal else "Bearish",
            "suggestion": suggestion,
            "support": round(s1, 2),     # ค่า Buy Limit
            "resistance": round(r1, 2)   # ค่า Sell Limit
        }

    except Exception as e:
        print(f"Error: {e}")
        return None

@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    target = "GC=F" if "XAU" in symbol or "Gold" in symbol else symbol
    target = "BTC-USD" if "BTC" in symbol else target
    result = analyze_logic(target)
    if result: return result
    return {"symbol": symbol, "price": 0, "trend": "Error"}

@app.post("/chat")
def chat_with_ai(req: ChatMessage):
    msg = req.message.lower()
    target = None
    if "gold" in msg or "ทอง" in msg: target = "GC=F"
    elif "btc" in msg or "bitcoin" in msg: target = "BTC-USD"

    if target:
        data = analyze_logic(target)
        if data:
            reply = (
                f"🧠 **AI Analysis V2.0 ({data['symbol']})**\n"
                f"--------------------\n"
                f"➤ ราคา: ${data['price']}\n"
                f"➤ เทรนด์: {data['trend']} (ความแรง: {data['strength']})\n"
                f"➤ RSI: {data['rsi']} | MACD: {data['macd']}\n"
                f"--------------------\n"
                f"🎯 **แผนการเทรด (Limit Order)**\n"
                f"🔴 Sell Limit (ต้าน): ${data['resistance']}\n"
                f"🟢 Buy Limit (รับ): ${data['support']}\n"
                f"--------------------\n"
                f"💡 **AI แนะนำ:** {data['suggestion']}"
            )
        else: reply = "ขอโทษครับ คำนวณไม่สำเร็จ"
    elif "hello" in msg:
        reply = "สวัสดีครับ! ผมพร้อมวิเคราะห์ทองแบบเจาะลึก + วางแผน Limit Order ให้แล้วครับ"
    else:
        reply = "ถามเรื่อง 'วิเคราะห์ทอง' หรือ 'แผนเทรด' ได้เลยครับ"

    return {"reply": reply}