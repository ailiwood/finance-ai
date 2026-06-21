# API_KEY_FIX.md — "API key 格式无效"问题诊断与修复

> 放到项目 `docs/`。现象:用户确认 key 正确,但点"开始分析"报"key 格式无效"。
> 判断:这是代码里的**格式校验逻辑 bug**,不是 key 本身的问题。

---

## 一、根因判断

"key 格式无效"几乎不可能是供应商返回的(供应商返回的是 401 鉴权失败)。它一定来自项目自己代码里一段类似:
```python
if not api_key.startswith("sk-"):
    raise ValueError("API key 格式无效")
```
上几轮加了多供应商支持(OpenAI/DeepSeek/Kimi/MiniMax/通义/智谱...),但**不同供应商 key 格式完全不同**:
- OpenAI / DeepSeek / Kimi(Moonshot):`sk-` 开头
- MiniMax:常是 JWT 或其它格式,**并非 sk- 开头**
- 通义/智谱等:各不相同

**最可能的 bug:CC 写校验时用了针对 OpenAI 的硬编码规则(如 startswith("sk-") 或某个正则),套用到所有供应商,导致非 sk- 开头的 key、或被写错的正则误伤的 key 全被判"格式无效"。**

---

## 二、最可能的具体 bug(按概率)
1. **硬编码前缀校验** `startswith("sk-")` 套用所有供应商。
2. **正则写错**:过严或有误的 `re.match`,合法 key 也匹配不上。
3. **读取时 key 变脏**:从 .env/配置读出来带了空格/换行/引号(末尾 `\n`、被 `"..."` 包裹),长度/格式对不上。极常见——key 是对的,但读进来的字符串脏了。
4. **provider 与 key 错位**:选了 Kimi 却用 DeepSeek 的校验规则;或配置存取时 provider/key 字段没对应。
5. **空值误判**:读取链路问题导致 api_key 实际是空串,报"格式无效"。

---

## 三、核心修复原则:删掉本地格式校验,改用"真实调用"验证

**本地猜 key 格式是坏设计**:供应商太多、格式各异、随时会变,永远列不全规则,加一个供应商就可能误伤。

正确做法:
- 本地只做最低检查:**非空 + `.strip()` 去首尾空白**,其余一律放行。
- 真正的有效性判断交给**实际 API 调用**:发最小请求,返回 200 = 有效;401 = 提示"key 无效或余额不足";其它错误给对应提示。
- 这样无论什么供应商、什么格式,都不会本地误判。

---

## 四、具体修复步骤(CC 执行)

### 步骤 1 · 定位
全项目搜索报错文案:`格式无效` / `invalid` / `key format` / `格式` 等,找到抛出"key 格式无效"的校验代码,记录文件与行号。重点查 `src/llm/`、config/配置相关、配置向导、分析入口。

### 步骤 2 · 加脱敏调试日志(定位 key 是否变脏/provider 是否错位)
在校验逻辑执行前加(**绝不打印完整 key**):
```python
import logging
logger = logging.getLogger(__name__)
_has_ws = any(c in api_key for c in (" ", "\n", "\r", "\t"))
logger.info(f"[KEY调试] provider={provider!r}, 前缀={api_key[:4]!r}, "
            f"长度={len(api_key)}, 含空白字符={_has_ws}")
```
据此判断:key 是否带空格/换行、长度对不对、provider 是否正确。

### 步骤 3 · 重写校验逻辑(删硬编码,只查非空)
找到类似:
```python
# ❌ 错误:硬编码 sk- 前缀,误伤非 OpenAI 供应商
if not api_key.startswith("sk-"):
    raise ValueError("API key 格式无效")
```
改为:
```python
# ✅ 正确:只检查非空,去首尾空白,不猜格式
def validate_api_key(api_key: str) -> str:
    if api_key is None or not api_key.strip():
        raise ValueError("请填写 API Key")
    return api_key.strip()   # 返回清洗后的 key,供后续使用
```
- 删除所有针对 key 格式的 startswith / 正则 / 长度判断。
- 任何"格式"层面的限制一律取消,有效性交给 API 调用。

### 步骤 4 · 修复读取链路(去脏 + provider 对应)
1. 从 .env / 配置文件 / UI 表单读取 key 后,**一律 `.strip()`** 去首尾空白和换行。
2. 检查是否被引号包裹(`"sk-xxx"`),如有则去掉引号。
3. 确认 provider 字段与 key、base_url、model 正确对应(选 Kimi 就用 Kimi 的 base_url 和 key,不要错位)。
4. 配置读写用统一的 load_config/save_config,避免多处不一致。

### 步骤 5 · 有效性改由真实调用判断
1. 配置向导的"测试连接"按钮:用填写的 provider/key/base_url/model 发一个最小请求(如 messages=[{"role":"user","content":"ping"}], max_tokens=1)。
2. 返回 200 → 绿勾"连接成功";401 → "API Key 无效或余额不足";超时/连不上 → "无法连接到该供应商,请检查网络或 base_url"。
3. **分析流程入口不要再做本地格式校验**,直接用清洗后的 key 调用,让 API 返回决定成败。错误信息要区分"未填写 key""鉴权失败""网络问题",而非笼统的"格式无效"。

---

## 五、验证(工作报告必须包含)
1. 抛出"格式无效"的代码位置(文件+行号),以及它原来的错误逻辑。
2. 步骤 2 脱敏日志的真实输出(证明 key 读取正确、provider 对应正确)。
3. 改为"仅非空检查 + 真实调用验证"后的代码。
4. 用 DeepSeek 真实 key 跑通"开始分析"全流程的结果。
5. 若可能,用一个非 sk- 开头格式的 key(或 mock)验证不再误报"格式无效"。
