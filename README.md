# QuantSage — Claude Code 配置包说明

这是 QuantSage 项目的 Claude Code 配置文件集。把这些文件放到你的项目根目录，Claude Code 会自动加载，从而带着"项目规则 + 工作流 + 合规红线"工作。

## 文件清单

```
quantsage/
├── CLAUDE.md                          # 主上下文：项目定位、红线、技术栈、行为准则（每次会话自动加载）
├── workflow.md                        # 开发工作流：标准循环、里程碑任务、测试要求
├── CC_INIT_PROMPT.md                  # ★ 首次会话初始化提示词（粘贴给 CC，引导完成 M1）
├── DISCLAIMER.md                      # 免责声明母本：所有文案的唯一来源 + 违规措辞黑名单
├── THIRD_PARTY_LICENSES.md            # 第三方许可证登记（法律义务）
├── .env.example                       # 配置模板（复制为 .env，填入自己的密钥）
└── .claude/
    └── commands/                      # 自定义斜杠命令
        ├── setup.md                   # /setup        初始化环境
        ├── run-dev.md                 # /run-dev      本地调试启动
        ├── build-docker.md            # /build-docker 构建测试 Docker
        ├── check-compliance.md        # /check-compliance 合规扫描
        └── add-plugin.md              # /add-plugin   脚手架新插件
```

## 如何使用

1. **创建项目目录**，把以上文件复制进去。
2. **Fork 核心引擎**：`git clone https://github.com/hsliuping/TradingAgents-CN.git` 作为 `src/core/` 的基础。
3. **在项目根目录启动 Claude Code**：`claude`。它会自动读取 `CLAUDE.md`。
4. **首次会话**：把 `CC_INIT_PROMPT.md` 里的【提示词正文】整段粘贴给 CC，它会引导你从 M1（打地基）开始本地部署——**今晚就能开干**。
5. **日常开发**：按 `workflow.md` 的里程碑顺序推进（**先做通方案 A 的 M1→M6，再做方案 B 的 M7**）；涉及 UI/报告改动后跑 `/check-compliance`。

## 设计要点（为什么这么配）

- **CLAUDE.md 第1节"绝对红线"** 是核心：禁止实盘下单、强制免责声明、措辞合规、保留许可证、密钥只存本地。这些是 Claude Code 工作时的硬约束。
- **DISCLAIMER.md 作为单一来源**：避免免责声明在各处写得不一致，也给合规扫描器一个权威黑名单。
- **降级优先原则贯穿始终**：无 GPU / 无网络 / 无密钥都要能优雅退化——这是"用户简单配置就能用"的前提。
- **斜杠命令封装高频操作**，让重复工作标准化、可复用。
- **CLAUDE.md 第7节"当前阶段"** 是活文档：每次会话先看这里，让 Claude Code 知道项目进展到哪。

## 给两台机器的提示

- **Win 端 Claude Code**：用这套配置做工程/UI/打包/合规。
- **Linux 虚拟机 Codex**：做 Kronos/FinBERT 模型实验。两端用 Git 同步，插件以 HTTP API 解耦。

---

> 记住红线：本软件只做研究分析，不做实盘下单；每处输出都带免责声明。
