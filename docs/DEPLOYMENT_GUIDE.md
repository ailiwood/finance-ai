# QuantSage 激活系统 · 完整部署指引

> 从零到上线，每一步都有详细的网址、命令、截图说明。
> 预计耗时：30-60 分钟（不含发卡平台审核时间）。

---

## 〇、前置条件（已完成，无需操作）

以下工作已经由 CC 完成，你无需再操作：

- [x] Cloudflare Worker 已部署：`https://quantsage-activation.lk166564317.workers.dev/`
- [x] D1 数据库已创建：`quantsage_db`（ID: `61ee22ab-03c5-431f-9640-a4856c92d366`）
- [x] 表结构已建好：`vouchers`（凭证码表）+ `activations`（激活记录表）
- [x] Ed25519 私钥已设为 Worker 环境变量（`PRIVATE_KEY_HEX`），绝不外泄
- [x] Admin Secret 已设为 Worker 环境变量（`ADMIN_SECRET`）= `97fb8f8070d0cf4626f6e398329e9b15`
- [x] 客户端安装包已构建：`dist/installer/QuantSage_Setup_v1.0.0.exe`

你可以随时在浏览器打开你的 Cloudflare 控制台查看这些资源：
👉 **https://dash.cloudflare.com/** → 登录 → 点击左侧 "Workers & Pages" → 看到 `quantsage-activation`

---

## 一、生成凭证码（在你的电脑上操作）

凭证码就是用户付款后自动收到的"卡密"。你需要预先生成一批，上传到发卡平台。

### 步骤 1.1：打开终端，激活 Python 环境

```bash
# 打开 Git Bash 或 PowerShell，然后执行：
source E:/Anaconda3/etc/profile.d/conda.sh
conda activate quantsage_py311
cd E:/AI_projects/fin
```

### 步骤 1.2：生成 100 个凭证码

```bash
python scripts/gen_vouchers.py --count 100 --output-dir ./vouchers_batch_01
```

执行后会生成 3 个文件：
```
vouchers_batch_01/
├── vouchers_20260624_XXXXXX.csv    ← 上传到发卡平台用的
├── vouchers_20260624_XXXXXX.txt    ← 你自己留存备查的
└── vouchers_20260624_XXXXXX.sql    ← 导入到 D1 数据库用的
```

> **建议**：先用 `--count 10` 生成 10 个做测试，流程跑通后再生成大批量。

### 步骤 1.3：把凭证码导入云数据库（D1）

打开终端，在项目根目录执行：

```bash
cd E:/AI_projects/fin/cloudflare
npx wrangler d1 execute quantsage_db --file=../vouchers_batch_01/vouchers_20260624_XXXXXX.sql --remote
```

> ⚠️ 注意：把 `XXXXXX` 替换为实际生成的时间戳（查看 `vouchers_batch_01/` 目录下的文件名）。

执行成功后，你会看到类似输出：
```
🚣 Executed 100 commands in Xms
```

**验证**（可选）：在 Cloudflare Dashboard 查看 D1 数据
👉 打开 https://dash.cloudflare.com/ → 左侧 "Workers & Pages" → 点 "D1" 标签 → 点 `quantsage_db` → "Console" 标签 → 输入：
```sql
SELECT COUNT(*) FROM vouchers WHERE status = 'unused';
```
应该显示 `100`。

---

## 二、注册发卡平台 & 挂商品

发卡平台负责收款 + 自动发凭证码。你不需要自己接支付接口。

### 步骤 2.1：选择发卡平台

国内常用的自动发卡平台（任选一家，按个人偏好）：

| 平台 | 网址 | 特点 |
|------|------|------|
| 独角数卡（自建） | https://github.com/assimon/dujiaoka | 开源自建，需服务器 |
| 发卡网（SaaS） | 搜索"虚拟商品自动发卡平台" | 无需服务器，注册即用 |
| 七七发卡 | https://www.77faka.com/ | SaaS，个人可用 |
| 玛雅发卡 | https://www.mayafaka.com/ | SaaS，支持微信/支付宝 |

> **建议 MVP 选 SaaS 型发卡平台**（无需自己部署服务器），注册一个账号即可。

以下以通用 SaaS 发卡平台为例，具体界面大同小异。

### 步骤 2.2：注册账号

1. 打开你选的发卡平台网址，点"注册"
2. 填写邮箱、密码（**不要用和重要账号相同的密码**）
3. 完成邮箱验证
4. 登录后台

### 步骤 2.3：配置支付通道

1. 进入后台 → "支付通道" 或 "支付配置"
2. 添加支付方式（通常是支付宝个人码/微信个人码收款）
3. 按平台指引上传收款码、设置回调

> ⚠️ 每个平台的支付配置不同，**仔细阅读该平台的帮助文档**。一般流程是：
> - 上传你的支付宝/微信收款二维码
> - 设置收款通知方式（一般是 APP 通知 + 平台监控）
> - 有些平台需要你挂一个"监控端"（安卓 APP 或浏览器插件）

### 步骤 2.4：创建商品

1. 进入后台 → "商品管理" → "添加商品"
2. 填写以下信息：

| 字段 | 建议填写 |
|------|---------|
| 商品名称 | `QuantSage 股票研究助手 - 激活许可证（绑定1台设备，有效期1年）` |
| 商品分类 | 软件/激活码/CDK |
| 售价 | 你定的价格（如 ¥19.90） |
| 库存方式 | **"卡密库存"** 或 "自动发卡" |
| 商品详情 | 见下方模板 ↓ |

**商品详情文案模板**（复制粘贴到商品描述）：

```
QuantSage 是一个本地运行的 AI 股票研究助手。

【包含功能】
✅ 8 个 AI Agent 自动分析生成研究报告
✅ 真实 K 线数据（前复权），MA/MACD/RSI/KDJ/BOLL 多周期指标
✅ 基本面 + 情绪面 + 技术面三维分析
✅ Kronos 深度学习 K 线预测模型
✅ 报告导出 PDF

【激活方式】
1. 下载安装 QuantSage 软件
2. 打开软件，在激活页面查看你的"设备码"
3. 打开激活网页：https://quantsage-activation.lk166564317.workers.dev/
4. 输入本页面购买后获得的"凭证码" + 你的"设备码"
5. 点击获取激活码，复制粘贴到软件里完成激活

【重要说明】
⚠️ 本软件仅供参考研究，不构成任何投资建议，盈亏自负。
⚠️ 一个许可证密钥绑定一台设备，不可转让。
⚠️ 有效期为激活日起 1 年。
⚠️ 凭证码为一次性使用，兑换后即失效。
⚠️ 如有问题，联系开发者（飞书群：见软件内）。
```

### 步骤 2.5：上传凭证码库存

1. 在商品管理页面，找到刚创建的商品
2. 点"卡密管理"或"库存管理" → "导入卡密"
3. 上传你在步骤 1.2 生成的 `vouchers_*.csv` 文件
4. 确认导入。平台会显示导入数量。

---

## 三、测试购买 → 激活全流程（必做！）

在上线前，必须完整走一遍用户流程。

### 步骤 3.1：模拟购买

1. 打开你的发卡平台商品页面（前台，不是后台）
2. 下一个测试单（用 1 分钱或平台提供的测试模式）
3. 付款完成后，平台会自动显示一个**凭证码**（形如 `QS-c3e3b5acabde1f3944a408c1`）
4. **记下这个凭证码**，下一步要用

### 步骤 3.2：用凭证码兑换激活码

1. 打开浏览器，访问：
   👉 **https://quantsage-activation.lk166564317.workers.dev/**

2. 你会看到激活网页。页面有两个输入框：
   - "购买凭证码"：粘贴你上一步拿到的凭证码
   - "设备码"：需要从 QuantSage 客户端获取

3. 打开 QuantSage 软件（安装 `dist/installer/QuantSage_Setup_v1.0.0.exe` 后启动）
   - 首次启动会看到激活页面
   - 页面上方显示**设备码**（如 `70E3032EA0E74D51`）
   - 复制这个设备码

4. 回到浏览器激活网页，粘贴设备码，点击"获取激活码"

5. 如果一切正常，你会看到：
   ```
   ✅ 激活码获取成功！等级: pro | 到期: 2027-06-24
   ```
   下方显示一长串激活码（以 `QS` 开头）

6. 复制这个激活码，粘贴到 QuantSage 客户端的"许可证密钥"输入框

7. 点击"激活"按钮 → 显示激活成功 → 进入主界面！

### 步骤 3.3：验证一码一用

1. 回到激活网页
2. 用**同一个凭证码** + **另一个设备码**（随便编一个如 `0000111122223333`）
3. 点击"获取激活码"
4. 应该显示错误：**"凭证码已被使用"** ✅

这就证明了一码只能用一次的安全机制有效。

---

## 四、给运维/内部人员签发永久码

永久码不会过期，给核心运维人员使用。

### 步骤 4.1：获取对方的设备码

让运维人员：
1. 安装 QuantSage 软件
2. 打开软件到激活页面
3. 复制屏幕上显示的**设备码**（16 位十六进制）
4. 把设备码发给你

### 步骤 4.2：签发绑设备的永久码

在终端执行：

```bash
source E:/Anaconda3/etc/profile.d/conda.sh
conda activate quantsage_py311
cd E:/AI_projects/fin

# 设置 Admin Secret（只需设置一次）
export QUANTSAGE_ADMIN_SECRET="97fb8f8070d0cf4626f6e398329e9b15"

# 签发永久码（把 <设备码> 替换为对方发给你的实际设备码）
python scripts/issue_permanent.py --device <设备码> --note "运维-张三"
```

执行后会输出：
```
{
  "success": true,
  "license_key": "QS...",
  "level": "permanent",
  "expires": "9999-12-31"
}
```

把 `QS...` 开头的激活码发给对方，对方粘贴到软件里即可永久激活。

### 步骤 4.3：签发万能码（应急用，谨慎！）

万能码不绑设备，任何机器都能用。**只给你自己和最核心的人**。

```bash
python scripts/issue_permanent.py --device MASTER --note "应急万能码-01"
```

> ⚠️ **万能码一旦泄露，任何人都能激活。务必安全保管！**

### 步骤 4.4：永久码记录

每次签发的永久码都会自动保存为 JSON 文件（`permanent_licenses_*.json`），请妥善存档。

也可以随时在 Cloudflare Dashboard 查看所有激活记录：
👉 https://dash.cloudflare.com/ → "Workers & Pages" → "D1" → `quantsage_db` → "Console" → 输入：
```sql
SELECT * FROM activations WHERE level LIKE 'permanent%' ORDER BY created_at DESC;
```

---

## 五、日常运维

### 日常售卖（全自动，你什么都不用管）

1. 用户在发卡平台付款
2. 平台自动发凭证码
3. 用户去激活网页兑换激活码
4. 用户把激活码贴进软件 → 激活完成

你只需要：
- 定期查看发卡平台余额 → 提现
- 凭证码快用完时，重新执行步骤 1.2 ~ 1.3 补充库存

### 补充凭证码库存

```bash
# 1. 生成新的凭证码
python scripts/gen_vouchers.py --count 100 --output-dir ./vouchers_batch_02

# 2. 导入 D1
cd cloudflare
npx wrangler d1 execute quantsage_db --file=../vouchers_batch_02/vouchers_*.sql --remote

# 3. 把新生成的 CSV 上传到发卡平台的商品 → 卡密管理 → 导入
```

### 查看激活统计

在 Cloudflare Dashboard 的 D1 Console 中执行：
```sql
-- 总激活数
SELECT COUNT(*) FROM activations;

-- 今天激活数
SELECT COUNT(*) FROM activations WHERE date(created_at) = date('now');

-- 剩余未用凭证码
SELECT COUNT(*) FROM vouchers WHERE status = 'unused';

-- 已用凭证码
SELECT COUNT(*) FROM vouchers WHERE status = 'used';
```

---

## 六、可选优化

### 6.1 绑定自己的域名（更正式）

当前激活网页地址是：
`https://quantsage-activation.lk166564317.workers.dev/`

如果你有自己的域名（如 `activate.你的域名.com`），可以绑定到 Worker：

1. 在 Cloudflare Dashboard 中添加你的域名（https://dash.cloudflare.com/ → "添加站点"）
2. 把域名的 DNS 服务器改为 Cloudflare 提供的
3. 进入 "Workers & Pages" → `quantsage-activation` → "Triggers" 标签 → "Add Custom Domain"
4. 输入 `activate.你的域名.com`
5. 然后更新客户端代码 `src/ui/activation_gate.py` 中的 `ACTIVATION_PAGE_URL`，重新打包

### 6.2 调整激活码有效期

当前 pro 激活码有效期为 1 年（365 天）。如需调整：

编辑 `cloudflare/worker.js`，找到：
```javascript
const expDays = expDaysFromNow(365);
```
把 `365` 改成你想要的天数（如 `730` = 2 年），然后重新部署：
```bash
cd cloudflare
npx wrangler deploy
```

---

## 七、故障排查

### Worker 返回 500 错误

1. 打开 Cloudflare Dashboard：https://dash.cloudflare.com/
2. "Workers & Pages" → `quantsage-activation` → "Logs" 标签
3. 查看实时日志，定位错误原因

### wrangler 命令报错 "not logged in"

```bash
npx wrangler login
```
浏览器会弹出 Cloudflare 授权页面，点"允许"。

### 凭证码在发卡平台显示"已售罄"

说明凭证码库存用完了，执行步骤五的"补充凭证码库存"。

### 用户说"凭证码已被使用"

可能原因：
1. 用户自己已经兑换过了（问清楚）
2. 发卡平台重复发了同一个凭证码（联系平台客服）
3. 恶意尝试（查看 D1 中该凭证码的 `used_at` 和 `bound_device`）

---

## 八、速查表

| 项目 | 值 |
|------|-----|
| 激活网页（用户用） | https://quantsage-activation.lk166564317.workers.dev/ |
| Cloudflare 控制台 | https://dash.cloudflare.com/ |
| Worker 名称 | `quantsage-activation` |
| D1 数据库名 | `quantsage_db` |
| Admin Secret | `97fb8f8070d0cf4626f6e398329e9b15` |
| 公钥（客户端硬编码） | `3fce9236ba6b25f81e633cea68485906ffced084cb4e4aa0de5dd22554cac9c3` |
| 私钥（云端，绝不出站） | Worker Secret: `PRIVATE_KEY_HEX` |
| 安装包位置 | `E:\AI_projects\fin\dist\installer\QuantSage_Setup_v1.0.0.exe` |
| GitHub | https://github.com/ailiwood/finance-ai |
