# DATA_ACCURACY_FIX.md — 数据正确性修复(最高优先级)

> 放到项目 `docs/`。这是本轮**最重要**的修复:数据错了,一切技术分析都是错的。
> CC 必须把这一项作为第一优先级,且**必须写验证脚本自证修复成功**。

---

## 一、问题定性:几乎可以确定是"复权方式"错误

现象:分析贵州茅台(600519),程序算出 MA5 ≈ 1600,而同花顺/官网真实值 ≈ 1250。

### 根因分析
A 股有三种价格口径,akshare 的 `stock_zh_a_hist(adjust=...)` 参数控制:
- `adjust=""`(不复权):显示当时的真实成交价。
- `adjust="qfq"`(前复权):保持最新价不变、回调历史价。**各大行情软件(同花顺/东财/通达信)默认显示这个**,也是看盘和算技术指标的标准口径。
- `adjust="hfq"`(后复权):保持历史价不变、放大当前价。茅台这种多年分红送股的票,后复权会把价格抬高几百元。

**关键证据**:同样一只股票,后复权价可以比真实价高出一大截(例:平安银行真实约 9 元,后复权显示 1575 元)。茅台真实 ~1250,你算出 ~1600,这个偏离方向和量级,**高度符合"误用了后复权(hfq)数据"**。

### 结论
你的取数代码很可能:
1. 用了 `adjust="hfq"`(后复权),或
2. 多个数据源/缓存层之间复权口径不一致(取数时一种、算指标时另一种),或
3. 缓存里存了旧的/错误口径的数据,没刷新。

---

## 二、修复要求(CC 必须逐条做)

### 1. 统一复权口径为"前复权 qfq"
- 全项目取 A 股日线数据**统一用 `adjust="qfq"`**(与同花顺/东财默认一致,用户对得上)。
- 在数据层封装一个唯一入口,例如 `get_kline(symbol, start, end, adjust="qfq")`,**所有**地方都走它,禁止各处直接调 akshare 自带不同 adjust。
- 技术指标(MA/MACD/RSI/KDJ/BOLL 等)一律基于该 qfq 序列计算。

### 2. 排查缓存污染
- 检查 DuckDB/Parquet/SQLite 缓存:缓存 key 必须包含 `adjust` 维度(不同复权要分开存),否则会串味。
- 提供一个"清空并重建缓存"的方法/按钮;本次修复后**强制清一次旧缓存**,因为旧缓存里可能是 hfq 的脏数据。

### 3. 校验数据源一致性
- 若项目同时接了 akshare / tushare / baostock,确认它们的复权口径统一(都取前复权)。tushare 的 `pro_bar(adj='qfq')`、baostock 的 `adjustflag="2"` 对应前复权。
- 不同源之间做一次交叉校验(见下方验证脚本)。

### 4. 时间窗口要对
- MA5 指"最近 5 个**交易日**"。确认取数覆盖到最新交易日(注意当日数据要收盘后才有;盘中分析应说明用的是最近已收盘的 N 日)。
- 确认排序正确(按日期升序),MA 计算用的是最后 5 行而不是最前 5 行。

---

## 三、CC 必须写并运行的验证脚本(自证修复)

新建 `scripts/verify_data_accuracy.py`,内容要点:
```python
import akshare as ak
import pandas as pd

def verify(symbol="600519"):
    # 1) 取前复权日线
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                            adjust="qfq").tail(10)
    df = df.sort_values("日期")
    closes = df["收盘"].astype(float).tolist()

    # 2) 手算 MA5(最近5个收盘价的均值)
    ma5_manual = sum(closes[-5:]) / 5

    # 3) 调项目自己的取数+指标函数,拿到程序算的 MA5
    from src.data.market_data import get_kline      # 按实际路径
    from src.analysis.indicators import calc_ma     # 按实际路径
    proj_df = get_kline(symbol, adjust="qfq")
    ma5_project = calc_ma(proj_df, 5).iloc[-1]

    print(f"最近收盘价(qfq): {closes[-5:]}")
    print(f"手算 MA5     : {ma5_manual:.2f}")
    print(f"程序 MA5     : {ma5_project:.2f}")
    print(f"最新收盘价   : {closes[-1]:.2f}")
    # 断言:程序值与手算值几乎相等
    assert abs(ma5_manual - ma5_project) < 0.5, "MA5 不一致,仍有 bug!"
    # 合理性检查:茅台 MA5 应在最新价附近(几百到一两千的合理区间),
    # 远大于真实价(如 >2000)说明仍是后复权污染
    print("✅ 通过" if 800 < ma5_project < 2500 else "❌ 数值异常,疑似复权错误")

if __name__ == "__main__":
    verify()
```
**CC 必须实际运行它并把输出贴进工作报告**。手算 MA5 与程序 MA5 必须吻合,且数值落在合理区间(茅台当前应在 ~1250 附近,而非 1600)。

> 注意:akshare 是实时数据,具体数值随当天行情变化。重点是"程序值 == 手算值"且"接近同花顺前复权口径",而非死磕某个固定数字。

---

## 四、加一道"数据健全性检查"防回归
在数据层加轻量校验,异常时告警而非静默出错:
- 价格非负、最高≥最低≥0、收盘在最高最低之间。
- 最新价与上一交易日偏离超过 ±20%(非涨跌停票)时打 warning(可能数据错乱)。
- 取到的行数 < 预期窗口时报错提示"数据不足"。
- 把"当前使用的复权方式"显示在报告里(透明,让用户能对账)。
