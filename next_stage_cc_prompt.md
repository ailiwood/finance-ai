# 下一阶段 CC 提示词(直接整段粘贴给 Claude Code)

> 粘贴前确认:你在项目根目录、CC 已加载 CLAUDE.md。本轮目标是修复打包依赖、改进安装器、美化前端、加合规审查闸与版权/免责。

---

## 【提示词正文 · 从下方开始复制】

本轮要解决 4 类问题。请逐项实施,**改完先做源码级自测,再提交 git**。注意:你无法测试最终 exe(打包/安装在我的 Windows 机器上进行),所以你的"测试"指源码层面(streamlit run 本地跑通、import 检查、单元测试),exe 层面的验证由我来做——不要声称 exe 已测试通过。

参考随附的两份指导文档:`docs/PACKAGING_FIXES.md`(打包与安装器)和 `docs/UI_COMPLIANCE_SPEC.md`(前端与合规)。严格按其中规范执行。

### 任务 1 · 修复打包缺依赖(unittest / fpdf)
报错:点导出时 `No module named 'unittest'`,导入链是 fpdf → sign.py → unittest。根因:PyInstaller 默认排除了 unittest 等标准库测试模块,且 fpdf 收集不全。
1. 在 pyinstaller_quantsage.spec 中:
   - 从 excludes 里移除 unittest(若存在);并显式加入 hiddenimports:
     `["unittest", "unittest.mock"]`
   - 用 collect_all 收全 fpdf:`collect_all("fpdf")` 与 `collect_all("fpdf2")`(两个名字都试,用 try/except 包裹)。
   - 顺带补 reportlab(若 PDF 用到)、PIL/Pillow 的 collect_all。
2. 把"导出 PDF/Markdown"改为**惰性导入 + 失败降级**:在 home.py 里,导出相关的 import 移到点击导出按钮的回调内部,用 try/except 包裹;导入失败时给 st.error 友好提示"PDF 导出组件不可用,请改用 Markdown 导出",**绝不让导出依赖问题阻断主分析流程**。
3. 全局排查其它"用到时才 import"的可选功能(Kronos/FinBERT 插件等),统一改为惰性导入 + 降级,符合 CLAUDE.md 的"降级优先"原则。

### 任务 2 · 改进 Inno Setup 安装器选项
当前只能选安装路径。按 `docs/PACKAGING_FIXES.md` 第二节,在 installer 的 .iss 脚本 [Tasks] 段加入用户可勾选项:
- 创建桌面快捷方式(desktopicon,默认勾选)
- 添加到开始菜单(默认勾选)
- 开机自启动(autostart,默认**不**勾选)
- 快速启动栏(可选)
并把 [Icons] 与各 Task 关联。保留中文界面。

### 任务 3 · 报告输出前增加 LLM 合规审查闸(重要)
按 `docs/UI_COMPLIANCE_SPEC.md` 第三节实施。在最终报告呈现给用户**之前**,插入一道 LLM 审查:
1. 新建 `src/compliance/report_reviewer.py`,函数 `review_and_sanitize(report_text) -> sanitized_text`。
2. 用项目已配置的 LLM(DeepSeek),system prompt 见 `docs/UI_COMPLIANCE_SPEC.md` 附的"合规审查系统提示词",作用:把方向性投资建议(买入/卖出/目标价/评级)改写为中性研究表述;移除情绪化、夸大、保证性措辞;确保不触监管红线;保留分析逻辑与数据。
3. 审查失败或 LLM 不可用时降级:回退到本地正则规则(复用 DISCLAIMER.md 违规词黑名单)做关键词替换,绝不阻断出报告。
4. 当前日志里出现过 `{'action':'卖出','target_price':1380.0}` 这类输出——审查闸必须把这类改写为"基于X因素,模型观察到下行风险信号,仅供研究参考"之类的中性表述。

### 任务 4 · 前端美化 + 版权 + 免责声明
按 `docs/UI_COMPLIANCE_SPEC.md` 第一、二节实施:
1. **配色与对比度**:采用深色科技风主题(规范里给了配色token),确保所有文字与背景对比度 ≥ WCAG AA(正文 4.5:1)。修掉当前"字看不清"的低对比问题。用 st.markdown 注入统一 CSS。
2. **免责声明**:全站统一替换为新文案,**放大字号 + 亮红色 + 加粗 + 醒目边框**:
   「本软件的产出仅供参考,不构成任何投资建议,盈亏自负!慎重参考!」
   首屏免责关口和每份报告顶部都要显示这条(大号红字);页脚可放小号常驻版。
3. **版权声明**:每个页面底部都加版权页脚(规范里给了 HTML):
   本软件由 ailiwood 开发 | GitHub: https://github.com/ailiwood | 抖音号: 23230218947
4. 统一从 DISCLAIMER.md 读取文案,保持单一来源。

### 收尾(必须做)
1. 源码级自测:本地 `streamlit run src/ui/app.py` 跑通首屏→配置→分析→导出全流程;对 report_reviewer 写单元测试(给定含"买入/目标价"的样例,断言输出已中性化)。
2. 跑 `/check-compliance`(若存在该命令),确认无违规措辞、版权与免责就位。
3. 更新 CLAUDE.md 第7节进度;按 Conventional Commits 提交,commit message 分任务清晰拆分。
4. 输出一份本阶段工作报告(见 `docs/UI_COMPLIANCE_SPEC.md` 末尾的报告模板),列出:改了哪些文件、每个问题如何解决、哪些只能由我在 exe 层面验证、下一步我该如何重新打包与测试。
5. 最后明确提醒我:**请重新打包(onedir)→ 重新安装 → 依次验证 4 类问题**。

## 【提示词正文 · 复制到此结束】

---

## 给你(开发者本人)的额外提醒

- CC 改完提交后,你要做的固定动作:`git pull`(如果在另一台打包机)→ 重新跑 PyInstaller(onedir)→ Inno Setup 重新生成安装包 → 安装 → 点击测试 4 项。
- 重点回归测试:① 安装时有没有桌面/开始菜单勾选项;② 点"导出"还报不报 unittest;③ 报告里"卖出/目标价"有没有被合规闸改写成中性表述;④ 字看不看得清、版权和红色免责在不在。
- 刷新中断那条:本轮先用"分析中提示勿刷新 + 结果存 session_state"缓解;若你希望彻底做成后台任务(刷新不丢),告诉我,我单独给你一版后台线程方案(改动较大,建议 V1 之后再做)。
