# LICENSE_SIGNING_GUIDE.md — 非对称签名激活模块 + 开发者密钥生成器

> 放到项目 `docs/`。目标:用私钥签名/公钥验证替换现有16位校验和,并给开发者一个一键运行的密钥生成器(exe/bat)。

---

## 一、原理(为什么这样防得住伪造)

```
开发者本地(只有你):
  【私钥】对 (设备码+过期+等级) 签名 → 密钥
  私钥绝不进软件、绝不进git

用户软件内:
  内置【公钥】对用户输入的密钥验签
  验签通过 + 设备码匹配 + 未过期 → 激活
```
- 用户逆向软件只能拿到**公钥**(只能验签,不能签发)。
- 没有私钥就**算不出有效签名** → 伪造不出能通过验签的密钥。
- 这比"16位校验和"强一个量级:校验和算法可逆向复制,非对称签名的私钥用户永远拿不到。

用 **Ed25519**(椭圆曲线,密钥短、签名短、速度快,适合做license)。Python 用 `cryptography` 库。

---

## 二、密钥对生成(一次性,开发者做)

scripts/gen_keypair.py(只跑一次,生成你的私钥/公钥):
```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

priv = Ed25519PrivateKey.generate()
pub = priv.public_key()

# 私钥保存到本地(绝不进git!)
priv_bytes = priv.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption())
open("quantsage_private.key", "wb").write(priv_bytes)

# 公钥(硬编码进客户端)
pub_bytes = pub.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw)
print("公钥(hex,硬编码进客户端):", pub_bytes.hex())
```
- 运行后:`quantsage_private.key` 你保管(加.gitignore、备份);公钥hex硬编码进客户端验证模块。

---

## 三、密钥格式设计

密钥载荷(payload)= 设备码 + 过期日期 + 等级,签名后编码成可读格式:
```
payload = {
    "device": "设备码前16位",   # 绑定设备
    "exp": "2027-12-31",        # 过期日期;"9999-12-31"=永久
    "level": "pro",             # free/pro,按等级解锁
}
签名 = Ed25519_sign(私钥, json(payload))
密钥 = base32(payload + 签名)  → 分段成 XXXX-XXXX-XXXX-... 便于输入
```

---

## 四、客户端验证(src/core/license.py)

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PUBLIC_KEY_HEX = "...粘贴第二步输出的公钥..."

def verify_license(key_str: str, device_code: str) -> dict:
    """返回 {valid, level, exp, reason}。"""
    try:
        payload, signature = _decode(key_str)   # 反解分段格式
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
        pub.verify(signature, json_bytes(payload))   # 验签,失败抛异常
        if payload["device"] != device_code[:16]:
            return {"valid": False, "reason": "密钥与本设备不匹配"}
        if payload["exp"] != "9999-12-31" and today() > payload["exp"]:
            return {"valid": False, "reason": "密钥已过期"}
        return {"valid": True, "level": payload["level"], "exp": payload["exp"]}
    except Exception:
        return {"valid": False, "reason": "密钥无效"}
```
- 替换掉现有的16位校验和验证逻辑。
- 激活成功后本地存储已验证状态(下次启动复验)。

---

## 五、开发者密钥生成器(一键运行,核心交付)

### 要求:你点一下就能用,生成密钥发给客户
做一个带简单界面的生成器,**两种形态二选一**(让CC做对你最方便的):

**形态A:GUI小程序(推荐,最友好)** scripts/keygen_gui.py:
- 用 tkinter(Python自带,无需额外依赖)做个小窗口:
  - 输入框:设备码(粘贴客户发来的)
  - 下拉:等级(free/pro)
  - 下拉/输入:有效期(1年/永久/自定义日期)
  - 按钮:[生成密钥] → 显示密钥 + [复制]按钮
- 打包成 keygen.exe(PyInstaller),你双击即用。

**形态B:bat一键运行** scripts/keygen.bat:
- 双击运行 python scripts/keygen.py,命令行交互输入设备码→输出密钥。
- 更简单但不如GUI友好。

### 生成器逻辑(keygen 核心)
```python
def generate_key(device_code, level="pro", exp="9999-12-31"):
    priv = load_private_key("quantsage_private.key")
    payload = {"device": device_code[:16], "exp": exp, "level": level}
    signature = priv.sign(json_bytes(payload))
    return _encode(payload, signature)   # 编码成 XXXX-XXXX-... 格式
```

### 开发者最高权限(生成器支持)
- 给任意设备码生成密钥。
- **永久密钥**:exp="9999-12-31"(给你自己/VIP)。
- **年订阅密钥**:exp=明年今天。
- **等级**:free/pro,控制功能解锁。
- 一键生成自己设备的永久pro密钥(给自己用)。

---

## 六、安全红线
1. **私钥(quantsage_private.key)是命根子**:
   - 绝不进 git(加 .gitignore)。
   - 绝不进用户安装包。
   - 本地加密保管 + 备份(丢了就没法发新密钥,泄露=任何人能造密钥)。
2. keygen 工具(含私钥)只在你开发机,不分发。
3. 公钥进客户端无所谓(本来就该公开)。
4. .gitignore 必须含:`*.key`、`quantsage_private.key`、keygen 生成的产物。

---

## 七、验证(工作报告必须包含)
1. gen_keypair 生成密钥对,公钥已硬编码客户端。
2. keygen 工具(exe或bat)能运行,输入设备码→输出密钥的演示。
3. 客户端 verify_license:正确密钥通过、错误/他设备/过期密钥被拒 的测试。
4. 演示:永久密钥 + 年订阅密钥 + 等级密钥 各生成验证一次。
5. 确认私钥在 .gitignore,不在仓库、不在安装包。
6. 现有16位校验和逻辑已被替换。
