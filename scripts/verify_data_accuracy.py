"""Verify A-share data accuracy — MA5 correctness proof.

Run: python scripts/verify_data_accuracy.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime


def verify(symbol: str = "600519") -> bool:
    print(f"\n{'='*60}")
    print(f"  数据准确性验证 — {symbol} (前复权 qfq)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # 1. Purge old cache (dirty hfq data from previous runs)
    from src.data.market_data import clear_cache, get_kline, calc_ma
    import akshare as ak

    clear_cache()
    print("[1] 已清除旧缓存（防止hfq脏数据污染）\n")

    # 2. Fetch via akShare directly (manual ground truth)
    print("[2] 手动取数 (akshare stock_zh_a_hist, qfq)...")
    raw = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
    raw = raw.sort_values("日期")
    closes_raw = raw["收盘"].astype(float).tolist()
    ma5_manual = sum(closes_raw[-5:]) / 5
    latest_close = closes_raw[-1]
    dates_raw = raw["日期"].tolist()

    print(f"    最近5个交易日收盘价(qfq):")
    for i in range(5):
        idx = -(5 - i)
        print(f"      {dates_raw[idx]}: {closes_raw[idx]:.2f}")

    # 3. Fetch via our unified layer
    print(f"\n[3] 程序取数 (get_kline, qfq)...")
    df_proj = get_kline(symbol, adjust="qfq", include_today_intraday=False)
    closes_proj = df_proj["close"].tolist()
    ma5_proj = float(calc_ma(df_proj, 5).iloc[-1])
    dates_proj = df_proj["date"].tolist()

    print(f"    程序最近5个收盘价:")
    for i in range(5):
        idx = -(5 - i)
        d = dates_proj[idx]
        c = closes_proj[idx]
        print(f"      {d}: {c:.2f}")

    # 4. Compare
    print(f"\n{'='*60}")
    print(f"  验证结果")
    print(f"{'='*60}")
    print(f"  最新收盘价 (akshare) : {latest_close:>10.2f}")
    print(f"  最新收盘价 (程序)   : {closes_proj[-1]:>10.2f}")
    print(f"  手算 MA5            : {ma5_manual:>10.2f}")
    print(f"  程序 MA5            : {ma5_proj:>10.2f}")

    diff = abs(ma5_manual - ma5_proj)

    all_ok = True

    # Check 1: MA5 program vs manual
    if diff < 0.5:
        print(f"  ✅ MA5 程序值 vs 手算值一致 (差={diff:.4f})")
    else:
        print(f"  ❌ MA5 不一致 (差={diff:.4f})")
        all_ok = False

    # Check 2: reasonable range
    if 900 < ma5_proj < 1500:
        print(f"  ✅ MA5 量级合理 ({ma5_proj:.2f}，茅台应~1250)")
    else:
        print(f"  ❌ MA5 量级异常 ({ma5_proj:.2f}，疑似仍为hfq污染)")
        all_ok = False

    # Check 3: not absurdly high
    if ma5_proj < 2000:
        print(f"  ✅ MA5 < 2000（排除hfq极端值）")
    else:
        print(f"  ❌ MA5 > 2000（hfq污染！同花顺前复权应~1250）")
        all_ok = False

    print(f"\n  {'✅ 全部通过' if all_ok else '❌ 存在失败项'}")
    print(f"  复权方式: 前复权(qfq)，与同花顺/东方财富默认一致")
    return all_ok


if __name__ == "__main__":
    try:
        ok = verify("600519")
    except Exception as e:
        print(f"\n❌ 验证异常: {e}")
        import traceback
        traceback.print_exc()
        ok = False
    sys.exit(0 if ok else 1)
