/**
 * QuantSage Cloud Activation Worker
 *
 * Endpoints:
 *   GET  /                        — Activation web page
 *   POST /redeem                  — Redeem voucher code → signed license
 *   POST /admin/issue-permanent   — Admin: issue permanent license
 *
 * Ed25519 signing via Web Crypto (native in Cloudflare Workers).
 * Private key stored in env.PRIVATE_KEY_HEX (Secret, never in code/git).
 */

// ── Constants ────────────────────────────────────────────────────────────────
const EPOCH = new Date("2024-01-01T00:00:00Z");
const PERMANENT = 0xFFFF;
const LEVEL_PRO = 0x01;
const LEVEL_FREE = 0x00;

// ── Helpers ──────────────────────────────────────────────────────────────────

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

function bytesToBase64url(bytes) {
  // Standard base64 → base64url (replace +/ with -_, strip =)
  let b64 = btoa(String.fromCharCode(...bytes));
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64urlToBytes(str) {
  // base64url → standard base64 → bytes
  let b64 = str.replace(/-/g, "+").replace(/_/g, "/");
  const pad = 4 - (b64.length % 4);
  if (pad < 4) b64 += "=".repeat(pad);
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function daysSinceEpoch(dateStr) {
  // dateStr format: "YYYY-MM-DD"
  const target = new Date(dateStr + "T00:00:00Z");
  return Math.floor((target - EPOCH) / (1000 * 60 * 60 * 24));
}

/**
 * Calculate exp_days from epoch (2024-01-01) for "N days from now".
 */
function expDaysFromNow(daysFromNow) {
  const now = new Date();
  const target = new Date(now.getTime() + daysFromNow * 24 * 60 * 60 * 1000);
  return Math.max(0, Math.min(0xFFFE, Math.floor((target - EPOCH) / (1000 * 60 * 60 * 24))));
}

function expDaysToString(expDays) {
  if (expDays === PERMANENT) return "9999-12-31";
  const d = new Date(EPOCH);
  d.setDate(d.getDate() + expDays);
  return d.toISOString().split("T")[0];
}

/**
 * Wrap a raw 32-byte Ed25519 seed into PKCS#8 format (RFC 8410).
 *
 * PKCS#8 structure for Ed25519:
 *   SEQUENCE {
 *     INTEGER 0
 *     SEQUENCE { OID 1.3.101.112 }
 *     OCTET STRING { OCTET STRING { 32-byte seed } }
 *   }
 *
 * Cloudflare Workers Web Crypto requires PKCS#8 for Ed25519 private key import.
 */
function rawToPkcs8(rawKeyBytes) {
  const oid = new Uint8Array([0x06, 0x03, 0x2b, 0x65, 0x70]); // OID 1.3.101.112
  const algoSeq = new Uint8Array(2 + oid.length);
  algoSeq[0] = 0x30; algoSeq[1] = oid.length;
  algoSeq.set(oid, 2);

  // Inner OCTET STRING wrapping the 32-byte seed
  const innerOctet = new Uint8Array(2 + rawKeyBytes.length);
  innerOctet[0] = 0x04; innerOctet[1] = rawKeyBytes.length;
  innerOctet.set(rawKeyBytes, 2);

  // Outer OCTET STRING
  const outerOctet = new Uint8Array(2 + innerOctet.length);
  outerOctet[0] = 0x04; outerOctet[1] = innerOctet.length;
  outerOctet.set(innerOctet, 2);

  // Version INTEGER 0
  const version = new Uint8Array([0x02, 0x01, 0x00]);

  // Build the full SEQUENCE
  const content = new Uint8Array(version.length + algoSeq.length + outerOctet.length);
  content.set(version, 0);
  content.set(algoSeq, version.length);
  content.set(outerOctet, version.length + algoSeq.length);

  const pkcs8 = new Uint8Array(2 + content.length);
  pkcs8[0] = 0x30; pkcs8[1] = content.length;
  pkcs8.set(content, 2);

  return pkcs8;
}

/**
 * Sign an 11-byte payload with Ed25519 using Web Crypto.
 * Returns 64-byte raw signature.
 */
async function signEd25519(payload, privateKeyHex) {
  const keyBytes = hexToBytes(privateKeyHex);
  if (keyBytes.length !== 32) {
    throw new Error(`Invalid private key length: ${keyBytes.length} (expected 32)`);
  }

  // Web Crypto requires PKCS#8 format for Ed25519 private keys
  const pkcs8 = rawToPkcs8(keyBytes);

  const key = await crypto.subtle.importKey(
    "pkcs8",
    pkcs8,
    { name: "Ed25519" },
    false,
    ["sign"]
  );

  const sig = await crypto.subtle.sign(
    { name: "Ed25519" },
    key,
    payload
  );

  return new Uint8Array(sig);
}

/**
 * Build a license key string: "QS" + base64url(11-byte-payload + 64-byte-signature)
 */
function buildLicenseKey(payload, signature) {
  const combined = new Uint8Array(payload.length + signature.length);
  combined.set(payload, 0);
  combined.set(signature, payload.length);
  return "QS" + bytesToBase64url(combined);
}

/**
 * Create signed license key for a given device and parameters.
 */
async function issueLicense(deviceCode, level, expDays, privateKeyHex) {
  // Validate device code: 16 hex chars → 8 bytes
  if (!/^[0-9a-fA-F]{16}$/.test(deviceCode)) {
    throw new Error("设备码格式无效，需要16位十六进制字符");
  }

  const devBytes = hexToBytes(deviceCode); // 8 bytes
  const expBytes = new Uint8Array(2);
  expBytes[0] = (expDays >> 8) & 0xFF;
  expBytes[1] = expDays & 0xFF;
  const levelByte = new Uint8Array(1);
  levelByte[0] = level;

  const payload = new Uint8Array(devBytes.length + expBytes.length + levelByte.length);
  payload.set(devBytes, 0);
  payload.set(expBytes, 8);
  payload.set(levelByte, 10);

  const signature = await signEd25519(payload, privateKeyHex);
  return buildLicenseKey(payload, signature);
}

// ── CORS headers ─────────────────────────────────────────────────────────────

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Admin-Secret",
    "Access-Control-Max-Age": "86400",
  };
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(),
    },
  });
}

// ── Handlers ─────────────────────────────────────────────────────────────────

/**
 * POST /redeem
 * Body: { voucher_code, device_code }
 *
 * Flow:
 *   1. Validate inputs
 *   2. Check voucher exists and is unused (SELECT)
 *   3. Sign license (Ed25519)
 *   4. Atomically: mark voucher used + record activation
 *   5. Return license key
 */
async function handleRedeem(request, env) {
  try {
    const body = await request.json();
    const { voucher_code, device_code } = body;

    // Validate required fields
    if (!voucher_code || !device_code) {
      return jsonResponse({ error: "缺少必要参数：voucher_code（凭证码）和 device_code（设备码）" }, 400);
    }

    // Validate device_code format
    if (!/^[0-9a-fA-F]{16,32}$/.test(device_code)) {
      return jsonResponse({ error: "设备码格式无效（至少16位十六进制字符）" }, 400);
    }

    // Step 1: Check voucher
    const voucher = await env.DB.prepare(
      "SELECT voucher_code, status, bound_device FROM vouchers WHERE voucher_code = ?"
    ).bind(voucher_code).first();

    if (!voucher) {
      return jsonResponse({ error: "凭证码无效：该凭证码不存在" }, 404);
    }

    if (voucher.status !== "unused") {
      return jsonResponse({
        error: "凭证码已被使用",
        used_at: voucher.bound_device ? `已绑定设备: ${voucher.bound_device}` : "已使用",
      }, 409);
    }

    // Step 2: Sign the license (pro level, 365 days from now)
    const expDays = expDaysFromNow(365);
    let licenseKey;
    try {
      licenseKey = await issueLicense(device_code, LEVEL_PRO, expDays, env.PRIVATE_KEY_HEX);
    } catch (e) {
      return jsonResponse({ error: `签发激活码失败: ${e.message}` }, 500);
    }

    // Step 3: Atomically update voucher + insert activation
    // Use D1 batch for atomicity
    const updateResult = await env.DB.prepare(
      `UPDATE vouchers
       SET status = 'used',
           used_at = datetime('now'),
           bound_device = ?,
           issued_license = ?
       WHERE voucher_code = ? AND status = 'unused'`
    ).bind(device_code, licenseKey, voucher_code).run();

    // Check for race condition (another request claimed this voucher)
    if (!updateResult.meta?.rows_written && updateResult.changes === 0) {
      // Double-check: maybe it was just claimed
      return jsonResponse({ error: "凭证码兑换失败：可能已被并发使用，请重试" }, 409);
    }

    // Step 4: Record activation
    await env.DB.prepare(
      `INSERT INTO activations (device_code, license_key, level, created_at, voucher_code)
       VALUES (?, ?, 'pro', datetime('now'), ?)`
    ).bind(device_code, licenseKey, voucher_code).run();

    // Success!
    return jsonResponse({
      success: true,
      license_key: licenseKey,
      level: "pro",
      expires: expDaysToString(expDays),
      device_code: device_code,
      message: "激活码签发成功！请复制激活码，回到 QuantSage 客户端粘贴激活。",
    });

  } catch (e) {
    if (e instanceof SyntaxError) {
      return jsonResponse({ error: "请求格式无效，需要 JSON body" }, 400);
    }
    return jsonResponse({ error: `服务器内部错误: ${e.message}` }, 500);
  }
}

/**
 * POST /admin/issue-permanent
 * Headers: X-Admin-Secret: <admin secret>
 * Body: { device_code, note? }
 *
 * Issues a permanent (non-expiring) license bound to the given device.
 * Special device_code values:
 *   "MASTER" → universal permanent key (skip device match in client)
 */
async function handleAdminIssue(request, env) {
  try {
    // Auth check
    const adminSecret = request.headers.get("X-Admin-Secret");
    if (!adminSecret || adminSecret !== env.ADMIN_SECRET) {
      return jsonResponse({ error: "未授权：管理员密钥无效" }, 401);
    }

    const body = await request.json();
    const { device_code, note } = body;

    if (!device_code) {
      return jsonResponse({ error: "缺少必要参数：device_code（设备码）" }, 400);
    }

    let finalDeviceCode;
    const isMaster = device_code.toUpperCase() === "MASTER";

    if (isMaster) {
      // Universal key: use all-F device code, client skips device check
      finalDeviceCode = "FFFFFFFFFFFFFFFF";
    } else {
      // Validate device_code format
      if (!/^[0-9a-fA-F]{16,32}$/.test(device_code)) {
        return jsonResponse({ error: "设备码格式无效（至少16位十六进制字符）" }, 400);
      }
      finalDeviceCode = device_code.slice(0, 16).toUpperCase();
    }

    // Sign permanent license
    let licenseKey;
    try {
      licenseKey = await issueLicense(finalDeviceCode, LEVEL_PRO, PERMANENT, env.PRIVATE_KEY_HEX);
    } catch (e) {
      return jsonResponse({ error: `签发永久码失败: ${e.message}` }, 500);
    }

    // Record activation
    const levelStr = isMaster ? "permanent_master" : "permanent";
    await env.DB.prepare(
      `INSERT INTO activations (device_code, license_key, level, created_at, voucher_code)
       VALUES (?, ?, ?, datetime('now'), ?)`
    ).bind(finalDeviceCode, licenseKey, levelStr, note || "admin_issued").run();

    return jsonResponse({
      success: true,
      license_key: licenseKey,
      level: levelStr,
      expires: "9999-12-31",
      device_code: finalDeviceCode,
      is_master: isMaster,
      note: note || "",
      message: isMaster
        ? "万能永久码签发成功！⚠️ 此码不绑设备，请安全保管。"
        : "永久激活码签发成功！",
    });

  } catch (e) {
    if (e instanceof SyntaxError) {
      return jsonResponse({ error: "请求格式无效，需要 JSON body" }, 400);
    }
    return jsonResponse({ error: `服务器内部错误: ${e.message}` }, 500);
  }
}

// ── Activation Web Page (GET /) ──────────────────────────────────────────────

const ACTIVATION_HTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QuantSage 激活</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', 'Microsoft YaHei', system-ui, -apple-system, sans-serif;
    background: radial-gradient(ellipse at 50% 0%, #1a1040 0%, #0d1117 50%, #0a0e1a 100%);
    color: #e8eaed;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .container { max-width: 480px; width: 100%; }
  .card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 2rem;
    margin-bottom: 1rem;
  }
  h1 { text-align: center; font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem; color: #e8eaed; }
  .subtitle { text-align: center; color: #9ca3af; font-size: 0.9rem; margin-bottom: 1.5rem; }
  label { display: block; color: #9ca3af; font-size: 0.85rem; margin-bottom: 0.35rem; margin-top: 1rem; }
  input[type="text"] {
    width: 100%; padding: 12px 14px;
    background: #0a0e1a; border: 1px solid #1f2937; border-radius: 8px;
    color: #e8eaed; font-size: 1rem; font-family: 'Consolas', 'Courier New', monospace;
    outline: none; transition: border-color 0.2s;
  }
  input[type="text"]:focus { border-color: #22d3ee; }
  button {
    width: 100%; padding: 12px; margin-top: 1.25rem;
    background: linear-gradient(135deg, #0891b2, #06b6d4);
    border: none; border-radius: 8px;
    color: white; font-size: 1rem; font-weight: 600; cursor: pointer;
    transition: all 0.2s;
  }
  button:hover { background: linear-gradient(135deg, #06b6d4, #22d3ee); transform: translateY(-1px); }
  button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .result {
    margin-top: 1rem; padding: 1rem;
    background: #0a0e1a; border-radius: 8px; border: 1px solid #1f2937;
  }
  .result.success { border-color: #34d399; }
  .result.error { border-color: #f87171; }
  .result .header { font-weight: 600; margin-bottom: 0.5rem; }
  .result.success .header { color: #34d399; }
  .result.error .header { color: #f87171; }
  .license-key {
    background: #0a0e1a; border: 2px solid #22d3ee; border-radius: 8px;
    padding: 14px; margin: 10px 0; text-align: center;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 0.85rem; color: #22d3ee; word-break: break-all;
    user-select: all;
  }
  .copy-btn {
    background: #1f2937; color: #9ca3af; font-size: 0.85rem; padding: 8px; margin-top: 0.5rem;
  }
  .copy-btn:hover { background: #374151; color: #e8eaed; }
  .disclaimer {
    text-align: center; color: #6b7280; font-size: 0.75rem; margin-top: 1rem;
    padding-top: 1rem; border-top: 1px solid #1f2937;
  }
  .steps { background: #0a0e1a; border: 1px solid #1f2937; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
  .steps h3 { color: #22d3ee; font-size: 0.9rem; margin-bottom: 0.5rem; }
  .steps ol { color: #9ca3af; font-size: 0.85rem; padding-left: 1.25rem; }
  .steps ol li { margin-bottom: 0.35rem; }
  .spinner {
    display: inline-block; width: 16px; height: 16px; border: 2px solid transparent;
    border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite;
    margin-right: 6px; vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <div class="card">
    <h1>🔑 QuantSage 激活</h1>
    <p class="subtitle">输入购买凭证码和设备码，获取激活码</p>

    <div class="steps">
      <h3>📋 激活步骤</h3>
      <ol>
        <li>在 QuantSage 客户端点击"激活"，复制显示的<strong>设备码</strong></li>
        <li>前往发卡平台购买，获取<strong>购买凭证码</strong></li>
        <li>在下方输入凭证码和设备码，点击"获取激活码"</li>
        <li>将激活码复制回客户端，完成激活</li>
      </ol>
    </div>

    <label for="voucher">🎫 购买凭证码</label>
    <input type="text" id="voucher" placeholder="粘贴从发卡平台获取的凭证码" autocomplete="off">

    <label for="device">📟 设备码</label>
    <input type="text" id="device" placeholder="从 QuantSage 客户端复制设备码" autocomplete="off">

    <button id="activateBtn" onclick="redeem()">🔓 获取激活码</button>

    <div id="result" style="display:none;"></div>
    <div id="licenseDisplay" style="display:none;">
      <div class="license-key" id="licenseKey"></div>
      <button class="copy-btn" onclick="copyLicense()">📋 复制激活码</button>
    </div>

    <p class="disclaimer">
      ⚠️ 本软件仅供参考研究，不构成任何投资建议，盈亏自负。<br>
      激活码绑定设备，一码一机。
    </p>
  </div>
</div>

<script>
const API = "/redeem";

async function redeem() {
  const voucher = document.getElementById("voucher").value.trim();
  const device = document.getElementById("device").value.trim();
  const btn = document.getElementById("activateBtn");
  const resultDiv = document.getElementById("result");
  const licenseDisplay = document.getElementById("licenseDisplay");

  // Hide previous results
  resultDiv.style.display = "none";
  licenseDisplay.style.display = "none";

  // Validate
  if (!voucher) {
    showError("请输入购买凭证码");
    return;
  }
  if (!device) {
    showError("请输入设备码（从 QuantSage 客户端复制）");
    return;
  }
  if (!/^[0-9a-fA-F]{16,32}$/.test(device)) {
    showError("设备码格式无效（至少16位十六进制）");
    return;
  }

  // Loading state
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>正在签发激活码...';

  try {
    const resp = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voucher_code: voucher, device_code: device }),
    });
    const data = await resp.json();

    if (resp.ok && data.success) {
      document.getElementById("licenseKey").textContent = data.license_key;
      licenseDisplay.style.display = "block";
      const expMsg = data.expires === "9999-12-31" ? "永久有效" : "到期: " + data.expires;
      showSuccess("✅ 激活码获取成功！" + (data.level ? " 等级: " + data.level + " | " + expMsg : ""));
    } else {
      showError(data.error || "激活码获取失败，请重试");
    }
  } catch (e) {
    showError("网络错误，无法连接到激活服务器。请检查网络后重试。");
  } finally {
    btn.disabled = false;
    btn.textContent = "🔓 获取激活码";
  }
}

function showError(msg) {
  const resultDiv = document.getElementById("result");
  resultDiv.style.display = "block";
  resultDiv.className = "result error";
  resultDiv.innerHTML = '<div class="header">❌ ' + msg + '</div>';
}

function showSuccess(msg) {
  const resultDiv = document.getElementById("result");
  resultDiv.style.display = "block";
  resultDiv.className = "result success";
  resultDiv.innerHTML = '<div class="header">' + msg + '</div>';
}

function copyLicense() {
  const key = document.getElementById("licenseKey").textContent;
  if (key && navigator.clipboard) {
    navigator.clipboard.writeText(key).then(() => {
      const btn = document.querySelector(".copy-btn");
      btn.textContent = "✅ 已复制！";
      setTimeout(() => { btn.textContent = "📋 复制激活码"; }, 2000);
    });
  } else if (key) {
    // Fallback for older browsers
    const ta = document.createElement("textarea");
    ta.value = key;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    const btn = document.querySelector(".copy-btn");
    btn.textContent = "✅ 已复制！";
    setTimeout(() => { btn.textContent = "📋 复制激活码"; }, 2000);
  }
}
</script>
</body>
</html>`;

// ── Main Fetch Handler ───────────────────────────────────────────────────────

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    // GET / → Activation page
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(ACTIVATION_HTML, {
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "public, max-age=300",
          ...corsHeaders(),
        },
      });
    }

    // POST /redeem
    if (url.pathname === "/redeem" && request.method === "POST") {
      return handleRedeem(request, env);
    }

    // POST /admin/issue-permanent
    if (url.pathname === "/admin/issue-permanent" && request.method === "POST") {
      return handleAdminIssue(request, env);
    }

    // 404
    return jsonResponse({ error: "Not Found" }, 404);
  },
};
