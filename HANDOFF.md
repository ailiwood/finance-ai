# Handoff — 2026-06-24 01:00

## 当前状态摘要

QuantSage v1.0.0 桌面股票研究软件，已完成核心分析和打包，**激活模块需从离线 keygen 迁移到云端**。

## 已完成

| 模块 | 状态 | 说明 |
|------|------|------|
| 多智能体分析 | ✅ | 8 Agent (TradingAgents-CN)，DeepSeek API |
| K线数据 | ✅ | 4源降级 (BaoStock→AKShare→Tushare→东财)，全qfq |
| Kronos K线预测 | ✅ | CPU torch 打包进 exe，406MB 权重离线加载，辩论前注入 |
| FinBERT 情绪 | ✅ | 规则引擎降级 |
| 报告生成 | ✅ | Markdown + PDF，合规审查，多周期指标 |
| 安装器 | ✅ | Inno Setup，4步纯净安装（欢迎→功能→协议→安装），无激活拦截 |
| 应用内激活门 | ✅ | `src/ui/activation_gate.py`，启动流程：免责→激活→配置→主页 |
| 设备码 | ✅ | 持久化 UUID，`%LOCALAPPDATA%\QuantSage\device.id`，100% 可靠 |
| 密钥签名 | ✅ | Ed25519，公私钥已生成，公钥硬编码在 `src/core/license.py` |
| 打包 | ✅ | PyInstaller onedir，~1.4GB（含 CPU torch + Kronos 权重） |
| 测试 | ✅ | 143 tests passed |

## 未完成（明天）

### P0：线上激活系统（替代离线 keygen）

离线 keygen 反复踩坑（GUI 打包、私钥分发、路径查找），决定切换到云方案：

- **激活网页**：用户浏览器打开 → 显示设备码 → 扫码付款 → 自动返回密钥
- **云函数**：Cloudflare Worker（免费），接收设备码 → Ed25519 签名 → 返回密钥
- **订单存储**：Cloudflare D1 或 KV
- **私钥安全**：存云函数环境变量，绝不离开服务器

### P1：反编译保护

- PyInstaller 打包的 Python 字节码可被 uncompyle6/decompyle3 反编译
- 需加一层保护：PyArmor（付费，~$50）/ PyObfuscate（免费）
- 至少保护 `src/core/license.py`（含公钥和验证逻辑）

## 关键文件路径

```
E:\AI_projects\fin\
├── src/core/license.py       ← Ed25519 验证，公钥硬编码
├── src/core/device_id.py     ← 设备码（持久化UUID）
├── src/ui/activation_gate.py ← 应用内激活页面
├── src/ui/app.py             ← 主流程（免责→激活→配置→主页）
├── src/ui/home.py            ← 首页（设备码显示在标题下）
├── installer/quantsage.iss   ← Inno Setup 安装脚本（无激活拦截）
├── scripts/keygen_gui.py     ← 离线 keygen GUI（将废弃）
├── scripts/gen_keypair.py    ← 密钥对生成（一次性）
├── quantsage_private.key     ← Ed25519 私钥（32字节，不提交git）
├── pyinstaller_quantsage.spec← PyInstaller 打包配置
├── CLAUDE.md                 ← 项目主文档
└── dist/
    ├── QuantSage_v1.0.0/     ← PyInstaller 输出（~1.4GB）
    ├── installer/QuantSage_Setup_v1.0.0.exe  ← 安装包
    └── QuantSage_Keygen/     ← 离线 keygen（将废弃）
```

## 环境

- Conda env: `quantsage_py311` (Python 3.11)
- Activate: `source E:/Anaconda3/etc/profile.d/conda.sh && conda activate quantsage_py311`
- PyTorch: 2.12.1+cpu（打包用，不用 CUDA）
- Ed25519 私钥: `quantsage_private.key`（已加 .gitignore）
- Ed25519 公钥: `3fce9236ba6b25f81e633cea68485906ffced084cb4e4aa0de5dd22554cac9c3`
- GitHub: https://github.com/ailiwood/finance-ai

## 构建命令

```bash
# 激活环境
source E:/Anaconda3/etc/profile.d/conda.sh && conda activate quantsage_py311

# 测试
python -m pytest tests/ -x -q

# 构建主程序
pyinstaller pyinstaller_quantsage.spec --noconfirm

# 构建安装器
"/c/Users/Windows11/AppData/Local/Programs/Inno Setup 6/ISCC.exe" installer/quantsage.iss
```

## 已知问题

- 离线 keygen GUI 不可靠（EXE 路径查找、跨机器不一致），明天用云方案替代
- 安装包 ~1.4GB（含 torch CPU + Kronos 406MB 权重）
- fpdf2 LGPLv3（动态调用不传染，合规）
- PyInstaller GPL+Bootloader Exception（打包闭源合法）
