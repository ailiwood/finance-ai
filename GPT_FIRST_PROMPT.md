# GPT 第一次对话提示词

> 将此文件内容复制粘贴到 ChatGPT 对话中作为第一条消息。

---

## 背景

我正在开发一个 Windows 桌面股票研究软件 **QuantSage**，代码仓库在 https://github.com/ailiwood/finance-ai。

当前激活系统架构是"方案 B"：用户在第三方发卡平台付款 → 获取凭证码 → 打开激活网页兑换激活码 → 激活码贴入客户端。激活网页和云函数部署在 Cloudflare Workers + D1 上。

现在决定**跳过第三方发卡平台**，原因是：
1. 推荐的发卡平台（七七发卡、玛雅发卡等）需要付费或挂梯子才能打开
2. 我已经申请了**支付宝商家收款码**（图片已放在项目 `pay_img/` 目录下）
3. 希望完全自主，不依赖任何外部平台

## 你要做的任务

### 总体目标

构建**自建收款 + 激活流程**，替代第三方发卡平台。技术路线：自建网页 + 支付宝收款码 + 人工确认签发。

### 用户完整流程（设计目标）

1. 用户安装 QuantSage → 首次启动看到激活页面
2. 激活页面显示：设备码 + 支付宝收款码 + 付款指引
3. 用户扫码付款，在付款备注里填上设备码
4. 用户在激活网页提交"设备码"作为订单
5. 我（开发者）收到支付宝到账通知，在管理后台查到该设备码的待处理订单
6. 我在管理后台点"签发激活码"→ 云函数用私钥签名 → 激活码存入数据库
7. 用户回到激活网页，输入设备码查询 → 获得激活码 → 贴入软件完成激活

### 具体子任务

#### 子任务 1：激活网页改造（修改 `cloudflare/worker.js` 的 GET / 页面）

当前的 GET / 返回一个凭证码兑换页面。需要改造为：

- **上半部分**：显示支付宝商家收款码图片 + 付款金额 + 付款指引
  - 收款码图片放在 `pay_img/` 目录，需要在 Worker 中以静态资源方式提供
  - 或者直接将图片转为 base64 data URI 嵌入 HTML
  
- **中间部分**：设备码输入框 + "提交订单"按钮
  - 用户输入设备码 → POST 到新接口 `/order/create`
  - 如果设备码已有已签发的激活码 → 直接显示激活码
  - 如果设备码已有待处理订单 → 显示"订单待处理，请稍后查询"
  - 如果是新设备码 → 创建 pending 订单，显示"订单已提交，付款后等待激活码"

- **下半部分**："查询激活码"区域
  - 用户输入设备码 → GET `/order/status?device_code=XXX`
  - 如果已签发 → 显示激活码 + 复制按钮
  - 如果待处理 → 显示"请等待开发者确认收款后签发"
  - 如果不存在 → 显示"未找到订单，请先提交订单"

- **保留**原有凭证码兑换功能（向下兼容）

#### 子任务 2：新增 API 端点（在 `cloudflare/worker.js` 中）

新增以下端点：

**POST `/order/create`**：
```json
// Request
{ "device_code": "ABCD1234ABCD1234" }
// 校验：device_code 必须是 16 位 hex

// Response (200 — 新订单)
{ "success": true, "status": "pending", "message": "订单已创建，请付款后等待激活码" }

// Response (200 — 已有激活码)
{ "success": true, "status": "completed", "license_key": "QS...", "message": "激活码已就绪" }
```

**GET `/order/status?device_code=XXXX`**：
```json
// Response (200 — 已完成)
{ "success": true, "status": "completed", "license_key": "QS...", "level": "pro", "expires": "2027-06-24" }

// Response (200 — 待处理)
{ "success": true, "status": "pending", "message": "订单待处理，请等待开发者确认收款" }

// Response (404 — 不存在)
{ "success": false, "error": "未找到该设备码的订单" }
```

**GET `/admin`**（新增管理后台页面，HTML）：
- Admin Secret 登录表单
- 登录成功后显示：
  - **待处理订单列表**（从 `orders` 表查 status='pending'），每条显示设备码、提交时间
  - 每条旁边有"签发激活码"按钮 → POST `/admin/issue`
  - **最近已签发列表**（最近 50 条），显示设备码、激活码、签发时间

**POST `/admin/issue`**：
```json
// Request
// Header: X-Admin-Secret: 97fb8f8070d0cf4626f6e398329e9b15
{ "device_code": "ABCD1234ABCD1234" }

// Response (200)
{ "success": true, "license_key": "QS...", "level": "pro", "expires": "2027-06-24" }
```

**POST `/admin/issue-batch`**（批量签发，勾选多条订单一键处理）：
```json
// Request
// Header: X-Admin-Secret: ...
{ "device_codes": ["ABCD1234ABCD1234", "BBBB5678BBBB5678"] }

// Response (200)
{ "success": true, "results": [{ "device_code": "...", "license_key": "..." }, ...] }
```

#### 子任务 3：D1 数据库新增表

在 `cloudflare/schema.sql` 新增（并在远程 D1 执行）：

```sql
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_code TEXT NOT NULL,
  status TEXT DEFAULT 'pending',   -- pending / completed / rejected
  license_key TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_device ON orders(device_code);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
```

#### 子任务 4：客户端激活页更新（`src/ui/activation_gate.py`）

- 在设备码显示区域下方，增加支付宝收款码的显示（指向 `pay_img/` 下的图片）
- 更新购买指引文字（不再提发卡平台，改为支付宝扫码付款）
- 指向激活网页 URL（不变：`https://quantsage-activation.lk166564317.workers.dev/`）
- 保留激活码输入框和激活按钮

#### 子任务 5：部署

- 更新 `cloudflare/wrangler.toml`（无需改动，直接用）
- `cd cloudflare && npx wrangler d1 execute quantsage_db --file=schema.sql --remote`（执行新表）
- `cd cloudflare && npx wrangler deploy`（部署 Worker）
- 重新打包 Windows 安装包（PyInstaller + Inno Setup）

## 技术约束

1. **私钥绝不进代码**：signEd25519 函数继续使用 Worker 环境变量 `PRIVATE_KEY_HEX`
2. **签名格式不变**：11 字节 payload + 64 字节签名，和现有 `verify_license` 完全兼容
3. **Admin Secret 校验**：所有 `/admin/*` 端点必须校验 `X-Admin-Secret` header
4. **设备码格式**：必须是 16 位及以上 hex（0-9, A-F），小写自动转大写
5. **支付宝收款码图片**：当前在 `pay_img/` 目录下，文件名待确认。处理方式：base64 内嵌到 HTML 中
6. **中文优先**：所有 UI 文案、错误提示用简体中文
7. **免责声明**：激活网页和客户端必须包含免责声明："本软件仅供参考研究，不构成任何投资建议，盈亏自负"

## 关键参考

- Worker 主文件：`cloudflare/worker.js`
- 客户端验签：`src/core/license.py`
- 激活页面：`src/ui/activation_gate.py`
- Worker URL：`https://quantsage-activation.lk166564317.workers.dev/`
- Admin Secret：`97fb8f8070d0cf4626f6e398329e9b15`
- 公钥：`3fce9236ba6b25f81e633cea68485906ffced084cb4e4aa0de5dd22554cac9c3`
- D1 数据库：`quantsage_db`（ID: `61ee22ab-03c5-431f-9640-a4856c92d366`）
- Cloudflare 账号：`bb34b0be9208212351387ce918c190e2`
- 项目完整背景见：`GPT_PROJECT.md`

## 输出要求

请完成以下交付：
1. 更新后的 `cloudflare/worker.js`（完整文件）
2. 更新后的 `cloudflare/schema.sql`（完整文件）
3. 更新后的 `src/ui/activation_gate.py`（完整文件）
4. 部署命令（终端执行顺序）
5. 自测验证脚本（Python 脚本，测试新增的 API 端点）
