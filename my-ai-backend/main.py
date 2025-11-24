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

# --- สมอง AI รุ่น Ultimate (Trend + Score + Setup) ---
def analyze_logic(symbol: str):
    try:
        # 1. ดึงข้อมูล
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", interval="1d")
        if len(df) < 50: return None

        # 2. คำนวณ Indicator
        df.ta.rsi(length=14, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.macd(append=True)
        df.ta.adx(append=True)
        df.ta.atr(length=14, append=True) # เพิ่ม ATR เพื่อคำนวณ SL/TP

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = last['Close']
        rsi = last['RSI_14']
        ema50 = last['EMA_50']
        adx = last['ADX_14']
        atr = last['ATRr_14'] # ค่าความผันผวน
        
        macd_line = last['MACD_12_26_9']
        macd_signal = last['MACDs_12_26_9']

        # 3. ระบบ Scoring
        bull_score = 0
        bear_score = 0

        if price > ema50: bull_score += 2
        else: bear_score += 2

        if macd_line > macd_signal: bull_score += 1
        else: bear_score += 1

        if rsi > 50: bull_score += 1
        else: bear_score += 1

        # 4. คำนวณ Pivot & Setup (Entry / SL / TP)
        pp = (prev['High'] + prev['Low'] + prev['Close']) / 3
        r1 = (2 * pp) - prev['Low']
        s1 = (2 * pp) - prev['High']

        # สูตรคำนวณ SL/TP จาก ATR
        # Buy Setup (เข้าที่แนวรับ)
        buy_entry = s1
        buy_sl = buy_entry - (atr * 1.2)      # SL ต่ำกว่าแนวรับ
        buy_tp = buy_entry + ((buy_entry - buy_sl) * 1.5) # TP 1.5 เท่า

        sell_entry = r1
        sell_sl = sell_entry + (atr * 1.2)    
        sell_tp = sell_entry - ((sell_sl - sell_entry) * 1.5)

        bias = "SIDEWAY"
        action_rec = "รอจังหวะ (Wait)"
        
        if bull_score > bear_score:
            bias = "BULLISH (ขาขึ้น)"
            if rsi > 70: action_rec = "ระวังย่อตัว (Overbought)"
            else: action_rec = "✅ ฝั่ง BUY ได้เปรียบ"
            
        elif bear_score > bull_score:
            bias = "BEARISH (ขาลง)"
            if rsi < 30: action_rec = "ระวังเด้งสวน (Oversold)"
            else: action_rec = "✅ ฝั่ง SELL ได้เปรียบ"

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
            "buy_setup": {
                "entry": round(buy_entry, 2),
                "sl": round(buy_sl, 2),
                "tp": round(buy_tp, 2)
            },
            "sell_setup": {
                "entry": round(sell_entry, 2),
                "sl": round(sell_sl, 2),
                "tp": round(sell_tp, 2)
            }
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
            focus_plan = ""
            if "BUY" in data['action']:
                focus_plan = (
                    f"🟢 **แผนฝั่ง BUY (ตามเทรนด์)**\n"
                    f"   • Entry: ${data['buy_setup']['entry']}\n"
                    f"   • ⛔ SL: ${data['buy_setup']['sl']}\n"
                    f"   • ✅ TP: ${data['buy_setup']['tp']}"
                )
            elif "SELL" in data['action']:
                focus_plan = (
                    f"🔴 **แผนฝั่ง SELL (ตามเทรนด์)**\n"
                    f"   • Entry: ${data['sell_setup']['entry']}\n"
                    f"   • ⛔ SL: ${data['sell_setup']['sl']}\n"
                    f"   • ✅ TP: ${data['sell_setup']['tp']}"
                )
            else:
                focus_plan = (
                    f"🟢 **แผนย่อซื้อ (Buy Limit)**\n"
                    f"   • เข้า: ${data['buy_setup']['entry']} | SL: ${data['buy_setup']['sl']} | TP: ${data['buy_setup']['tp']}\n"
                    f"--------------------\n"
                    f"🔴 **แผนเด้งขาย (Sell Limit)**\n"
                    f"   • เข้า: ${data['sell_setup']['entry']} | SL: ${data['sell_setup']['sl']} | TP: ${data['sell_setup']['tp']}"
                )

            reply = (
                f"💎 **AI Setup: {data['symbol']}**\n"
                f"--------------------\n"
                f"➤ ราคา: ${data['price']} ({data['trend']})\n"
                f"➤ RSI: {data['rsi']} | Score: {data['score']}\n"
                f"📢 สรุป: {data['action']}\n"
                f"--------------------\n"
                f"{focus_plan}\n"
                f"--------------------\n"
                f"*(คำเตือน: SL คำนวณจากความผันผวน ATR)*"
            )
        else: reply = "ขอโทษครับ คำนวณไม่สำเร็จ"
    elif "hello" in msg:
        reply = "ผมคือ AI ส่วนตัวของคุณ สอบถามแผนทอง หรือ แผน BTC ได้เลยครับ"
    else:
        reply = "พิมพ์ 'วิเคราะห์ทอง' หรือ 'แผน BTC' ได้เลยครับ"

    return {"reply": reply}