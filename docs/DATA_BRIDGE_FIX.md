# DATA_BRIDGE_FIX.md — 数据桥接修复(把可用数据端给 TA-CN Agent)

> 放到项目 `docs/`。根因已由日志100%确认:get_kline() 取到真实数据但只用于"验证",没喂给 TA-CN Agent;Agent 自己走断裂的管线B全线崩溃。
> 核心策略:**不修管线B,用 get_kline 在工具层拦截,把真实数据端给所有 Agent。**

---

## 一、根因(已确认,无需再猜)
日志铁证:get_kline("600519") 返回 733行真实数据(close=1215.00, source=BaoStock),但仅用于步骤[1]的数据验证,**没传给 TA-CN Agent**。Agent 在步骤[3]走 TA-CN 内部管线B(data_source_manager),而管线B 被 app.core 污染 + AKShare bug + tuple 解包错 全线崩溃。

一句话:**好数据取到了却没用在该用的地方。**

---

## 二、核心决策:绕过管线B,不修它

放弃修复 TA-CN 的 data_source_manager(8个错误里 #1/#2/#3/#4/#8 都源于这个被改乱的黑盒,已耗多轮)。改为:**在"工具层"用已验证的 get_kline() 拦截,返回真实数据,让管线B 根本不被执行。**

### 给 CC 的硬约束(防止再次跑偏)
> 不许再花时间修复 TA-CN data_source_manager 的内部逻辑(不要 mock app.core、不要纠结 tuple 解包)。统一在工具函数入口处用 get_kline 拦截并返回真实数据,让 TA-CN 的断裂管线根本不被执行到。工作面限定在"几个工具函数入口",不要钻进 data_source_manager 黑盒。

---

## 三、四个维度逐一桥接

### 维度1(最优先)· 技术面/K线
**位置**:`TradingAgents-CN/tradingagents/agents/utils/agent_utils.py` 的 `get_stock_market_data_unified`。
**改法**:在该工具内部,检测到中国A股时,**直接调用 src 的 get_kline() + format_market_data_for_llm()**,返回真实数据字符串,return 掉,不再往下走 get_china_stock_data_unified(那条会崩)。
```python
def get_stock_market_data_unified(ticker, start_date, end_date, ...):
    # A股:直接用我们已验证的管线A,绕过断裂的管线B
    if _is_china_a_share(ticker):
        try:
            from src.data.market_data import get_kline, format_market_data_for_llm
            df = get_kline(ticker, start_date, end_date)
            if df is not None and len(df):
                return format_market_data_for_llm(df)  # 真实数据字符串
        except Exception as e:
            logger.error(f"[桥接] get_kline 失败: {e}")
            return f"❌ 无法获取 {ticker} 的真实行情数据,本次分析终止。"  # 报错不编造
    # 非A股走原逻辑
    ...
```
注意:import 放函数内部(惰性),避免 TA-CN 模块加载时的循环依赖。

### 维度2 · 基本面
**现状**:假价格10.0已删→现在返回None;财务数据全断。
**改法**:
1. 在基本面工具(get_stock_fundamentals_unified 或 optimized_china_data 的相关入口)同样桥接:A股时用我们的数据。
2. 价格用 get_kline 的最新收盘价。
3. 财务指标(PE/PB/ROE/财报):用 **BaoStock query_stock_basic / query_profit_data / query_growth_data** 或 AKShare 财务接口(都免费)。建议在 src/data/ 下新增 get_fundamentals(symbol) 统一封装,供桥接调用。
4. 取不到的指标明确标注"该指标暂不可用",**不编造、不回退假值**。

### 维度3 · 新闻(解药已在手边)
**现状**:报告明说 `_fetch_china_news_free()` 已写好但 `get_stock_sentiment_unified`/`get_stock_news_unified` 没调用它。
**改法**:把现成的 `_fetch_china_news_free()`(akshare stock_news_em,免费)接到新闻工具的A股分支。这是"写了没接上",接一下即可。取不到则明确报错,不编造。

### 维度4 · 情绪
**现状**:返回"❌情绪数据暂不可用"(数据缺失不编造,正确)。
**改法**:
1. 基于维度3拿到的新闻,用 FinBERT 或 LLM 打分得情绪指数。
2. 若暂不做打分,保持"明确报错"现状(可接受,不编造就行)。

---

## 四、统一原则(贯穿四维度)
1. **A股一律走管线A(get_kline等),绕过管线B。**
2. **数据缺失一律明确报错,绝不编造**(技术面那个"假设价格¥1680"必须根除——和之前的红线一致)。
3. 桥接的 import 用函数内惰性导入,避免循环依赖。
4. 数据来源/复权方式透传到报告(读 df.attrs)。

---

## 五、验证(用上一轮的日志模块自证)
点一次分析600519,贴出该次 trace 的完整链路日志,确认:
1. get_stock_market_data_unified 返回的是真实数据(含1215左右价格),不再有 'tuple'...split 错误。
2. 技术面报告:真实MA/价格(~1215-1250),无"假设价格¥1680"这类编造。
3. 基本面:真实价格 + 能取到的财务指标;取不到的明确标注,无假数据。
4. 新闻面:有真实新闻(_fetch_china_news_free 被调用),或明确报错。
5. 情绪面:基于真实新闻打分,或明确报错(不编造)。
6. 全链路日志显示数据从 get_kline 一路传到了各 Agent(不再是"取了就扔")。
7. 143个已有测试仍通过。
8. streamlit run 端到端跑通。
