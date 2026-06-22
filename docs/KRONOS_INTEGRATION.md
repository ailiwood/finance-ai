# KRONOS_INTEGRATION.md — 集成真正的 Kronos 深度学习模型

> 放到项目 `docs/`。目标:把 StatsEngine(统计基线)升级为真正的 Kronos Transformer 深度学习预测,完成 M3。
> 所有信息已核实(官方仓库/HuggingFace/论文)。

---

## 一、Kronos 精确信息(已核实)

- **官方仓库**:https://github.com/shiyu-coder/Kronos (MIT 许可,AAAI 2026,arXiv 2508.02739)
- **作者**:Yu Shi 等(清华)
- **权重托管**:HuggingFace `NeoQuasar` 组织,MIT 许可,免费

### 模型变体(Model Zoo)
| 模型 | 参数量 | 上下文 | 对应 tokenizer | HuggingFace |
|------|--------|--------|---------------|-------------|
| Kronos-mini | 4.1M | 2048 | Kronos-Tokenizer-2k | NeoQuasar/Kronos-mini |
| Kronos-small | 24.7M | 512 | Kronos-Tokenizer-base | NeoQuasar/Kronos-small |
| **Kronos-base(本项目强制使用)** | 102.3M | 512 | Kronos-Tokenizer-base | NeoQuasar/Kronos-base |
| Kronos-large | 499.2M | — | — | ❌ 未公开 |

### 选型结论(强制)
**本项目强制只使用 Kronos-base(102.3M)+ Kronos-Tokenizer-base,不使用 mini/small。**
- 模型名固定:`NeoQuasar/Kronos-base` + `NeoQuasar/Kronos-Tokenizer-base`,**写死,不提供 mini/small 选项**。
- 理由:base 是公开变体中参数量最大、预测质量最高的,而 102M 依然极小——5070Ti 跑它绰绰有余,纯 CPU 也能跑,权重也只有约一两百MB。质量优先。
- 上下文 512(max_context=512)。

---

## 二、依赖与加载

### 依赖
Kronos 的 `model` 模块来自其 GitHub 仓库(不是 pip 包)。两种集成方式:
- **方式A(推荐)**:把 Kronos 仓库的 `model/` 目录(含 Kronos/KronosTokenizer/KronosPredictor 定义)vendored 进项目(如 `src/plugins/kronos_service/kronos_model/`),保留其 MIT LICENSE。
- 方式B:作为 git submodule 引入。
依赖:torch(已有,CPU版)、huggingface_hub、einops、安装 Kronos requirements.txt 里列的(numpy/pandas/tqdm 等,多数已有)。**不要引入超大新依赖。**

### 加载(从 HuggingFace Hub)
```python
from model import Kronos, KronosTokenizer, KronosPredictor  # 来自 vendored 的 Kronos model 模块

tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
model = Kronos.from_pretrained("NeoQuasar/Kronos-base")   # 强制 base
predictor = KronosPredictor(model, tokenizer, device=DEVICE, max_context=512)
```
- 首次加载会从 HuggingFace 下载权重(base 约一两百MB),缓存到本地 HF 缓存目录。
- 国内网络:可设 HF_ENDPOINT=https://hf-mirror.com 镜像加速(给用户一个配置项)。
- DEVICE 用之前的 pick_device()(cuda/mps/cpu)。

---

## 三、预测 API(对接已修好的 get_kline)

```python
pred_df = predictor.predict(
    df=x_df,                  # 含 ['open','high','low','close'](volume/amount可选)
    x_timestamp=x_timestamp,  # 历史K线的时间戳 Series
    y_timestamp=y_timestamp,  # 要预测的未来时间戳 Series
    pred_len=N,               # 预测未来N根K线
    T=1.0,                    # 温度,控制随机性
    top_p=0.9,
    sample_count=M,           # >1 做 Monte Carlo 概率预测(取均值+区间)
)
```
要点:
- **输入直接来自 get_kline()**:你的 get_kline 已返回标准 OHLCV DataFrame,正好喂进去。注意列名要是小写 open/high/low/close(你的 format 层已标准化)。
- **lookback ≤ 512**(small/base 上限),超了 KronosPredictor 自动截断,但最好主动控制传入长度。
- **概率预测**:sample_count 设 >1(如 30),predict 会跑多次 Monte Carlo,可得预测均值 + 不确定区间(demo 里的橙色阴影带),这正适合做风险加权的概率性预测。
- 返回 pred_df 是未来 N 根的 OHLCV 预测。

---

## 四、集成到 model_engine.py 作为 KronosEngine

当前结构:Kronos 插件只有 StatsEngine(统计基线)。新增 KronosEngine 并设为首选,StatsEngine 降级保留。
```python
class KronosEngine:
    def __init__(self, model_name="NeoQuasar/Kronos-base",          # 强制 base,不可改
                 tokenizer_name="NeoQuasar/Kronos-Tokenizer-base"):
        self.device = pick_device()
        self._loaded = False  # 惰性加载,首次预测才加载模型

    def _lazy_load(self):
        if self._loaded: return
        from model import Kronos, KronosTokenizer, KronosPredictor
        self.tokenizer = KronosTokenizer.from_pretrained(self.tokenizer_name)
        self.model = Kronos.from_pretrained(self.model_name)
        self.predictor = KronosPredictor(self.model, self.tokenizer,
                                         device=self.device, max_context=512)
        self._loaded = True

    def predict(self, df, pred_len=10, sample_count=30):
        self._lazy_load()
        # 构造 x_timestamp/y_timestamp,调 predictor.predict
        # 返回预测均值 + 不确定区间
        ...

# 引擎选择:Kronos 优先,失败/不可用降级 StatsEngine
def get_engine():
    try:
        return KronosEngine()
    except Exception as e:
        logger.warning(f"Kronos 不可用,降级 StatsEngine: {e}")
        return StatsEngine()
```
- **惰性加载**:首次预测才加载模型,避免启动慢、避免没用插件的用户白等。
- **降级链**:Kronos 加载/推理失败 → StatsEngine 统计基线 → 明确标注用的哪个引擎。
- UI 的"Kronos 状态"应显示真实状态:"深度学习模型(Kronos-base, GPU/CPU)" 或 "统计基线(StatsEngine)"。

---

## 五、打包注意
1. vendored 的 Kronos model 代码 + LICENSE 加入 PyInstaller datas。
2. huggingface_hub、einops 等加入 hiddenimports/collect。
3. 模型权重:可首次运行下载(联网),或随包预置(base 约一两百MB)。给国内用户 HF 镜像配置项。
4. 在 THIRD_PARTY_LICENSES.md 登记 Kronos(MIT)。

---

## 六、合规
Kronos 输出的是概率性价格预测,在报告中必须:
- 标注"基于深度学习模型的概率性预测,非确定性结论,仅供参考"。
- 沿用全局红线:不构成投资建议;预测失败时明确报错不编造。

---

## 七、验证(工作报告必须包含)
1. KronosEngine 成功从 HuggingFace 加载 Kronos-base,UI"Kronos状态"显示"深度学习模型"而非"统计基线"。
2. 对 600519 用真实 get_kline 数据跑预测,输出未来N日预测 + 不确定区间,贴真实输出。
3. CUDA_VISIBLE_DEVICES=-1 强制 CPU 下也能跑通(证明无显卡可用),记录耗时。
4. Kronos 不可用时降级 StatsEngine,主流程不崩。
5. 预测值合理(茅台预测应在当前价~1215附近的合理区间,不是离谱数字)。
6. 143 测试通过;THIRD_PARTY_LICENSES 登记 Kronos MIT。
