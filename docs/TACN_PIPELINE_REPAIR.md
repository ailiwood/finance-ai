# TACN_PIPELINE_REPAIR.md — 修复 TA-CN 数据管线断裂(根因级)

> 放到项目 `docs/`。CC 已正确诊断出"双管线"问题:你的 get_kline() 没被 TA-CN Agent 使用。
> 但 CC 的修复方向有两处需纠偏。本文件给出更彻底的修法。

---

## 一、纠正两个判断偏差(关键)

### 偏差1:`app.core` 不是要 mock,而是要删除
经核实,TA-CN 原版(hsliuping/TradingAgents-CN)的 data_source_manager **根本不依赖 `app.core` 模块**。它用环境变量(MONGODB_ENABLED=false 等)+ 自己的 config 读配置。
**`No module named 'app.core'` 是之前某轮改动往 TA-CN 源码里引入的外来依赖(import 写错/半成品)。** 它是错误 #1/#3/#5 的共同根源。
**正解:找到并删除/改正所有 `from app.core...` 的错误 import,恢复 TA-CN 原本的配置读取方式。绝不要再造一个假的 app.core 模块去喂它(那是在污染上再加污染)。**

### 偏差2:优先"修好 TA-CN 原生 BaoStock 通道",而非只桥接K线
TA-CN 原版自己就支持 BaoStock(它的数据源之一)。当前"双管线"很可能也是之前改乱 TA-CN 数据层才另起炉灶写了 src/data/market_data.py。
**主路线 B(推荐):删掉 app.core 污染,让 TA-CN 原生 baostock/akshare 通道复活 → 一次修好 K线+基本面+新闻全部。**
**辅路线 A(保底):K线这一条用已验证的 get_kline() 桥接,确保至少技术面有真实数据。**

---

## 二、修复任务(按根因→分支)

### 任务 1(根因)· 清除 app.core 外来污染
1. 全项目搜索 `app.core`、`from app.`、`import app`,找到所有引用点(日志说 data_source_manager.py 等)。
2. 判断每处**本意**是想读什么配置(数据源选择?token?缓存开关?)。
3. 改为 TA-CN 原生方式或你的 src/config 正确路径:
   - 如果想读你的 QuantSage 配置 → 用正确的 `src.config...` 路径(确认包结构,大概率是路径写错成了 app.core)。
   - 如果是 TA-CN 自己的配置 → 恢复它原本的读取(环境变量/default_config)。
4. 删除后确认 data_source_manager 能正常初始化,不再抛 No module named 'app.core'。

### 任务 2 · 恢复/确保 TA-CN BaoStock 通道可用(主路线B)
1. 检查 TradingAgents-CN/tradingagents/dataflows/providers/china/baostock.py 是否完好(没被改坏)。
2. 确保 data_source_manager 的降级链能走到 baostock 并取到前复权数据。
3. 让 BaoStock 成为 A股首选(它免费、已验证可用)。

### 任务 3(保底A)· K线工具桥接 get_kline()
若任务2短期内修不彻底,把 get_stock_market_data_unified 的底层数据获取桥接到 src/data/market_data.py 的 get_kline()+format_market_data_for_llm():
1. 用 monkey-patch 或在工具实现里直接调用 get_kline(),最小侵入。
2. 确保 df.attrs 的 source/adjust 传到报告。
3. 这样即使 TA-CN 原生管线还没完全修好,技术面也有真实数据。

### 任务 4(红线)· 基本面假价格 10.0 必须拦截
错误#3:MongoDB 不可用 → 回退假价格 10.0 → LLM 拿到垃圾。这违反"禁止编造"红线。
1. 找到回退假价格的代码(optimized_china_data.py 的 _generate_fundamentals_report 附近),**删除"回退到10.0/默认价"的逻辑**。
2. 基本面数据(价格/PE/PB)取不到时,**明确标注"基本面数据暂不可用",不传假数据给 LLM**。
3. 基本面数据来源补救:用 BaoStock 的 query_stock_basic / AKShare 财务接口补 PE/PB/财报(免费)。
4. 在代码层面拦截:任何"默认/占位/假"价格都不许进入 LLM 上下文。

### 任务 5 · 彻底关闭 ChromaDB 记忆(DeepSeek 无 embedding 端点)
错误#4:DeepSeek 没有 /v1/embeddings,ChromaDB 记忆每次 404。
1. 加配置开关 ENABLE_MEMORY=false(默认关),关闭时完全不初始化 ChromaDB/embedding。
2. 记忆功能对单次股票分析非必需,关掉不影响主流程,还省内存(呼应之前的内存优化)。
3. 确认关闭后无 404 噪音、无崩溃。

### 任务 6 · AKShare scalar 错误
错误#2:`If using all scalar values, you must pass an index`。
1. 定位 TA-CN akshare.py 的 get_stock_info,这是构造 DataFrame 时传了全标量没给 index。
2. 修复构造方式(传 index 或用 pd.Series),或优先走 baostock 取股票信息绕开它。

### 任务 7 · 新闻分析返回空
错误#6:新闻 LLM 调用完成但报告 0 字符。
1. 检查 news_analyst 的新闻数据源是否配置/可用。
2. 接免费新闻源(akshare stock_news_em);取不到时**明确报错"新闻数据暂不可用",不编造**。

### 任务 8 · setup_logging 幂等
错误#7:每次 Streamlit rerun 重复执行 setup_logging,日志膨胀。
1. setup_logging 加幂等保护:检查 logger 是否已有 handler,有则跳过。
   ```python
   if logger.handlers: return  # 已初始化,跳过
   ```
2. 或用模块级标志位 _LOGGING_INITIALIZED 保证只初始化一次。

---

## 三、验证(工作报告必须包含)
1. app.core 引用已全部清除(搜索结果为空),data_source_manager 正常初始化。
2. 分析 600519:技术面有真实MA/价格(~1215-1250),来源=BaoStock。
3. 基本面:有真实价格/PE/PB,**或明确报错——绝无 10.0 假价格**。
4. 新闻面:有真实新闻,或明确报错(不编造)。
5. 无 DeepSeek embedding 404 噪音。
6. 143 个已有测试仍通过。
7. setup_logging 不再重复刷屏。
8. streamlit run 下端到端跑通。
