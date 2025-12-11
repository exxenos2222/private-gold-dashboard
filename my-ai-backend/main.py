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

def get_real_price(symbol):
    try:
        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            return float(data['price'])
            
        elif "BTC" in symbol:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            return float(data['price'])
            
    except Exception as e:
        print(f"Price Fetch Error: {e}")
        
    return None

def get_data_safe(symbol, interval, period):
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

    try:
        fallback_sym = "GC=F" if "GC=F" in symbol or "GOLD" in symbol else symbol
        df = yf.Ticker(fallback_sym).history(period="1mo", interval="60m")
        return df, "H1 (Backup)"
    except:
        return pd.DataFrame(), "Error"

def analyze_dynamic(symbol: str, mode: str):
    try:
        if mode == "scalping":
            req_int = "15m"; req_per = "5d"
            sl_mult = 0.5; tp_mult = 1.5 
            tf_name = "M15 (Scalping)"
            strategy = "trend_follow"
        elif mode == "daytrade":
            req_int = "60m"; req_per = "1mo"
            sl_mult = 0.8; tp_mult = 2.5
            tf_name = "H1 (Daytrade)"
            strategy = "pullback"
        else: 
            req_int = "1d"; req_per = "1y"
            sl_mult = 1.5; tp_mult = 4.0
            tf_name = "D1 (Swing)"
            strategy = "mean_reversion"

        df, actual_tf_label = get_data_safe(symbol, req_int, req_per)
        if df.empty or len(df) < 10: return None 

        last = df.iloc[-1]
        raw_price = last['Close']
        
        real_price = get_real_price(symbol)
        offset = 0
        price = raw_price
        is_calibrated = False
        
        if real_price:
            price = real_price
            if abs(real_price - raw_price) < 5:
                offset = 0
            else:
                offset = real_price - raw_price
                is_calibrated = True
        
        atr = price * 0.005; rsi = 50; ema50 = price; ema200 = price; adx = 25
        stoch_k = 50; stoch_d = 50
        
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
            
            # Stochastic RSI (Momentum Filter)
            df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
            if 'STOCHRSIk_14_14_3_3' in df.columns:
                stoch_k = df['STOCHRSIk_14_14_3_3'].iloc[-1]
                stoch_d = df['STOCHRSId_14_14_3_3'].iloc[-1]
        except: pass

        bullish_ob = None
        bearish_ob = None
        
        try:
            for i in range(len(df)-2, len(df)-50, -1):
                curr = df.iloc[i]
                next_c = df.iloc[i+1]
                
                # Bullish OB: Red Candle -> Green Candle (Engulfing or Strong Move)
                if bullish_ob is None and curr['Close'] < curr['Open']:
                    # Relaxed: Body > 0.5 ATR and Close > Prev High (Strong Rejection)
                    if next_c['Close'] > curr['High'] and (next_c['Close'] - next_c['Open']) > (atr * 0.5):
                        bullish_ob = curr['Low'] + offset
                        
                # Bearish OB: Green Candle -> Red Candle
                if bearish_ob is None and curr['Close'] > curr['Open']:
                    # Relaxed: Body > 0.5 ATR and Close < Prev Low
                    if next_c['Close'] < curr['Low'] and (next_c['Open'] - next_c['Close']) > (atr * 0.5):
                        bearish_ob = curr['High'] + offset
                
                if bullish_ob and bearish_ob: break
        except: pass

        bull_score = 0
        bear_score = 0
        reasons = []

        if price > ema50: bull_score += 2; reasons.append("Price > EMA50")
        else: bear_score += 2; reasons.append("Price < EMA50")

        if rsi > 55: bull_score += 1
        elif rsi < 45: bear_score += 1
        
        if rsi < 30: bull_score += 2; reasons.append("RSI Oversold")
        elif rsi > 70: bear_score += 2; reasons.append("RSI Overbought")
        
        if adx > 25: reasons.append(f"Strong Trend (ADX {int(adx)})")
        else: reasons.append(f"Weak Trend (ADX {int(adx)})")

        if bullish_ob:
            reasons.append(f"Bullish OB Found ({round(bullish_ob, 2)})")
            if abs(price - bullish_ob) < (atr * 2): 
                bull_score += 1; reasons.append("Price Near Bullish OB")
                
        if bearish_ob:
            reasons.append(f"Bearish OB Found ({round(bearish_ob, 2)})")
            if abs(price - bearish_ob) < (atr * 2): 
                bear_score += 1; reasons.append("Price Near Bearish OB")

        if bull_score > bear_score:
            bias = "BULLISH"
            action_rec = "🟢 เน้นฝั่ง BUY"
        elif bear_score > bull_score:
            bias = "BEARISH"
            action_rec = "🔴 เน้นฝั่ง SELL"
        else:
            bias = "SIDEWAY"
            action_rec = "⚠️ รอเลือกทาง"

        buy_entry = price
        sell_entry = price

        if strategy == "trend_follow": # Scalping M15
            if bias.startswith("BULLISH"):
                if bullish_ob and bullish_ob < price:
                    buy_entry = bullish_ob
                elif (price > ema50) and (stoch_k < 20 or rsi < 45):
                    buy_entry = ema50
                elif (price > bb_mid) and (stoch_k < 20 or rsi < 45):
                    buy_entry = bb_mid
                else:
                    # Fallback: Wait for pullback
                    buy_entry = price - (atr * 0.5)

                sell_entry = bb_upper

            elif bias.startswith("BEARISH"):
                # Priority 1: Order Block
                if bearish_ob and bearish_ob > price:
                    sell_entry = bearish_ob
                # Priority 2: EMA50/BB Mid (Only if Momentum is good)
                elif (price < ema50) and (stoch_k > 80 or rsi > 55):
                    sell_entry = ema50
                elif (price < bb_mid) and (stoch_k > 80 or rsi > 55):
                    sell_entry = bb_mid
                else:
                    sell_entry = price + (atr * 0.5)

                buy_entry = bb_lower

            else:
                buy_entry = bb_lower
                sell_entry = bb_upper
                
            if adx < 20: 
                action_rec = "⚠️ ระวัง (ADX ต่ำ)"
                bias = "SIDEWAY (Weak ADX)"

        elif strategy == "pullback": # Daytrade
            if bias == "BULLISH":
                if bullish_ob and abs(bullish_ob - price) < (atr * 3):
                    buy_entry = bullish_ob
                elif price > ema50:
                    buy_entry = ema50
                else:
                    buy_entry = bb_mid
                
                sell_entry = bb_upper

            elif bias == "BEARISH":
                if bearish_ob and abs(bearish_ob - price) < (atr * 3):
                    sell_entry = bearish_ob
                elif price < ema50:
                    sell_entry = ema50
                else:
                    sell_entry = bb_mid
                
                buy_entry = bb_lower

            else:
                buy_entry = bb_lower
                sell_entry = bb_upper

        elif strategy == "mean_reversion": # Swing
            buy_entry = bb_lower
            if bullish_ob and abs(bullish_ob - bb_lower) < atr:
                buy_entry = bullish_ob
            
            sell_entry = bb_upper
            if bearish_ob and abs(bearish_ob - bb_upper) < atr:
                sell_entry = bearish_ob

        if (price - buy_entry) > (atr * 3): buy_entry = price - atr
        if (sell_entry - price) > (atr * 3): sell_entry = price + atr

        if buy_entry >= price: buy_entry = price - (atr * 0.1)
        if sell_entry <= price: sell_entry = price + (atr * 0.1)

        if "GC=F" in symbol or "XAU" in symbol or "GOLD" in symbol:
            max_sl_usd = 5.0
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

        reasoning_text = ""
        if strategy == "trend_follow":
            if bias.startswith("BULLISH"):
                reasoning_text = f"เทรนด์ขาขึ้น (ADX {int(adx)}) "
                if buy_entry == bullish_ob: reasoning_text += f"แนะนำเข้าที่ Order Block ({round(buy_entry, 2)}) "
                elif buy_entry == ema50: reasoning_text += f"แนะนำเข้าที่แนวรับ EMA50 ({round(buy_entry, 2)}) (StochRSI {int(stoch_k)}) "
                elif buy_entry == bb_mid: reasoning_text += f"แนะนำเข้าที่เส้นกลาง BB ({round(buy_entry, 2)}) (StochRSI {int(stoch_k)}) "
                else: reasoning_text += f"แนะนำย่อซื้อที่ {round(buy_entry, 2)} "
            elif bias.startswith("BEARISH"):
                reasoning_text = f"เทรนด์ขาลง (ADX {int(adx)}) "
                if sell_entry == bearish_ob: reasoning_text += f"แนะนำเข้าที่ Order Block ({round(sell_entry, 2)}) "
                elif sell_entry == ema50: reasoning_text += f"แนะนำเข้าที่แนวต้าน EMA50 ({round(sell_entry, 2)}) (StochRSI {int(stoch_k)}) "
                elif sell_entry == bb_mid: reasoning_text += f"แนะนำเข้าที่เส้นกลาง BB ({round(sell_entry, 2)}) (StochRSI {int(stoch_k)}) "
                else: reasoning_text += f"แนะนำเด้งขายที่ {round(sell_entry, 2)} "
            else:
                reasoning_text = f"ตลาด Sideway (ADX {int(adx)}) รอเล่นตามกรอบหรือ Order Block"

        elif strategy == "pullback":
            if bias == "BULLISH":
                reasoning_text = f"แนวโน้มขาขึ้น (Daytrade) "
                if buy_entry == bullish_ob: reasoning_text += f"รอเข้าที่ Order Block ({round(buy_entry, 2)}) "
                elif buy_entry == ema50: reasoning_text += f"รอราคาย่อมาที่ EMA50 ({round(buy_entry, 2)}) "
                else: reasoning_text += f"รอราคาย่อมาที่เส้นกลาง BB ({round(buy_entry, 2)}) "
            elif bias == "BEARISH":
                reasoning_text = f"แนวโน้มขาลง (Daytrade) "
                if sell_entry == bearish_ob: reasoning_text += f"รอเข้าที่ Order Block ({round(sell_entry, 2)}) "
                elif sell_entry == ema50: reasoning_text += f"รอราคาดีดไปที่ EMA50 ({round(sell_entry, 2)}) "
                else: reasoning_text += f"รอราคาดีดไปที่เส้นกลาง BB ({round(sell_entry, 2)}) "
            else:
                reasoning_text = "ตลาดไม่มีเทรนด์ชัดเจน แนะนำให้รอเลือกทาง"

        elif strategy == "mean_reversion":
            reasoning_text = f"กลยุทธ์ Swing Trade "
            if buy_entry == bullish_ob: reasoning_text += f"แนะนำเข้าที่ Bullish OB ({round(buy_entry, 2)}) ซึ่งซ้อนทับกับแนวรับ "
            else: reasoning_text += f"แนะนำรอซื้อที่ขอบล่าง Bollinger Bands ({round(buy_entry, 2)}) "

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
        return {"reply": "❌ การเชื่อมต่อ Server ล้มเหลว"}

@app.get("/analyze/{symbol}")
def analyze_market(symbol: str):
    try:
        target = "GC=F" if "GC=F" in symbol or "GOLD" in symbol else symbol
        ticker = yf.Ticker(target)
        data = ticker.history(period="2d", interval="1h")
        
        real_price = get_real_price(symbol)
        
        if data.empty: return {"symbol": symbol, "price": 0, "change":0, "percent":0}
        
        price = real_price if real_price else data['Close'].iloc[-1]
        prev = data['Close'].iloc[0]
        change = price - prev
        percent = (change / prev) * 100
        
        return {"symbol": symbol, "price": round(price, 2), "change": round(change, 2), "percent": round(percent, 2)}
    except: return {"symbol": symbol, "price": 0}