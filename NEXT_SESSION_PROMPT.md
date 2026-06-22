## Claude Code 初始化提示词

请先阅读以下项目文件了解全貌：
1. CLAUDE.md（项目规则、红线、技术栈）
2. workflow.md（开发工作流、里程碑）
3. README.md（项目概述）

### 当前状态

QuantSage M7 阶段（Windows 安装包 + 商用化），已接近完成。
134 个测试通过。onedir 模式打包，Inno Setup 安装器。

### 当前卡住的问题

**用户点击"开始分析"后报 401 错误**：
```
Error code: 401 - Authentication Fails, Your api key: ****D___ is invalid
```

**背景**：
- 用户已在配置向导填写了正确的 DeepSeek API Key（以 `sk-` 开头）
- 数据体检页工作正常（BaoStock 前复权数据正确，600519 收盘价 ~1215）
- Fernet 加密存储 API Key 到 `~/.quantsage/encrypted_keys.json`
- `load_config()` 三层加载：.env → encrypted_keys.json → OS env
- 上一轮已修复：移除硬编码 `startswith("sk-")` 校验、`.strip()` 清理 key
- 但问题仍然存在

**需要排查**：
1. 解密后的 key 值到底是什么——添加脱敏日志：
```python
key_masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
logger.info(f"[KEY DEBUG] provider=deepseek, len={len(key)}, masked={key_masked}")
```
2. Fernet 解密是否成功——检查 `encrypted_keys.json` 和 `.fernet_key` 是否匹配
3. `.env` 文件中的 `DEEPSEEK_API_KEY=___ENCRYPTED___` 占位符是否被正确覆盖
4. 如果覆盖安装后 `.fernet_key` 未变但 key 仍然无效 → 让用户重新配置一次 key

**可能的根因**：
- `.env` 中 `___ENCRYPTED___` 占位符没被覆盖（encrypted_keys.json 加载失败）
- Fernet key 和 encrypted value 不匹配（跨版本安装）

### 当前架构

- `src/core/config_manager.py`：配置管理，Fernet 加密，key 校验
- `src/ui/home.py`：分析入口，`_run_analysis()` 函数
- `src/data/market_data.py`：4 源数据降级链（BaoStock→AKShare Sina→Tushare→AKShare EM）
- `src/ui/app.py`：主入口，免责弹窗 → 配置向导 → 首页
- `src/llm/`：多 LLM 供应商（14 家）
- `pyinstaller_quantsage.spec`：打包配置
- `installer/quantsage.iss`：Inno Setup 安装脚本

### 构建命令

```bash
conda activate quantsage_py311
cd E:\AI_projects\fin
pyinstaller pyinstaller_quantsage.spec --noconfirm
cd installer
"C:\Users\Windows11\AppData\Local\Programs\Inno Setup 6\ISCC.exe" quantsage.iss
```

### 任务

修复 401 认证错误，确保用户配置的 DeepSeek API Key 能正确传递到 TA-CN 的 LLM 调用。
