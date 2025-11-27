from main import analyze_dynamic

def test_sl_cap():
    print("--- Testing SL Cap Logic ---")
    
    # Test Daytrade (Max $10)
    print("\nTesting Daytrade (Max $10)...")
    result = analyze_dynamic("GC=F", "daytrade")
    if result:
        buy_entry = result['buy_setup']['entry']
        buy_sl = result['buy_setup']['sl']
        diff = buy_entry - buy_sl
        print(f"Buy Entry: {buy_entry}")
        print(f"Buy SL: {buy_sl}")
        print(f"Diff: {diff:.2f}")
        if diff <= 10.1: # Allow small float error
            print("✅ Daytrade SL Cap Passed")
        else:
            print("❌ Daytrade SL Cap Failed")
    else:
        print("❌ No Result")

    # Test Scalping (Max $5)
    print("\nTesting Scalping (Max $5)...")
    result = analyze_dynamic("GC=F", "scalping")
    if result:
        buy_entry = result['buy_setup']['entry']
        buy_sl = result['buy_setup']['sl']
        diff = buy_entry - buy_sl
        print(f"Buy Entry: {buy_entry}")
        print(f"Buy SL: {buy_sl}")
        print(f"Diff: {diff:.2f}")
        if diff <= 5.1:
            print("✅ Scalping SL Cap Passed")
        else:
            print("❌ Scalping SL Cap Failed")

if __name__ == "__main__":
    test_sl_cap()
