# QuantSage 代码审查报告(基于实际代码)

> 审查范围:app.py、home.py、market_data.py、trading_graph.py、pyinstaller_quantsage.spec
> 审查视角:商业软件成熟度
> 总评:已达到"接近可售"形态,工程质量扎实(降级链、日志、后台线程、合规)。以下按严重度列出问题与建议。

---

## 总评先行

值得肯定的(读代码确认的真实优点):
- 后台线程 + 邮箱(_ANALYSIS_MAILBOX)+ 自适应轮询的分析架构,比常见的前台阻塞高明,进度反馈也已存在。
- 四源数据降级、Kronos→Stats、FinBERT→规则,降级体系是项目最扎实的部分。
- trading_graph.py 在 src/ 下封装调用 tradingagents.*,而非直接改 TA-CN 源码 —— 上游升级冲突风险低,这点做对了。
- 合规(免责/中性化/不下单/sanitize_decision)贯穿,是项目亮点。

下面是需要改的。

---

## 🔴 严重问题

### S1. 内存缓存无 TTL、key 不含日期(market_data.py:292)
```python
_cache_key = (symbol, adjust)         # 只有 symbol+adjust
if _cache_key in _kline_cache: ...    # 永不过期
```
**问题**:
- 无 TTL:用户开着软件一整天,下午分析拿到的还是早上缓存的旧价格。对金融软件是硬伤。
- key 不含日期:跨天复用同一缓存,今天明天数据会串。
**修复**:
- 缓存 key 加入交易日:`(symbol, adjust, today_trade_date)`。
- 加 TTL(如 30 分钟)或在"数据体检/分析"入口提供"强制刷新"。
- 盘中/盘后区分(盘中数据未定稿)。

### S2. License 是"16位校验和离线验证" —— 防不住盗版(商业模式命门)
校验和算法在本地、可逆向,有人扒出规则即可做注册机批量生成有效 key。对靠卖授权的软件,等于没有授权。
**建议**(按投入排序,自行取舍):
- 最低:设备指纹绑定(key 绑机器码),提高单 key 复制成本。
- 推荐:在线激活 —— 激活时联服务器校验 key+设备,服务端记录已激活设备数。需要一个轻量后端(可用 Serverless/云函数,成本极低)。
- 这是"卖软件"商业模式能否成立的根本,优先级取决于你对盗版的容忍度。

### S3. app.py 的 auto-reconnect JS 可能打断正在跑的分析
```javascript
if (r.ok) { window.location.reload(); }   // 服务器可达就 reload
```
Streamlit reload = session 重建 = 打断分析。这段 JS 在 200s 分析期间若触发,会把用户的分析直接打断,比它想解决的 WebSocket 超时更伤。且 window 'error' 监听捕获 WebSocket 错误并不可靠。
**修复**:
- 你已经有后台线程+邮箱+session_state 的架构,分析结果不依赖 WebSocket 持续连接 —— 那么这段激进 reload 的 JS 应**移除或大幅弱化**(至少:分析进行中(analysis_running)时绝不 reload)。
- 真正的断线恢复应靠"结果已在后台线程算完、存 mailbox,重连后从 session_state 读回",而非主动 reload。

---

## 🟠 中等问题

### M1. 静默吞异常(app.py 两处 `except Exception: pass`)
load_config / marker 写入用了裸 except pass。你做了优秀的日志系统,这里却把异常吞了,排查期会漏信息。
**修复**:至少 `_log.debug(...)` 记录,不要纯 pass。

### M2. 版权 footer 漏了 GitHub(app.py _COPYRIGHT_HTML)
当前只有"ailiwood + 抖音号",之前定的规范含 GitHub 主页。补上 `github.com/ailiwood` 保持一致。

### M3. 进度反馈是"第N次轮询",非语义化步骤
home.py 已有进度条+轮询计数,但显示"第N次轮询/已等待X分钟",用户不知道在干嘛。
**改进**:改成语义化阶段 —— "正在获取行情数据 → 技术面分析 → 基本面分析 → 情绪分析 → 多空辩论 → 风控评估 → 生成报告"。可在 trading_graph 各 Agent 节点回调更新进度文本(配合后台线程写一个共享进度变量)。这是体验提升最明显的一处。

### M4. 基本面缺财务指标(已知#4)
BaoStock 免费接口不给 PE/PB/ROE。
**修复**:AKShare 有免费财务接口(stock_financial_abstract / stock_a_indicator_lg 等)可补 PE/PB/ROE,接入 get_fundamentals,不必强依赖 Tushare Token。取不到的明确标注,不编造。

### M5. 报告历史无上限/清理(home.py 显示"最多30条",但存储侧?)
确认 save_report 是否有总量上限/轮转。否则长期使用 history 目录无限增长。
**修复**:保留最近 N 条(如100),超出自动清理最旧;或按大小上限。

---

## 🟡 轻微 / 可放心忽略

### 你列的许可证顾虑,两个可以卸下包袱:
- **PyInstaller(已知#2)**:GPL 带 **Bootloader Exception,明确允许打包闭源商业软件**。无数商业软件在用。**不用换 Nuitka,不用管。**
- **fpdf2(已知#1)**:LGPLv3,**动态调用(import 用 API)不传染你的代码**,商用合规。只有改 fpdf2 源码并分发才需开源那部分。你只调 API,**没问题,不用换 reportlab**。

这两个省下来,别花精力。

### 其它轻微
- app.py 的 100+ 行 CSS 硬编码在主文件 → 抽到独立 styles 模块,主文件清爽。
- 安装器部分英文(已知#6):小瑕疵,商用前补全中文翻译。
- DEBUG print(home.py:94)打 key 长度 → 确认已脱敏(看代码是 masked,OK)。

---

## 商用前最该补的三件事(优先级排序)

1. **License 在线激活 + 设备绑定(S2)** —— 卖软件的根基,否则一份包传遍全网。
2. **修内存缓存 TTL/日期(S1)** —— 金融软件给旧价格是硬伤,且简单可修。
3. **自动更新检查** —— 卖出去后推 bug 修复的生命线(当前完全缺失)。加版本号 + 启动时查最新版本提示。

次优先:语义化进度(M3)、移除危险 reload JS(S3)、基本面财务指标(M4)。

---

## 合规最后提醒(商用红线)
安装器已有"扫码付款" —— 一旦真正收款销售,"卖工具不卖荐股结论"这条红线是你最大的法律暴露面。商用前务必:
1. 复查报告输出是中性研究表述,无"买入/卖出/目标价/评级"等方向性结论(sanitize_decision 要覆盖所有出口)。
2. 免责声明在每个报告、每页可见。
3. 这部分你已做得好,只需在"开始收钱"前再系统过一遍。
