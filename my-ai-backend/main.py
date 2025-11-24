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

def analyze_logic(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", interval="1d")
        if len(df) < 50: return None

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
        macd_line = last['MACD_12_26_9']
        macd_signal = last['MACDs_12_26_9']

        bull_score = 0 
        bear_score = 0  

        if price > ema50: bull_score += 2
        else: bear_score += 2

        if macd_line > macd_signal: bull_score += 1
        else: bear_score += 1

        if rsi > 50: bull_score += 1
        else: bear_score += 1

        bias = "SIDEWAY (เลือกทาง)"
        action_rec = "รอจังหวะ (Wait)"
        
        if bull_score > bear_score:
            bias = "BULLISH (ขาขึ้น)"
            if rsi > 70: action_rec = "ฝั่ง BUY ได้เปรียบ (แต่ระวังย่อตัว)"
            else: action_rec = "✅ เน้นฝั่ง BUY (ซื้อ) ได้เปรียบกว่า"
            
        elif bear_score > bull_score:
            bias = "BEARISH (ขาลง)"
            if rsi < 30: action_rec = "ฝั่ง SELL ได้เปรียบ (แต่ระวังเด้งสวน)"
            else: action_rec = "✅ เน้นฝั่ง SELL (ขาย) ได้เปรียบกว่า"

        pp = (prev['High'] + prev['Low'] + prev['Close']) / 3
        r1 = (2 * pp) - prev['Low']
        s1 = (2 * pp) - prev['High']

        change = price - prev['Close']
        percent = (change / prev['Close']) * 100

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change, 2),
            "percent": round(percent, 2),
            "trend": bias,             
            "action": action_rec,      
            "score": f"{bull_score} vs {bear_score}",
            "rsi": round(rsi, 2),
            "support": round(s1, 2),
            "resistance": round(r1, 2)
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
                f"🥊 **ผลชี้ขาด AI ({data['symbol']})**\n"
                f"--------------------\n"
                f"➤ ราคา: ${data['price']}\n"
                f"➤ ทิศทาง: {data['trend']}\n"
                f"➤ คะแนนกระทิง vs หมี: {data['score']}\n"
                f"--------------------\n"
                f"📢 **คำแนะนำ:** {data['action']}\n"
                f"--------------------\n"
                f"🎯 **แผนเข้าออเดอร์**\n"
                f"🔴 Sell Limit: ${data['resistance']}\n"
                f"🟢 Buy Limit: ${data['support']}"
            )
        else: reply = "ขอโทษครับ คำนวณผิดพลาด"
    elif "hello" in msg:
        reply = "สอบถามแผนทอง หรือ แผน BTC ได้เลยครับ"
    else:
        reply = "ถามเรื่อง 'วิเคราะห์ทอง' หรือ 'แผนเทรด' ได้เลยครับ"

    return {"reply": reply}