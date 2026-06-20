# QuantSage 5分钟安装指南

> 方案 A (Docker) — 面向发烧友 / 懂行用户 / 开发者快速本地部署

---

## 前置要求

| 组件 | Windows | Linux | macOS |
|------|---------|-------|-------|
| Docker Desktop 4.x+ | ✅ 必须 | — | ✅ 必须 |
| Docker Engine + Compose v2 | — | ✅ 必须 | — |
| NVIDIA GPU + Driver 525+ | 可选 (GPU插件) | 可选 (GPU插件) | ❌ 不支持 |
| NVIDIA Container Toolkit | 可选 | 可选 | — |
| 网络 | 需要访问 Docker Hub | 需要访问 Docker Hub | 需要访问 Docker Hub |

> **国内用户提示**: 如果拉取镜像慢，请配置 Docker 镜像加速或使用代理。
> 参见 [Docker Hub 镜像加速指南](https://docs.docker.com/engine/daemon/registry-mirror/)

---

## 第一步：获取代码

```bash
git clone https://github.com/ailiwood/finance-ai.git
cd finance-ai
```

## 第二步：配置 API Key

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，至少填入一个 LLM API Key
# Windows: notepad .env
# Linux/macOS: nano .env
```

**最小配置**（填入你的 DeepSeek API Key）：
```ini
DEEPSEEK_API_KEY=sk-your-actual-key-here
DEEPSEEK_ENABLED=true
DEFAULT_CHINA_DATA_SOURCE=akshare
```

获取 API Key: [platform.deepseek.com](https://platform.deepseek.com/)

## 第三步：启动服务

### 基础模式（仅 UI，CPU 推理）

```bash
docker compose up -d
```

打开浏览器访问 **http://localhost:8501**

### GPU 加速模式（需要 NVIDIA GPU）

```bash
# 启动 UI + GPU 插件
docker compose --profile gpu up -d
```

GPU 模式下会额外启动：
- Kronos K线预测服务 (端口 8100)
- FinBERT 情绪分析服务 (端口 8101)

### 单服务模式（开发调试）

```bash
docker compose up -d ui        # 仅 UI
docker compose up -d kronos    # 仅 Kronos
docker compose up -d finbert   # 仅 FinBERT
```

## 第四步：使用

1. 首次打开 http://localhost:8501 → 阅读并接受免责声明
2. 配置向导：输入 LLM API Key → 选择数据源 → 设置风险偏好
3. 完成后进入首页，可以：
   - 查看配置概览
   - 生成示例报告
   - 导出 PDF / Markdown 报告
   - 运行合规扫描

---

## 各系统注意事项

### Windows
- 需要 **Docker Desktop for Windows** (WSL2 后端)
- GPU 支持需要 **NVIDIA Container Toolkit for WSL2**
- 确认 WSL2 中 `nvidia-smi` 可运行

### Linux
- 需要 **Docker Engine 24+** + **Docker Compose v2**
- GPU 支持：安装 `nvidia-container-toolkit` 后重启 Docker
  ```bash
  sudo apt install nvidia-container-toolkit
  sudo systemctl restart docker
  ```

### macOS
- Docker Desktop for Mac (Apple Silicon / Intel)
- **GPU 插件不可用**（macOS 不支持 NVIDIA GPU 直通）
- 统计降级模型自动启用，功能不受影响

---

## 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 8501 | Streamlit UI | 主界面 |
| 8100 | Kronos | K线预测 (GPU可选) |
| 8101 | FinBERT | 情绪分析 (GPU可选) |

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 镜像拉取失败 | 配置 Docker 代理或镜像加速 |
| GPU 不可用 | 检查 `nvidia-smi`、`nvidia-container-toolkit` |
| 页面无法打开 | 确认端口 8501 未被占用 |
| 分析不出结果 | 检查 `.env` 中的 API Key 是否有效 |
| 报告缺免责声明 | 确认 `DISCLAIMER.md` 存在于项目根目录 |

---

## 停止和清理

```bash
# 停止所有服务
docker compose --profile full down

# 清理数据卷（重置所有配置）
docker compose down -v
```

---

*QuantSage · 本软件仅供参考研究，不构成任何投资建议，盈亏自负。*
