# Handoff — 2026-06-24 14:00 (M7 激活云端化完成)

## 当前状态摘要

QuantSage v1.0.0 激活系统已从离线 keygen 迁移至**云端在线签发**方案(方案B)。全部 6 项任务完成，143 测试通过。

## 本次完成

### P0：线上激活系统（替代离线 keygen）✅

- **Cloudflare Workers 后端**：
  - D1 数据库 `quantsage_db`（`vouchers` + `activations` 表）
  - `POST /redeem`：凭证码兑换激活码（事务防并发，一码一次）
  - `POST /admin/issue-permanent`：管理员签发永久码（MASTER 万能码 + 设备绑定）
  - Worker URL：`https://quantsage-activation.lk166564317.workers.dev/`
  - **私钥只存 Worker 环境变量**，不进代码/git/客户端

- **激活网页**：Worker 自带（GET /），单页 HTML+JS

- **脚本**：
  - `scripts/gen_vouchers.py`：批量生成凭证码（CSV/TXT/SQL）
  - `scripts/issue_permanent.py`：批量签发永久码
  - `scripts/obfuscate.py`：PyArmor 混淆脚本
  - `scripts/prepare_staging.py`：构建 staging 目录

### P1：反编译保护 ✅

- PyArmor 9.2.5 字节码混淆：`license.py`, `device_id.py`, `activation_gate.py`, `deployment/license.py`
- pyarmor_runtime 打包进 exe
- 文档：`docs/PYARMOR_OBFUSCATION.md`

### 客户端大幅简化 ✅

- 删除所有本地签发逻辑（`keygen_gui.py`, `keygen.spec`, `installer/keygen.py`）
- 公钥仅用于验签，增加 MASTER 万能码支持
- 激活页面指向云端激活页

### 重新打包 ✅

- PyInstaller onedir 构建（obfuscated + pyarmor_runtime）
- Inno Setup 安装包：`dist/installer/QuantSage_Setup_v1.0.0.exe`

## 关键凭证

| 项目 | 值 |
|------|-----|
| 公钥 | `3fce9236ba6b25f81e633cea68485906ffced084cb4e4aa0de5dd22554cac9c3` |
| 私钥（云端） | Worker Secret: `PRIVATE_KEY_HEX` |
| Admin Secret | Worker Secret: `ADMIN_SECRET` = `97fb8f8070d0cf4626f6e398329e9b15` |
| D1 DB ID | `61ee22ab-03c5-431f-9640-a4856c92d366` |
| Cloudflare Account | `bb34b0be9208212351387ce918c190e2` |
| Worker URL | `https://quantsage-activation.lk166564317.workers.dev/` |

## 你需要做的事（见 USER_TODO_CLOUD_SETUP.md）

1. 注册发卡平台，挂商品
2. 用 `python scripts/gen_vouchers.py -n 100` 生成凭证码
3. 上传凭证码到发卡平台
4. 给运维人员运行 `python scripts/issue_permanent.py --device <REAL_DEVICE_CODE> --note "xxx"`
5. 端到端购买→兑换→激活测试

## 构建命令

```bash
# 激活环境
source E:/Anaconda3/etc/profile.d/conda.sh && conda activate quantsage_py311

# 测试
python -m pytest tests/ -x -q

# 重新打包（全流程）
python scripts/obfuscate.py              # 1. PyArmor混淆
# 2. 替换源文件为混淆版
cp dist/obfuscated/src/core/license.py src/core/license.py
cp dist/obfuscated/src/core/device_id.py src/core/device_id.py
cp dist/obfuscated/src/ui/activation_gate.py src/ui/activation_gate.py
cp dist/obfuscated/src/deployment/license.py src/deployment/license.py
pyinstaller pyinstaller_quantsage.spec --noconfirm  # 3. 构建
# 4. 恢复源文件
"/c/Users/Windows11/AppData/Local/Programs/Inno Setup 6/ISCC.exe" installer/quantsage.iss  # 5. 安装包
```

## 环境

- Conda env: `quantsage_py311` (Python 3.11)
- PyTorch: 2.12.1+cpu
- PyArmor: 9.2.5 (trial)
- GitHub: https://github.com/ailiwood/finance-ai
