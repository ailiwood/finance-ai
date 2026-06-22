# LOGGING_MONITOR_MODULE.md — 全链路日志监控模块设计

> 放到项目 `docs/`。本模块优先级最高:它是排查数据链路问题的"眼睛",也是商业化售后的基础设施。
> 目标:让数据在每个关键节点的"进/出"都可追溯,出问题一看日志就知道断在哪。

---

## 一、为什么要做(动机)
前面几轮反复修数据链路都在"猜"根因,因为链路不透明——数据从"取数→传输→格式化→喂LLM→报告"中间隔着 TA-CN 黑盒,只能看到最后报错,看不到中间哪环出错。本模块让每个交接处的数据形态都被记录,把排查从"猜"变成"看"。

同时服务三个层次:
| 层次 | 用途 |
|------|------|
| 现在排查 | 详细链路追踪,看清数据每步形态 |
| 商业化售后 | 客户出问题一键导出日志发给开发者,远程判断 |
| 隐私合规 | 日志绝不含key、绝不回传 |

---

## 二、模块结构

新建 `src/monitor/logger.py`(或 src/logging/),统一日志入口。

### 1. 分级 + 双输出
```python
import logging, os, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_INITIALIZED = False  # 幂等标志,防 Streamlit rerun 重复初始化

def setup_logging():
    global _INITIALIZED
    if _INITIALIZED:
        return
    log_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QuantSage" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("quantsage")
    root.setLevel(logging.DEBUG)
    if root.handlers:           # 双保险幂等
        _INITIALIZED = True
        return

    # 控制台:INFO 以上(干净)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    # 文件:DEBUG 全量,按天/大小切分,自动清旧
    fh = RotatingFileHandler(log_dir / "quantsage.log",
                             maxBytes=10*1024*1024, backupCount=7,
                             encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(trace)s | %(message)s")
    for h in (ch, fh):
        h.setFormatter(fmt)
        root.addHandler(h)
    _INITIALIZED = True
```
要点:
- 日志放 `%LOCALAPPDATA%\QuantSage\logs\`,RotatingFileHandler 限 10MB×7 个文件,不无限增长。
- **幂等**:解决之前 setup_logging 每次 rerun 重复执行的问题。
- 编码 utf-8,解决之前 emoji 在 GBK 控制台报 UnicodeEncodeError 的问题(文件用utf-8;控制台可加 errors="replace")。

### 2. trace_id(链路追踪核心)
每次"开始分析"生成唯一 trace_id,贯穿本次所有日志:
```python
import uuid, contextvars
_trace = contextvars.ContextVar("trace", default="-")

def new_trace():
    tid = uuid.uuid4().hex[:8]
    _trace.set(tid)
    return tid

# 用 logging.Filter 把 trace 注入每条日志
class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace = _trace.get()
        return True
```
在点击"开始分析"的入口调用 new_trace(),这样这次分析的所有日志都带同一个 trace,能从一堆日志里精确挑出"这次600519分析"的完整链路。

### 3. 脱敏(硬性)
```python
def mask_secret(s: str) -> str:
    if not s or len(s) < 8:
        return "****"
    return f"{s[:4]}****{s[-2:]}(len={len(s)})"
```
任何 key/token 入日志前必须 mask。**绝不打印完整 key**——这模块将来客户会把日志发给你,绝不能成泄密渠道。

---

## 三、关键节点埋点(排查数据问题的关键)

在数据链路每个"交接处"记录数据**形态**(类型/行数/关键值/长度),不只记成功失败。建一个辅助函数:
```python
log = logging.getLogger("quantsage.data")

def log_data_shape(stage: str, obj):
    """记录数据在某阶段的形态"""
    import pandas as pd
    if isinstance(obj, pd.DataFrame):
        latest = obj["close"].iloc[-1] if "close" in obj and len(obj) else "?"
        log.debug(f"[{stage}] DataFrame 行数={len(obj)}, 最新close={latest}, "
                  f"attrs={dict(obj.attrs)}")
    elif isinstance(obj, str):
        log.debug(f"[{stage}] str 长度={len(obj)}, 前100字={obj[:100]!r}")
    elif obj is None:
        log.warning(f"[{stage}] 返回 None!")
    else:
        log.debug(f"[{stage}] type={type(obj).__name__}, repr={repr(obj)[:200]}")
```

### 必埋的节点(覆盖整条链路)
1. `get_kline` 入参 + 返回形态(行数、最新收盘、source)
2. `format_market_data_for_llm` 入参 + 返回(长度、前100字)→ 确认没变空/元组
3. TA-CN `get_stock_market_data_unified` / `get_china_stock_data_unified` 入参 + 返回 → **黑盒这里会暴露**
4. 实际传给 market_analyst / 各 Agent 的数据长度 → 确认数据进了 LLM
5. LLM 请求前:provider、model、消息总长度(不打key)
6. LLM 响应后:响应长度、是否含 tool_calls
7. 基本面/新闻/情绪各自取数的入参+返回形态
8. 每个数据源(BaoStock/AKShare/Tushare)调用的成功/失败+原因

这样一条 trace 看下来,数据在哪一步从"73行真实数据"变成"空/None/假价格",一目了然。

---

## 四、异常捕获
```python
def install_excepthook():
    import sys, traceback
    def hook(exc_type, exc, tb):
        logging.getLogger("quantsage").critical(
            "未捕获异常:\n" + "".join(traceback.format_exception(exc_type, exc, tb)))
        sys.__excepthook__(exc_type, exc, tb)
    sys.excepthook = hook
```
任何没被 catch 的崩溃都写进日志(含堆栈),避免"闪退但不知为什么"。子进程(streamlit)的 stdout/stderr 也重定向到日志文件。

---

## 五、一键导出诊断包(商业化售后基础设施)
在 UI(侧边栏/设置页)加"导出诊断日志"按钮:
```python
def export_diagnostics() -> str:
    """打包最近日志为 zip,返回路径。脱敏后供用户发给开发者。"""
    import zipfile, datetime
    # 收集 logs 目录 + 环境信息(OS/Python/torch版本/是否有GPU/数据源配置但不含key)
    # 打成 zip,放用户桌面或下载目录,返回路径
    ...
```
- 包含:日志文件 + 脱敏的环境/配置信息(OS、Python版本、torch build、GPU、启用的数据源/插件——但**不含任何key**)。
- 用途:现在你自己排查;将来客户报障点一下发给你,你远程看链路。
- 导出前再次扫描确保无 key 泄露。

---

## 六、UI 监控小面板(可选,锦上添花)
设置页可加一个"系统状态"小面板,实时显示:当前算力模式、各数据源连通状态、最近一次分析的 trace_id、日志文件路径。方便用户和你快速了解运行状态。

---

## 七、接入与替换
1. 全项目把散落的 print()、零散 logging 统一改用 quantsage logger。
2. app 启动时第一件事调用 setup_logging() + install_excepthook()。
3. 替换之前重复执行的 setup_logging(用本模块的幂等版)。
4. 确保打包(PyInstaller)后日志目录可写(用户目录,非程序目录)。

---

## 八、验证(工作报告必须包含)
1. 启动应用,确认日志文件生成在 %LOCALAPPDATA%\QuantSage\logs\。
2. 点一次"开始分析",**把该次 trace 的完整链路日志贴出来**——展示数据从 get_kline 到最终报告每一步的形态。
3. 确认日志中所有 key 都已脱敏(无完整key)。
4. 确认 setup_logging 不再重复执行(无每2-3秒刷屏)。
5. "导出诊断日志"按钮能生成 zip 且不含 key。
6. 用这套日志,定位当前数据链路到底断在哪一步,写一份"问题表现+可能原因"的描述。
