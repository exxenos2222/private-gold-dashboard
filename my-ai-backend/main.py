from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests

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

# --- 1. Get Real-time Price (Spot) ---
def get_real_price(symbol):
    try:
        # Gold: Use PAXG/USDT from Binance (Spot Price)
        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            return float(data['price'])
            
        # Bitcoin: Use BTC/USDT from Binance
        elif "BTC" in symbol:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            return float(data['price'])
            
    except Exception as e:
        print(f"Binance Price Error: {e}")
        
    return None

# --- 2. Get Historical Data (Chart Shape) ---
def get_data_safe(symbol, interval, period):
    # For Gold, prioritize Futures (GC=F) for chart shape as XAUUSD=X is unreliable
    if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
        try:
            df = yf.Ticker("GC=F").history(period=period, interval=interval)
            if len(df) > 15: return df, f"{interval} (Futures)"
        except: pass
    else:
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if len(df) > 15: return df, interval
        except: pass

    # Fallback
    try:
        fallback_sym = "GC=F" if "GC=F" in symbol or "GOLD" in symbol else symbol
        df = yf.Ticker(fallback_sym).history(period="1mo", interval="60m")
        return df, "H1 (Backup)"
    except:
        return pd.DataFrame(), "Error"

# --- 3. Analyze Logic ---
def analyze_dynamic(symbol: str, mode: str):
    try:
        # Config & Strategy Selection
        if mode == "scalping":
            # Scalping: M15, Trend Following
            req_int = "15m"; req_per = "5d"
            sl_mult = 0.5; tp_mult = 1.5 
            tf_name = "M15 (Scalping)"
            strategy = "trend_follow"
        elif mode == "daytrade":
            # Daytrade: H1, Pullback/Breakout
            req_int = "60m"; req_per = "1mo"
            sl_mult = 0.8; tp_mult = 2.5
            tf_name = "H1 (Daytrade)"
            strategy = "pullback"
        else: 
            # Swing: D1, Mean Reversion/Trend
            req_int = "1d"; req_per = "1y"
            sl_mult = 1.5; tp_mult = 4.0
            tf_name = "D1 (Swing)"
            strategy = "mean_reversion"

        # Get Data
        df, actual_tf_label = get_data_safe(symbol, req_int, req_per)
        if df.empty or len(df) < 10: return None 

        last = df.iloc[-1]
        raw_price = last['Close']
        
        # Get Real Price & Calculate Offset
        real_price = get_real_price(symbol)
        offset = 0
        price = raw_price
        is_calibrated = False
        
        if real_price:
            price = real_price
            offset = real_price - raw_price
            is_calibrated = True
        
        # Indicators Calculation (Apply Offset)
        atr = price * 0.005; rsi = 50; ema50 = price; ema200 = price; adx = 25
        
        try: 
            df.ta.atr(length=14, append=True)
            if pd.notna(df['ATRr_14'].iloc[-1]): atr = df['ATRr_14'].iloc[-1]
            
            df.ta.rsi(length=14, append=True)
            if pd.notna(df['RSI_14'].iloc[-1]): rsi = df['RSI_14'].iloc[-1]
            
            df.ta.adx(length=14, append=True)
            if pd.notna(df['ADX_14'].iloc[-1]): adx = df['ADX_14'].iloc[-1]
            
            df.ta.ema(length=50, append=True)
            if pd.notna(df['EMA_50'].iloc[-1]): ema50 = df['EMA_50'].iloc[-1] + offset

            df.ta.ema(length=200, append=True)
            if pd.notna(df['EMA_200'].iloc[-1]): ema200 = df['EMA_200'].iloc[-1] + offset
            
            df.ta.bbands(length=20, std=2, append=True)
            bb_lower = df['BBL_20_2.0'].iloc[-1] + offset if 'BBL_20_2.0' in df.columns else price - atr
            bb_upper = df['BBU_20_2.0'].iloc[-1] + offset if 'BBU_20_2.0' in df.columns else price + atr
            bb_mid = df['BBM_20_2.0'].iloc[-1] + offset if 'BBM_20_2.0' in df.columns else price
        except: pass

        # --- Order Block Detection (Simplified) ---
        bullish_ob = None
        bearish_ob = None
        
        try:
            # Look back 50 candles for the most recent OB
            for i in range(len(df)-2, len(df)-50, -1):
                curr = df.iloc[i]
                next_c = df.iloc[i+1]
                
                # Bullish OB: Red candle followed by strong Green move
                if bullish_ob is None and curr['Close'] < curr['Open']: # Red
                    if next_c['Close'] > curr['Open'] and (next_c['Close'] - next_c['Open']) > atr: # Strong Green engulfing
                        bullish_ob = curr['Low'] + offset # Use Low of OB as zone
                        
                # Bearish OB: Green candle followed by strong Red move
                if bearish_ob is None and curr['Close'] > curr['Open']: # Green
                    if next_c['Close'] < curr['Open'] and (next_c['Open'] - next_c['Close']) > atr: # Strong Red engulfing
                        bearish_ob = curr['High'] + offset # Use High of OB as zone
                
                if bullish_ob and bearish_ob: break
        except: pass

        # Trend Determination
        bull_score = 0
        bear_score = 0
        reasons = []

        # 1. EMA Trend
        if price > ema50: bull_score += 2; reasons.append("Price > EMA50")
        else: bear_score += 2; reasons.append("Price < EMA50")

        # 2. RSI Momentum
        if rsi > 55: bull_score += 1
        elif rsi < 45: bear_score += 1
        
        if rsi < 30: bull_score += 2; reasons.append("RSI Oversold")
        elif rsi > 70: bear_score += 2; reasons.append("RSI Overbought")
        
        # 3. ADX Trend Strength
        if adx > 25: reasons.append(f"Strong Trend (ADX {int(adx)})")
        else: reasons.append(f"Weak Trend (ADX {int(adx)})")

        # 4. Order Block Confluence
        if bullish_ob and abs(price - bullish_ob) < (atr * 2): 
            bull_score += 1; reasons.append("Near Bullish OB")
        if bearish_ob and abs(price - bearish_ob) < (atr * 2): 
            bear_score += 1; reasons.append("Near Bearish OB")

        # Verdict
        if bull_score > bear_score:
            bias = "BULLISH"
            action_rec = "🟢 เน้นฝั่ง BUY"
        elif bear_score > bull_score:
            bias = "BEARISH"
            action_rec = "🔴 เน้นฝั่ง SELL"
        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"

        # Entry Logic
        buy_entry = price
        sell_entry = price

        if strategy == "trend_follow": # Scalping
            if bias.startswith("BULLISH"):
                buy_entry = price - (atr * 0.2)
                if bullish_ob and bullish_ob < price: buy_entry = bullish_ob # Prefer OB entry
                sell_entry = bb_upper
            elif bias.startswith("BEARISH"):
                sell_entry = price + (atr * 0.2)
                if bearish_ob and bearish_ob > price: sell_entry = bearish_ob # Prefer OB entry
                buy_entry = bb_lower
            else:
                buy_entry = bb_lower
                sell_entry = bb_upper
                
            # ADX Filter for Scalping
            if adx < 20: 
                action_rec = "⚠️ ระวัง (ADX ต่ำ)"
                bias = "SIDEWAY (Weak ADX)"

        elif strategy == "pullback": # Daytrade
            if bias == "BULLISH":
                buy_entry = max(ema50, bb_mid)
                if bullish_ob and abs(bullish_ob - price) < (atr * 3): buy_entry = bullish_ob # Smart OB Entry
                sell_entry = bb_upper
            elif bias == "BEARISH":
                sell_entry = min(ema50, bb_mid)
                if bearish_ob and abs(bearish_ob - price) < (atr * 3): sell_entry = bearish_ob # Smart OB Entry
                buy_entry = bb_lower
            else:
                buy_entry = bb_lower
                sell_entry = bb_upper

        elif strategy == "mean_reversion": # Swing
            buy_entry = bb_lower
            if bullish_ob: buy_entry = bullish_ob
            sell_entry = bb_upper
            if bearish_ob: sell_entry = bearish_ob

        # Safety
        if (price - buy_entry) > (atr * 3): buy_entry = price - atr
        if (sell_entry - price) > (atr * 3): sell_entry = price + atr

        if buy_entry >= price: buy_entry = price - (atr * 0.1)
        if sell_entry <= price: sell_entry = price + (atr * 0.1)

        # TP/SL Calculation with Safety Cap
        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
            max_sl_usd = 5.0 # Default
            if mode == "scalping": max_sl_usd = 5.0
            elif mode == "daytrade": max_sl_usd = 10.0
            elif mode == "swing": max_sl_usd = 25.0
            
            current_sl_dist = atr * sl_mult
            if current_sl_dist > max_sl_usd:
                sl_dist = max_sl_usd
            else:
                sl_dist = current_sl_dist
        else:
            sl_dist = atr * sl_mult

        buy_sl = buy_entry - sl_dist
        buy_tp = buy_entry + (sl_dist * (tp_mult/sl_mult))
        
        sell_sl = sell_entry + sl_dist
        sell_tp = sell_entry - (sl_dist * (tp_mult/sl_mult))

        pips_scale = 10000 
        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol: pips_scale = 100 
        if "BTC" in symbol: pips_scale = 1

        final_tf_name = actual_tf_label
        if is_calibrated: final_tf_name += " ⚡(Real-time)"

        # Reasoning Logic
        reasoning_text = ""
        if strategy == "trend_follow":
            if bias.startswith("BULLISH"):
                reasoning_text = f"เทรนด์ขาขึ้น (ADX {int(adx)}) "
                if bullish_ob: reasoning_text += f"พบ Bullish Order Block ที่ {round(bullish_ob, 2)} เป็นแนวรับสำคัญ "
                reasoning_text += f"แนะนำย่อซื้อที่ {round(buy_entry, 2)}"
            elif bias.startswith("BEARISH"):
                reasoning_text = f"เทรนด์ขาลง (ADX {int(adx)}) "
                if bearish_ob: reasoning_text += f"พบ Bearish Order Block ที่ {round(bearish_ob, 2)} เป็นแนวต้านสำคัญ "
                reasoning_text += f"แนะนำเด้งขายที่ {round(sell_entry, 2)}"
            else:
                reasoning_text = f"ตลาด Sideway (ADX {int(adx)}) รอเล่นตามกรอบหรือ Order Block"

        elif strategy == "pullback":
            if bias == "BULLISH":
                reasoning_text = f"แนวโน้มขาขึ้น รอราคาย่อตัว "
                if bullish_ob: reasoning_text += f"มาที่โซน Order Block ({round(bullish_ob, 2)}) "
                else: reasoning_text += f"มาที่แนวรับ EMA50 ({round(buy_entry, 2)}) "
                reasoning_text += "แล้วเข้าซื้อเพื่อความได้เปรียบ"
            elif bias == "BEARISH":
                reasoning_text = f"แนวโน้มขาลง รอราคาดีดตัว "
                if bearish_ob: reasoning_text += f"ไปที่โซน Order Block ({round(bearish_ob, 2)}) "
                else: reasoning_text += f"ไปที่แนวต้าน EMA50 ({round(sell_entry, 2)}) "
                reasoning_text += "แล้วเปิดสถานะขาย"
            else:
                reasoning_text = "ตลาดไม่มีเทรนด์ชัดเจน แนะนำให้รอเลือกทาง"

        elif strategy == "mean_reversion":
            reasoning_text = f"กลยุทธ์ Swing Trade เน้นซื้อขายที่กรอบราคา "
            if bullish_ob: reasoning_text += f"โดยมี Bullish OB ที่ {round(bullish_ob, 2)} เป็นจุดเข้าซื้อที่น่าสนใจ"
            else: reasoning_text += f"โดยรอซื้อที่ขอบล่าง Bollinger Bands"

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "tf_name": final_tf_name,
            "trend": bias,
            "action": action_rec,
            "reasons": ", ".join(reasons[:3]),
            "reasoning_text": reasoning_text,
            "rsi": round(rsi, 2),
            "score": f"{bull_score}-{bear_score}",
            "buy_setup": {"entry": round(buy_entry, 2), "sl": round(buy_sl, 2), "tp": round(buy_tp, 2), "pips": int((buy_entry - buy_sl) * pips_scale)},
            "sell_setup": {"entry": round(sell_entry, 2), "sl": round(sell_sl, 2), "tp": round(sell_tp, 2), "pips": int((sell_sl - sell_entry) * pips_scale)}
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return None

@app.post("/analyze_custom")
def analyze_custom(req: AnalysisRequest):
    target = req.symbol
    data = analyze_dynamic(target, req.mode)
    
    if data:
        reply = (
            f"🏆 **สรุป: {data['action']}**\n"
            f"--------------------\n"
            f"💡 **เหตุผล:** {data['reasoning_text']}\n"
            f"--------------------\n"
            f"🎯 **แผนเทรด {data['symbol']}**\n"
            f"⚙️ ข้อมูล: {data['tf_name']}\n"
            f"💰 **ราคา: ${data['price']}**\n"
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
        return {"reply": "❌ ข้อมูลไม่พร้อมใช้งาน"}

@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    try:
        # Use GC=F for basic price check if XAU is requested, but prioritize Real Price logic if possible
        # For simple ticker, just get GC=F
        target = "GC=F" if "GC=F" in symbol or "GOLD" in symbol else symbol
        ticker = yf.Ticker(target)
        data = ticker.history(period="2d", interval="1h")
        
        # Try to get real price for display
        real_price = get_real_price(symbol)
        
        if data.empty: return {"symbol": symbol, "price": 0, "change":0, "percent":0}
        
        price = real_price if real_price else data['Close'].iloc[-1]
        prev = data['Close'].iloc[0]
        change = price - prev
        percent = (change / prev) * 100
        
        return {"symbol": symbol, "price": round(price, 2), "change": round(change, 2), "percent": round(percent, 2)}
    except: return {"symbol": symbol, "price": 0}