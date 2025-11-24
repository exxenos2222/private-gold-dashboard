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
        df = ticker.history(period="6mo", interval="1d")
        
        if len(df) < 14: return None

        df.ta.rsi(length=14, append=True)
        df.ta.ema(length=50, append=True)

        current_price = df['Close'].iloc[-1]
        rsi = df['RSI_14'].iloc[-1]
        ema50 = df['EMA_50'].iloc[-1]
        
        prev_high = df['High'].iloc[-2]
        prev_low = df['Low'].iloc[-2]
        prev_close = df['Close'].iloc[-2]

        pp = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pp) - prev_low  
        s1 = (2 * pp) - prev_high 

        trend = "UP (ขาขึ้น)" if current_price > ema50 else "DOWN (ขาลง)"
        
        suggestion = "WAIT"
        if rsi > 70:
            suggestion = "ระวังแรงขาย! (Overbought)"
        elif rsi < 30:
            suggestion = "หาจังหวะเข้าซื้อ (Oversold)"
        else:
            if current_price > ema50:
                suggestion = "ย่อซื้อที่แนวรับ (Buy on Dip)"
            else:
                suggestion = "เด้งขายที่แนวต้าน (Sell on Rally)"

        
        change = current_price - df['Close'].iloc[-2]
        percent = (change / df['Close'].iloc[-2]) * 100

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "change": round(change, 2),
            "percent": round(percent, 2),
            "trend": trend,
            "rsi": round(rsi, 2),
            "suggestion": suggestion,
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
    
    target_symbol = None
    if "gold" in msg or "ทอง" in msg: target_symbol = "GC=F"
    elif "btc" in msg or "bitcoin" in msg: target_symbol = "BTC-USD"

    if target_symbol:
        data = analyze_logic(target_symbol)
        if data:
            reply = (
                f"🤖 **วิเคราะห์ {data['symbol']}**\n"
                f"--------------------\n"
                f"➤ ราคา: ${data['price']}\n"
                f"➤ เทรนด์: {data['trend']}\n"
                f"➤ RSI: {data['rsi']}\n"
                f"--------------------\n"
                f"🎯 **แผนการเทรด (Limit Order)**\n"
                f"🔴 Sell Limit (ต้าน): ${data['resistance']}\n"
                f"🟢 Buy Limit (รับ): ${data['support']}\n"
                f"--------------------\n"
                f"💡 **แนะนำ:** {data['suggestion']}"
            )
        else:
            reply = "ดึงข้อมูลผิดพลาด ลองใหม่นะครับ"
            
    elif "hello" in msg or "สวัสดี" in msg:
        reply = "อยากสอบถามแผนการเทรดอะไรดี แผนทอง หรือ แผน BTC"
    else:
        reply = "ขอโทษครับ ผมยังไม่เข้าใจคำถาม ลองถามเกี่ยวกับทองคำหรือ Bitcoin "

    return {"reply": reply}