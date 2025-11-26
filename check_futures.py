import yfinance as yf

def check_futures():
    print("--- Checking Futures ---")
    try:
        df = yf.Ticker("GC=F").history(period="1d", interval="1m")
        if not df.empty:
            print(f"Yahoo GC=F: {df['Close'].iloc[-1]} (Time: {df.index[-1]})")
        else:
            print("Yahoo GC=F: No Data")
    except Exception as e:
        print(f"Error: {e}")

check_futures()
