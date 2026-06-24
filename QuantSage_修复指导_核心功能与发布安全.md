# QuantSage 修复指导：核心功能恢复、发布可靠性与基础防护

**版本**：2026-06-24  
**适用工作目录**：`E:\AI_projects\fin`  
**已安装测试目录**：`D:\QuantSage\`  
**本轮原则**：先复现、取证、测试，再作最小修复；禁止以吞掉异常、伪造成功、静默降级来掩盖核心模块故障。  
**不在本轮实现**：支付宝自动收款/自动发码。当前用户量较低，继续采用“支付宝收款码 + 人工核账 + 管理后台签发”的稳定流程。

---

## 0. 本轮优先级与验收目标

### P0：必须先修复

1. **Kronos 深度学习 K 线预测必须在已打包安装版真实执行。**
   - 不能仅展示“统计模型降级”却被 UI 标注为深度学习。
   - 必须把实际预测对象注入技术面分析、研究辩论与最终研究结论的上下文。
   - 必须在最终报告中明确展示：模型名称、CPU/GPU、数据行数、预测方向、预测区间、置信度、模型状态。
   - 如果模型确实不可用，必须显示“模型未执行 + 可诊断原因”，而不是静默消失。

2. **报告必须完整显示。**
   - 必须至少包含：技术面、基本面、投资者情绪、新闻（有有效内容时）、风险管控/最终研究决策、Kronos 预测、综合结论、免责声明。
   - 页面、Markdown 下载、PDF 下载三者内容结构一致。
   - 不得在“投资者情绪分析”附近被截断。

3. **安装版必须稳定启动并自动尝试打开本机网页。**
   - 安装后的默认行为：启动 EXE → 本机 Streamlit 成功监听 → 默认浏览器打开实际端口 URL。
   - 若端口 8501 被占用并切换到 8502+，必须明确记录并显示真实 URL。
   - 即使自动启动浏览器失败，用户必须能从启动器界面/控制台/日志快速获得可复制 URL。

### P1：必须完成的发布前基础防护

4. Windows 安装包与主程序的 Authenticode 签名流程。
5. Worker 管理后台从浏览器暴露 `Admin Secret` 升级为短时 HttpOnly 会话 Cookie + CSRF + 登录限速。
6. 授权验证从“单一启动门禁”升级为“入口门禁 + 高价值功能执行点门禁”。
7. QuantSage 自有代码许可证从 MIT 改为专有商业许可；第三方开源组件许可证和 Notice 必须保留。

---

## 1. 已有证据与初步根因判断

### 1.1 多智能体主链路并没有在“投资者情绪分析”处崩溃

本次日志中可看到：

- 市场、社交情绪、新闻、基本面、看多/看空辩论、研究经理、交易员、风险辩论、风险经理均有执行记录；
- 风险经理明确记录“最终决策生成完成”；
- 后续 `graph_signal_processing` 也完成；
- 因此“页面只显示到投资者情绪分析”不是 TradingAgents-CN 主图提前停止的直接证据。

**高概率根因：报告展示前的合规重写发生截断。**

当前 `src/ui/home.py` 会将所有报告段落拼接为完整 `report`，随后调用：

```python
report, review_method = review_and_sanitize(report)
```

而 `src/compliance/report_reviewer.py` 的 LLM 审查调用固定：

```python
max_tokens=4000
```

它会把整篇长报告交给 LLM 重写，并在没有检查 `finish_reason`、没有校验输出长度、没有校验所有标题仍然存在的情况下，直接使用 LLM 返回文本替换原报告。报告原始顺序恰好是：

1. 技术面；
2. 基本面；
3. 投资者情绪；
4. 新闻；
5. 风险/最终决策；
6. Kronos；
7. 综合结论。

用户看到报告在“投资者情绪分析”后断裂，与“整篇报告在 4000 输出 token 附近被合规 LLM 截断”高度一致。

### 1.2 `torchvision` 缺失日志大量出现，但不能直接等同于 Kronos 根因

安装版日志出现大量：

```text
ModuleNotFoundError: No module named 'torchvision'
streamlit.watcher.local_sources_watcher
transformers.models.<vision_model>.image_processing_...
```

当前 PyInstaller spec 同时呈现以下矛盾：

- 打包依赖收集了 `transformers`；
- `requirements.txt` 声明了 `torchvision`；
- `excludes` 又显式排除了 `torchvision`；
- Streamlit 文件监视器会检查 Transformers 的惰性导入对象，进而触发大量视觉模型模块导入；
- Kronos 本身的核心源码依赖至少包含 `torch`、`einops`、`numpy`、`pandas`、`huggingface_hub`、`tqdm`，其中 `einops` 必须在构建环境中被实际验证，而不能只依赖 spec 的 `try/except` 静默跳过。

**判断**：

- `torchvision` 警告很可能首先是“Streamlit 生产环境错误开启文件监视 + Transformers 惰性导入”的噪声与稳定性问题；
- 它不必然是 Kronos 不工作的唯一根因；
- 不能为了消灭日志盲目把庞大的 `torchvision` 重新塞进 CPU 安装包；
- 必须通过“安装版真实模型加载 + 一次真实预测”证明到底缺哪一个依赖/权重/元数据。

### 1.3 Kronos 当前实现存在三个可预见的工程问题

1. **状态不透明**  
   `home.py` 对预测区块采用宽泛 `except Exception: _kronos_pred = None`。一旦失败，UI 不展示错误，日志也没有足够的模型加载、权重路径、依赖版本、fallback 原因信息。

2. **同一次分析会重复创建/加载引擎**  
   分析开始前调用一次 `get_engine().predict()` 用于注入 agents；报告渲染阶段又调用一次 `get_engine().predict()`。`get_engine()` 当前会创建新 `KronosEngine`，很可能造成同一轮分析重复加载 102M 模型、重复推理、重复占用内存，也会得到不完全一致的随机采样结果。

3. **“深度学习模型”与降级模型必须严格区分**  
   预测函数设计了 StatsEngine 降级。产品必须显示真实 `method`，并只在 `method` 明确为 Kronos-base 时标记“深度学习模型”。降级不应伪装成核心创新模块已执行。

### 1.4 自动浏览器启动已实现多策略，但成功判定存在弱点

现有 `src/deployment/launcher.py` 已具备父进程启动子进程、健康检查、`webbrowser`、`os.startfile`、`ShellExecuteW`、`cmd start` 等策略。

但当前实现仍需修正：

- `webbrowser.open(url)` 返回真不等于用户实际看到了浏览器；
- `_shell_execute()` 未检查 Win32 `ShellExecuteW` 的返回码是否大于 32；
- `cmd start` 只要命令进程返回，不代表浏览器实际打开；
- 当 8501 被占用时会切换端口，但安装版用户可能仍只知道 8501；
- 生产模式仍运行 Streamlit 的文件监视器，会产生海量 Transformers/torchvision 告警与重复脚本执行噪声；
- 自动浏览器打开失败时，没有足够直观的“复制 URL / 重新打开浏览器”兜底。

---

## 2. P0 修复方案：Kronos、报告完整性、安装版启动

## 2.1 先做不可跳过的诊断与证据采集

CC 必须先完成以下动作，不能先凭猜测改 spec：

### A. 固定版本快照

在仓库与安装目录分别记录：

```powershell
git status
git branch --show-current
git log -1 --oneline
git rev-parse HEAD

Get-ChildItem D:\QuantSage -Force
Get-ChildItem D:\QuantSage\logs -Force
Get-ChildItem "$env:USERPROFILE\.quantsage\logs" -Force -ErrorAction SilentlyContinue
```

将当前 commit SHA、安装包文件名、测试时间写入 `HANDOFF.md` 与新的修复报告。

### B. 阅读完整日志而不是仅看 `error.log`

重点读取：

```text
D:\QuantSage\logs\*.log
%USERPROFILE%\.quantsage\logs\quantsage.log
%TEMP%\quantsage_app_executed.txt
```

检索关键词：

```text
Kronos
kronos_model
HF_HOME
HF_HUB_OFFLINE
from_pretrained
local_files_only
einops
torch
torchvision
transformers
Traceback
ModuleNotFoundError
report_reviewer
finish_reason
analysis_result
analysis_running
browser
ShellExecute
port
```

### C. 同时测试开发环境和“精确安装包环境”

必须分开记录：

1. 开发 conda 环境是否可真实加载 Kronos；
2. PyInstaller staging/onedir 是否可真实加载；
3. 安装到 `D:\QuantSage\` 后是否可真实加载。

不得用“开发环境能 import”替代“安装版能执行”。

---

## 2.2 需要新增的可执行诊断能力

在 `src/deployment/launcher.py` 或专用诊断模块中新增：

```text
QuantSage_v1.0.0.exe --diagnose-kronos
```

它必须：

1. 不启动 Streamlit UI；
2. 输出并记录结构化 JSON 诊断；
3. 不访问 Hugging Face 网络；
4. 强制使用包内权重；
5. 对内置/本地样例 OHLCV 数据执行一次 10 日预测；
6. 返回非零退出码当且仅当深度学习 Kronos 没有真实执行。

建议输出字段：

```json
{
  "ok": true,
  "frozen": true,
  "python": "...",
  "torch_version": "...",
  "torch_cuda_available": false,
  "device": "cpu",
  "einops_version": "...",
  "huggingface_hub_version": "...",
  "cache_path": "...",
  "cache_exists": true,
  "model_loaded": true,
  "prediction_method": "Kronos-base (深度学习模型, CPU模式)",
  "fallback_used": false,
  "error": null
}
```

**验收红线**：生产安装包的 P0 验收中，`fallback_used` 必须为 `false`，`prediction_method` 必须包含 `Kronos-base`。

---

## 2.3 修复 Kronos 的正确架构

### A. 一轮分析只计算一次预测

在 `_run_analysis()` 中：

1. 完成 500 日前复权 K 线数据获取；
2. 完成一次 `KronosEngine.predict()`；
3. 将预测结果、模型状态、数据行数、诊断错误信息都写入 `_ANALYSIS_MAILBOX`；
4. 将同一份结构化预测摘要注入 `TradingAgentsGraph.propagate(..., extra_context=...)`；
5. 报告渲染时只使用 mailbox 中的同一份结果，绝不再次调用模型。

建议 mailbox 增加：

```python
"kronos": {
    "status": "deep_loaded" | "stats_fallback" | "disabled" | "failed" | "insufficient_data",
    "method": "...",
    "prediction": {...} | None,
    "data_rows": 0,
    "device": "cpu" | "cuda:0" | None,
    "error_code": None,
    "error_detail": None,
}
```

### B. 引擎实例单例化并加锁

`get_engine()` 应改为带线程锁的进程内单例工厂，防止：

- 同时点击或 Streamlit rerun 时重复加载模型；
- 同一次分析的双次加载；
- CPU 内存峰值异常增加；
- 前后两次随机预测不一致。

### C. 依赖与权重应显式失败，不允许静默跳过

构建前和构建后均应验证：

```python
import torch
import einops
import numpy
import pandas
import huggingface_hub
import safetensors
from src.plugins.kronos_service.kronos_model.kronos import Kronos, KronosTokenizer, KronosPredictor
```

权重检查至少验证：

- `hf_cache` 目录存在；
- 模型与 tokenizer 所需 config/权重文件存在；
- `from_pretrained(..., local_files_only=True)` 成功；
- `HF_HUB_OFFLINE=1` 时仍成功；
- 无网络时完全可预测。

不得让 `collect_all()` 的 `try/except: pass` 成为对生产依赖缺失的掩盖。对于 Kronos 必需包，构建脚本应该 fail fast。

### D. 处理 `torchvision` 的正确顺序

1. 在冻结运行环境中关闭 Streamlit 文件监视器：
   ```python
   _config.set_option("server.fileWatcherType", "none")
   ```
   并在 `flag_options` 中同步传递相同配置。
2. 在安装版确认 `torchvision` 告警不再出现。
3. 单独运行 `--diagnose-kronos`。
4. **只有当诊断证明 Kronos 或 FinBERT 的真实功能确实直接依赖 torchvision 时**，才添加与 `torch` 严格匹配的 CPU 版 `torchvision`，并把版本锁定、加到 requirements、spec、构建验证和许可证清单。
5. 若 Kronos/FinBERT 均不需要，保持 `torchvision` 不打包，避免无效增重。

### E. 必须让 AI 分析师实际接收到 Kronos

不能只向 `TradingAgentsGraph.propagate` 传参数后假设生效。CC 必须审计 `TradingAgents-CN` 中 `propagate()` 对 `extra_context` 的具体注入链路，确认以下角色至少能看到结构化内容：

- 市场/技术分析师；
- 多头研究员；
- 空头研究员；
- 研究经理；
- 风险经理或最终综合节点。

新增单元测试：mock graph/LLM 后检查每个目标 prompt 或 state 中均包含：

```text
Kronos K线量化预测
模型方法
预测方向
预测区间
概率性预测、仅供研究参考
```

模型观点只能作为独立的量化研究证据，不能被转换为“买入、卖出、仓位、止损、目标价”等交易指令。

---

## 2.4 修复报告截断：移除“整篇报告 LLM 重写”的单点风险

### 方案选择：主路径采用无损结构化规则审查

不建议把完整报告再次交给一个 `max_tokens=4000` 的 LLM 重写后直接覆盖原文。

建议改为：

1. 上游 Agent prompts 从源头使用中性研究表述；
2. `sanitize_decision()` 与本地规则审查处理全量报告；
3. 如果保留 LLM 合规审查，只可对每个章节独立处理；
4. 每个章节必须具备完整性守卫；
5. LLM 失败/截断时回退为原章节 + 规则替换，绝不删除后续章节。

### 必须新增的完整性守卫

报告构建应提取结构化章节，而不是只有一个大字符串。应至少维护：

```python
sections = [
    {"id": "technical", "title": "技术面分析", "content": ...},
    {"id": "fundamental", "title": "基本面分析", "content": ...},
    {"id": "sentiment", "title": "投资者情绪分析", "content": ...},
    {"id": "news", "title": "新闻分析", "content": ...},
    {"id": "risk", "title": "风险管控与最终研究决策", "content": ...},
    {"id": "kronos", "title": "Kronos 深度学习 K线预测", "content": ...},
    {"id": "conclusion", "title": "综合结论", "content": ...},
]
```

在显示、Markdown 导出、PDF 导出之前执行：

```python
assert_required_sections_present(...)
assert_report_not_shorter_than_safe_threshold(...)
assert_conclusion_present(...)
```

其中：

- `news` 允许因真实数据不足而缺失；
- `kronos` 若失败可显示明确的失败状态，而不是消失；
- `conclusion` 永远必须存在；
- 合规重写返回 `finish_reason != "stop"`、输出显著变短、标题丢失、结尾缺失时，必须判定失败并回退。

### 需要同步修复上游合规

当前日志中的 Agent 输出包含明显的交易指令、仓位、止损、买入/卖出等内容。由于产品定位是“研究报告，不产出交易指令”，应从 prompts、graph signal、最终决策 UI 三处统一改为：

| 禁止表述 | 合规研究表述 |
|---|---|
| 买入 / 卖出 / 持有 | 信号偏积极 / 信号偏谨慎 / 信号中性 |
| 仓位建议 | 风险暴露观察 |
| 止损位 / 止盈位 | 历史波动风险参考区间 |
| 目标价 | 模型估算参考区间 |
| 最佳买点 | 需持续观察的价格与风险条件 |

这一步既是合规修复，也能显著降低最后一层“整篇 LLM 改写”的必要性和截断风险。

---

## 2.5 修复浏览器自动打开与安装版稳定启动

### A. 禁用生产环境文件监视

冻结环境的 Streamlit 配置必须显式关闭：

```text
server.fileWatcherType = none
server.runOnSave = false
server.headless = true
server.address = 127.0.0.1
```

开发模式仍可保留 watcher；生产打包模式必须禁用，避免对 `_internal/transformers` 的惰性模块扫描。

### B. 改造浏览器打开函数

目标：每一种方法都记录真实结果，不能虚报成功。

建议顺序：

1. `os.startfile(url)`；
2. `ShellExecuteW(None, "open", url, ...)`，仅当返回值 `> 32` 视为成功；
3. `webbrowser.open_new_tab(url)`；
4. `cmd /c start "" url`；
5. 若全部失败，记录失败原因并输出明确 URL。

每次都记录：

```text
browser_method
browser_result
ShellExecuteW_return_code
actual_port
actual_url
parent_pid
child_pid
```

### C. 增加用户可操作兜底

启动器成功监听后：

- 控制台必须打印并保留实际 URL；
- 写入 `D:\QuantSage\logs\last_server_url.txt` 或用户数据目录；
- 添加 `--open-browser`/`--no-browser`/`--copy-url` 等可诊断参数；
- 安装器结束页可以提供“启动 QuantSage”复选框；
- 若端口不是 8501，所有提示都必须显示实际端口。

### D. 测试矩阵

必须在至少两台机器验证：

| 场景 | 必须验证 |
|---|---|
| 开发机 | 8501 空闲、自动打开、报告完整、Kronos 深度模型 |
| 无 GPU 测试机 | CPU 模型加载、无 CUDA 依赖、自动打开、报告完整 |
| 8501 已占用 | 自动选择替代端口、打开正确端口 |
| 默认浏览器异常/未设置 | 日志有完整原因、用户可复制 URL |
| 断网后 | 已打包 Kronos 使用包内权重仍可预测；数据源失败时清晰提示 |
| 多次连续分析 | 不重复加载模型、不丢失结果、不发生报告截断 |

---

## 3. P1：Windows Authenticode 签名

## 3.1 目标与边界

代码签名不能阻止高级破解，也不能阻止用户复制安装包；它解决的是：

- 发布者身份可验证；
- 文件篡改可被检测；
- 安装器与主程序具有可信签名；
- 通过时间戳使签名在证书到期后仍可验证。

## 3.2 凭证与仓库红线

绝不把以下内容提交到 Git：

```text
*.pfx
*.p12
*.pvk
*.spc
证书密码
云签名 API Token
硬件令牌 PIN
timestamp provider secret（若有）
```

`.gitignore` 必须覆盖上述文件；签名证书由操作系统证书存储、硬件令牌或合规云签名服务管理。

## 3.3 推荐落地方式

1. 获取适用于 Windows Authenticode 的代码签名证书；
2. 安装 Windows SDK 中的 `signtool.exe`；
3. 新增本地签名脚本，例如 `scripts/sign_windows_artifacts.ps1`；
4. 该脚本接受证书存储/云签名 provider 参数，不把密码写进代码；
5. 构建顺序：
   - PyArmor 混淆；
   - PyInstaller onedir；
   - 签名自有主 EXE；
   - 用 Inno Setup 编译安装器，并配置签署 uninstaller；
   - 签名最终 installer；
   - 用 `signtool verify /pa /all /v` 验证；
   - 保存签名验证日志和 SHA-256 manifest。

命令应使用 SHA-256 文件摘要与 RFC 3161 时间戳摘要。时间戳地址通过受控环境变量/本地私密配置传入，而不要硬编码在开源仓库。

## 3.4 签名对象

最低要求：

```text
dist/QuantSage_v1.0.0/QuantSage_v1.0.0.exe
dist/installer/QuantSage_Setup_v1.0.0.exe
安装器生成的 uninstaller（使用 Inno Setup SignTool 配置）
```

是否签署其他 `.exe/.dll` 必须按“自有可执行文件优先、第三方已签名文件不重复破坏原签名”的原则审计后决定。

---

## 4. P1：Cloudflare 管理后台安全升级

## 4.1 当前风险

浏览器端若在 `sessionStorage` 保存或重复发送 Admin Secret，则：

- 任意 XSS、浏览器插件、开发者工具、共享电脑会话都可能暴露高权限口令；
- 管理后台登录与签发动作没有可撤销的会话边界；
- 无 CSRF 防护时，已登录浏览器可能被诱导执行跨站操作；
- 既有 Secret 曾出现在聊天、日志、截图或 Git 历史中的风险必须按“已泄露”处理。

## 4.2 新目标架构

```text
浏览器 POST /admin/login（HTTPS）
  ↓
Worker 使用常量时间比较验证 ADMIN_SECRET
  ↓
Worker 生成高熵随机 session token 与 csrf token
  ↓
D1 仅保存 token hash、csrf hash、过期时间、审计字段
  ↓
浏览器收到：
  __Host-qs_admin_session=<opaque token>;
  HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=7200
  ↓
前端只保存 csrf token（内存或 sessionStorage；不是 Admin Secret）
  ↓
所有写操作携带 Cookie + X-CSRF-Token
  ↓
Worker 校验会话、有效期、CSRF、限速，再签发
```

建议 session 有效期 2 小时；退出登录时服务端删除会话行并覆盖 Cookie。

## 4.3 数据库与接口建议

新增：

```text
admin_sessions
- id
- token_hash UNIQUE
- csrf_hash
- expires_at
- created_at
- last_seen_at
- user_agent_hash
- revoked_at

admin_login_attempts
- id
- ip_hash
- attempted_at
- success
```

接口：

```text
GET  /admin                 登录/后台页
POST /admin/login           验证口令，设置 Cookie
POST /admin/logout          Cookie + CSRF，撤销会话
GET  /admin/orders          Cookie 会话认证
POST /admin/issue           Cookie + CSRF
POST /admin/issue-batch     Cookie + CSRF
```

### 保留旧 CLI 能力的处理

如果 `POST /admin/issue-permanent` 仍需供本地管理员脚本调用：

- 只允许来自本地脚本的 `X-Admin-Secret`；
- 前端 JavaScript 绝不可使用该 Header；
- 设置显式开关 `ALLOW_LEGACY_ADMIN_HEADER=false` 为生产默认；
- 将本地管理员脚本和 Worker Admin UI 分开；
- 后续版本应迁移为短时 API token 或 Cloudflare Access 保护，不长期保留万能 Header。

## 4.4 登录限速、审计和边缘访问

1. 采用 D1 记录失败并限制同一来源短时间内连续尝试；
2. 额外配置 Cloudflare WAF/Rate Limiting 作为边缘保护；
3. 生产后台优先使用 Cloudflare Access 身份策略，或在稳定 IP 场景下使用 `CF-Connecting-IP` 白名单；
4. 所有签发、拒绝、批量签发、永久码签发记录审计时间、订单号/设备码摘要、操作结果；
5. 日志不可输出 Admin Secret、会话 token、完整 license key、私钥；
6. 为 `/admin` 返回 `Cache-Control: no-store`、CSP、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer` 等基础响应头。

## 4.5 立即轮换的 Secrets

独立轮换并分别保存：

```text
ADMIN_SECRET
PRIVATE_KEY_HEX
未来支付宝应用私钥（当前不实现自动支付）
ADMIN_AUDIT_SALT（用于 IP/UA 摘要）
```

禁止复用；禁止再次写入 `GPT_PROJECT.md`、README、`.env.example`、测试脚本、截图或 commit message。

---

## 5. P1：授权检查升级

## 5.1 设计原则

保留现有 activation gate，但不要把授权判断只放在启动页。

新增单一可信入口，例如：

```text
src/core/license_guard.py
```

其职责：

```python
get_license_status()
require_feature(feature_name)
assert_license_active(feature_name)
```

不得在任何业务模块中自己复制粘贴验签或自行吞掉授权错误。

## 5.2 必须加守卫的执行点

| 功能 | 守卫位置 |
|---|---|
| 开始股票分析 | `home.py` 点击“开始分析”前 |
| 后台分析线程 | `_run_analysis()` 开头，避免绕过 UI |
| Kronos 预测 | engine/predict service 边界 |
| FinBERT 情绪分析 | service/client 边界 |
| 多 Agent 综合分析 | 创建/执行 TradingAgentsGraph 前 |
| Markdown/PDF 导出 | export 函数入口 |
| 历史完整报告打开 | 高价值报告读取入口（如适用） |

守卫失败必须产生统一中文提示：

```text
许可证未激活、已过期或与当前设备不匹配。请完成激活后使用此研究功能。
```

不得用裸 `except` 把守卫失败转换为“功能正常但无结果”。

## 5.3 测试要求

- 未激活状态：不能运行分析、Kronos、FinBERT、PDF；
- 激活状态：上述功能正常；
- 只 monkeypatch 一个 UI 门禁：后台 service 仍然阻断；
- MASTER/永久/期限码按既有设计分别验证；
- 打包版验证许可证功能不依赖项目源码目录。

测试环境可以使用 fixture/mock 激活，但生产包中不得存在 `DEBUG_BYPASS_LICENSE=true` 一类永久旁路。

---

## 6. P1：MIT 许可证与商业化处理

## 6.1 当前 MIT 文件不符合“禁止无限分发、修改和二次销售”的商业目标

当前 `LICENSE.txt` 的 MIT 文本明确授予任何获得软件副本的人：

```text
use, copy, modify, merge, publish, distribute, sublicense, and/or sell
```

因此它不适合 QuantSage 自有代码的封闭商业发行。

## 6.2 重要法律边界

1. 将未来版本改为专有许可，不能撤销已经以 MIT 发布的历史版本/已获取副本所享有的 MIT 权利；
2. 删除或私有化 GitHub 仓库不能收回已发布 MIT 版本；
3. 你可以对**后续未以 MIT 发布的自有代码和二进制发行版**使用专有许可；
4. TradingAgents-CN、Kronos、PyTorch、Streamlit、Transformers 等第三方组件仍必须按各自许可证履行义务；
5. 不得用自己的专有许可证覆盖或剥夺 Apache/MIT/BSD 第三方组件已经授予的权利；
6. 发布安装包时应同时保留第三方版权声明、LICENSE 和 NOTICE 文件。

## 6.3 推荐文件布局

```text
LICENSE.txt                         # QuantSage 自有代码/二进制的专有许可
licenses/
  THIRD_PARTY_NOTICES.md            # 依赖清单、版本、许可证、来源
  Apache-2.0.txt
  MIT.txt
  ...依赖实际需要的原始许可证文本...
EULA_CN.md                          # 可读的中文终端用户许可与免责声明
```

本交付包提供 `licenses/QuantSage_Proprietary_LICENSE.txt` 草案。CC 必须：

- 先审计项目中哪些文件是自有代码、哪些是第三方复制/修改文件；
- 保留第三方 notice；
- 在正式对外商业发行前请具备软件许可经验的律师审阅条款、主体名称、适用法律、退款/售后、隐私与数据条款；
- 使用真实版权主体名称，不要长期使用模糊占位符。

---

## 7. 必须新增/更新的测试

### 核心功能

```text
test_kronos_deep_model_smoke.py
test_kronos_context_injection.py
test_report_completeness.py
test_report_reviewer_no_truncation.py
test_packaged_kronos_diagnostic.py
test_streamlit_production_config.py
test_launcher_browser_fallback.py
```

### 安全与授权

```text
test_admin_session_cookie.py
test_admin_csrf.py
test_admin_login_rate_limit.py
test_admin_session_expiry.py
test_license_guard_feature_enforcement.py
test_license_guard_no_ui_bypass.py
```

### 发布

```text
test_license_notice_manifest.py
test_build_dependency_manifest.py
test_codesign_verify.ps1
```

---

## 8. 本轮验收清单

### P0 不可妥协

- [ ] `--diagnose-kronos` 在 `D:\QuantSage\` 安装版返回深度模型成功，未使用 fallback；
- [ ] 在无网络/无 GPU 环境完成一次 Kronos 预测；
- [ ] 同一分析只执行一次 Kronos 推理；
- [ ] 预测内容进入指定 Agent 上下文，有自动化测试；
- [ ] 页面、Markdown、PDF 三者均有完整章节与综合结论；
- [ ] 特意构造大于 4000 token 的报告也不会丢结尾；
- [ ] `torchvision` watcher 告警在生产安装版消失或被明确证明不影响功能；
- [ ] 测试机双击 EXE 后自动打开实际 URL，8501 占用时能打开备用端口或明确显示 URL；
- [ ] 现有测试与新增测试全部通过。

### P1 发布前通过

- [ ] 管理后台前端不再保存/发送 Admin Secret；
- [ ] HttpOnly + Secure + SameSite=Strict Cookie 会话、CSRF、限速、退出登录、过期测试全部通过；
- [ ] 所有曾暴露的 Secret 已轮换且不再出现在 Git；
- [ ] 高价值功能均有 license guard；
- [ ] `LICENSE.txt` 改为 QuantSage 专有许可，`licenses/` 保留第三方许可与 Notice；
- [ ] 主 EXE、uninstaller、最终 installer 都经过 Authenticode 签名和时间戳验证；
- [ ] 新安装包在开发机与无 GPU 测试机完成端到端验证。

---

## 9. 本轮不应做的事情

- 不实现支付宝自动支付回调；
- 不通过移除日志/吞异常伪造“Kronos 正常”；
- 不用 `torchvision` 作为不经诊断的万能修复；
- 不让 LLM 整篇重写覆盖长报告而没有截断检测；
- 不在浏览器前端继续保存 Admin Secret；
- 不用“删除 GitHub 仓库”替代许可证治理；
- 不删除第三方开源许可证或 NOTICE；
- 不恢复“买入/卖出/仓位/止损”形式的交易指令；
- 不把私钥、管理员口令、证书、PFX、签名 token 写入任何可提交文件。
