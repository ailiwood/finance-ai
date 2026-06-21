"""Verify A-share data accuracy — confirm qfq adjustment is correct.

Run: python scripts/verify_data_accuracy.py

Validates that:
1. MA5 calculated from program data matches manual calculation
2. MA5 value falls in reasonable range (~1250 for 茅台 600519)
3. Forward adjustment (qfq) is consistently applied
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import akshare as ak
import pandas as pd

# Import our unified data layer
from src.data.market_data import get_kline, calc_ma


def verify(symbol: str = "600519") -> bool:
    """Verify MA5 accuracy for a given stock symbol."""
    print(f"\n{'='*60}")
    print(f"  验证 {symbol} 数据正确性（前复权 qfq）")
    print(f"{'='*60}\n")

    # ── Manual calculation ──
    print("[1] 手动取数 (akshare direct, qfq)...")
    df_raw = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
    df_raw = df_raw.sort_values("日期")
    closes_raw = df_raw["收盘"].astype(float).tolist()
    ma5_manual = sum(closes_raw[-5:]) / 5

    print(f"    最近5个交易日收盘价(qfq):")
    for i, close in enumerate(closes_raw[-5:]):
        date = df_raw["日期"].iloc[-(5-i)]
        print(f"      {date}: {close:.2f}")

    # ── Program calculation via unified layer ──
    print(f"\n[2] 程序取数 (get_kline, qfq)...")
    df_proj = get_kline(symbol, adjust="qfq")
    ma5_project = calc_ma(df_proj, 5).iloc[-1]

    # ── Cross-check with real market source ──
    print(f"\n[3] 交叉验证（东方财富实时快照）...")
    try:
        df_spot = ak.stock_zh_a_spot_em()
        row = df_spot[df_spot["代码"] == symbol]
        if not row.empty:
            market_price = float(row["最新价"].iloc[0])
            print(f"    东方财富实时最新价: {market_price:.2f}")
        else:
            market_price = None
            print(f"    未找到 {symbol} 实时行情")
    except Exception as e:
        market_price = None
        print(f"    获取实时行情失败: {e}")

    # ── Results ──
    print(f"\n{'='*60}")
    print(f"  验证结果")
    print(f"{'='*60}")
    print(f"  手动计算 MA5          : {ma5_manual:>10.2f}")
    print(f"  程序计算 MA5          : {ma5_project:>10.2f}")
    if market_price:
        print(f"  东方财富实时最新价    : {market_price:>10.2f}")

    diff = abs(ma5_manual - ma5_project)

    # Checks
    checks = []

    # Check 1: Manual vs program match
    if diff < 0.5:
        checks.append(("MA5 程序值 vs 手算值一致", True, f"差={diff:.4f}"))
    else:
        checks.append(("MA5 程序值 vs 手算值一致", False, f"差={diff:.4f} > 0.5"))

    # Check 2: Reasonable price range (茅台 should be ~1200-1400 in qfq)
    if 800 < ma5_project < 2500:
        checks.append(("MA5 数值在合理区间 (800-2500)", True, f"MA5={ma5_project:.2f}"))
    else:
        checks.append(("MA5 数值在合理区间 (800-2500)", False, f"MA5={ma5_project:.2f} 异常"))

    # Check 3: Not absurdly high (hfq contamination check)
    if ma5_project < 2000:
        checks.append(("MA5 < 2000（排除hfq污染）", True, f"MA5={ma5_project:.2f}"))
    else:
        checks.append(("MA5 < 2000（排除hfq污染）", False, f"MA5={ma5_project:.2f} 可能是hfq污染"))

    # Check 4: Close to market price
    if market_price and abs(ma5_project - market_price) / market_price < 0.15:
        checks.append(("MA5与实时价偏差<15%", True, f"偏差={abs(ma5_project-market_price)/market_price*100:.1f}%"))
    elif market_price:
        checks.append(("MA5与实时价偏差<15%", False, f"偏差={abs(ma5_project-market_price)/market_price*100:.1f}%"))
    else:
        checks.append(("MA5与实时价偏差<15%", None, "无实时价数据"))

    print(f"\n  检查项:")
    all_pass = True
    for name, passed, detail in checks:
        if passed is True:
            print(f"    ✅ {name}: {detail}")
        elif passed is False:
            print(f"    ❌ {name}: {detail}")
            all_pass = False
        else:
            print(f"    ⬜ {name}: {detail}")

    print(f"\n  {'✅ 全部通过' if all_pass else '❌ 存在失败，需修复'}")

    # Assertions
    assert diff < 0.5, f"程序 MA5 与手算不一致: 差={diff:.4f}"
    print(f"\n✅ 验证完成 — 复权方式: 前复权(qfq)，与同花顺/东方财富默认一致")

    return all_pass


if __name__ == "__main__":
    try:
        ok = verify("600519")
    except Exception as e:
        print(f"\n❌ 验证脚本异常: {e}")
        import traceback
        traceback.print_exc()
        ok = False

    sys.exit(0 if ok else 1)
