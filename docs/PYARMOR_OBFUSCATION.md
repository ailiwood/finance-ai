# PyArmor 代码加固方案

> QuantSage 核心模块字节码混淆，防止反编译后直接获取源码逻辑。

---

## 一、加固策略

三层防护：
1. **云端签名（核心防线）**：激活码由 Cloudflare Worker 私钥签发，客户端只有公钥。即使完全破解客户端，也签不出有效激活码。
2. **字节码混淆（本方案）**：PyArmor 对核心模块做字节码加密，解包后只能看到混淆过的 pyc，大幅提高逆向门槛。
3. **检测/完整性（可叠加）**：后续可加文件完整性校验，检测篡改。

## 二、保护范围

| 模块 | 路径 | 保护原因 |
|------|------|---------|
| 许可证验证 | `src/core/license.py` | 包含公钥 + Ed25519 验签逻辑 |
| 设备标识 | `src/core/device_id.py` | 设备码生成逻辑 |
| 激活页面 | `src/ui/activation_gate.py` | 激活流程 UI |
| 许可证持久化 | `src/deployment/license.py` | 许可证存储/加载 |

## 三、加固命令

```bash
# 激活环境
source E:/Anaconda3/etc/profile.d/conda.sh && conda activate quantsage_py311

# 安装 PyArmor（一次性）
pip install pyarmor

# 执行混淆
cd E:/AI_projects/fin
python scripts/obfuscate.py

# 输出: dist/obfuscated/
```

## 四、PyInstaller 集成

混淆后的文件在 `dist/obfuscated/`，打包时需要：

1. 将混淆后的 `.py` 文件替换原始 `src/` 下对应文件（或修改 spec 指向混淆目录）
2. 将 `dist/obfuscated/pyarmor_runtime_000000/` 打包进 exe（PyArmor 运行时）
3. 其余文件使用原始 `src/`

### 方式一：staging 目录（推荐）

```bash
# 准备 staging 目录
python scripts/prepare_staging.py

# 使用 staging 构建
pyinstaller pyinstaller_quantsage.spec --noconfirm \
  --add-data "dist/staging/pyarmor_runtime_000000:pyarmor_runtime_000000"
```

### 方式二：直接替换（简单，开发用）

```bash
# 1. 备份原始文件
cp src/core/license.py src/core/license.py.bak
cp src/core/device_id.py src/core/device_id.py.bak
cp src/ui/activation_gate.py src/ui/activation_gate.py.bak
cp src/deployment/license.py src/deployment/license.py.bak

# 2. 替换为混淆文件
cp dist/obfuscated/src/core/license.py src/core/license.py
cp dist/obfuscated/src/core/device_id.py src/core/device_id.py
cp dist/obfuscated/src/ui/activation_gate.py src/ui/activation_gate.py
cp dist/obfuscated/src/deployment/license.py src/deployment/license.py

# 3. 构建
pyinstaller pyinstaller_quantsage.spec --noconfirm

# 4. 恢复原始文件
mv src/core/license.py.bak src/core/license.py
mv src/core/device_id.py.bak src/core/device_id.py
mv src/ui/activation_gate.py.bak src/ui/activation_gate.py
mv src/deployment/license.py.bak src/deployment/license.py
```

## 五、验证混淆效果

```bash
# 检查混淆后的文件
head -5 dist/obfuscated/src/core/license.py
# 应显示: # Pyarmor 9.x ... 和一堆二进制数据
# 不应显示: 原始 Python 源码

# 验证逻辑正确性
python -m pytest tests/ -x -q
# 143 passed
```

## 六、效果说明

- 反编译 `.exe` → 得到混淆后的 `.pyc` → 无法阅读原始逻辑
- 即使提取出公钥（`3fce...`），由于私钥在云端，无法签发有效激活码
- 破解成本（时间+工具+知识）远高于直接购买（19.90 RMB）
- PyArmor 9.2.5 trial 版有限制，正式发布需购买 license（~$50）

## 七、重新打包流程

每次发布新版本时：
1. `python scripts/obfuscate.py` — 重新混淆
2. 按第四节集成到 PyInstaller
3. `pyinstaller pyinstaller_quantsage.spec --noconfirm`
4. `"ISCC.exe" installer/quantsage.iss`
5. 确认 `quantsage_private.key` 不在安装包中
