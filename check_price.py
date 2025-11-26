import yfinance as yf
import requests
import time

def check_prices():
    print("--- Checking Prices ---")
    
    # 1. Yahoo XAUUSD=X
    try:
        df = yf.Ticker("XAUUSD=X").history(period="1d", interval="1m")
        if not df.empty:
            yahoo_price = df['Close'].iloc[-1]
            yahoo_time = df.index[-1]
            print(f"Yahoo XAUUSD=X: {yahoo_price} (Time: {yahoo_time})")
        else:
            print("Yahoo XAUUSD=X: No Data")
    except Exception as e:
        print(f"Yahoo Error: {e}")

    # 2. Binance PAXGUSDT
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        binance_price = float(data['price'])
        print(f"Binance PAXGUSDT: {binance_price}")
    except Exception as e:
        print(f"Binance Error: {e}")

check_prices()
