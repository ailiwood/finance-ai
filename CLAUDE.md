# CLAUDE.md — QuantSage 项目说明（Claude Code 主上下文）

> 这是 Claude Code 在本项目中的"宪法"。每次会话自动加载。请严格遵守。

---

## 0. 一句话项目定位

QuantSage 是一个**本地运行的多智能体股票研究辅助软件**，基于 TradingAgents-CN（Apache 2.0）二次封装，加入 Kronos K线预测插件、FinBERT 情绪分析插件，做成"用户简单配置即可使用"的打包软件。

**它产出研究报告，不产出交易指令；不集成任何实盘下单功能。**

---

## 1. 🚨 绝对红线（违反即视为严重错误）

1. **禁止编写任何实盘下单 / 自动交易 / 经纪商交易接口代码。** 本软件只做分析与信息整合。如果某个需求暗示要"自动买卖""连接券商下单"，**停下来，向用户确认并提示合规风险**，不要直接实现。
2. **每一处面向用户的输出（UI 首屏、报告、PDF 页脚、API 响应）都必须包含免责声明**："本软件仅供参考研究，不构成任何投资建议，盈亏自负。" 删除或弱化免责声明属于红线行为。
3. **措辞合规**：代码注释、UI 文案、报告模板中禁止出现"推荐买入""稳赚""保证收益""必涨"等表述。统一用"研究观点""分析参考""仅供参考"。
4. **保留所有第三方开源许可证**：任何引入的依赖，其 LICENSE / NOTICE 必须保留，并登记到 `THIRD_PARTY_LICENSES.md`。
5. **用户密钥只存本地**：API Key、token 等敏感信息只能存在用户本地（`.env` 或本地配置文件），**绝不写入代码、绝不上传、绝不打日志**。

> 任何一条红线，宁可暂停问用户，也不要擅自越过。

---

## 2. 技术栈（不要随意替换）

| 层 | 选型 | 说明 |
|----|------|------|
| 核心引擎 | TradingAgents-CN | Apache 2.0，多智能体骨架，勿重造轮子 |
| Web UI | Streamlit（V1）→ Tauri/Electron（商业版）| 先复用现成的 |
| LLM 后端 | DeepSeek/通义 API（默认）+ Ollama/vLLM（本地可选）| FP8 量化 Qwen3-14B 跑在 5070 Ti |
| K线预测 | Kronos（MIT），封装为 FastAPI 微服务 | GPU 可选，不可用则降级 |
| 情绪分析 | FinBERT / FinBERT2 | 本地推理 |
| 数据源 | AkShare（免费默认）/ Tushare（进阶）/ Finnhub（美股）| 多源 + 本地缓存 |
| 缓存存储 | DuckDB / Parquet | 避免重复请求被限频 |
| 打包 | Docker Compose（首发）+ PyInstaller/Tauri（商业版）| 见 workflow.md |
| 语言 | Python 3.10+ | |

**硬件目标**：Win11 + 9950X + RTX 5070 Ti (16GB) + 64GB。代码要兼容"无 GPU 降级运行"。

---

## 3. 项目结构约定

```
quantsage/
├── CLAUDE.md                  # 本文件
├── workflow.md                # 开发工作流（必读）
├── THIRD_PARTY_LICENSES.md    # 第三方许可证登记
├── DISCLAIMER.md              # 免责声明母本（所有文案引用此处）
├── .env.example               # 配置模板（绝不含真实密钥）
├── docker-compose.yml         # 方案A 一键部署
├── src/
│   ├── core/                  # TradingAgents-CN 封装层
│   ├── plugins/
│   │   ├── kronos_service/    # Kronos K线预测微服务
│   │   └── finbert_service/   # FinBERT 情绪分析
│   ├── data/                  # 数据源适配 + 缓存
│   ├── ui/                    # Streamlit 界面 + 配置向导
│   ├── report/                # 报告生成 + PDF 导出（含免责注入）
│   └── compliance/            # 免责声明注入、措辞校验
├── tests/
└── docs/
```

---

## 4. 编码规范

- **风格**：遵循 PEP8，用 `ruff` 格式化与 lint，`mypy` 做类型检查。所有函数写类型注解。
- **降级优先**：任何依赖 GPU / 外部 API / 付费数据的功能，必须有"不可用时优雅降级"的分支，绝不让主流程崩溃。
- **配置外置**：所有可变参数（模型名、API 端点、风险阈值）走配置文件 / 环境变量，禁止硬编码。
- **可解释性**：Agent 的每个决策都要带 `{方向, 置信度, 理由}`，禁止黑箱输出。
- **错误处理**：对外部调用（LLM/数据 API）做重试 + 超时 + 友好报错，不暴露原始堆栈给最终用户。
- **中文优先**：面向中国用户，UI/报告/错误提示默认中文。

---

## 5. Claude Code 行为准则

1. **先读后写**：改动前先 `read` 相关文件与 `workflow.md`，理解现状再动手。
2. **小步提交**：每个改动聚焦单一目标，配合清晰的 commit message。
3. **遇红线即停**：触及第 1 节任何红线时，停止并向用户说明，不擅自实现。
4. **测试同行**：新功能必须配单元测试（`tests/`），关键路径要有降级测试。
5. **改 UI 文案 / 报告模板时**，自动检查是否带免责声明、是否有违规措辞（调用 `src/compliance/` 的校验）。
6. **引入新依赖前**：确认其许可证可商用（MIT/Apache/BSD 优先），并登记到 `THIRD_PARTY_LICENSES.md`。GPL/AGPL 类需先问用户。
7. **不假设密钥存在**：涉及 API Key 的代码要处理"未配置"情况，引导用户走配置向导。

---

## 6. 常用命令（详见 .claude/commands/）

- `/setup` — 初始化开发环境
- `/run-dev` — 本地启动 Streamlit 调试
- `/build-docker` — 构建并测试 Docker 镜像
- `/check-compliance` — 全项目扫描免责声明与违规措辞
- `/add-plugin` — 按规范脚手架一个新插件

---

## 7. 当前进度（活文档，每次会话先看这里）

> 用里程碑追踪进度，不设时间。整体顺序：**先做通方案 A（M1→M6），再做方案 B（M7）**。
> 详见 `workflow.md` 第三节。完成一个里程碑就在这里更新勾选状态。

**阶段**：阶段一 · 方案 A（Docker，面向发烧友/懂行用户/作者本人）

- [x] **M1 打地基** — Fork TradingAgents-CN，Docker 跑通，分析一只 A股 ✅ (2025-06-20)
- [x] **M2 配置向导 + 免责关口** — 免责弹窗 + 3步配置向导 + 加密持久化 ✅ (2025-06-20)
- [x] **M3 Kronos 插件（GPU 可选）** — FastAPI 微服务 + GPU 检测 + 统计降级 ✅ (2025-06-20)
- [x] **M4 FinBERT 情绪插件** — 情绪打分 + 批量新闻评分 + 情绪指数 ✅ (2025-06-21)
- [x] **M5 报告 + 合规** — 报告模板 + PDF 导出 + 合规扫描 ✅ (2025-06-21)
- [x] **M6 方案 A 可分发** — Docker Compose + GPU profiles + 安装指南 ✅ (2025-06-21)
- [ ] **M7 方案 B**（Windows 安装包，商用化）← *阶段二，M6 稳定后启动*

**阶段一完成！** 仓库: https://github.com/ailiwood/finance-ai
**开发环境**：`E:\Anaconda3\envs\quantsage_py311` (Python 3.11, PyTorch 2.11+cu128, RTX 5070 Ti)
**已知问题**：
- fpdf2 为 LGPLv3 许可证，如需完全合规可替换为 reportlab (BSD)
- M2 加密密钥存储在 ~/.quantsage/.fernet_key，Windows 下无法 chmod 限制权限

---

_本文件随项目演进持续更新。任何架构级决策变更，先改本文件再写代码。_
