# 方案 A 完整测试指引

> 按顺序逐项验证。每项通过打 ✅，失败记录现象。

---

## 测试环境

| 项目 | 你的配置 |
|------|---------|
| Python | `E:\Anaconda3\envs\quantsage_py311\python.exe` |
| 工作目录 | `E:\AI_projects\fin` |
| GPU | RTX 5070 Ti (16GB) |
| 代理 | Clash @ 127.0.0.1:7897 |

---

## 一、基础环境验证 (5 分钟)

### 1.1 Python 环境

```bash
E:\Anaconda3\envs\quantsage_py311\python.exe --version
```
预期: `Python 3.11.x`

### 1.2 PyTorch + GPU

```bash
E:\Anaconda3\envs\quantsage_py311\python.exe -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```
预期: `CUDA: True`, `GPU: NVIDIA GeForce RTX 5070 Ti`

### 1.3 全部单元测试

```bash
cd E:\AI_projects\fin
set KMP_DUPLICATE_LIB_OK=TRUE
E:\Anaconda3\envs\quantsage_py311\python.exe -m pytest tests/ -v
```
预期: `79 passed`

---

## 二、Streamlit UI 测试 (10 分钟)

### 2.1 启动 UI

```bash
cd E:\AI_projects\fin
E:\Anaconda3\envs\quantsage_py311\python.exe -m streamlit run src/ui/app.py
```
打开浏览器访问 **http://localhost:8501**

### 2.2 免责声明弹窗

- [ ] 页面显示 "QuantSage 免责声明"
- [ ] "同意并继续" 按钮默认灰色不可点击
- [ ] 勾选 "我已阅读并同意上述免责声明" 后按钮变亮
- [ ] 点击 "同意并继续" → 进入配置向导

### 2.3 3步配置向导

**步骤 1: LLM 密钥**
- [ ] 下拉框显示 "DeepSeek (推荐，性价比高)"
- [ ] 输入你的 DeepSeek API Key (sk-...)
- [ ] 点击 "测试连接" → 显示 "✅ 连接成功"
- [ ] （可选）点击 "如何获取 API Key?" 展开帮助

**步骤 2: 数据源**
- [ ] AkShare 复选框默认已勾选
- [ ] 展开 Tushare 配置（可选）

**步骤 3: 风险偏好**
- [ ] 选择 "平衡" 风险偏好
- [ ] 分析深度设为 3
- [ ] Kronos 开关默认关闭
- [ ] FinBERT 开关默认关闭
- [ ] 点击 "完成配置"

### 2.4 首页

- [ ] 显示配置概览（DeepSeek 状态 ✅）
- [ ] 插件状态面板正常显示
- [ ] 每页底部有免责声明
- [ ] 点击 "生成示例报告" → 显示报告预览
- [ ] 点击 "下载 Markdown 报告" → 下载 .md 文件
- [ ] 点击 "下载 PDF 报告" → 下载 .pdf 文件（打开验证页脚有免责声明）
- [ ] 点击 "合规扫描自检" → 显示扫描结果

---

## 三、Kronos GPU 预测服务测试 (5 分钟)

### 3.1 启动服务

```bash
cd E:\AI_projects\fin
set KMP_DUPLICATE_LIB_OK=TRUE
E:\Anaconda3\envs\quantsage_py311\python.exe -m uvicorn src.plugins.kronos_service.service:app --port 8100
```

### 3.2 健康检查

```bash
curl http://localhost:8100/health
```
- [ ] `"status": "disabled"`（因为 KRONOS_ENABLED=false）
- [ ] `"gpu_available": true`
- [ ] `"gpu_name": "NVIDIA GeForce RTX 5070 Ti"`
- [ ] `"fp8_supported": true`

### 3.3 GPU 状态

```bash
curl http://localhost:8100/gpu
```
- [ ] VRAM 约 16 GB
- [ ] FP8 supported: true

### 3.4 启用后预测测试

```bash
# 设置启用标志
set KRONOS_ENABLED=true
# 重新启动服务后
curl -X POST http://localhost:8100/predict ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"600519\",\"ohlcv\":[{\"date\":\"2025-06-01\",\"open\":100,\"high\":102,\"low\":99,\"close\":101,\"volume\":10000}],\"horizon_days\":5}"
```
（注意：Windows cmd 中使用 `^` 换行，PowerShell 中用 `` ` ``）
- [ ] 返回包含 `direction`, `confidence`, `target_price`, `lower_bound`, `upper_bound`
- [ ] `"method"` 为 `"stats_baseline"` 或 `"kronos_fallback_stats"`

---

## 四、FinBERT 情绪分析测试 (5 分钟)

### 4.1 启动服务

```bash
cd E:\AI_projects\fin
set KMP_DUPLICATE_LIB_OK=TRUE
E:\Anaconda3\envs\quantsage_py311\python.exe -m uvicorn src.plugins.finbert_service.service:app --port 8101
```

### 4.2 健康检查

```bash
curl http://localhost:8101/health
```
- [ ] `"service": "finbert-sentiment-analysis"`
- [ ] `"gpu_available": true`
- [ ] `"engine_name"` 为 `"finbert"` 或 `"rule_based"`

### 4.3 单条分析

```bash
curl -X POST http://localhost:8101/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"公司业绩大幅增长，盈利超预期，市场份额持续提升\"}"
```
- [ ] `"label": "positive"`
- [ ] `"score"` > 0.5
- [ ] `"confidence"` > 0

### 4.4 批量分析

```bash
curl -X POST http://localhost:8101/batch_analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"texts\":[\"业绩大幅增长\",\"业绩大幅下滑\",\"公司正常经营\",\"行业景气度提升\"]}"
```
- [ ] `"daily_index"` 在 0-10 之间
- [ ] `"sentiment_label"` 为 "乐观" / "中性" / "悲观"

---

## 五、核心引擎端到端测试 (10 分钟)

### 5.1 分析一只 A 股

```bash
cd E:\AI_projects\fin
set KMP_DUPLICATE_LIB_OK=TRUE
set PYTHONIOENCODING=utf-8
set DEEPSEEK_API_KEY=你的真实API Key

E:\Anaconda3\envs\quantsage_py311\python.exe -c "
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import sys; sys.path.insert(0, 'E:/AI_projects/TradingAgents-CN')
config = DEFAULT_CONFIG.copy()
config['llm_provider'] = 'deepseek'
config['backend_url'] = 'https://api.deepseek.com'
config['deep_think_llm'] = 'deepseek-chat'
config['quick_think_llm'] = 'deepseek-chat'
config['max_debate_rounds'] = 1
print('Starting analysis...')
ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate('600519', '2025-06-18')
print('=== RESULT ===')
print('Direction:', decision.get('action'))
print('Confidence:', decision.get('confidence'))
print('Risk score:', decision.get('risk_score'))
print('Reasoning:', decision.get('reasoning')[:200])
"
```
- [ ] 输出包含 `Direction`, `Confidence`, `Risk score`, `Reasoning`
- [ ] 无报错退出
- [ ] 总耗时 < 5 分钟

---

## 六、报告生成测试 (2 分钟)

### 6.1 从分析结果生成报告

```bash
cd E:\AI_projects\fin
E:\Anaconda3\envs\quantsage_py311\python.exe -c "
from src.report.report_generator import generate_report
from src.report.pdf_exporter import export_report_pdf, export_report_markdown

output = {
    'decision': {
        'action': '持有',
        'confidence': 0.6,
        'risk_score': 0.4,
        'target_price': 1500.0,
        'reasoning': '基本面稳健，技术面震荡，建议持有观望',
    },
    'reasoning': '整体评估中性偏积极',
}
report, data = generate_report('600519', '茅台', output)
print(f'Report length: {len(report)} chars')
print(f' Sections: {[s[\"title\"] for s in data[\"sections\"]]}')

# Export
md = export_report_markdown(report, 'reports/test_600519.md')
pdf = export_report_pdf(report, 'reports/test_600519.pdf')
print(f'Markdown: {md}')
print(f'PDF: {pdf} ({pdf.stat().st_size} bytes)')

# Check disclaimer in markdown
assert '仅供参考研究' in report
print('DISCLAIMER: Present')

# Check PDF is valid
assert pdf.read_bytes()[:4] == b'%PDF'
print('PDF: Valid')
"
```
- [ ] 报告包含 4 个章节 + 综合结论
- [ ] 免责声明存在于报告正文
- [ ] Markdown 文件可打开
- [ ] PDF 文件有效可打开

### 6.2 合规扫描

```bash
cd E:\AI_projects\fin
E:\Anaconda3\envs\quantsage_py311\python.exe -c "
from src.compliance.phrase_checker import scan_project, check_banned_phrases, has_disclaimer
from src.compliance.disclaimer import get_ui_disclaimer
print('Scanning project...')
violations = scan_project()
if violations:
    for v in violations:
        print(f'  VIOLATION: {v.phrase} ({v.category})')
else:
    print('No violations found')

# Test banned phrase detection
assert check_banned_phrases('推荐买入这只股票') == ['推荐买入']
assert check_banned_phrases('稳赚不赔的机会') == ['稳赚']
assert check_banned_phrases('基于数据分析的参考观点') == []
print('Phrase checker: OK')
print('UI disclaimer:', get_ui_disclaimer())
"
```
- [ ] 项目扫描无违规措辞
- [ ] 禁止词检测正常工作

---

## 七、降级场景测试 (5 分钟)

### 7.1 Kronos 无 GPU 降级

```bash
cd E:\AI_projects\fin
E:\Anaconda3\envs\quantsage_py311\python.exe -c "
from src.plugins.kronos_service.gpu_detector import detect_gpu
from src.plugins.kronos_service.model_engine import StatsEngine, get_engine

# CPU-only engine
engine = get_engine(prefer_gpu=False)
print(f'CPU engine: {engine.name}')

# Must produce valid output
ohlcv = [{'date': f'2025-06-{i:02d}', 'open': 100+i, 'high': 102+i, 'low': 99+i, 'close': 101+i, 'volume': 10000} for i in range(30)]
result = engine.predict(ohlcv, 5)
print(f'Direction: {result[\"direction\"]}')
print(f'Confidence: {result[\"confidence\"]}')
print('Stats engine OK')
"
```
- [ ] 无 GPU 时返回统计基线引擎
- [ ] 预测结果格式正确

### 7.2 FinBERT 无 GPU 降级

```bash
E:\Anaconda3\envs\quantsage_py311\python.exe -c "
from src.plugins.finbert_service.sentiment_engine import RuleBasedEngine
engine = RuleBasedEngine()
result = engine.analyze('业绩增长，市场看好')
print(f'Label: {result[\"label\"]}, Score: {result[\"score\"]}')
# Must not crash with empty text
r2 = engine.analyze('')
print(f'Empty text: {r2[\"label\"]}')
assert result['label'] == 'positive'
print('Rule-based engine OK')
"
```
- [ ] 规则引擎正确识别正面情绪
- [ ] 空文本不崩溃

---

## 八、配置文件安全检查 (2 分钟)

```bash
E:\Anaconda3\envs\quantsage_py311\python.exe -c "
from src.core.config_manager import encrypt_api_key, decrypt_api_key, save_config, load_config

# Encrypt roundtrip
key = 'sk-test-my-secret-api-key-12345'
enc = encrypt_api_key(key)
assert enc != key
assert decrypt_api_key(enc) == key
print('Encryption OK')

# Check .env does NOT contain plaintext key
with open('.env', 'r') as f:
    env_content = f.read()
assert 'sk-test-my-secret-api-key-12345' not in env_content
print('.env clean: no plaintext keys')
"
```
- [ ] 加密往返正确
- [ ] .env 文件中不含明文密钥

---

## 测试结果汇总

| 测试项 | 状态 | 备注 |
|--------|------|------|
| 1.1 Python 环境 | ⬜ | |
| 1.2 PyTorch GPU | ⬜ | |
| 1.3 全部单元测试 | ⬜ | 79 passed |
| 2.1 UI 启动 | ⬜ | |
| 2.2 免责弹窗 | ⬜ | |
| 2.3 配置向导 | ⬜ | |
| 2.4 首页 + 报告 | ⬜ | |
| 3.2 Kronos 健康检查 | ⬜ | |
| 3.3 GPU 状态 | ⬜ | |
| 4.2 FinBERT 健康检查 | ⬜ | |
| 4.3 情绪分析 | ⬜ | |
| 5.1 A股分析 | ⬜ | 600519 贵州茅台 |
| 6.1 报告生成 | ⬜ | |
| 6.2 合规扫描 | ⬜ | |
| 7.1 Kronos 降级 | ⬜ | |
| 7.2 FinBERT 降级 | ⬜ | |
| 8. 配置文件安全 | ⬜ | |

---

## 开始测试

```bash
cd E:\AI_projects\fin
set KMP_DUPLICATE_LIB_OK=TRUE
set PYTHONIOENCODING=utf-8
set NO_PROXY=localhost,127.0.0.1,pypi.tuna.tsinghua.edu.cn,eastmoney.com

# 第一步: 跑全部单元测试
E:\Anaconda3\envs\quantsage_py311\python.exe -m pytest tests/ -v

# 第二步: 启动 UI
E:\Anaconda3\envs\quantsage_py311\python.exe -m streamlit run src/ui/app.py
```

---

_测试完成后告诉我结果，通过后进入 M7 方案 B。_
