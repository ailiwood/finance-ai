# DATA_RELIABILITY_DEEPFIX.md — 数据可靠性彻底修复 + 多周期支持

> 放到项目 `docs/`。本轮最高优先级。上一轮"改成 qfq"显然没彻底解决,本轮要做到**全链路可追溯、可对账、可防回归**,并支持长中短期多周期。
> 铁律:CC 不准只说"已修复",必须用"数据体检"脚本/页面把真实数字摊出来自证。

---

## 一、先定位:为什么数据还是不对?逐层排查

数据从源头到指标要经过:`数据源API → 复权处理 → 缓存 → 时间窗口切片 → 指标计算 → 展示`。任何一层错都会导致结果错。CC 必须逐层验证,不能只看最后结果。

### 排查清单(CC 逐条确认并在报告中说明)
1. **复权是否真改对**:全项目搜 `adjust=`,确认 A股取数全部是 `"qfq"`,没有遗漏的 `"hfq"` 或 `""`。
2. **旧缓存是否真清**:上一轮如果改了代码但没清缓存,程序仍读到旧的 hfq 脏数据。本轮**强制清空缓存目录**并重建,缓存 key 必须含 `adjust` 和 `period`。
3. **"实时/当日"数据陷阱**:akshare 的当日K线要**收盘后**才完整;盘中取到的"今天"是不完整快照,会把 MA 算歪。必须区分:
   - 盘中分析 → 用"最近 N 个**已收盘**交易日",明确不含未收盘的今日,或单独标注"今日为盘中快照"。
   - 收盘后 → 才纳入当日。
4. **排序与切片**:确认按日期**升序**排列,MA5 取**最后** 5 行;别取反了。
5. **字段映射**:akshare 返回中文列名(日期/开盘/收盘/最高/最低/成交量),确认代码映射正确,没把"开盘"当"收盘"。
6. **股票代码与市场**:600519 是沪市,确认代码、市场、前缀处理正确,没串到别的票。

---

## 二、统一数据入口(唯一真相来源)

新建/确认 `src/data/market_data.py`,提供唯一入口,**全项目只准用它取K线**:
```python
def get_kline(symbol: str,
              period: str = "daily",      # daily / weekly
              adjust: str = "qfq",        # 统一前复权
              lookback_days: int = 1100,  # 默认取约3年,供多周期切片
              include_today_intraday: bool = False) -> pd.DataFrame:
    """返回标准化K线: 列为 date, open, high, low, close, volume(英文标准列),
    date 升序。带本地缓存(key 含 symbol/period/adjust)。
    include_today_intraday=False 时,剔除未收盘的当日数据。"""
    ...
```
要求:
- 中文列名统一重命名为英文标准列。
- 缓存 key:`f"{symbol}:{period}:{adjust}"`,存 DuckDB/Parquet。
- 提供 `clear_cache()`,本轮调用一次清旧数据。
- 取数失败/为空时抛清晰异常,不返回半截数据。

---

## 三、多周期技术分析(3年/1年/6月/3月/1月/1周)

### 设计:一次取足,本地切片(省请求、口径一致)
```python
PERIODS = {
    "近1周":  {"days": 7,    "granularity": "daily"},
    "近1月":  {"days": 30,   "granularity": "daily"},
    "近3月":  {"days": 90,   "granularity": "daily"},
    "近6月":  {"days": 180,  "granularity": "daily"},
    "近1年":  {"days": 365,  "granularity": "daily"},
    "近3年":  {"days": 1095, "granularity": "weekly"},  # 长周期用周线,减噪
}
```
实现:
1. 一次 `get_kline(symbol, lookback_days=1100)` 取够约3年日线,缓存。
2. 各周期从这份数据**按日期切片**,不重复请求。
3. 近3年可用周线重采样(日线 → 周线)降噪,更看趋势。
4. 每个周期分别算技术指标(MA/MACD/RSI/KDJ/BOLL),汇总给分析 Agent。

### 指标计算
- MA5/MA10/MA20/MA60、MACD、RSI、KDJ、BOLL 等基于对应周期序列计算。
- 用成熟库(pandas-ta 或自实现并写单测),不要手搓易错公式。
- 短周期(1周)数据点少,部分长周期指标(如MA60)无意义 → 标注"数据不足"而非给错值。

---

## 四、最关键:数据体检页/脚本(让你能逐行对账)

### 1. 命令行验证脚本 scripts/verify_data_accuracy.py(CC 必须运行并贴输出)
```python
import akshare as ak
from src.data.market_data import get_kline
from src.analysis.indicators import calc_ma  # 按实际路径

def verify(symbol="600519"):
    # 项目取数
    df = get_kline(symbol, adjust="qfq")
    df = df.sort_values("date")
    closes = df["close"].astype(float).tolist()
    ma5_proj = calc_ma(df, 5).iloc[-1]
    ma5_manual = sum(closes[-5:]) / 5

    print(f"最近5个收盘价(qfq): {[round(c,2) for c in closes[-5:]]}")
    print(f"最新收盘价: {closes[-1]:.2f}")
    print(f"手算 MA5 : {ma5_manual:.2f}")
    print(f"程序 MA5 : {ma5_proj:.2f}")
    assert abs(ma5_manual - ma5_proj) < 0.5, "MA5 不一致!"
    # 茅台前复权应在 ~1250 量级,若 >1500 几乎肯定还是复权错误
    print("✅ 量级合理" if 900 < ma5_proj < 1500 else "❌ 仍疑似复权/数据错误")

if __name__ == "__main__":
    verify()
```

### 2. 网页端"数据体检"标签页(给用户/你自己对账)
在 UI 加一个"数据体检"页:输入代码 → 显示:
- 最近 10 个交易日的原始 OHLCV 表格(让用户能和同花顺逐行对比)。
- 当前复权方式("前复权")、数据源、数据更新时间。
- 算出的各周期 MA 值。
这是透明度,也是你每次能快速验证数据对不对的工具。

---

## 五、数据源健康与多源校验
- akshare 免费源会限频/偶发脏数据。加:重试 + 超时 + 异常拦截。
- 若配了 tushare(前复权 `pro_bar(adj='qfq')`)或 baostock(`adjustflag="2"`),做一次交叉校验:同一天收盘价两源偏差 >2% 时告警。
- 健全性检查:价格非负、high≥low、收盘在 [low,high] 内、非停牌票日间偏离 >20% 告警。
