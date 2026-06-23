# KRONOS_COMPLETE_GUIDE.md — K线预测完善 + 网页集成 + 依赖打包策略

> 放到项目 `docs/`。三件事:① torch 依赖打包策略(解决500MB体积问题);② Kronos 真正运行(CPU也能跑);③ 预测在分析师讨论**之前**完成,接入辩论。

---

## 第一部分:依赖打包策略 —— 全部依赖一次性打进 exe(已确定)

### 决定:torch/transformers 等全部依赖直接打入 exe,离线即用
- 已确认:Kronos 在 CPU 环境可跑通(无需GPU)。
- **最终方案:把 CPU 版 torch、transformers 及全部 Kronos 依赖,连同 406MB 权重,全部打进 exe。** 用户安装后完全离线可用,无首次下载、无联网等待、无环境配置 —— 对商业分发最省心、最可靠。
- 体积权衡:包会到约 1GB(500MB 现状 + torch CPU版约200MB + 权重406MB + transformers等)。这对桌面软件可接受,很多专业软件都上 GB。**省心可靠优先于体积。**

### 实现(PyInstaller spec)
1. spec 里**移除对 torch/transformers 的任何 exclude**。
2. 用 collect_all 收全所有依赖:
   ```python
   from PyInstaller.utils.hooks import collect_all, copy_metadata
   datas, binaries, hiddenimports = [], [], []
   for pkg in ["torch", "transformers", "einops", "safetensors",
               "huggingface_hub", "tokenizers", "regex", "filelock",
               "numpy", "tqdm", "packaging", "pyyaml"]:
       d, b, h = collect_all(pkg)
       datas += d; binaries += b; hiddenimports += h
   datas += copy_metadata("torch")
   datas += copy_metadata("transformers")
   ```
3. **用 CPU 版 torch**(打包前确保环境装的是 CPU 版):
   ```
   pip uninstall torch torchvision torchaudio -y
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   ```
   CPU 版比 CUDA 版小很多,且无 N 卡机器也能跑。
4. Kronos 权重(406MB)随包打入(已在 hf_cache/),作为 datas 加进去;确保运行时能从打包目录定位到权重(用 sys._MEIPASS 解析路径,离线加载,不联网下载)。
5. onedir 模式(你当前用的)下,这些会放进 _internal 目录,没问题。

### 体积优化(可选,锦上添花,不强求)
若想压一点体积(但不影响"全部打进去"的决定):
- torch 只保留 CPU 后端(CPU版本来就没 CUDA dll)。
- UPX 压缩(注意可能被杀软误报,谨慎)。
- 不做也行,1GB 可接受。

### 验证
- 打包后,在**无 N 卡、无预装 torch 的干净环境**(或 CUDA_VISIBLE_DEVICES=-1 模拟)双击 exe,确认 Kronos 真加载、能出预测、**全程无需联网**。

---

## 第二部分:Kronos 真正运行(CPU)

### 确保真加载,不降级
1. 确保 torch/transformers/einops/safetensors/huggingface_hub/tokenizers 全部打进 exe 且运行时可 import。
2. KronosEngine 用 CPU 版 torch,device=pick_device()(无GPU走cpu)。
3. 模型 Kronos-base(NeoQuasar/Kronos-base)+ Kronos-Tokenizer-base,权重406MB随包打入,运行时从打包目录离线加载(不联网下载)。
4. **验证**:运行时日志必须显示"已加载 Kronos-base 深度学习模型",而非"降级 StatsEngine"。这是真假分水岭。

### CPU 性能注意
- Kronos-base 102M 参数,CPU推理单次预测约几秒~几十秒,可接受。
- 用进度提示;预测耗时纳入总分析进度。

---

## 第三部分:预测在分析师讨论之前完成(接入辩论)

### 这是核心改动:Kronos 要先算,喂给辩论
```
正确流程:
1. [分析开始] 先取K线数据(get_kline)
2. [先算Kronos] 用历史K线算未来N日概率预测(方向+区间+置信度)
3. [注入上下文] Kronos预测作为工具结果/上下文,给到分析师
4. [分析师辩论] 技术分析师、多空研究员、交易员都能看到Kronos预测并引用、辩论
5. [最终决策] 是"LLM分析+深度学习预测"协同的结果
6. [报告] Kronos预测展示在"综合结论之前",结论引用其方向
```

### 实现
1. 在 trading_graph 启动多智能体**之前**,先调 KronosEngine 算预测。
2. 把预测格式化成文本(中性措辞),作为:
   - 做法A(推荐):一个工具 get_kline_prediction(symbol),技术分析师Agent可调用。
   - 做法B(简单):塞进市场分析师/交易员的输入上下文/system message。
3. 辩论环节(Bull/Bear研究员)的输入里也带上Kronos预测,让多空双方都能就它辩论。
4. 报告里Kronos预测块移到结论之前;结论的reasoning体现对预测的参考。

### 合规
- Kronos预测注入前 sanitize:概率预测保留(标"模型概率预测,非投资建议"),"目标价"改"预测区间中值"。
- 失败不静默:log.warning + 报告标"K线预测暂不可用",不能 except pass。

---

## 验证(工作报告必须包含)
1. 安装包里 Kronos **真加载**(日志显示Kronos-base,非StatsEngine);CUDA_VISIBLE_DEVICES=-1 强制CPU也能跑。
2. 依赖全部打进exe:在无N卡/无预装torch的干净环境(或CUDA_VISIBLE_DEVICES=-1)双击exe,Kronos真加载、能预测、**全程无需联网**;说明最终包多大。
3. Kronos预测在多智能体分析**之前**算出(贴日志时序证明)。
4. 技术分析师/多空研究员输入上下文**包含**Kronos预测(贴日志)。
5. 报告中预测在结论之前,结论引用其方向;无裸目标价;失败不静默。
