# LOCAL_FULL_TEST.md — 本地全量测试指引(含 K线预测 + 情绪模块)

> 放到项目 `docs/`。本轮修复后,在开发机做一次"所有模块全开"的端到端测试。
> 目的:确认数据正确流转到每个模块(技术分析/K线预测/情绪分析),尤其 Kronos 能读到数据并出预测。

---

## 一、为什么要全量测试
之前都是单点测试,容易遗漏"模块间数据传递"的问题(本轮的 tuple bug 就是模块间传递出错)。全量测试 = 把 K线预测、情绪分析全部开启,端到端跑一遍,暴露集成问题。

## 二、测试前准备
1. 开发机(你的 64GB + 5070Ti 主力机),源码运行(不用打包,打包是最后一步)。
2. 配置 .env / config:
   - LLM:DeepSeek key(已验证可用)
   - 数据源:BaoStock(免费,已验证733行成功)
   - 启用插件:`ENABLE_KRONOS=true`、`ENABLE_FINBERT=true`(或情绪源开关)
3. 确认依赖装全:baostock、torch(CPU或CUDA版)、kronos相关、akshare(情绪新闻)。

## 三、分层测试步骤(从底层到端到端)

### 第1层:数据层(最基础,先确认)
```bash
python scripts/verify_data_accuracy.py   # 上几轮的脚本
```
确认:get_kline("600519") 返回 DataFrame(不是 tuple),最新收盘价/MA5 与同花顺前复权一致(~1215-1250区间)。

### 第2层:数据→LLM 格式化
单独测 format_market_data_for_llm(df),确认输出文本含真实数值,不是元组 repr、不是空。

### 第3层:各模块独立测
- **技术分析**:输入 600519,确认输出含真实 MA/MACD/RSI,无 'tuple'...split 错误。
- **Kronos K线预测**(重点):
  ```bash
  # 启动 Kronos 微服务
  uvicorn src.plugins.kronos_service.service:app --port 8100
  # 测试预测端点
  python scripts/test_kronos.py 600519
  ```
  确认:Kronos 能从 get_kline 拿到历史K线(注意 lookback 不超过模型 max_context=512)、device 自动选(cuda/cpu)、输出未来N日概率预测+不确定区间,不报错。
- **情绪分析**:输入 600519,确认抓到真实新闻并打分;若无数据,明确报错而非编造"6.5/10"。

### 第4层:端到端 Web 测试
```bash
streamlit run src/ui/app.py
```
浏览器走完整流程:
1. 首屏免责声明 → 同意
2. 配置向导 → 填 DeepSeek key、选 BaoStock
3. 侧边栏开启「K线预测」「情绪分析」
4. 输入 600519 → 开始分析
5. 逐项检查报告:
   - [ ] 技术面:有真实价格/MA/MACD,无 tuple 错误
   - [ ] K线预测:有 Kronos 预测曲线+区间
   - [ ] 情绪面:有真实新闻情绪,或明确报错(不编造)
   - [ ] 数据来源显示 BaoStock、复权方式前复权
   - [ ] 数据体检页最近10日OHLCV与同花顺一致
   - [ ] 红色免责声明、版权页脚都在

## 四、Kronos 全量测试要点(你特别关注的)
1. **数据对接**:Kronos 的输入必须来自统一 get_kline(返回 DataFrame),确认列名、长度、复权方式正确;lookback ≤ 512。
2. **设备适配**:无N卡时走 CPU(你主力机有5070Ti会走cuda),确认 pick_device() 正常,CPU 模式也能出结果(慢些)。
3. **输出合理性**:预测值应在合理价格区间(茅台 ~1200-1300附近),不是离谱数字;用 Monte Carlo 出概率区间。
4. **失败降级**:Kronos 出错时,主分析流程不崩,报告里标注"K线预测暂不可用",其它模块照常。

## 五、测试记录模板(CC 在工作报告附上)
```
## 全量测试结果
| 模块 | 状态 | 说明 |
|------|------|------|
| 数据层 get_kline | ✅/❌ | 返回DataFrame?MA5与同花顺一致? |
| 数据格式化 | ✅/❌ | 给LLM的文本含真实值? |
| 技术分析 | ✅/❌ | 无tuple错误?有真实指标? |
| Kronos预测 | ✅/❌ | 读到数据?出预测?设备模式? |
| 情绪分析 | ✅/❌ | 真实数据?还是报错(不编造)? |
| 端到端Web | ✅/❌ | 全流程跑通? |
```
