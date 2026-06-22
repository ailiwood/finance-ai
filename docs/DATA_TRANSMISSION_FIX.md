# DATA_TRANSMISSION_FIX.md — 数据传输链路修复(tuple bug)+ 情绪源 + 编造红线

> 放到项目 `docs/`。本轮决定性发现:数据源已经好了,problem 出在"数据传给分析模块"的环节。
> 日志铁证:`BaoStock ✅: 733行, 1510.74~1215.00`(数据对了)但报告报 `'tuple' object has no attribute 'split'`。

---

## 一、根因:get_kline() 返回三元组,下游当字符串用

### 铁证
```
[数据] BaoStock ✅: 733行, 1510.74~1215.00   ← 数据源成功,价格正确(茅台~1215-1510)
报告: 'tuple' object has no attribute 'split'  ← 但下游崩溃
```
`'tuple' object has no attribute 'split'` = 某代码期望字符串(调 .split()),实际拿到元组。

### 定位
上一轮(多源降级)把统一入口设计成返回三元组:
```python
return _normalize(df), "baostock", "qfq"   # (DataFrame, 来源, 复权方式)
```
但调用 get_kline() 的下游(市场分析工具 get_stock_market_data_unified、市场分析师链路、技术指标计算、格式化为给LLM的文本)**还停留在旧接口假设**,以为返回单个对象(DataFrame 或字符串),拿到三元组后:
- 要么直接对元组调 .split() → 崩
- 要么把整个元组传给期望 DataFrame 的函数 → 行为错乱(日志里 733行/13行不一致也是这个原因)

### 这是"接口改了、调用方没同步改"的典型 bug

---

## 二、修复方案:理顺 get_kline 的返回契约,统一所有调用方

### 方案(二选一,推荐 A)

**方案 A(推荐):get_kline 只返回 DataFrame,来源/复权方式用对象属性或单独函数**
```python
def get_kline(symbol, start_date, end_date, period="daily") -> pd.DataFrame:
    """只返回标准化 DataFrame(英文列, date升序)。
    来源和复权方式存到 df.attrs,不改变主返回值类型。"""
    df, source, adjust = _fetch_with_fallback(...)   # 内部降级链
    df.attrs["source"] = source      # pandas 支持 df.attrs 存元数据
    df.attrs["adjust"] = adjust
    return df                         # 下游永远拿到 DataFrame,不会再 tuple

# 需要来源信息时:
df = get_kline("600519", ...)
print(df.attrs.get("source"), df.attrs.get("adjust"))
```
优点:下游所有调用方不用改,永远拿到 DataFrame。数据体检页/报告要显示来源时读 df.attrs。

**方案 B:保持三元组,但全面改造所有调用方**
```python
df, source, adjust = get_kline(...)   # 每个调用处都要解包
```
缺点:要找全所有调用点逐个改,漏一个就崩。**不推荐**,除非调用点很少。

### 必须做:全局排查所有 get_kline 调用点
1. 全项目搜索 `get_kline(` 的所有调用处。
2. 确认每一处接收的都是 DataFrame(方案A)或都正确解包(方案B)。
3. 重点查:get_stock_market_data_unified、市场分析师工具、技术指标计算函数、把数据格式化成给LLM文本的函数。
4. 那个调 `.split()` 的地方:它本来想 split 什么?如果是想把数据格式化成文本,确认它拿到的是正确的字符串/DataFrame,而非元组。

---

## 三、数据→LLM 的格式化要可验证
数据取到后,要变成给 LLM 的文本(含OHLCV、MA、MACD等)。这一步要:
1. 单独成函数 `format_market_data_for_llm(df) -> str`,输入 DataFrame,输出结构化文本。
2. 写单元测试:给定样例 DataFrame,断言输出文本含正确的最新收盘价、MA5 等。
3. 在日志里(DEBUG)打印传给 LLM 的数据文本前 500 字,确认不是空的、不是元组的 repr。

---

## 四、情绪面:接通数据源 + 禁止编造(红线复发)

### 问题1:情绪数据源未接通
报告自述"实时社交媒体API数据暂未完全集成"。即情绪源还是空的。
- 按之前 SENTIMENT_CONFIG 文档,接通至少一个**免费可用**的情绪/新闻源:
  - A股新闻:akshare 的新闻接口(如 stock_news_em 个股新闻)是免费的,优先接这个。
  - 财经资讯情感:抓取新闻标题/摘要 → FinBERT 或 LLM 打分 → 情绪指数。
- 社交媒体(微博/股吧)源可作为可选项,没有免费稳定源就先不做,**但绝不能因此编造**。

### 问题2(红线!):情绪缺失时 LLM 编造了"6.5/10"
报告编造了情绪指数,这违反 round4 定的红线。说明"数据缺失禁止编造"只在技术面生效,情绪面漏了。
**修复:把"数据缺失禁止编造"的硬约束应用到所有模块(技术面/情绪面/基本面)**:
1. 情绪 Agent 的提示词加:"若未获取到真实情绪/新闻数据,必须明确说明'情绪数据获取失败,无法分析',严禁编造情绪指数或任何评分。"
2. 情绪数据获取失败时,该模块直接输出"❌ 情绪数据暂不可用(数据源未配置或获取失败)",不调 LLM 编造。
3. 全局复查:基本面、技术面、情绪面、风控——任何模块拿不到真实数据,都明确报错,绝不编造。

---

## 五、本轮验证(工作报告必须包含)
1. get_kline 返回契约改造方式(方案A/B),以及排查到的所有调用点。
2. `'tuple' ... split` 错误已消除的证明(本地跑通技术分析,报告含真实 MA/价格)。
3. format_market_data_for_llm 单测结果。
4. 情绪源接通情况(接了哪个免费源)。
5. 情绪缺失时报错而非编造的验证。
6. 数据来源/复权方式在报告中正确显示(读 df.attrs)。
