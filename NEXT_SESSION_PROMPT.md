# 下一阶段：线上激活系统 + 反编译保护

> 将本文发给新 Claude Code 会话作为初始指令。

---

请先阅读 HANDOFF.md 了解项目当前状态，然后执行：

## 任务 1：线上激活系统（替代离线 keygen）

离线 keygen 反复踩坑，切换到云方案。

**目标**：用户打开网页 → 输入设备码 → 扫码付款 → 自动获得密钥 → 在 App 激活。

**技术栈**：Cloudflare Worker (JS) + Cloudflare Pages (静态 HTML)

**实现**：
1. `cloud/worker.js` — Worker 代码
   - 用 `@noble/ed25519` 库签名（npm 可装）
   - 实现与 Python `scripts/keygen_gui.py` 的 `generate_key()` 完全一致的二进制 payload 格式
   - 私钥存 Worker 环境变量 `PRIVATE_KEY_HEX`
   - POST /api/activate 返回 `{"key": "QS..."}`
2. `cloud/activate.html` — 激活网页
   - 输入设备码 → 调用 Worker → 显示密钥
   - 付款二维码（先静态图，后续接支付宝/微信支付）
3. 本地 `wrangler dev` 测试 → 部署 `wrangler publish`

**关键数据**：
- 私钥 hex 从 `quantsage_private.key`（32字节）转 hex 得到
- 公钥 `3fce9236ba6b25f81e633cea68485906ffced084cb4e4aa0de5dd22554cac9c3`
- Payload 格式：dev_bytes[8] + exp_days[2] + lv[1] = 11 bytes
- 签名后 total 75 bytes → base64url → "QS" prefix → 102 chars

## 任务 2：反编译保护

PyInstaller 打包可被反编译。需保护核心模块。

**推荐方案**：PyArmor（付费 ~$50，混淆+加密字节码）或 Cython 编译关键模块为 .pyd。

**最小保护范围**：`src/core/license.py`, `src/core/device_id.py`

## 环境

- Conda: `source E:/Anaconda3/etc/profile.d/conda.sh && conda activate quantsage_py311`
- 构建: `pyinstaller pyinstaller_quantsage.spec --noconfirm`
- 测试: `python -m pytest tests/ -x -q`
- 安装器: Inno Setup 6 在 `C:/Users/Windows11/AppData/Local/Programs/Inno Setup 6/ISCC.exe`

## 重要

- 私钥不进 git、不进安装包、只存开发者本地 + 云端环境变量
- 线上密钥格式必须与 App 验证逻辑 100% 兼容
- 143 tests 保持通过
