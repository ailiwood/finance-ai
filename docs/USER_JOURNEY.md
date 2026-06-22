# QuantSage 全流程说明——从分发到运行

> 面向用户：完整说明获取、安装、配置、使用的全部流程。
> 面向开发者：完整说明打包、分发、激活的技术实现。

---

## 一、分发与获取

```
用户 → 抖音/飞书 → 联系开发者 → 支付宝付款 ¥19.90 → 获取安装包 + License Key
```

| 步骤 | 说明 |
|------|------|
| 1. 发现 | 用户在抖音 (@23230218947) 或飞书群看到 QuantSage |
| 2. 咨询 | 私信开发者了解功能、系统要求 (Win10/11, 64位) |
| 3. 付款 | 支付宝扫码支付 ¥19.90（一次性买断，终身使用） |
| 4. 获取 | 开发者发送安装包下载链接 + 唯一的 License Key |
| 5. 下载 | 用户下载 `QuantSage_Setup_v1.0.0.exe` (~1.2GB, 含 AI 模型) |

---

## 二、安装流程

```
双击 exe → 免责声明 → 扫码付款 → 输入 License Key → 验证 → 安装 → 完成
```

### 安装器页面顺序

| 页面 | 内容 |
|------|------|
| **Welcome** | 欢迎页，显示软件名称和版本 |
| **License & Purchase** | 四项内容：①软件用途说明（研究工具，非交易系统）②风险警告（不构成投资建议，盈亏自负）③支付宝收款码 ④License Key 输入框 |
| **Key Validation** | 离线校验 Key 的数学 checksum，不联网。有效 → 继续；无效 → 提示联系开发者 |
| **Component Selection** | 选择安装组件（默认：核心程序） |
| **Installation** | 解压 ~1.2GB 文件到 `%LOCALAPPDATA%\Programs\QuantSage\` |
| **Finish** | 安装完成，可选立即启动 |

### License Key 技术细节

- **格式**: `QS-XXXX-YYYY-ZZZZ-WWWW` (4组4位十六进制)
- **验证**: 纯数学 modular checksum，完全离线，不需要服务器
- **生成**: 开发者使用 `installer/keygen.py` 生成
- **一机一码**: 当前版本未强制绑定机器，后续版本加入机器码验证

### 安装目录结构

```
%LOCALAPPDATA%\Programs\QuantSage\
├── QuantSage_v1.0.0.exe          # 主程序启动器
├── _internal\                     # 所有依赖和资源
│   ├── src\                       # QuantSage 代码
│   ├── tradingagents\             # TA-CN 多智能体引擎
│   ├── .env.example               # 配置模板
│   └── ...
└── licenses\                      # 第三方许可证
```

---

## 三、首次启动与配置

```
启动 exe → 免责弹窗 → 配置向导 (3步) → 首页
```

### 步骤详解

| 步骤 | 页面 | 用户操作 |
|------|------|----------|
| **Gate 1** | 免责声明弹窗 | 阅读风险警告，勾选"同意"才能继续。不同意则退出 |
| **Gate 2** | 配置向导 Step 1 | 选择 LLM 供应商 (DeepSeek)，输入 API Key，点击"测试连接"验证 |
| **Gate 2** | 配置向导 Step 2 | 选择数据源 (默认 AkShare 免费)，可选填 Tushare Token |
| **Gate 2** | 配置向导 Step 3 | 设置风险偏好 (保守/平衡/积极) + 分析深度 (1-5) |
| **首页** | 首页 | 配置完成，进入主界面 |

### API Key 获取

- **DeepSeek**: 访问 [platform.deepseek.com](https://platform.deepseek.com/)，注册 → 创建 API Key → 复制
- Key 以明文存储在用户本地 `~/.quantsage/.env`，绝不会上传或回传

---

## 四、日常使用流程

```
首页 → 输入股票代码 → 选择分析深度 → 点击"开始分析" → 等待 3-5 分钟 → 查看报告
```

### 分析引擎工作流程（内部）

```
用户点击"开始分析"
│
├─ [1] 数据验证
│   └─ get_kline(symbol) → BaoStock 前复权 K线
│       ├─ 返回: DataFrame (733行, 收盘价=1215.00)
│       ├─ 检查: 数据是否为空? 行数 ≥ 3?
│       └─ 失败 → 终止分析，提示用户检查网络
│
├─ [2] LLM 配置
│   ├─ 读取 API Key (DeepSeek)
│   ├─ 创建 ChatOpenAI 客户端
│   └─ 设置 max_tokens=16384, temperature 等
│
├─ [3] 多智能体分析 (LangGraph)
│   ├─ Market Analyst (技术面)
│   │   └─ 桥接: get_kline() + format_market_data_for_llm() → LLM
│   ├─ Fundamentals Analyst (基本面)
│   │   └─ 桥接: get_kline() 最新收盘价 + get_fundamentals() → LLM
│   ├─ News Analyst (新闻面)
│   │   └─ 桥接: fetch_china_news() → 东方财富个股新闻 → LLM
│   ├─ Sentiment Analyst (情绪面)
│   │   └─ 桥接: fetch_china_news() → LLM 基于真实新闻打分
│   ├─ Bull/Bear Researchers (多空辩论)
│   ├─ Research Manager (辩论裁判)
│   ├─ Trader (交易决策)
│   └─ Risk Management (风险评估)
│
├─ [4] 报告组装
│   ├─ 技术面分析 → 含真实 MA/MACD/RSI/价格
│   ├─ 基本面分析 → 真实价格 + 可得财务数据
│   ├─ 情绪面分析 → 基于真实新闻的情绪判断
│   └─ 新闻面分析 → 真实个股公告/新闻
│
├─ [5] 合规审查
│   ├─ 扫描报告中的违规措辞 (买入推荐/保证收益等)
│   ├─ 检查免责声明完整性
│   └─ 替换为合规措辞 (研究观点/分析参考)
│
└─ [6] 展示报告
    ├─ 网页端显示完整报告 (含 SVG 图标卡片)
    ├─ 可下载 Markdown / PDF
    └─ PDF 每页页脚强制注入免责声明
```

### 分析深度设置

| 深度 | 含义 | 预计耗时 |
|------|------|----------|
| 1 | 快速扫描 | ~2分钟 |
| 2 | 基础分析 | ~3分钟 |
| 3 | 标准分析 (默认) | ~4分钟 |
| 4 | 深度分析 | ~5分钟 |
| 5 | 全面研究 | ~7分钟 |

---

## 五、数据来源

### K 线数据 (股价)

| 优先级 | 数据源 | 复权方式 | 费用 |
|--------|--------|----------|------|
| 1 | **BaoStock** | 前复权 (qfq) | 免费 |
| 2 | AKShare 新浪 | 前复权 (qfq) | 免费 |
| 3 | Tushare | 不复权 | 需注册 Token |
| 4 | AKShare 东方财富 | 前复权 (qfq) | 免费 |

### 新闻数据

| 优先级 | 数据源 | 费用 |
|--------|--------|------|
| 1 | 东方财富个股公告 (HTTP 直连) | 免费 |
| 2 | Google News | 免费 |

### 基本面数据

| 数据 | 来源 | 说明 |
|------|------|------|
| 公司名称/行业/上市日期 | BaoStock query_stock_basic | 免费 |
| PE/PB/ROE/EPS | 暂不可用 | 需 Tushare Token |

### AI 模型

| 模型 | 用途 | 来源 |
|------|------|------|
| DeepSeek V4 Flash | 多智能体分析推理 | DeepSeek API (用户自备 Key) |
| Kronos-base (102.3M) | K 线深度学习预测 | HuggingFace (内置权重) |
| FinBERT | 情绪分析 | HuggingFace (可选) |

---

## 六、硬件检测与 GPU 升级

```
启动 → detect_hardware() → 显示算力模式
  ├─ 无 NVIDIA 显卡 → "CPU 模式 (适用于所有电脑)"
  ├─ 有 NVIDIA 显卡 + CPU 版 PyTorch → "检测到 RTX 5070 Ti, 可升级 GPU 版 [按钮]"
  └─ 有 NVIDIA 显卡 + CUDA 版 PyTorch → "GPU 加速已启用"
```

- **默认**: 安装包内置 CPU 版 PyTorch，所有电脑开箱即用
- **升级**: 用户主动点击"升级 GPU 版" → pip 安装 CUDA 版 PyTorch → 重启生效
- **失败回退**: GPU 升级失败不破坏 CPU 版，仍可正常使用

---

## 七、日志与诊断

```
所有日志 → %LOCALAPPDATA%\QuantSage\logs\
  ├─ quantsage_2026-06-22_17-11.log              # 主日志 (每次启动一个文件)
  └─ quantsage_2026-06-22_17-11_600519_a3b84b8d.log  # 每次分析的专属日志

用户出问题时:
  1. 打开首页 → 点击"诊断日志"按钮 → 下载 zip
  2. 将 zip 发给开发者
  3. zip 包含: 最近日志 + 系统信息 (不含 API Key)
```

---

## 八、技术架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      QuantSage 架构                          │
├─────────────────────────────────────────────────────────────┤
│  UI 层 (Streamlit)                                          │
│  ├─ app.py          → 路由 (免责 → 配置 → 首页)               │
│  ├─ home.py         → 分析入口 + 报告展示 + 学习中心          │
│  ├─ config_wizard.py → 3步配置向导                           │
│  └─ data_inspection.py → 数据体检                            │
├─────────────────────────────────────────────────────────────┤
│  数据层 (src/data/)                                          │
│  ├─ market_data.py  → get_kline() 4源降级链                  │
│  │                   + format_market_data_for_llm()           │
│  │                   + fetch_china_news() + get_fundamentals()│
│  └─ indicators.py   → compute_all_indicators()                │
├─────────────────────────────────────────────────────────────┤
│  引擎层 (TradingAgents-CN, Apache 2.0)                       │
│  ├─ agents/         → 市场/基本面/新闻/情绪/多空/风控 8个Agent │
│  ├─ graph/          → LangGraph 工作流编排                    │
│  └─ llm_clients/    → DeepSeek/OpenAI 统一客户端              │
├─────────────────────────────────────────────────────────────┤
│  插件层 (src/plugins/)                                       │
│  ├─ kronos_service/ → Kronos-base (102.3M) K线深度学习预测    │
│  └─ finbert_service/→ FinBERT 情绪分析                        │
├─────────────────────────────────────────────────────────────┤
│  监控层 (src/monitor/)                                       │
│  ├─ logger.py       → 分级日志 + trace_id + 脱敏              │
│  └─ diagnostics.py  → 一键导出诊断包                          │
├─────────────────────────────────────────────────────────────┤
│  合规模块 (src/compliance/)                                  │
│  ├─ disclaimer.py   → 免责声明注入                             │
│  └─ phrase_checker.py → 违规措辞扫描                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 九、红线约束（开发者必读）

1. **禁止实盘下单**：本软件只做分析，不集成任何交易接口
2. **每处输出必须带免责声明**："仅供参考研究，不构成任何投资建议，盈亏自负"
3. **禁止编造数据**：所有模块数据缺失时必须明确报错，绝不编造
4. **禁止推荐措辞**：代码/UI/报告中禁用"推荐买入""稳赚""保证收益"等
5. **API Key 只存本地**：绝不写入代码、绝不上传、绝不记入日志
6. **保留所有第三方许可证**

---

*QuantSage — 智能股票研究助手 | 仅供参考研究 | 不构成投资建议*
