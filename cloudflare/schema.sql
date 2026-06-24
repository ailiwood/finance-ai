-- QuantSage Activation Database Schema
-- Cloudflare D1
--
-- Migration notes (2026-06-24):
--   This file APPENDS the orders table.
--   It does NOT alter existing vouchers or activations tables.
--   Existing columns are preserved: vouchers(voucher_code,status,used_at,bound_device,issued_license)
--                                activations(id,device_code,license_key,level,created_at,voucher_code)
--   Execute: npx wrangler d1 execute quantsage_db --file=schema.sql --remote

-- Purchase voucher codes (pre-generated, uploaded to payment platform)
-- KEPT from M7 — do not change column names
CREATE TABLE IF NOT EXISTS vouchers (
  voucher_code TEXT PRIMARY KEY,
  status TEXT DEFAULT 'unused',   -- unused / used
  used_at TEXT,
  bound_device TEXT,
  issued_license TEXT
);

-- Activation records
-- KEPT from M7 — do not change column names
CREATE TABLE IF NOT EXISTS activations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_code TEXT NOT NULL,
  license_key TEXT NOT NULL,
  level TEXT NOT NULL,             -- pro / permanent / permanent_master
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  voucher_code TEXT
);

-- Self-service orders (NEW — self-built payment flow)
-- device_code: original user input (may be > 16 chars with separators)
-- bound_device: normalized first 16 uppercase hex chars (used for signing)
-- status: pending / completed / rejected
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_code TEXT NOT NULL,
  bound_device TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  license_key TEXT,
  level TEXT DEFAULT 'pro',
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  completed_at TEXT
);

-- Prevent duplicate pending orders for the same bound device
-- SQLite partial unique index: only enforces uniqueness when status = 'pending'
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_pending
  ON orders(bound_device) WHERE status = 'pending';

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_vouchers_status ON vouchers(status);
CREATE INDEX IF NOT EXISTS idx_activations_device ON activations(device_code);
CREATE INDEX IF NOT EXISTS idx_activations_created ON activations(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_device ON orders(bound_device);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
