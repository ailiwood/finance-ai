-- QuantSage Activation Database Schema
-- Cloudflare D1

-- Purchase voucher codes (pre-generated, uploaded to payment platform)
CREATE TABLE IF NOT EXISTS vouchers (
  voucher_code TEXT PRIMARY KEY,
  status TEXT DEFAULT 'unused',   -- unused / used
  used_at TEXT,
  bound_device TEXT,
  issued_license TEXT
);

-- Activation records
CREATE TABLE IF NOT EXISTS activations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_code TEXT NOT NULL,
  license_key TEXT NOT NULL,
  level TEXT NOT NULL,             -- pro / permanent
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  voucher_code TEXT
);

-- Index for quick lookup
CREATE INDEX IF NOT EXISTS idx_vouchers_status ON vouchers(status);
CREATE INDEX IF NOT EXISTS idx_activations_device ON activations(device_code);
CREATE INDEX IF NOT EXISTS idx_activations_created ON activations(created_at);
