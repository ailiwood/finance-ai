# MULTI_LLM_PROVIDERS.md — 多 LLM 供应商接入指导

> 放到项目 `docs/`。目标:兼容市面主流模型,用户在配置向导里下拉选供应商、填 key 即用。

---

## 一、设计原则:统一走 OpenAI 兼容接口

好消息:现在**绝大多数主流大模型都提供"OpenAI 兼容"的 API 端点**,即同样的 `/chat/completions` 协议,只是 `base_url`、`api_key`、`model` 不同。所以不要为每家写一套 SDK,而是用**一个统一客户端 + 各家的 base_url/model 配置表**。项目已经在用 DeepSeek(httpx POST chat/completions),沿用这个模式扩展即可。

> 例外:个别厂商(如 Anthropic Claude 原生接口、Google Gemini 原生接口)协议略有不同。对这两家,要么用它们各自提供的 OpenAI 兼容端点,要么用 LangChain 对应的 ChatModel 封装。优先选 OpenAI 兼容端点,最省事。

---

## 二、供应商配置表(内置到项目)

新建 `src/llm/providers.py`,维护一张供应商注册表。每家给出:显示名、base_url、常用 model 列表、api_key 环境变量名、是否 OpenAI 兼容。下面是建议覆盖的主流供应商(base_url 以各家官方文档为准,CC 实施时需逐一核对最新地址):

| 供应商 | OpenAI 兼容 | 备注 |
|--------|-------------|------|
| DeepSeek | 是 | 已接入,作为默认 |
| OpenAI | 是(原生) | GPT 系列 |
| 月之暗面 Kimi (Moonshot) | 是 | moonshot 系列 |
| MiniMax | 是 | abab/MiniMax 系列 |
| 阿里通义千问 (DashScope) | 是(兼容模式) | qwen 系列 |
| 智谱 GLM (Zhipu) | 是(兼容模式) | glm 系列 |
| 字节豆包 (Volcengine Ark) | 是 | doubao 系列 |
| 百度文心 (Qianfan) | 是(兼容模式) | ernie 系列 |
| 腾讯混元 | 是(兼容模式) | hunyuan 系列 |
| 零一万物 (01.AI) | 是 | yi 系列 |
| 硅基流动 (SiliconFlow) | 是 | 聚合多家开源模型,一个 key 多模型 |
| OpenRouter | 是 | 聚合海量模型,一个 key 通吃,适合"其它/自定义" |
| 本地 Ollama | 是 | localhost:11434,零成本 |
| 自定义(Custom) | 是 | 用户自填 base_url + model,兜底任意兼容端点 |

> **强烈建议保留"自定义/OpenRouter"两个兜底项**:这样即使某家没预置,用户也能填 base_url+model 用起来,实现"兼容所有主流模型"的目标。

数据结构示例:
```python
PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "key_env": "DEEPSEEK_API_KEY",
        "openai_compatible": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],  # 以官方现行为准
        "key_env": "OPENAI_API_KEY",
        "openai_compatible": True,
    },
    "moonshot": {
        "label": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "key_env": "MOONSHOT_API_KEY",
        "openai_compatible": True,
    },
    "minimax": {
        "label": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",   # 以官方现行为准
        "models": ["abab6.5s-chat"],
        "key_env": "MINIMAX_API_KEY",
        "openai_compatible": True,
    },
    "custom": {
        "label": "自定义 (OpenAI 兼容)",
        "base_url": "",      # 用户填
        "models": [],        # 用户填
        "key_env": "CUSTOM_API_KEY",
        "openai_compatible": True,
    },
    # ... 其余按上表补全
}
```
**重要**:base_url、model 名称、是否兼容,各家会变。CC 不要凭记忆写死,实施时用 web 检索各家"OpenAI 兼容 / API 文档"确认最新值,拿不准的供应商在注释里标注"需用户核对"。

---

## 三、统一客户端

新建 `src/llm/client.py`,一个 `LLMClient`:
```python
import httpx

class LLMClient:
    def __init__(self, provider_key, api_key, base_url=None, model=None):
        cfg = PROVIDERS[provider_key]
        self.base_url = base_url or cfg["base_url"]
        self.model = model or (cfg["models"][0] if cfg["models"] else None)
        self.api_key = api_key

    def chat(self, system, user, temperature=0.7, timeout=120):
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            json={"model": self.model,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}],
                  "temperature": temperature},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
```
- 让 TradingAgents 的 LLM 后端也能指向这个统一配置(TradingAgents 本身支持自定义 base_url,把用户选的 provider 的 base_url/model/key 传进去即可)。
- 失败处理:超时/限流/鉴权错误要给**用户能看懂的中文提示**(如"API Key 无效或余额不足""该供应商地址无法连接"),并允许重试或换供应商。

---

## 四、配置向导改造(UI)
在配置向导"选 LLM"那一步:
1. 下拉选「供应商」(读 PROVIDERS 的 label)。
2. 选「模型」(读该供应商的 models;custom 时让用户手填)。
3. 填「API Key」(密码框,只存本地,绝不上传/打日志)。
4. custom/openrouter 时,额外显示「base_url」输入框。
5. 一个「测试连接」按钮:用填的配置发一条最小请求(如 "ping"),成功提示绿勾,失败给中文原因。
6. 也保留「本地 Ollama」选项(无需 key)。

`.env.example` 同步补充各供应商的 key 变量名(留空)。

---

## 五、自测要求
- 写单元测试:mock httpx,验证不同 provider 的 base_url/model 拼接正确。
- 至少用 DeepSeek(你有 key)真实跑通"测试连接"。其它供应商无 key 时,验证 UI 选择与配置保存逻辑即可,真实连通由用户自测。
