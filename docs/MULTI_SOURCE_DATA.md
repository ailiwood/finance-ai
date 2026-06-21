# MULTI_SOURCE_DATA.md — 多数据源整合(BaoStock 免费前复权为主力)

> 放到项目 `docs/`。核心结论:**BaoStock 免费提供前复权,无需积分**,直接解决"Tushare前复权需2000积分"的痛点。
> 改造数据层为四源降级链,彻底摆脱单一源依赖。

---

## 一、核心发现(基于实测资料)

1. **BaoStock 原生支持前复权,完全免费、无需注册付费、无积分门槛**。
   - `query_history_k_data_plus(..., adjustflag="2")` → 2=前复权,1=后复权,3=不复权。
   - 这直接解决了 Tushare 前复权需 2000 积分的问题。
2. **AKShare 新浪接口前复权质量很高**,对标 Wind 在茅台股改(2006-05-25)后数据完全一致。之前失败是用了东财接口(连不上)或没重试。
3. **单一数据源有断供风险**(Tushare 曾突发停运),行业最佳实践是"主备结合、多源互补 + 本地缓存"。
4. **新浪极简实时接口**:`http://hq.sinajs.cn/list=sh600519` 一个 HTTP 请求拿实时报价,无需库/注册,适合做"当前价"校验。

---

## 二、目标:四源降级链(全部免费可用)

```
1) BaoStock        前复权(免费,无积分)      ← 前复权主力
2) AKShare 新浪接口 前复权(免费,质量对标Wind) ← 备用前复权
3) Tushare         前复权需2000积分→降级不复权  ← 不复权兜底(用户已有130积分)
4) 明确报错(绝不编造)                         ← 红线兜底
另:新浪实时接口做"当前价"快速校验(数据体检页)
```
任一源成功即返回并标注来源与复权方式;全失败则明确报错。

---

## 三、各源接入要点

### 1. BaoStock(新增,设为前复权首选)
```python
import baostock as bs
import pandas as pd

def get_baostock_kline(symbol, start_date, end_date, adjustflag="2"):
    # symbol 格式: sh.600519 / sz.000001
    code = _to_baostock_code(symbol)   # 600519 -> sh.600519
    lg = bs.login()
    try:
        rs = bs.query_history_k_data_plus(
            code,
            "date,open,high,low,close,volume,amount,turn,pctChg",
            start_date=start_date, end_date=end_date,
            frequency="d", adjustflag=adjustflag)  # 2=前复权
        rows = []
        while (rs.error_code == "0") and rs.next():
            rows.append(rs.get_row_data())
        df = pd.DataFrame(rows, columns=rs.fields)
        return df
    finally:
        bs.logout()

def _to_baostock_code(symbol):
    s = symbol.split(".")[0]
    if s.startswith(("6","9")): return f"sh.{s}"
    if s.startswith(("0","3","2")): return f"sz.{s}"
    if s.startswith(("4","8")): return f"bj.{s}"  # 北交所
    return f"sh.{s}"
```
注意:
- BaoStock 要 login()/logout(),并发时注意会话管理;打包时确认 baostock 已加入 requirements 和 PyInstaller hiddenimports。
- 列是字符串,需转 float;date 升序。
- 数据从 2006 年起较全。

### 2. AKShare 新浪接口(备用前复权)
- 优先用新浪接口 `stock_zh_a_daily(symbol="sh600519", adjust="qfq")`(质量高),而非之前连不上的东财 `stock_zh_a_hist`。
- 加指数退避重试(3次)。两个接口可互为备份。

### 3. Tushare(不复权兜底)
- 沿用上一轮"前复权优先,失败(积分不足)降级 pro.daily() 不复权"的逻辑。
- 用户当前 130 积分,前复权(需2000)拿不到,但不复权可用,作为第三兜底。

### 4. 新浪实时接口(当前价校验,可选)
```python
import requests
def get_sina_realtime(symbol):  # symbol: sh600519
    url = f"http://hq.sinajs.cn/list={symbol}"
    r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=5)
    # 解析返回的逗号分隔字符串,取最新价等
    return r.text
```
注意:需带 Referer 头,否则可能被拒。仅用于数据体检页"当前价"对账,不作为K线主源。

---

## 四、统一封装(唯一入口)
在 src/data/market_data.py 的 get_kline() 内实现降级链:
```python
def get_kline(symbol, start_date, end_date, period="daily"):
    errors = []
    # 1) BaoStock 前复权
    try:
        df = get_baostock_kline(symbol, start_date, end_date, "2")
        if _valid(df): return _normalize(df), "baostock", "qfq"
    except Exception as e: errors.append(f"BaoStock: {e}")
    # 2) AKShare 新浪 前复权
    try:
        df = get_akshare_sina_kline(symbol, start_date, end_date, "qfq")
        if _valid(df): return _normalize(df), "akshare_sina", "qfq"
    except Exception as e: errors.append(f"AKShare新浪: {e}")
    # 3) Tushare 不复权兜底
    try:
        df, adj = get_tushare_kline(...)
        if _valid(df): return _normalize(df), "tushare", adj
    except Exception as e: errors.append(f"Tushare: {e}")
    # 4) 全失败 → 明确报错(绝不编造)
    raise DataFetchError("所有数据源均失败:\n" + "\n".join(errors))
```
- 返回标准英文列、date升序、来源标签、复权方式。
- 缓存 key 含 symbol/period/复权方式/来源。
- 数据体检页和报告显示"数据来源 + 复权方式",透明可对账。

---

## 五、依赖与打包
- requirements 加 `baostock`。
- PyInstaller spec 用 collect_all("baostock"),并补 hiddenimports(baostock 有动态导入)。
- 重新打包后验证 BaoStock 在 exe 环境能 login 成功。

---

## 六、验证(工作报告必须包含)
1. 用 BaoStock 取 600519 前复权最近5日收盘价,确认与同花顺一致(~1250)。**贴输出**。
2. 降级链测试:模拟 BaoStock 失败,确认自动转 AKShare 新浪。
3. 数据体检页显示当前数据来源和复权方式。
4. exe 打包后 BaoStock 可用。
