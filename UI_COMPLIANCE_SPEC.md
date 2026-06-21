# UI_COMPLIANCE_SPEC.md — 前端美化、版权/免责、合规审查闸 指导

> 放到项目 `docs/` 下。CC 实施任务 3、任务 4 时严格参照本文件。

---

## 一、视觉设计:深色科技风 + 高对比度

### 设计方向
深色背景 + 高对比文字 + 单一强调色(科技蓝/青)。目标:专业、冷静、可信,绝不花哨。所有文字必须在背景上清晰可读(WCAG AA:正文对比度 ≥ 4.5:1,大字 ≥ 3:1)。

### 配色 token(注入全局 CSS)
```
--bg-base:      #0d1117   /* 主背景,深炭黑 */
--bg-elevated:  #161b22   /* 卡片/面板背景 */
--bg-input:     #1c2128   /* 输入框背景 */
--text-primary: #e6edf3   /* 正文,亮灰白 — 对比度足够 */
--text-secondary:#9da7b3  /* 次要文字 */
--accent:       #2f81f7   /* 科技蓝,强调/按钮 */
--accent-hover: #4a90ff
--border:       #30363d   /* 分隔线/边框 */
--success:      #2ea043
--warning:      #d29922
--danger:       #f85149   /* 免责声明红 */
```

### 实施方式(Streamlit)
在 app.py 早期用 `st.markdown(unsafe_allow_html=True)` 注入一段全局 `<style>`:
- 设置 `.stApp` 背景为 `--bg-base`,默认文字 `--text-primary`。
- 输入框、按钮、卡片用上面的 token。
- 按钮:`--accent` 背景、白字、圆角、hover 变 `--accent-hover`。
- **重点修复当前"字看不清":** 检查所有用浅灰字配浅背景的地方,统一改为 `--text-primary`。
- 标题用等宽或几何无衬线字体增加科技感(如 `font-family: "Segoe UI", "Microsoft YaHei", system-ui`)。
- 可加细微元素提升质感:卡片 1px `--border` 边、轻微阴影、关键数字用 `--accent` 高亮。不要用渐变轰炸或大量 emoji。

### 自检
逐页检查:有没有任何文字在其背景上读不清?有的话调到 `--text-primary` 或加深背景。

---

## 二、免责声明 + 版权声明(每页都要)

### 免责声明(替换全部旧文案,单一来源放 DISCLAIMER.md)
新文案(逐字):
> 本软件的产出仅供参考,不构成任何投资建议,盈亏自负!慎重参考!

展示要求:**大号字 + 亮红(`--danger` #f85149)+ 加粗 + 醒目边框**。HTML 示例:
```html
<div style="
    border: 2px solid #f85149;
    background: rgba(248,81,73,0.08);
    color: #f85149;
    font-size: 18px;
    font-weight: 700;
    text-align: center;
    padding: 14px 16px;
    border-radius: 8px;
    margin: 12px 0;">
  ⚠ 本软件的产出仅供参考，不构成任何投资建议，盈亏自负！慎重参考！
</div>
```
出现位置:① 首屏免责关口(必须勾选同意);② 每份研究报告顶部;③ 页脚常驻一条小号版(同文案,字号小些即可)。

### 版权声明(每页底部页脚)
逐字信息:
> 本软件由 ailiwood 开发 | GitHub: https://github.com/ailiwood | 抖音号: 23230218947

HTML 示例(放每页底部):
```html
<div style="
    border-top: 1px solid #30363d;
    color: #9da7b3;
    font-size: 12px;
    text-align: center;
    padding: 12px 0;
    margin-top: 32px;">
  本软件由 <b>ailiwood</b> 开发 ·
  GitHub: <a href="https://github.com/ailiwood" style="color:#2f81f7;">github.com/ailiwood</a> ·
  抖音号: 23230218947
  <br/>
  <span style="color:#f85149;">本软件的产出仅供参考，不构成任何投资建议，盈亏自负！慎重参考！</span>
</div>
```
建议做成一个 `render_footer()` 工具函数,每个页面调用,避免重复。

---

## 三、报告输出前的 LLM 合规审查闸

### 目的
在最终报告呈现给用户**之前**,用 LLM 过一道合规审查,把方向性投资建议改写成中性研究表述、去除情绪化/夸大/保证性措辞、规避监管红线。这是把合规从"事后免责"前移到"事前拦截",契合路线 B 的"输出中性化"。

### 实施
新建 `src/compliance/report_reviewer.py`:
```python
def review_and_sanitize(report_text: str, llm_client=None) -> str:
    """对最终报告做合规审查与中性化改写。
    LLM 不可用时降级到本地规则替换,绝不阻断出报告。"""
    try:
        if llm_client is None:
            llm_client = _get_default_llm()  # 复用项目已配置的 DeepSeek
        resp = llm_client.chat(
            system=COMPLIANCE_REVIEW_SYSTEM_PROMPT,
            user=report_text,
        )
        return resp.strip()
    except Exception as e:
        logger.warning(f"LLM 合规审查不可用,降级到本地规则: {e}")
        return _local_rule_sanitize(report_text)  # 用 DISCLAIMER.md 黑名单做替换
```
在生成最终报告、展示之前调用它。

### 合规审查系统提示词(COMPLIANCE_REVIEW_SYSTEM_PROMPT)
```
你是一名金融内容合规审查员。你的任务是审查并改写下面的股票研究文本,
使其严格符合合规要求,然后只输出改写后的完整文本(不要输出解释)。

改写规则:
1. 删除或改写一切方向性投资建议:不得出现"买入/卖出/建仓/清仓/加仓/减仓"
   等操作指令,不得给出"目标价""评级"。将其改写为中性的研究观察,例如
   "模型识别到下行风险信号""估值处于历史区间下沿,需结合自身判断"。
2. 删除情绪化、夸大、煽动性表达(如"果断""暴跌在即""黄金坑""双杀")。
   改为冷静客观的描述。
3. 不得出现任何收益保证、确定性预测(如"必涨""一定")。
4. 不得出现"内幕""庄家"等违规表述。
5. 保留原文的分析逻辑、数据、因子,只改"结论的表述方式",不要凭空增删事实。
6. 在文本结尾保留(若没有则补上)一行:
   "本内容仅供参考研究,不构成任何投资建议,盈亏自负。"

只输出改写后的完整研究文本。
```

### 本地降级规则(_local_rule_sanitize)
复用 DISCLAIMER.md 的违规词黑名单,对命中的词做中性替换(如"买入"→"值得关注的标的"、"卖出"→"需警惕风险的标的"、删除"目标价 XXXX"等),保证 LLM 不可用时仍有兜底。

### 单元测试
给定样例输入含 `{'action':'卖出','target_price':1380.0,...果断清仓...戴维斯双杀}`,
断言输出中**不含**"卖出""目标价""果断清仓"等词,且**包含**结尾免责句。

---

## 四、本阶段工作报告模板(CC 收尾时按此输出)

```
# QuantSage 本阶段工作报告

## 本轮解决的问题
1. unittest/fpdf 打包缺失 — [如何解决] — 改动文件: ...
2. 安装器选项 — [如何解决] — 改动文件: installer/*.iss
3. LLM 合规审查闸 — [如何解决] — 新增: src/compliance/report_reviewer.py
4. 前端美化/版权/免责 — [如何解决] — 改动文件: ...

## 我做了哪些源码级测试(已验证)
- streamlit run 本地全流程: [结果]
- report_reviewer 单元测试: [结果]
- /check-compliance: [结果]

## 只能由你在 exe 层面验证的项(我无法测)
- 安装器勾选项是否出现
- 打包后点导出是否还报 unittest
- 安装/卸载体验

## 下一步请你操作
1. git pull(打包机)
2. 重新 PyInstaller 打包(onedir)
3. Inno Setup 重新生成安装包
4. 安装并依次验证 4 类问题
5. 把结果/新日志反馈给我

## 提交记录
- commit: feat(packaging): ...
- commit: feat(installer): ...
- commit: feat(compliance): ...
- commit: feat(ui): ...
```
