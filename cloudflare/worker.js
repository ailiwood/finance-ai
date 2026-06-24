/**
 * QuantSage Cloud Activation Worker
 *
 * Endpoints:
 *   GET  /                        — Activation web page (QR + order + redeem)
 *   GET  /admin                   — Admin backend (login shell, sessionStorage)
 *   GET  /admin/orders            — List pending + recent completed orders (JSON)
 *   POST /order/create            — Submit device code → pending order
 *   GET  /order/status            — Query order status by device_code
 *   POST /order/redeem-voucher    — (keep) Redeem voucher code → signed license
 *   POST /admin/issue             — Admin: issue license for a single device
 *   POST /admin/issue-batch       — Admin: issue licenses for multiple devices
 *   POST /admin/issue-permanent   — Admin: issue permanent license (keep)
 *
 * Ed25519 signing via Web Crypto (native in Cloudflare Workers).
 * Private key stored in env.PRIVATE_KEY_HEX (Secret, never in code/git).
 */

// ── Constants ────────────────────────────────────────────────────────────────
const EPOCH = new Date("2024-01-01T00:00:00Z");
const PERMANENT = 0xFFFF;
const LEVEL_PRO = 0x01;
const LEVEL_FREE = 0x00;
const DISCLAIMER = "本软件仅供参考研究，不构成任何投资建议，盈亏自负";

// ── Helpers ──────────────────────────────────────────────────────────────────

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

function bytesToBase64url(bytes) {
  let b64 = btoa(String.fromCharCode(...bytes));
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function daysSinceEpoch(dateStr) {
  const target = new Date(dateStr + "T00:00:00Z");
  return Math.floor((target - EPOCH) / (1000 * 60 * 60 * 24));
}

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

function normalizeDeviceCode(raw) {
  // Accept 16+ hex chars, uppercase, take first 16 for binding
  const cleaned = raw.trim().toUpperCase().replace(/[^0-9A-F]/g, "");
  if (cleaned.length < 16) return null;
  return { original: raw.trim(), bound: cleaned.slice(0, 16) };
}

// ── Ed25519 PKCS#8 wrapping ──────────────────────────────────────────────────

function rawToPkcs8(rawKeyBytes) {
  const oid = new Uint8Array([0x06, 0x03, 0x2b, 0x65, 0x70]);
  const algoSeq = new Uint8Array(2 + oid.length);
  algoSeq[0] = 0x30; algoSeq[1] = oid.length;
  algoSeq.set(oid, 2);

  const innerOctet = new Uint8Array(2 + rawKeyBytes.length);
  innerOctet[0] = 0x04; innerOctet[1] = rawKeyBytes.length;
  innerOctet.set(rawKeyBytes, 2);

  const outerOctet = new Uint8Array(2 + innerOctet.length);
  outerOctet[0] = 0x04; outerOctet[1] = innerOctet.length;
  outerOctet.set(innerOctet, 2);

  const version = new Uint8Array([0x02, 0x01, 0x00]);

  const content = new Uint8Array(version.length + algoSeq.length + outerOctet.length);
  content.set(version, 0);
  content.set(algoSeq, version.length);
  content.set(outerOctet, version.length + algoSeq.length);

  const pkcs8 = new Uint8Array(2 + content.length);
  pkcs8[0] = 0x30; pkcs8[1] = content.length;
  pkcs8.set(content, 2);
  return pkcs8;
}

async function signEd25519(payload, privateKeyHex) {
  const keyBytes = hexToBytes(privateKeyHex);
  if (keyBytes.length !== 32) {
    throw new Error(`Invalid private key length: ${keyBytes.length} (expected 32)`);
  }
  const pkcs8 = rawToPkcs8(keyBytes);
  const key = await crypto.subtle.importKey("pkcs8", pkcs8, { name: "Ed25519" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "Ed25519" }, key, payload);
  return new Uint8Array(sig);
}

function buildLicenseKey(payload, signature) {
  const combined = new Uint8Array(payload.length + signature.length);
  combined.set(payload, 0);
  combined.set(signature, payload.length);
  return "QS" + bytesToBase64url(combined);
}

async function issueLicense(deviceCode, level, expDays, privateKeyHex) {
  if (!/^[0-9A-F]{16}$/.test(deviceCode)) {
    throw new Error("设备码格式无效，需要16位十六进制字符");
  }
  const devBytes = hexToBytes(deviceCode);
  const expBytes = new Uint8Array([(expDays >> 8) & 0xFF, expDays & 0xFF]);
  const levelByte = new Uint8Array([level]);
  const payload = new Uint8Array(11);
  payload.set(devBytes, 0);
  payload.set(expBytes, 8);
  payload.set(levelByte, 10);
  const signature = await signEd25519(payload, privateKeyHex);
  return buildLicenseKey(payload, signature);
}

// ── CORS ─────────────────────────────────────────────────────────────────────

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
    headers: { "Content-Type": "application/json; charset=utf-8", ...corsHeaders() },
  });
}

// ── Auth helper ──────────────────────────────────────────────────────────────

function checkAdmin(request, env) {
  const secret = request.headers.get("X-Admin-Secret");
  if (!secret || secret !== env.ADMIN_SECRET) {
    return false;
  }
  return true;
}

function requireAdmin(request, env) {
  if (!checkAdmin(request, env)) {
    return jsonResponse({ error: "未授权：管理员密钥无效" }, 401);
  }
  return null; // null means "passed, continue"
}

// ── License term ─────────────────────────────────────────────────────────────

function getLicenseTermDays(env) {
  // Default 365 days; configurable via env.LICENSE_TERM_DAYS
  const val = env.LICENSE_TERM_DAYS;
  if (val) {
    const n = parseInt(val, 10);
    if (!isNaN(n) && n > 0 && n <= 3650) return n; // max 10 years
  }
  return 365;
}

// ══════════════════════════════════════════════════════════════════════════════
// HANDLERS
// ══════════════════════════════════════════════════════════════════════════════

// ── POST /order/create ───────────────────────────────────────────────────────

async function handleOrderCreate(request, env) {
  try {
    const body = await request.json();
    const { device_code } = body;
    if (!device_code) {
      return jsonResponse({ error: "缺少必要参数：device_code（设备码）" }, 400);
    }
    const norm = normalizeDeviceCode(device_code);
    if (!norm) {
      return jsonResponse({ error: "设备码格式无效（至少16位十六进制字符）" }, 400);
    }

    // Check if a completed order already exists for this bound device
    const existing = await env.DB.prepare(
      "SELECT device_code, status, license_key, level, completed_at FROM orders WHERE bound_device = ? AND status = 'completed' ORDER BY completed_at DESC LIMIT 1"
    ).bind(norm.bound).first();

    if (existing) {
      // Return the existing license key
      const expDays = PERMANENT; // We don't store expDays separately; decode from key
      // For simplicity return what we have
      return jsonResponse({
        success: true,
        status: "completed",
        license_key: existing.license_key,
        level: existing.level || "pro",
        message: "激活码已就绪！请复制下方激活码，回到客户端完成激活。",
      });
    }

    // Check if a pending order already exists
    const pending = await env.DB.prepare(
      "SELECT device_code, created_at FROM orders WHERE bound_device = ? AND status = 'pending'"
    ).bind(norm.bound).first();

    if (pending) {
      return jsonResponse({
        success: true,
        status: "pending",
        message: "订单已存在，正在等待开发者确认收款。请稍后查询激活码。",
      });
    }

    // Create new pending order
    await env.DB.prepare(
      "INSERT INTO orders (device_code, bound_device, status, created_at) VALUES (?, ?, 'pending', datetime('now'))"
    ).bind(norm.original, norm.bound).run();

    return jsonResponse({
      success: true,
      status: "pending",
      message: "订单已创建！请使用支付宝扫描收款码付款，并在付款备注中填写您的设备码。付款后请等待激活码签发（通常5分钟内），然后在下方查询。",
    });

  } catch (e) {
    if (e instanceof SyntaxError) {
      return jsonResponse({ error: "请求格式无效，需要 JSON body" }, 400);
    }
    return jsonResponse({ error: `服务器内部错误: ${e.message}` }, 500);
  }
}

// ── GET /order/status ────────────────────────────────────────────────────────

async function handleOrderStatus(request, env) {
  const url = new URL(request.url);
  const device_code = url.searchParams.get("device_code");
  if (!device_code) {
    return jsonResponse({ error: "缺少参数：device_code" }, 400);
  }
  const norm = normalizeDeviceCode(device_code);
  if (!norm) {
    return jsonResponse({ error: "设备码格式无效" }, 400);
  }

  const order = await env.DB.prepare(
    "SELECT device_code, bound_device, status, license_key, level, created_at, completed_at, notes FROM orders WHERE bound_device = ? ORDER BY created_at DESC LIMIT 1"
  ).bind(norm.bound).first();

  if (!order) {
    return jsonResponse({ success: false, status: "not_found", error: "未找到该设备码的订单。请先在激活页面点击「提交订单」。" }, 404);
  }

  return jsonResponse({
    success: true,
    status: order.status,
    device_code: order.device_code,
    license_key: order.license_key || undefined,
    level: order.level || undefined,
    created_at: order.created_at,
    completed_at: order.completed_at || undefined,
    notes: order.notes || undefined,
  });
}

// ── POST /redeem (kept for backward compat) ──────────────────────────────────

async function handleRedeem(request, env) {
  try {
    const body = await request.json();
    const { voucher_code, device_code } = body;

    if (!voucher_code || !device_code) {
      return jsonResponse({ error: "缺少必要参数：voucher_code（凭证码）和 device_code（设备码）" }, 400);
    }
    if (!/^[0-9a-fA-F]{16,32}$/.test(device_code)) {
      return jsonResponse({ error: "设备码格式无效（至少16位十六进制字符）" }, 400);
    }

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

    const termDays = getLicenseTermDays(env);
    const expDays = expDaysFromNow(termDays);
    let licenseKey;
    try {
      licenseKey = await issueLicense(device_code.slice(0, 16).toUpperCase(), LEVEL_PRO, expDays, env.PRIVATE_KEY_HEX);
    } catch (e) {
      return jsonResponse({ error: `签发激活码失败: ${e.message}` }, 500);
    }

    const updateResult = await env.DB.prepare(
      `UPDATE vouchers SET status = 'used', used_at = datetime('now'), bound_device = ?, issued_license = ? WHERE voucher_code = ? AND status = 'unused'`
    ).bind(device_code, licenseKey, voucher_code).run();

    if (!updateResult.meta?.rows_written && updateResult.changes === 0) {
      return jsonResponse({ error: "凭证码兑换失败：可能已被并发使用，请重试" }, 409);
    }

    await env.DB.prepare(
      "INSERT INTO activations (device_code, license_key, level, created_at, voucher_code) VALUES (?, ?, 'pro', datetime('now'), ?)"
    ).bind(device_code, licenseKey, voucher_code).run();

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

// ── GET /admin/orders ────────────────────────────────────────────────────────

async function handleAdminOrders(request, env) {
  const authErr = requireAdmin(request, env);
  if (authErr) return authErr;

  const pending = await env.DB.prepare(
    "SELECT id, device_code, bound_device, status, created_at, notes FROM orders WHERE status = 'pending' ORDER BY created_at DESC LIMIT 100"
  ).all();

  const completed = await env.DB.prepare(
    "SELECT id, device_code, bound_device, status, license_key, level, created_at, completed_at, notes FROM orders WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 50"
  ).all();

  return jsonResponse({
    pending: pending.results || [],
    completed: completed.results || [],
  });
}

// ── POST /admin/issue ────────────────────────────────────────────────────────

async function handleAdminIssueSingle(request, env) {
  const authErr = requireAdmin(request, env);
  if (authErr) return authErr;

  try {
    const body = await request.json();
    const { device_code, note } = body;
    if (!device_code) {
      return jsonResponse({ error: "缺少必要参数：device_code" }, 400);
    }
    const norm = normalizeDeviceCode(device_code);
    if (!norm) {
      return jsonResponse({ error: "设备码格式无效" }, 400);
    }

    // Check if already completed for this bound device
    const existing = await env.DB.prepare(
      "SELECT license_key FROM orders WHERE bound_device = ? AND status = 'completed'"
    ).bind(norm.bound).first();
    if (existing) {
      return jsonResponse({
        success: true,
        license_key: existing.license_key,
        message: "该设备已有已签发的激活码（幂等返回）",
        already_issued: true,
      });
    }

    const termDays = getLicenseTermDays(env);
    const expDays = expDaysFromNow(termDays);
    const licenseKey = await issueLicense(norm.bound, LEVEL_PRO, expDays, env.PRIVATE_KEY_HEX);

    // Update pending order → completed, or create completed order if no pending
    const pending = await env.DB.prepare(
      "SELECT id FROM orders WHERE bound_device = ? AND status = 'pending'"
    ).bind(norm.bound).first();

    if (pending) {
      await env.DB.prepare(
        "UPDATE orders SET status = 'completed', license_key = ?, level = 'pro', completed_at = datetime('now'), notes = COALESCE(NULLIF(notes, ''), ?) WHERE id = ?"
      ).bind(licenseKey, note || null, pending.id).run();
    } else {
      await env.DB.prepare(
        "INSERT INTO orders (device_code, bound_device, status, license_key, level, notes, completed_at) VALUES (?, ?, 'completed', ?, 'pro', ?, datetime('now'))"
      ).bind(norm.original, norm.bound, licenseKey, note || null).run();
    }

    // Record activation
    await env.DB.prepare(
      "INSERT INTO activations (device_code, license_key, level, created_at, voucher_code) VALUES (?, ?, 'pro', datetime('now'), ?)"
    ).bind(norm.bound, licenseKey, note || "admin_issued").run();

    return jsonResponse({
      success: true,
      license_key: licenseKey,
      level: "pro",
      expires: expDaysToString(expDays),
      device_code: norm.bound,
      message: "激活码签发成功！",
    });

  } catch (e) {
    if (e instanceof SyntaxError) {
      return jsonResponse({ error: "请求格式无效，需要 JSON body" }, 400);
    }
    return jsonResponse({ error: `签发失败: ${e.message}` }, 500);
  }
}

// ── POST /admin/issue-batch ──────────────────────────────────────────────────

async function handleAdminIssueBatch(request, env) {
  const authErr = requireAdmin(request, env);
  if (authErr) return authErr;

  try {
    const body = await request.json();
    const { device_codes } = body;
    if (!device_codes || !Array.isArray(device_codes) || device_codes.length === 0) {
      return jsonResponse({ error: "缺少 device_codes 数组" }, 400);
    }
    if (device_codes.length > 50) {
      return jsonResponse({ error: "单次最多签发50个" }, 400);
    }

    const termDays = getLicenseTermDays(env);
    const results = [];
    for (const dc of device_codes) {
      try {
        const norm = normalizeDeviceCode(dc);
        if (!norm) { results.push({ device_code: dc, success: false, error: "设备码格式无效" }); continue; }

        const existing = await env.DB.prepare(
          "SELECT license_key FROM orders WHERE bound_device = ? AND status = 'completed'"
        ).bind(norm.bound).first();
        if (existing) {
          results.push({ device_code: norm.bound, success: true, license_key: existing.license_key, already_issued: true });
          continue;
        }

        const expDays = expDaysFromNow(termDays);
        const licenseKey = await issueLicense(norm.bound, LEVEL_PRO, expDays, env.PRIVATE_KEY_HEX);

        const pending = await env.DB.prepare(
          "SELECT id FROM orders WHERE bound_device = ? AND status = 'pending'"
        ).bind(norm.bound).first();

        if (pending) {
          await env.DB.prepare(
            "UPDATE orders SET status = 'completed', license_key = ?, level = 'pro', completed_at = datetime('now') WHERE id = ?"
          ).bind(licenseKey, pending.id).run();
        } else {
          await env.DB.prepare(
            "INSERT INTO orders (device_code, bound_device, status, license_key, level, completed_at) VALUES (?, ?, 'completed', ?, 'pro', datetime('now'))"
          ).bind(norm.original, norm.bound, licenseKey).run();
        }

        await env.DB.prepare(
          "INSERT INTO activations (device_code, license_key, level, created_at, voucher_code) VALUES (?, ?, 'pro', datetime('now'), 'batch_issued')"
        ).bind(norm.bound, licenseKey).run();

        results.push({ device_code: norm.bound, success: true, license_key: licenseKey, level: "pro", expires: expDaysToString(expDays) });
      } catch (e) {
        results.push({ device_code: dc, success: false, error: e.message });
      }
    }

    return jsonResponse({ success: true, results });

  } catch (e) {
    if (e instanceof SyntaxError) {
      return jsonResponse({ error: "请求格式无效，需要 JSON body" }, 400);
    }
    return jsonResponse({ error: `批量签发失败: ${e.message}` }, 500);
  }
}

// ── POST /admin/issue-permanent (kept from M7) ───────────────────────────────

async function handleAdminIssuePermanent(request, env) {
  const authErr = requireAdmin(request, env);
  if (authErr) return authErr;

  try {
    const body = await request.json();
    const { device_code, note } = body;
    if (!device_code) {
      return jsonResponse({ error: "缺少必要参数：device_code（设备码）" }, 400);
    }

    let finalDeviceCode;
    const isMaster = device_code.toUpperCase() === "MASTER";
    if (isMaster) {
      finalDeviceCode = "FFFFFFFFFFFFFFFF";
    } else {
      const norm = normalizeDeviceCode(device_code);
      if (!norm) {
        return jsonResponse({ error: "设备码格式无效（至少16位十六进制字符）" }, 400);
      }
      finalDeviceCode = norm.bound;
    }

    let licenseKey;
    try {
      licenseKey = await issueLicense(finalDeviceCode, LEVEL_PRO, PERMANENT, env.PRIVATE_KEY_HEX);
    } catch (e) {
      return jsonResponse({ error: `签发永久码失败: ${e.message}` }, 500);
    }

    const levelStr = isMaster ? "permanent_master" : "permanent";
    await env.DB.prepare(
      "INSERT INTO activations (device_code, license_key, level, created_at, voucher_code) VALUES (?, ?, ?, datetime('now'), ?)"
    ).bind(finalDeviceCode, licenseKey, levelStr, note || "admin_permanent").run();

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

// ══════════════════════════════════════════════════════════════════════════════
// HTML PAGES
// ══════════════════════════════════════════════════════════════════════════════

// Pay QR code embedded as data URI
const PAY_QR_DATA_URI = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAaQBDgDASIAAhEBAxEB/8QAHAABAAIDAQEBAAAAAAAAAAAAAAYHAQUIBAMC/8QAZRAAAQMCAgMICgoLDAcJAQADAAECAwQFBhEHEiETFzE2QVWTsxQVFlFUcXWk0dIiN1Zhg5GSlLLTMjVSc3SBoaOxweIIGCNCRlNmcoTD4eMmMzRERWWiJCUnQ2JkgsLwY6XxxP/EABwBAQACAwEBAQAAAAAAAAAAAAAFBgEDBAIHCP/EAEERAQABAwEDCgILAAEDAwQDAAABAgMEEQVScRITFBUhMTNRkaFBgQYWFyIyNFNhsdHwwSNCciQ1kiVDVGJjsvH/2gAMAwEAAhEDEQA/ANaAD6Gp4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGYAADlyAADPZmABkAYBlUy4TAAAAAAABkwAAAAAAAZMAAAAAAAAAAAAAAAAAAAAAAAAAAM8kzMgYBkAYBkAY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b3tJ0HI3fdBATveyXnfzb9sb2S87+bftjrTE3vaToORu+6CAne9kvO/m37Y3sl5382/bHWmJve0nQcjd90EBO97Jed/Nv2xvZLzv5t+2OtMTe9pOg5G77oICd72S87+bftjeyXnfzb9sdaYm97SdByN33QQE73sl5382/bG9kvO/m37Y60xN72k6DkbvuggJ3vZLzv5t+2N7Jed/Nv2x1pib3tJ0HI3fdBATveyXnfzb9sb2S87+bftjrTE3vaToORu+6CAne9kvO/m37Y3sl5382/bHWmJve0nQcjd90EBO97Jed/Nv2xvZLzv5t+2OtMTe9pOg5G77oICd72S87+bftjeyXnfzb9sdaYm97SdByN33QQE73sl5382/bG9kvO/m37Y60xN72k6DkbvuggJ3vZLzv5t+2N7Jed/Nv2x1pib3tJ0HI3fdBATveyXnfzb9sb2S87+bftjrTE3vaToORu+6CAne9kvO/m37Y3sl5382/bHWmJve0nQcjd90EBO97Jed/Nv2xvZLzv5t+2OtMTe9pOg5G77oICd72S87+bftjeyXnfzb9sdaYm97SdByN33QQE73sl5382/bG9kvO/m37Y60xN72k6DkbvuggJ3vZLzv5t+2N7Jed/Nv2x1pib3tJ0HI3fdBATveyXnfzb9sb2S87+bftjrTE3vaToORu+6CAne9kvO/m37Y3sl5382/bHWmJve0nQcjd90EBO97Jed/Nv2xvZLzv5t+2OtMTe9pOg5G77oICd72S87+bftjeyXnfzb9sdaYm97SdByN33QQE73sl5382/bG9kvO/m37Y60xN72k6DkbvuggJ3vZLzv5t+2N7Jed/Nv2x1pib3tJ0HI3fdBATveyXnfzb9sb2S87+bftjrTE3vaToORu+6CAne9kvO/m37Y3sl5382/bHWmJve0nQcjd90EBO97Jed/Nv2xvZLzv5t+2OtMTe9pOg5G77oICd72S87+bftjeyXnfzb9sdaYm97SdByN33QQE73sl5382/bG9kvO/m37Y60xN72k6DkbvuggJ3vZLzv5t+2N7Jed/Nv2x1pib3tJ0HI3fdBATveyXnfzb9sb2S87+bftjrTE3vaToORu+6CAne9kvO/m37Y3sl5382/bHWmJve0nQcjd90EBO97Jed/Nv2xvZLzv5t+2OtMTe9pOg5G77oICd72S8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";

const COMMON_CSS = `
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', 'Microsoft YaHei', system-ui, -apple-system, sans-serif;
  background: radial-gradient(ellipse at 50% 0%, #1a1040 0%, #0d1117 50%, #0a0e1a 100%);
  color: #e8eaed; min-height: 100vh; padding: 20px;
}
.container { max-width: 520px; margin: 0 auto; }
.card { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 1.5rem 2rem; margin-bottom: 1rem; }
h1 { text-align: center; font-size: 1.5rem; font-weight: 700; margin-bottom: 0.3rem; color: #e8eaed; }
h2 { font-size: 1.15rem; font-weight: 600; color: #e8eaed; margin: 1rem 0 0.5rem; }
.subtitle { text-align: center; color: #9ca3af; font-size: 0.85rem; margin-bottom: 1rem; }
label { display: block; color: #9ca3af; font-size: 0.85rem; margin-bottom: 0.3rem; margin-top: 0.75rem; }
input[type="text"], input[type="password"] {
  width: 100%; padding: 11px 13px; background: #0a0e1a; border: 1px solid #1f2937; border-radius: 8px;
  color: #e8eaed; font-size: 0.95rem; font-family: 'Consolas', 'Courier New', monospace;
  outline: none; transition: border-color 0.2s;
}
input[type="text"]:focus, input[type="password"]:focus { border-color: #22d3ee; }
input[type="checkbox"] { margin-right: 6px; transform: scale(1.15); }
button, .btn {
  width: 100%; padding: 11px; margin-top: 0.75rem;
  background: linear-gradient(135deg, #0891b2, #06b6d4); border: none; border-radius: 8px;
  color: white; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
  text-align: center; text-decoration: none; display: inline-block;
}
button:hover, .btn:hover { background: linear-gradient(135deg, #06b6d4, #22d3ee); transform: translateY(-1px); }
button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.btn-sm { width: auto; padding: 6px 14px; font-size: 0.8rem; margin-top: 0; }
.btn-red { background: linear-gradient(135deg, #b91c1c, #dc2626); }
.result { margin-top: 0.75rem; padding: 0.75rem 1rem; background: #0a0e1a; border-radius: 8px; border: 1px solid #1f2937; display: none; }
.result.success { border-color: #34d399; display: block; }
.result.error { border-color: #f87171; display: block; }
.result.info { border-color: #60a5fa; display: block; }
.result .header { font-weight: 600; margin-bottom: 0.25rem; }
.result.success .header { color: #34d399; }
.result.error .header { color: #f87171; }
.result.info .header { color: #60a5fa; }
.license-key {
  background: #0a0e1a; border: 2px solid #22d3ee; border-radius: 8px; padding: 12px; margin: 8px 0;
  text-align: center; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.8rem;
  color: #22d3ee; word-break: break-all; user-select: all;
}
.qr-box { text-align: center; margin: 1rem 0; }
.qr-box img { max-width: 260px; border-radius: 8px; border: 2px solid #1f2937; }
.steps { background: #0a0e1a; border: 1px solid #1f2937; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.75rem; }
.steps h3 { color: #22d3ee; font-size: 0.9rem; margin-bottom: 0.4rem; }
.steps ol, .steps ul { color: #9ca3af; font-size: 0.82rem; padding-left: 1.25rem; }
.steps ol li, .steps ul li { margin-bottom: 0.25rem; }
.disclaimer { text-align: center; color: #6b7280; font-size: 0.72rem; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #1f2937; }
.divider { border: none; border-top: 1px solid #1f2937; margin: 1rem 0; }
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid transparent; border-top-color: white; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 6px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
.tabs { display: flex; gap: 0; margin-bottom: 1rem; border-bottom: 1px solid #1f2937; }
.tab { flex: 1; text-align: center; padding: 10px; cursor: pointer; color: #9ca3af; font-size: 0.9rem; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tab.active { color: #22d3ee; border-bottom-color: #22d3ee; }
.tab-content { display: none; }
.tab-content.active { display: block; }
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
th { text-align: left; color: #9ca3af; font-weight: 600; padding: 6px 8px; border-bottom: 1px solid #1f2937; }
td { padding: 6px 8px; border-bottom: 1px solid #0a0e1a; color: #d1d5db; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.78rem; word-break: break-all; }
tr:hover td { background: #1a2236; }
`;

// ── GET / Activation Page ────────────────────────────────────────────────────

const ACTIVATION_HTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QuantSage 激活</title>
<style>${COMMON_CSS}</style>
</head>
<body>
<div class="container">

  <!-- ═══ Tab Navigation ═══ -->
  <div class="tabs">
    <div class="tab active" onclick="switchTab('pay')">💳 付款激活</div>
    <div class="tab" onclick="switchTab('query')">🔍 查询激活码</div>
    <div class="tab" onclick="switchTab('voucher')">🎫 凭证码兑换</div>
  </div>

  <!-- ═══ Tab 1: Pay & Submit Order ═══ -->
  <div id="tab-pay" class="tab-content active">
    <div class="card">
      <h1>🔑 QuantSage 激活</h1>
      <p class="subtitle">支付宝扫码付款 → 提交设备码 → 等待激活码</p>

      <div class="steps">
        <h3>📋 激活步骤</h3>
        <ol>
          <li>在 QuantSage 客户端激活页面查看您的<strong>设备码</strong></li>
          <li>使用支付宝扫描下方收款码，<strong>付款时在备注中填写您的设备码</strong></li>
          <li>付款后，在下方输入设备码并点击「提交订单」</li>
          <li>等待开发者确认收款后签发激活码（通常 5 分钟内）</li>
          <li>在「查询激活码」标签页输入设备码获取激活码</li>
          <li>将激活码粘贴回客户端，完成激活</li>
        </ol>
      </div>

      <div class="qr-box">
        <p style="color:#9ca3af;font-size:0.85rem;margin-bottom:0.5rem;">📱 支付宝商家收款码（付款时备注设备码）</p>
        <img src="${PAY_QR_DATA_URI}" alt="支付宝收款码" style="max-width:240px;">
        <p style="color:#fbbf24;font-size:0.85rem;margin-top:0.5rem;">⚠️ 付款备注务必填写设备码，否则无法自动匹配</p>
      </div>

      <label for="orderDevice">📟 您的设备码</label>
      <input type="text" id="orderDevice" placeholder="从 QuantSage 客户端复制（16位十六进制）" autocomplete="off">

      <button id="orderBtn" onclick="createOrder()">📝 提交订单</button>
      <div id="orderResult" class="result"></div>
    </div>
  </div>

  <!-- ═══ Tab 2: Query Activation Key ═══ -->
  <div id="tab-query" class="tab-content">
    <div class="card">
      <h1>🔍 查询激活码</h1>
      <p class="subtitle">付款并提交订单后，在此查询您的激活码</p>

      <label for="queryDevice">📟 设备码</label>
      <input type="text" id="queryDevice" placeholder="输入您的设备码查询激活状态" autocomplete="off">

      <button id="queryBtn" onclick="queryOrder()">🔍 查询</button>
      <div id="queryResult" class="result"></div>
      <div id="queryLicense" style="display:none;">
        <div class="license-key" id="queryLicenseKey"></div>
        <button class="btn-sm" onclick="copyText('queryLicenseKey')">📋 复制激活码</button>
      </div>
    </div>
  </div>

  <!-- ═══ Tab 3: Voucher Redeem (legacy) ═══ -->
  <div id="tab-voucher" class="tab-content">
    <div class="card">
      <h1>🎫 凭证码兑换</h1>
      <p class="subtitle">已有购买凭证码？在此兑换激活码</p>

      <label for="voucher">🎫 购买凭证码</label>
      <input type="text" id="voucher" placeholder="粘贴凭证码" autocomplete="off">

      <label for="voucherDevice">📟 设备码</label>
      <input type="text" id="voucherDevice" placeholder="从 QuantSage 客户端复制" autocomplete="off">

      <button id="redeemBtn" onclick="redeemVoucher()">🔓 获取激活码</button>
      <div id="redeemResult" class="result"></div>
      <div id="redeemLicense" style="display:none;">
        <div class="license-key" id="redeemLicenseKey"></div>
        <button class="btn-sm" onclick="copyText('redeemLicenseKey')">📋 复制激活码</button>
      </div>
    </div>
  </div>

  <p class="disclaimer">⚠️ ${DISCLAIMER}<br>激活码绑定设备，一码一机。</p>
</div>

<script>
function $(id) { return document.getElementById(id); }

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector('.tab:nth-child(' + ({pay:1,query:2,voucher:3}[name]) + ')').classList.add('active');
  $('tab-' + name).classList.add('active');
}

function showResult(id, type, msg) {
  const el = $(id); el.style.display = 'block'; el.className = 'result ' + type;
  el.innerHTML = '<div class="header">' + msg + '</div>';
}

function copyText(elemId) {
  const text = $(elemId).textContent;
  if (text && navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = event.target.textContent;
      event.target.textContent = '✅ 已复制！';
      setTimeout(() => { event.target.textContent = orig; }, 2000);
    });
  }
}

// ── Create Order ──
async function createOrder() {
  const device = $('orderDevice').value.trim();
  const btn = $('orderBtn');
  $('orderResult').style.display = 'none';
  if (!device) { showResult('orderResult','error','❌ 请输入设备码'); return; }
  if (!/^[0-9a-fA-F]{16,32}$/.test(device)) { showResult('orderResult','error','❌ 设备码格式无效（至少16位十六进制）'); return; }

  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>提交中...';
  try {
    const resp = await fetch('/order/create', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({device_code: device})
    });
    const data = await resp.json();
    if (data.status === 'completed') {
      showResult('orderResult','success','✅ 激活码已就绪！请切换到「查询激活码」标签页获取。');
    } else if (data.status === 'pending') {
      showResult('orderResult','info','📝 ' + data.message);
    } else {
      showResult('orderResult','error','❌ ' + (data.error || '未知错误'));
    }
  } catch(e) {
    showResult('orderResult','error','❌ 网络错误，请重试');
  } finally {
    btn.disabled = false; btn.textContent = '📝 提交订单';
  }
}

// ── Query Order ──
async function queryOrder() {
  const device = $('queryDevice').value.trim();
  const btn = $('queryBtn');
  $('queryResult').style.display = 'none'; $('queryLicense').style.display = 'none';
  if (!device) { showResult('queryResult','error','❌ 请输入设备码'); return; }

  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>查询中...';
  try {
    const resp = await fetch('/order/status?device_code=' + encodeURIComponent(device));
    const data = await resp.json();
    if (data.status === 'completed' && data.license_key) {
      $('queryLicenseKey').textContent = data.license_key;
      $('queryLicense').style.display = 'block';
      const lvl = data.level || 'pro';
      showResult('queryResult','success','✅ 激活码已就绪！等级: ' + lvl);
    } else if (data.status === 'pending') {
      showResult('queryResult','info','⏳ 订单待处理，请等待开发者确认收款后签发激活码。');
    } else if (data.status === 'rejected') {
      showResult('queryResult','error','❌ 订单已被拒绝：' + (data.notes || ''));
    } else {
      showResult('queryResult','error','❌ 未找到该设备码的订单。请先在「付款激活」标签页提交订单。');
    }
  } catch(e) {
    showResult('queryResult','error','❌ 网络错误，请重试');
  } finally {
    btn.disabled = false; btn.textContent = '🔍 查询';
  }
}

// ── Redeem Voucher (legacy) ──
async function redeemVoucher() {
  const voucher = $('voucher').value.trim();
  const device = $('voucherDevice').value.trim();
  const btn = $('redeemBtn');
  $('redeemResult').style.display = 'none'; $('redeemLicense').style.display = 'none';
  if (!voucher) { showResult('redeemResult','error','❌ 请输入凭证码'); return; }
  if (!device) { showResult('redeemResult','error','❌ 请输入设备码'); return; }
  if (!/^[0-9a-fA-F]{16,32}$/.test(device)) { showResult('redeemResult','error','❌ 设备码格式无效'); return; }

  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>签发中...';
  try {
    const resp = await fetch('/redeem', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({voucher_code: voucher, device_code: device})
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      $('redeemLicenseKey').textContent = data.license_key;
      $('redeemLicense').style.display = 'block';
      const expMsg = data.expires === '9999-12-31' ? '永久有效' : '到期: ' + data.expires;
      showResult('redeemResult','success','✅ 激活码获取成功！' + expMsg);
    } else {
      showResult('redeemResult','error','❌ ' + (data.error || '获取失败'));
    }
  } catch(e) {
    showResult('redeemResult','error','❌ 网络错误');
  } finally {
    btn.disabled = false; btn.textContent = '🔓 获取激活码';
  }
}
</script>
</body>
</html>`;

// ── GET /admin Admin Backend Page ────────────────────────────────────────────

const ADMIN_HTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QuantSage 管理后台</title>
<style>${COMMON_CSS}</style>
</head>
<body>
<div class="container" id="app">

  <!-- ═══ Login Screen ═══ -->
  <div id="loginScreen">
    <div class="card">
      <h1>🔐 管理后台</h1>
      <p class="subtitle">请输入管理员密钥以继续</p>
      <label for="adminSecret">管理员密钥</label>
      <input type="password" id="adminSecret" placeholder="输入 Admin Secret" autocomplete="off">
      <button onclick="login()">🔓 登录</button>
      <div id="loginError" class="result"></div>
    </div>
  </div>

  <!-- ═══ Admin Dashboard (hidden until login) ═══ -->
  <div id="dashboard" style="display:none;">
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h1 style="margin:0;">📊 管理后台</h1>
        <button class="btn-sm btn-red" onclick="logout()" style="margin:0;">退出登录</button>
      </div>
      <p class="subtitle">待处理订单 · 签发激活码 · 永久码</p>
    </div>

    <!-- Single Issue -->
    <div class="card">
      <h2>🔑 单设备签发</h2>
      <label for="issueDevice">设备码</label>
      <input type="text" id="issueDevice" placeholder="输入16位设备码">
      <label for="issueNote">备注（可选）</label>
      <input type="text" id="issueNote" placeholder="备注信息">
      <button onclick="issueSingle()">签发激活码</button>
      <div id="issueResult" class="result"></div>
      <div id="issueLicense" style="display:none;">
        <div class="license-key" id="issueLicenseKey"></div>
        <button class="btn-sm" onclick="copyText('issueLicenseKey')">📋 复制</button>
      </div>
    </div>

    <!-- Permanent Issue -->
    <div class="card">
      <h2>⭐ 签发永久码</h2>
      <label for="permDevice">设备码（或输入 MASTER 生成万能码）</label>
      <input type="text" id="permDevice" placeholder="设备码 或 MASTER">
      <label for="permNote">备注（可选）</label>
      <input type="text" id="permNote" placeholder="备注">
      <button onclick="issuePermanent()">签发永久码</button>
      <div id="permResult" class="result"></div>
      <div id="permLicense" style="display:none;">
        <div class="license-key" id="permLicenseKey"></div>
        <button class="btn-sm" onclick="copyText('permLicenseKey')">📋 复制</button>
      </div>
    </div>

    <!-- Pending Orders -->
    <div class="card">
      <h2>⏳ 待处理订单</h2>
      <button onclick="loadOrders()">🔄 刷新列表</button>
      <div id="pendingList" style="margin-top:0.75rem;"></div>
      <div id="batchActions" style="display:none;margin-top:0.5rem;">
        <button class="btn-sm" onclick="issueSelected()">✅ 签发所选</button>
      </div>
      <div id="batchResult" class="result"></div>
    </div>

    <!-- Recent Completed -->
    <div class="card">
      <h2>✅ 最近已签发</h2>
      <div id="completedList"></div>
    </div>

    <p class="disclaimer">⚠️ ${DISCLAIMER}</p>
  </div>
</div>

<script>
let ADMIN_TOKEN = null;

function api(method, path, body) {
  const opts = { method, headers: {} };
  if (ADMIN_TOKEN) opts.headers['X-Admin-Secret'] = ADMIN_TOKEN;
  if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  return fetch(path, opts).then(r => r.json().then(d => ({ok: r.ok, status: r.status, ...d})));
}

function login() {
  const secret = document.getElementById('adminSecret').value.trim();
  if (!secret) { showResult('loginError','error','❌ 请输入密钥'); return; }
  // Store in sessionStorage — never in URL, cookie, or HTML
  sessionStorage.setItem('qs_admin_secret', secret);
  ADMIN_TOKEN = secret;
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('dashboard').style.display = 'block';
  loadOrders();
}

function logout() {
  sessionStorage.removeItem('qs_admin_secret');
  ADMIN_TOKEN = null;
  document.getElementById('loginScreen').style.display = 'block';
  document.getElementById('dashboard').style.display = 'none';
}

// Auto-login from sessionStorage
(function() {
  const saved = sessionStorage.getItem('qs_admin_secret');
  if (saved) { ADMIN_TOKEN = saved; document.getElementById('loginScreen').style.display = 'none'; document.getElementById('dashboard').style.display = 'block'; loadOrders(); }
})();

function showResult(id, type, msg) {
  const el = document.getElementById(id); el.style.display = 'block'; el.className = 'result ' + type;
  el.innerHTML = '<div class="header">' + msg + '</div>';
}

function copyText(elemId) {
  const text = document.getElementById(elemId).textContent;
  if (text && navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      const orig = event.target.textContent;
      event.target.textContent = '✅ 已复制！';
      setTimeout(() => { event.target.textContent = orig; }, 2000);
    });
  }
}

async function loadOrders() {
  const resp = await api('GET', '/admin/orders');
  if (resp.status === 401) { logout(); return; }

  const pending = resp.pending || [];
  const completed = resp.completed || [];

  let pHtml = pending.length === 0
    ? '<p style="color:#9ca3af;">暂无待处理订单</p>'
    : '<table><tr><th><input type="checkbox" onclick="toggleAll(this)" id="selectAll"></th><th>设备码</th><th>提交时间</th><th>备注</th></tr>'
      + pending.map(o => '<tr><td><input type="checkbox" class="orderCb" value="' + o.device_code + '"></td><td>' + o.device_code + '</td><td>' + (o.created_at||'') + '</td><td>' + (o.notes||'') + '</td></tr>').join('')
      + '</table>';

  document.getElementById('pendingList').innerHTML = pHtml;
  document.getElementById('batchActions').style.display = pending.length > 0 ? 'block' : 'none';

  let cHtml = completed.length === 0
    ? '<p style="color:#9ca3af;">暂无已签发记录</p>'
    : '<table><tr><th>设备码</th><th>激活码</th><th>等级</th><th>签发时间</th><th>备注</th></tr>'
      + completed.map(o => '<tr><td>' + o.device_code + '</td><td style="font-size:0.7rem;">' + (o.license_key||'').slice(0,30) + '...</td><td>' + (o.level||'pro') + '</td><td>' + (o.completed_at||'') + '</td><td>' + (o.notes||'') + '</td></tr>').join('')
      + '</table>';
  document.getElementById('completedList').innerHTML = cHtml;
}

function toggleAll(el) {
  document.querySelectorAll('.orderCb').forEach(cb => cb.checked = el.checked);
}

function getSelected() {
  return [...document.querySelectorAll('.orderCb:checked')].map(cb => cb.value);
}

async function issueSelected() {
  const codes = getSelected();
  if (codes.length === 0) { showResult('batchResult','error','❌ 请勾选至少一个订单'); return; }
  const resp = await api('POST', '/admin/issue-batch', {device_codes: codes});
  if (resp.status === 401) { logout(); return; }
  if (resp.success) {
    const ok = resp.results.filter(r => r.success).length;
    const fail = resp.results.filter(r => !r.success).length;
    showResult('batchResult','success','✅ 签发完成: ' + ok + ' 成功, ' + fail + ' 失败');
  } else {
    showResult('batchResult','error','❌ ' + (resp.error || '失败'));
  }
  loadOrders();
}

async function issueSingle() {
  const dc = document.getElementById('issueDevice').value.trim();
  const note = document.getElementById('issueNote').value.trim();
  if (!dc) { showResult('issueResult','error','❌ 请输入设备码'); return; }
  const resp = await api('POST', '/admin/issue', {device_code: dc, note: note || undefined});
  if (resp.status === 401) { logout(); return; }
  if (resp.success) {
    document.getElementById('issueLicenseKey').textContent = resp.license_key;
    document.getElementById('issueLicense').style.display = 'block';
    showResult('issueResult','success','✅ 签发成功！有效期至: ' + (resp.expires||''));
  } else {
    showResult('issueResult','error','❌ ' + (resp.error || '签发失败'));
  }
  loadOrders();
}

async function issuePermanent() {
  const dc = document.getElementById('permDevice').value.trim();
  const note = document.getElementById('permNote').value.trim();
  if (!dc) { showResult('permResult','error','❌ 请输入设备码或 MASTER'); return; }
  const resp = await api('POST', '/admin/issue-permanent', {device_code: dc, note: note || undefined});
  if (resp.status === 401) { logout(); return; }
  if (resp.success) {
    document.getElementById('permLicenseKey').textContent = resp.license_key;
    document.getElementById('permLicense').style.display = 'block';
    showResult('permResult','success','✅ ' + (resp.is_master ? '万能永久码！' : '永久码签发成功！'));
  } else {
    showResult('permResult','error','❌ ' + (resp.error || '签发失败'));
  }
}
</script>
</body>
</html>`;

// ══════════════════════════════════════════════════════════════════════════════
// MAIN FETCH HANDLER
// ══════════════════════════════════════════════════════════════════════════════

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    // ── GET routes ──
    if (request.method === "GET") {
      if (url.pathname === "/") {
        return new Response(ACTIVATION_HTML, {
          headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=300", ...corsHeaders() },
        });
      }
      if (url.pathname === "/admin") {
        return new Response(ADMIN_HTML, {
          headers: { "Content-Type": "text/html; charset=utf-8", ...corsHeaders() },
        });
      }
      if (url.pathname === "/admin/orders") {
        return handleAdminOrders(request, env);
      }
      if (url.pathname === "/order/status") {
        return handleOrderStatus(request, env);
      }
    }

    // ── POST routes ──
    if (request.method === "POST") {
      if (url.pathname === "/order/create") {
        return handleOrderCreate(request, env);
      }
      if (url.pathname === "/redeem") {
        return handleRedeem(request, env);
      }
      if (url.pathname === "/admin/issue") {
        return handleAdminIssueSingle(request, env);
      }
      if (url.pathname === "/admin/issue-batch") {
        return handleAdminIssueBatch(request, env);
      }
      if (url.pathname === "/admin/issue-permanent") {
        return handleAdminIssuePermanent(request, env);
      }
    }

    return jsonResponse({ error: "Not Found" }, 404);
  },
};
