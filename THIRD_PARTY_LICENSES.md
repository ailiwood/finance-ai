# 第三方开源许可证登记

> 每引入一个新依赖，必须登记到本文件。许可证以 MIT / Apache 2.0 / BSD 优先。

---

## 核心依赖

| 依赖 | 版本 | 许可证 | 用途 | 出处 |
|------|------|--------|------|------|
| TradingAgents-CN | v1.0.1 | Apache 2.0 (核心) / 专有 (app, frontend) | 多智能体骨架 | https://github.com/hsliuping/TradingAgents-CN |
| DeepSeek API | - | 服务条款 | LLM 后端 | https://platform.deepseek.com/ |
| AkShare | 1.18+ | MIT | A股数据源 | https://github.com/akfamily/akshare |
| Streamlit | 1.x | Apache 2.0 | Web UI 框架 | https://github.com/streamlit/streamlit |
| cryptography | 46.x | Apache 2.0 / BSD | Fernet 加密 (API Key 本地加密存储) | https://github.com/pyca/cryptography |
| FastAPI | 0.x | MIT | Kronos / FinBERT 微服务框架 | https://github.com/tiangolo/fastapi |
| PyTorch | 2.x | BSD | GPU 推理 + CUDA 支持 | https://pytorch.org/ |
| fpdf2 | 2.x | LGPLv3 | PDF 报告生成 | https://github.com/py-pdf/fpdf2 |
| transformers | 5.x | Apache 2.0 | FinBERT 模型加载 | https://huggingface.co/ProsusAI/finbert |

---

## TradingAgents-CN 自带依赖

以下依赖随 TradingAgents-CN 安装，保留其原始 LICENSE 文件：

- openai (Apache 2.0)
- langchain / langchain-core / langchain-openai (MIT)
- langgraph (MIT)
- pymongo (Apache 2.0)
- redis-py (MIT)
- chromadb (Apache 2.0)
- fastapi (MIT)
- uvicorn (BSD)
- akshare (MIT)
- tushare (MIT)
- baostock (BSD)

完整清单见 TradingAgents-CN 仓库的 requirements.txt。

---

## 计划引入（待登记）

| 依赖 | 许可证 | 用途 | 阶段 |
|------|--------|------|------|
| transformers (HuggingFace) | Apache 2.0 | FinBERT 模型加载 (M4) |
| PyInstaller | GPL (需确认) | Windows 打包 | M7 |

---

_本文件随依赖引入持续更新。引入 GPL/AGPL 依赖前必须先问用户。_
