import yfinance as yf
import requests
import time

def check_prices():
    print("--- Price Debug ---")
    
    try:
        ticker = yf.Ticker("GC=F")
        fast_price = ticker.fast_info.get('last_price')
        reg_price = ticker.info.get('regularMarketPrice')
        hist = ticker.history(period="1d", interval="1m")
        hist_price = hist['Close'].iloc[-1] if not hist.empty else None
        
        print(f"Yahoo (GC=F) Fast Info: {fast_price}")
        print(f"Yahoo (GC=F) Regular: {reg_price}")
        print(f"Yahoo (GC=F) History Last: {hist_price}")
    except Exception as e:
        print(f"Yahoo Error: {e}")

    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"
        resp = requests.get(url, timeout=5)
        binance_price = float(resp.json()['price'])
        print(f"Binance (PAXGUSDT): {binance_price}")
    except Exception as e:
        print(f"Binance Error: {e}")

if __name__ == "__main__":
    check_prices()
