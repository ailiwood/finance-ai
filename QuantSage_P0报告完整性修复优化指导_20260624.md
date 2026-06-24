# QuantSage P0：报告完整性与 Kronos 展示链路修复指导（优化版）

**适用范围**：本文件仅处理“分析完成但网页、Markdown、PDF 只显示到投资者情绪分析附近”的 P0 故障，以及与其直接相关的 Kronos 结果展示与报告合规处理链路。  
**不在本次范围**：自动发卡、支付、安装包签名、后台 Cookie 会话、许可证在线校验、数据源策略重构、模型推理性能优化。

---

## 1. 结论与修复决策

当前根因是：

```text
完整报告组装
  → 以整篇长报告调用 LLM 合规改写
  → max_tokens=4000
  → LLM 的输出到达长度上限
  → 代码未检查 finish_reason / 章节完整性 / 输出比例
  → 将截断文本作为最终网页、Markdown、PDF 报告
```

本次采取的正式策略是：

> **完整报告必须走“本地确定性合规处理 + 结构完整性验证”路径；不得把整篇报告交给 LLM 改写。**

LLM 未来可用于“短章节、显式启用、可验证、可回退”的辅助审查，但不再是完整报告最终文本的单点依赖。

---

## 2. 对现有三层计划的判断

### 2.1 CC 的第 1 层：方向正确，但实现方式必须调整

“完整报告不再调用 LLM，直接使用本地规则”是正确的立即止血方案。

但不要在 `home.py` 中写：

```python
from src.compliance.report_reviewer import _review_via_regex
```

理由：

1. `_review_via_regex` 是私有实现，调用方不应依赖；
2. 后续规则改名、增加审计、增加元信息时会造成多个调用点耦合；
3. 需要统一返回“处理方法、完整性检查结果、回退原因”。

应当把本地处理暴露为公共 API，例如：

```python
review_and_sanitize(report_text, mode="local", expected_sections=...)
```

或：

```python
sanitize_report_locally(report_text)
```

`home.py` 只调用公共 API。

### 2.2 CC 的第 2 层：必须保留，但不能把“提高 token 上限”当作根治

必须加入：

- `finish_reason == "length"` 拒收；
- 空输出、异常、内容显著变短、必需章节缺失时拒收；
- 拒收后回退到本地确定性结果；
- 可记录“为什么拒收”。

但把 `max_tokens` 从 4000 改为 16384 **不是主修复**。它只能延后未来的截断点，还会增加 API 耗时、成本和不确定性。

LLM 审查若保留，仅允许用于**单个短章节**，而不是完整报告。

### 2.3 CC 的第 3 层：本轮不做完整 LLM 逐章改写

现有 `src/report/report_assembler.py` 已提供“结构化组装、免责声明置末、完整性检查”的方向，应在本轮接入或复用其能力。

但“逐章 LLM 改写”仍可能：

- 改写章节事实；
- 把原始分析压缩得过短；
- 在多个章节之间产生术语不一致；
- 增加 API 调用次数和失败面。

因此，本轮只完成 **结构化报告 + 本地规则 + 完整性门禁**。  
LLM 逐章审查作为后续可选增强，不纳入 P0 发布阻塞项。

---

## 3. 必须同时修复的第二个问题：成功 Kronos 结果未回传展示层

当前 `_run_analysis()` 成功获得 `_kpred` 后：

- 生成了 `_kronos_ctx`；
- 将其注入 TradingAgents 辩论上下文；
- 记录了成功日志；

但成功路径没有构造 `_kronos_status`。后续 mailbox 使用：

```python
"kronos_status": _kronos_status if "_kronos_status" in dir() else None
```

这会导致：

- Kronos 确实参与了分析师讨论；
- 但网页最终报告的 `result.get("kronos_status")` 可能为 `None`；
- “Kronos 深度学习 K 线预测”章节无法稳定展示；
- “Kronos 与多智能体结论是否一致”的交叉结论也可能丢失。

### 3.1 必须采用的状态对象

进入 try 前先初始化，确保每条路径均有状态：

```python
_kronos_status = {
    "status": "not_run",
    "method": None,
    "engine_label": None,
    "direction": None,
    "current_price": None,
    "target_price": None,
    "lower_bound": None,
    "upper_bound": None,
    "confidence": None,
    "horizon_days": 10,
    "data_rows": 0,
    "error": None,
    "disclaimer": "概率性量化预测，仅供研究参考，不构成投资建议。",
}
```

成功时，立刻从 `_kpred` 和 K 线数据构造一个**仅含 JSON 可序列化基础类型**的完整对象，并放入 mailbox。

要求：

- `method` 必须保留真实引擎返回，例如 `Kronos-base` 或统计降级方法；
- 仅当真实 `method` 表明为 Kronos-base 时，`engine_label` 才能写“ Kronos-base 深度学习模型”；
- 降级模型必须明确显示“统计模型（降级）”，不得伪装为深度学习模型；
- 失败时必须写 `status="failed"` 与简化后的 error；
- 数据不足时写 `status="skipped"`；
- 不得因为 Kronos 失败而中断完整分析流程，但报告中必须有可见状态说明；
- 展示层不得再次调用 `.predict()`，必须复用 mailbox 的预测对象。

---

## 4. P0 目标架构

```text
TradingAgents + Kronos
    ↓
结构化报告章节（sections）
    ↓
本地确定性合规过滤
    ↓
完整性验证（章节、末尾免责声明、最小长度、Markdown 结束状态）
    ↓
display_report
    ├─ Streamlit 页面
    ├─ Markdown 下载
    ├─ PDF 输入
    └─ 历史记录
```

必须保留：

```text
raw_report      # 组装后、合规过滤前的完整原文，仅用于受控审计/调试
display_report  # 本地过滤并通过完整性验证的最终报告
report_meta     # source_length、display_length、method、完整性、missing、fallback_reason
```

页面、Markdown、PDF 和历史记录必须全部使用同一个 `display_report`，不能各自重新构建、重新调用 LLM 或重新预测。

---

## 5. 文件级实施要求

## 5.1 `src/compliance/report_reviewer.py`

### A. 公共 API

保留原有 `review_and_sanitize()` 名称以降低兼容性风险，但改成显式策略：

```python
def review_and_sanitize(
    report_text: str,
    *,
    mode: Literal["local", "section_llm", "auto"] = "local",
    expected_sections: Sequence[str] | None = None,
) -> tuple[str, str]:
```

约束：

- **默认 `mode="local"`**；
- `home.py` 必须明确传 `mode="local"`；
- `"section_llm"` 只能用于单章节，不得由完整报告调用；
- `"auto"` 若保留，只能对短文本使用 LLM；输入超过合理阈值（建议 3500～5000 中文字符）时必须自动走 local；
- 不允许 `home.py` 导入 `_` 开头的私有函数。

建议额外提供：

```python
def sanitize_report_locally(text: str) -> str: ...
def validate_sanitized_report(
    raw_text: str,
    sanitized_text: str,
    expected_sections: Sequence[str],
) -> tuple[bool, list[str]]: ...
```

### B. 本地规则必须修正

当前代码对中文方向词使用 `\b`，不能作为可靠的中文边界策略；同时不能把“中性”全局替换为“信号为中性”，否则会污染“中性偏积极”等正常表述。

本地规则要求：

1. 不修改 Markdown 一级/二级标题；
2. 不全局替换“中性”；
3. 优先替换“建议/推荐/操作/评级/交易提案”等**指令性上下文**；
4. 对已知结论行进行字段级处理，例如：
   - `投资评级`
   - `交易提案`
   - `操作策略`
   - `建议`
   - `Action`
   - `最终决策`
5. 将风险性词语转为研究性表述，例如：
   - “建议买入” → “模型综合信号偏积极，供研究参考”
   - “建议卖出” → “模型观察到下行风险信号，供研究参考”
   - “止损位” → “风险观察参考位”
   - “目标价” → “模型估算参考值”
   - “仓位建议” → “风险暴露观察说明”
6. 删除或中性化保证性措辞：
   - “稳赚”
   - “必涨”
   - “保证收益”
   - “精准预测”
   - “最佳买点”
   - “现在就是买入的最佳时机”
7. 过滤后必须保留所有数值、数据来源、事实描述和章节结构；
8. 添加 `find_prohibited_instruction_patterns()` 供测试和日志使用。

### C. LLM 兜底必须严格验收

即使未来有人调用 `mode="section_llm"`，也必须：

- 读取并检查 `response.choices[0].finish_reason`；
- 只有 `finish_reason == "stop"` 才可能接收；
- `finish_reason == "length"`、`content_filter`、空内容、异常均返回 `None`；
- 输出必须通过结构检查；
- 输出长度不能异常短于输入；
- 任一失败都返回本地过滤结果，而不是抛出或显示半截文本；
- 记录 warning：输入长度、输出长度、finish reason、回退原因；
- 禁止 `except Exception: pass` 静默吞掉问题。

---

## 5.2 `src/report/report_assembler.py`

该文件应成为结构完整性的单一来源。

### A. 章节与顺序

建议最终顺序：

1. 技术面分析
2. 基本面分析
3. 投资者情绪分析
4. 新闻分析（可选）
5. 风险管控与最终研究结论
6. Kronos 深度学习 K 线预测
7. 综合结论
8. 多周期技术指标汇总（可选）
9. 免责声明（必须最后）

说明：

- 当前 `home.py` 在免责声明之后继续添加“多周期技术指标汇总”，这违反“免责声明始终最后”的设计；
- 必须把指标汇总移至免责声明之前；
- 免责声明仅保留一份，并且是报告去掉尾部空白后的最后一段。

### B. 必需章节检查必须结构化

不得只做 `"结论" in report` 这种宽松检查。  
应根据 Markdown 标题逐项检查，例如：

```text
## 技术面分析
## 基本面分析
## 投资者情绪分析
## 风险管控与最终研究结论
## Kronos 深度学习 K 线预测
## 综合结论
```

Kronos 章节建议始终出现：

- 成功：展示真实预测；
- 降级：明确“统计模型（降级）”；
- 失败：明确“预测未完成 + 原因”；
- 用户禁用：明确“插件未启用”。

不要因“模型未运行”而静默省略这一核心模块。

### C. 组装时不要跳过必需章节

当前 `assemble_report_sections()` 对空内容直接 `continue`。  
对于必需章节，应展示透明的占位内容，例如：

```text
> 本模块本次未返回有效内容，原因：……
```

这样报告仍然结构完整，用户也能明确知道是哪个模块失败，而不是误以为报告结束了。

---

## 5.3 `src/ui/home.py`

### A. 报告构建

不要继续用“手工 parts + 全篇 LLM 改写”的模式。

最低可接受做法：

1. 构造有标题的 section 列表；
2. 使用 `report_assembler` 组装；
3. 在**所有附加内容（包括指标）完成后**添加最终免责声明；
4. 得到 `raw_report`；
5. 调用 `review_and_sanitize(raw_report, mode="local", expected_sections=...)`；
6. 运行完整性验证；
7. 验证失败时：
   - 先输出日志；
   - 回退为 `sanitize_report_locally(raw_report)`；
   - 再次验证；
   - 若仍失败，页面必须显示“系统完整性错误”，并保留可诊断信息，但不得把半截 LLM 输出伪装成完整报告。

### B. 缓存和幂等

报告一经生成，在当前 `analysis_result` 生命周期内应缓存 `report_bundle`：

```python
{
    "raw_report": ...,
    "display_report": ...,
    "meta": {
        "method": "regex_local",
        "is_complete": True,
        "missing_sections": [],
        "raw_chars": ...,
        "display_chars": ...,
        "fallback_reason": None,
    },
}
```

要求：

- 页面 rerun、展开折叠、点击下载、生成 PDF 时不重新调用 LLM；
- 不重新调用 Kronos；
- 页面、Markdown、PDF、历史记录共享 `display_report`。

### C. 显示用标签

将原来的“LLM 合规审查”标签改为真实来源，例如：

```text
✅ 本地确定性合规过滤 + 报告完整性验证通过
```

不要因为未调用 LLM 而显示“审查跳过”。

---

## 6. 强制测试与验收

新增或更新测试，不得只依赖手工点击。

### 6.1 单元测试

至少覆盖：

1. 12000+ 字符完整报告使用 `mode="local"` 后：
   - 所有必需章节仍存在；
   - 免责声明位于最后；
   - 输出非空；
   - 输出长度不异常缩短；
   - 不会调用 OpenAI 客户端。
2. 模拟 LLM 返回 `finish_reason="length"`：
   - 必须回退 local；
   - 不得返回截断内容。
3. 模拟 `finish_reason="stop"` 但缺失“综合结论”：
   - 必须回退 local。
4. 模拟 LLM 抛异常：
   - 必须回退 local，且记录原因。
5. 本地过滤：
   - 能处理指令性“建议买入/建议卖出/止损位/目标价/仓位建议”等；
   - 不把“中性偏积极”错误替换；
   - 不破坏 Markdown 标题。
6. 免责声明在全部指标与内容之后。
7. Kronos 成功路径：
   - mailbox 有 `kronos_status`；
   - `method`、方向、价格区间、置信度和 engine label 完整；
   - 页面章节可读取；
   - 展示阶段不再次执行 `predict()`。
8. Kronos 失败/数据不足/降级路径：
   - 报告仍完整；
   - Kronos 章节明确状态；
   - 不伪装成成功模型。

### 6.2 开发机真实冒烟测试

以 600519 或 300750，深度 3 运行一次完整分析，保存：

- 启动时间；
- 完成时间；
- `D:\QuantSage\logs\tradingagents.log` 的 Kronos 成功或降级证据；
- `raw_chars` / `display_chars`；
- `report_meta`；
- 完整报告中的最终章节标题；
- Markdown 下载文件；
- PDF 生成输入与输出路径。

验收条件：

```text
网页、Markdown、PDF 三者均出现：
- 投资者情绪分析
- 风险管控与最终研究结论
- Kronos 深度学习 K 线预测
- 综合结论
- 最后免责声明

且页面不再在“投资者情绪分析”中段终止。
```

---

## 7. 本轮禁止事项

- 不仅将 `max_tokens` 改大就结束；
- 不把完整报告再送入任何单次 LLM 改写；
- 不从 `home.py` 导入 `_review_via_regex` 等私有函数；
- 不使用 `except Exception: pass` 吞掉合规审查与完整性故障；
- 不把 Kronos 的统计降级结果标为“Kronos-base”；
- 不在免责声明后继续追加报告正文；
- 不重新计算 Kronos 来做展示；
- 不以“测试通过”替代真实一次运行证据；
- 不在本轮修改支付、激活、安装包签名或许可证模块。

---

## 8. 交付要求

完成后必须输出：

1. 修改文件清单；
2. 每个文件的修改理由；
3. 关键 diff 摘要；
4. 新增/更新测试清单与结果；
5. 真实 600519 或 300750 冒烟测试证据；
6. 原始报告、网页展示、Markdown、PDF 输入三者长度对照；
7. 是否需要重打安装包的结论。

只有开发环境的所有单元测试和真实冒烟测试通过后，才允许进入重打包阶段。
