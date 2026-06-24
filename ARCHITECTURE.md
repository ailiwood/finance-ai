# QuantSage v1.0.0 架构文档

> 完整系统架构、模块职责、数据流、部署说明。
> 最后更新：2026-06-24 (build `44d58e6`)

---

## 一、系统概览

QuantSage 是一个 **Windows 桌面股票研究辅助软件**，基于 TradingAgents-CN 多智能体框架构建。

### 1.1 核心能力

```
用户输入股票代码
    ↓
多源 K 线数据获取（BaoStock → AKShare → Tushare → 东财）
    ↓
Kronos 深度学习 K 线预测（Kronos-base 102.3M, MIT）
    ↓
8 Agent 多智能体协作分析（TradingAgents-CN）
    ↓
结构化报告组装 → 本地合规过滤 → 完整性验证
    ↓
网页展示 / Markdown 下载 / PDF 导出 / 历史存档
```

### 1.2 技术栈

| 层 | 技术 |
|----|------|
| 桌面壳 | Python 3.11 + Streamlit |
| 打包 | PyInstaller onedir + Inno Setup |
| AI 引擎 | DeepSeek API（14 供应商可选） |
| 多智能体 | TradingAgents-CN（Apache 2.0） |
| K 线预测 | Kronos-base（MIT，102.3M 参数） |
| 情绪分析 | FinBERT + 规则引擎降级 |
| 数据源 | BaoStock → AKShare(Sina) → Tushare → AKShare(EM) |
| 激活系统 | Cloudflare Workers + D1，Ed25519 签名 |
| 反编译保护 | PyArmor 9 字节码混淆 |
| 合规 | 本地确定性正则过滤，无 LLM 依赖 |

---

## 二、目录结构与模块职责

```
E:\AI_projects\fin\
├── src/                            # 全部 Python 源码
│   ├── core/                       # 核心模块（许可、配置、设备标识）
│   │   ├── license.py              # Ed25519 公钥验签 + MASTER 万能码
│   │   ├── license_guard.py        # 统一激活守卫（60s 缓存）
│   │   ├── device_id.py            # 持久化设备 UUID（%LOCALAPPDATA%\QuantSage\device.id）
│   │   └── config_manager.py       # 配置加载/存储/加密（~/.quantsage/.env）
│   │
│   ├── ui/                         # Streamlit 页面（按启动顺序）
│   │   ├── app.py                  # 主入口：免责→激活→配置→主页 流程编排
│   │   ├── disclaimer_gate.py      # 免责弹窗（首次启动强制确认）
│   │   ├── activation_gate.py      # 激活页面（设备码+支付宝收款码+激活码输入）
│   │   ├── config_wizard.py        # 3 步配置向导（API Key / 数据源 / 偏好）
│   │   ├── home.py                 # 主页：股票分析输入、后台线程、报告展示
│   │   ├── data_inspection.py      # 数据体检页（OHLCV 与同花顺/东财对账）
│   │   └── plugin_manager.py       # 插件管理页（Kronos / FinBERT 开关）
│   │
│   ├── data/                       # 数据获取与缓存
│   │   └── market_data.py          # get_kline() 4 源降级链 + 内存缓存（TTL 5min）
│   │
│   ├── analysis/                   # 技术指标计算
│   │   └── indicators.py           # compute_all_indicators() MA/MACD/RSI/KDJ/BOLL
│   │
│   ├── compliance/                 # 合规审查（红线执行）
│   │   ├── report_reviewer.py      # 本地确定性正则过滤 + LLM 门禁（仅短章节）
│   │   ├── disclaimer.py           # 免责声明母本（所有文案引用此处）
│   │   └── phrase_checker.py       # 全项目扫描违规措辞
│   │
│   ├── report/                     # 报告生成与导出
│   │   ├── report_assembler.py     # 结构化章节组装 + 完整性验证
│   │   ├── report_generator.py     # 报告生成器（Markdown 模板）
│   │   ├── pdf_exporter.py         # PDF 导出（fpdf2，SimHei 中文字体）
│   │   ├── history.py              # 报告历史存档（~/.quantsage/reports/）
│   │   └── templates.py            # 报告模板定义
│   │
│   ├── plugins/                    # 分析插件
│   │   ├── kronos_service/         # Kronos K 线预测（MIT 许可证）
│   │   │   ├── model_engine.py     # 引擎抽象层：BaseEngine → StatsEngine → KronosEngine
│   │   │   ├── gpu_detector.py     # GPU 检测（nvidia-smi / CUDA 可用性）
│   │   │   ├── service.py          # FastAPI 微服务（可选，独立进程）
│   │   │   ├── client.py           # HTTP 客户端（连接微服务）
│   │   │   ├── config.py           # 插件配置
│   │   │   └── kronos_model/       # Vendored Kronos 源码 + HF 权重缓存
│   │   │       ├── kronos.py       # KronosPredictor / KronosTokenizer
│   │   │       ├── module.py       # 模型模块定义
│   │   │       └── hf_cache/       # HuggingFace 离线权重（~406MB）
│   │   │
│   │   └── finbert_service/        # FinBERT 情绪分析
│   │       ├── sentiment_engine.py # 情绪引擎（FinBERT + 规则降级）
│   │       ├── service.py          # FastAPI 微服务（可选）
│   │       ├── client.py           # HTTP 客户端
│   │       └── config.py           # 插件配置
│   │
│   ├── deployment/                 # 部署与启动
│   │   ├── launcher.py             # 桌面启动器（父进程→子进程→健康检查→浏览器）
│   │   ├── license.py              # 许可证持久化（~/.quantsage/license.json）
│   │   ├── version.py              # 版本号
│   │   ├── resource_path.py        # 资源路径解析（开发 vs 冻结模式）
│   │   └── gpu_upgrade.py          # GPU 升级向导（CPU→CUDA torch）
│   │
│   ├── llm/                        # LLM 适配层
│   │   ├── client.py               # 统一 LLM 客户端
│   │   └── providers.py            # 14 供应商配置（DeepSeek/通义/OpenAI...）
│   │
│   ├── config/                     # 应用配置
│   │   └── sentiment_sources.py    # 情绪数据源配置
│   │
│   └── monitor/                    # 日志监控
│       ├── logger.py               # 统一日志 + trace_id
│       └── diagnostics.py          # 诊断包导出
│
├── cloudflare/                     # Cloudflare Workers 激活系统
│   ├── worker.js                   # Worker 主代码（/redeem, /order/create, /admin...）
│   ├── schema.sql                  # D1 数据库建表（vouchers + activations + orders）
│   └── wrangler.toml               # Wrangler 部署配置
│
├── installer/                      # Windows 安装包
│   ├── quantsage.iss               # Inno Setup 脚本（4 步安装向导）
│   └── assets/                     # 安装器素材（图标、许可、中文语言文件）
│
├── scripts/                        # 开发/运维脚本
│   ├── gen_vouchers.py             # 批量生成凭证码（→ CSB/TXT/SQL）
│   ├── issue_permanent.py          # 管理员签发永久码（→ /admin/issue-permanent）
│   ├── obfuscate.py                # PyArmor 字节码混淆
│   ├── prepare_staging.py          # 构建 staging 目录
│   └── gen_keypair.py              # Ed25519 密钥对生成（一次性，已执行）
│
├── patches/                        # 补丁文件（记录关键 diff）
├── tests/                          # 单元测试与集成测试
├── docs/                           # 外部文档
├── dist/                           # 构建输出（gitignored）
│   ├── QuantSage_v1.0.0/           # PyInstaller onedir 输出
│   ├── installer/                  # Inno Setup 安装包
│   └── obfuscated/                 # PyArmor 混淆输出
│
├── CLAUDE.md                       # Claude Code 项目上下文
├── GPT_PROJECT.md                  # GPT 项目指令
├── HANDOFF.md                      # 会话移交记录
├── ARCHITECTURE.md                 # 本文件
├── pyinstaller_quantsage.spec      # PyInstaller 打包配置
└── pyproject.toml                  # Python 项目配置（pytest markers）
```

---

## 三、核心数据流

### 3.1 启动流程

```
launcher.py main()
    ├── 解析命令行参数（--diagnose-kronos, --no-browser, --reset-config）
    ├── 端口检测（8501 被占用则自动切换）
    ├── spawn 子进程（--_server 模式运行 Streamlit）
    │       └── _run_server_mode()
    │           ├── 设置 Streamlit config（headless, CORS, fileWatcherType=none）
    │           └── bootstrap.run(app.py)
    │
    ├── 等待健康检查（/_stcore/health → 200）
    ├── 打开浏览器（webbrowser → os.startfile → ShellExecuteW → cmd start）
    └── 等待子进程退出
```

### 3.2 页面路由（app.py）

```
app.py main()
    ├── Gate 1: disclaimer_gate.py → 免责声明未接受 → st.stop()
    ├── Gate 2: activation_gate.py → 未激活且未跳过 → st.stop()
    │       └── is_activated() → load_license() → verify_license(key, device_code)
    ├── Gate 3: config_wizard.py → 未配置 API Key → st.stop()
    └── home.py show_home() → 主分析页面
```

### 3.3 股票分析流程（home.py）

```
用户点击"开始分析"
    ↓
show_home() 启动后台线程
    ↓
_run_analysis(symbol, stock_name, market, depth)      ← 后台线程
    ├── 1. 校验 API Key
    ├── 2. 配置 TradingAgents（max_tokens=16384, deepseek-chat）
    ├── 3. P0 数据验证：get_kline() 至少 3 行 → 否则终止
    ├── 4. Kronos 预测（注入辩论上下文）
    │       ├── get_kline(lookback_days=500) → 需 ≥30 行
    │       ├── get_engine() → KronosEngine（单例，延迟加载）
    │       ├── engine.predict(ohlcv, horizon_days=10)
    │       ├── 构造 _kronos_ctx（注入 extra_context）
    │       └── 构造 _kronos_status（写入 mailbox）
    ├── 5. TradingAgentsGraph.propagate()
    │       ├── Market Analyst → 技术面
    │       ├── Social Media Analyst → 情绪面
    │       ├── News Analyst → 新闻
    │       ├── Fundamentals Analyst → 基本面
    │       ├── Bull/Bear Debate → 多空辩论
    │       ├── Research Manager → 综合分析
    │       ├── Risk Analyst（Risky/Safe/Neutral）→ 风险三轮讨论
    │       ├── Risk Manager → 最终交易决策
    │       └── SignalProcessor → 信号处理
    ├── 6. 构建 mailbox：{symbol, decision, agent_reports, kronos_status}
    └── 写入全局 _ANALYSIS_MAILBOX

主线程轮询 _ANALYSIS_MAILBOX
    ↓
收到结果 → 写入 st.session_state.analysis_result
    ↓
show_home() 渲染报告
    ├── 1. 从 agent_reports 提取各模块内容
    ├── 2. 构建 parts 列表（按章节顺序）
    │       ├── 技术面分析（market_report）
    │       ├── 基本面分析（fundamentals_report）
    │       ├── 投资者情绪分析（sentiment_report）
    │       ├── 新闻分析（news_report，可选）
    │       ├── 风险管控与最终决策（final_trade_decision）
    │       ├── Kronos 深度学习 K 线预测（从 mailbox kronos_status 复用）
    │       ├── 综合结论（交叉引用 Kronos 预测）
    │       ├── 多周期技术指标汇总（compute_all_indicators）
    │       └── 免责声明（始终最后）
    ├── 3. 合规过滤：review_and_sanitize(report, mode="local")
    │       └── 本地确定性正则（永不调用 LLM）
    ├── 4. 完整性验证：validate_sanitized_report()
    ├── 5. 展示：st.markdown(display_report)
    ├── 6. 导出：Markdown 下载 / PDF 下载（同一份 display_report）
    └── 7. 存档：save_report() → ~/.quantsage/reports/
```

### 3.4 K 线数据获取链

```
get_kline(symbol, adjust, lookback_days)
    ├── 缓存检查（key=(symbol, adjust, lookback_days, today), TTL=300s）
    ├── 源 1: _fetch_baostock()      → BaoStock 免费前复权
    ├── 源 2: _fetch_akshare_sina()  → AKShare 新浪接口
    ├── 源 3: _fetch_tushare()       → Tushare（需 Token）
    └── 源 4: _fetch_akshare_em()    → AKShare 东方财富接口
        ↓
    DataFrame 返回（含 .attrs: source, adjust）
```

### 3.5 Kronos 引擎架构

```
model_engine.py
├── BaseEngine（抽象基类）
│   └── predict(ohlcv, horizon_days) → PredictionResult
│
├── StatsEngine（统计基线，零依赖）
│   ├── EMA 交叉判断方向
│   ├── ATR 波动率计算置信区间
│   └── 永远可用
│
├── KronosEngine（深度学习，MIT）
│   ├── 延迟加载：首次 predict() 才加载 406MB 模型
│   ├── HF cache：vendored 权重 → local_files_only=True
│   ├── Monte Carlo 采样：sample_count=30
│   ├── GPU/CPU 自动检测
│   └── 失败自动降级 → StatsEngine
│
└── get_engine()（单例工厂，线程安全锁）
    └── 全局缓存 _ENGINE_INSTANCE，避免重复加载
```

### 3.6 激活系统

```
用户购买流程：
    支付宝扫码付款（备注设备码）
    → 激活网页提交订单（POST /order/create）
    → 开发者管理后台确认收款（GET /admin）
    → 签发激活码（POST /admin/issue）
    → 用户查询激活码（GET /order/status）
    → 用户粘贴激活码到客户端

技术链：
    Cloudflare Worker（worker.js）
    ├── Ed25519 签名（Web Crypto PKCS#8）
    ├── 私钥仅存 Worker Secret（PRIVATE_KEY_HEX）
    ├── D1 数据库：vouchers + activations + orders
    └── Admin Secret 保护管理端点

客户端验证：
    license.py verify_license()
    ├── base64url 解码 → 11 字节 payload + 64 字节签名
    ├── Ed25519 公钥验签（cryptography 库）
    ├── 设备码匹配（前 8 字节）
    ├── MASTER 万能码检测（FFFFFFFFFFFFFFFF + 0xFFFF）
    └── 过期检查（epoch=2024-01-01, exp_days）
```

---

## 四、关键设计决策

### 4.1 报告完整性（P0 架构）

| 决策 | 理由 |
|------|------|
| 完整报告 **永不** 经 LLM 改写 | `max_tokens=4000` 导致截断，LLM 改写可能丢失章节 |
| 本地正则过滤为默认 | 确定性、无 API 耗时、不截断、可审计 |
| LLM 仅用于单章节（门禁保护） | `finish_reason="stop"` + 输出 ≥50% 输入 + 非空 |
| 免责声明始终最后 | 合规红线，不受报告内容影响 |

### 4.2 Kronos 单次执行

| 决策 | 理由 |
|------|------|
| 预测只在 `_run_analysis()` 执行一次 | 避免 406MB 模型重复加载（~10s 开销） |
| 结果通过 mailbox 传递给展示层 | 展示层不调用 `.predict()`，只读取 `kronos_status` |
| 引擎单例 + 线程锁 | 多线程安全，不会重复创建 KronosEngine |

### 4.3 私钥安全

| 决策 | 理由 |
|------|------|
| 私钥仅存 Cloudflare Worker Secret | 绝不出站：不在代码、git、客户端、环境变量 |
| 客户端只有公钥 | 被反编译也只能验签，无法签发 |
| PyArmor 字节码混淆 | 提高逆向门槛，公钥和验签逻辑不可读 |

### 4.4 数据真实性

| 决策 | 理由 |
|------|------|
| P0 数据验证闸 | 无数据 → 立即终止分析，禁止 LLM 编造 |
| 多源降级 | 单一数据源不可用时自动切换 |
| 缓存 TTL 5 分钟 | 防止重复请求被限频，同时保证数据新鲜度 |

---

## 五、外部依赖与许可证

| 依赖 | 许可证 | 用途 |
|------|--------|------|
| TradingAgents-CN | Apache 2.0 | 多智能体骨架 |
| Kronos-base | MIT | K 线预测模型 |
| PyInstaller | GPL + Bootloader Exception | 打包 |
| fpdf2 | LGPLv3（动态调用不传染） | PDF 导出 |
| Streamlit | Apache 2.0 | Web UI |
| DeepSeek API | 商业 API | LLM 后端 |
| cryptography | Apache 2.0 / BSD | Ed25519 验签 |
| PyArmor | 商业试用 | 字节码混淆 |

---

## 六、构建与部署

### 6.1 开发环境

```bash
conda activate quantsage_py311
cd E:\AI_projects\fin
python -m pytest tests/ -q    # 153 tests
```

### 6.2 构建安装包

```bash
# 1. 混淆核心模块
python scripts/obfuscate.py

# 2. 替换源文件为混淆版
cp dist/obfuscated/src/core/license.py src/core/license.py
cp dist/obfuscated/src/core/device_id.py src/core/device_id.py
cp dist/obfuscated/src/ui/activation_gate.py src/ui/activation_gate.py
cp dist/obfuscated/src/deployment/license.py src/deployment/license.py

# 3. PyInstaller 打包（~3 分钟）
pyinstaller pyinstaller_quantsage.spec --noconfirm

# 4. 恢复源文件
cp src/core/license.py.bak src/core/license.py   # ...同上

# 5. Inno Setup 安装包（~4 分钟）
"ISCC.exe" installer/quantsage.iss

# 输出：dist/installer/QuantSage_Setup_v1.0.0.exe (~604 MB)
```

### 6.3 部署 Worker

```bash
cd cloudflare
npx wrangler d1 execute quantsage_db --file=schema.sql --remote
npx wrangler deploy
```

---

## 七、日志与诊断

| 位置 | 内容 |
|------|------|
| `~/.quantsage/logs/quantsage.log` | 启动器日志（含崩溃堆栈） |
| `D:\QuantSage\logs\tradingagents.log` | TA-CN 分析日志（Kronos 预测、Agent 输出） |
| `D:\QuantSage\logs\error.log` | 错误日志 |
| `%TEMP%\quantsage_app_executed.txt` | 执行标记（frozen 状态、Python 路径） |
| `--diagnose-kronos` | Kronos 离线诊断（JSON 输出） |
