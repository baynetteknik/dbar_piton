-- Yalnızca testler için SQLite eşdeğeri (üretimde migrations/*.sql kullanılır; yeni bir migrasyon eklenince bu dosya da elle eşlenmelidir).

CREATE TABLE IF NOT EXISTS portal_publications (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  token         TEXT NOT NULL UNIQUE,
  source        TEXT NOT NULL,
  external_ref  TEXT NOT NULL,
  title         TEXT,
  customer_name TEXT,
  customer_email TEXT,
  currency      TEXT NOT NULL DEFAULT 'TRY',
  grand_total   REAL NOT NULL DEFAULT 0,
  valid_until   TEXT,
  snapshot_json TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'published',
  allow_counter INTEGER NOT NULL DEFAULT 1,
  token_expires TEXT NOT NULL,
  view_count    INTEGER NOT NULL DEFAULT 0,
  last_view     TEXT,
  action_taken  TEXT,
  action_date   TEXT,
  counter_amount REAL,
  counter_note  TEXT,
  decision_note TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  UNIQUE (source, external_ref)
);

CREATE TABLE IF NOT EXISTS portal_events (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  publication_id INTEGER NOT NULL,
  event_type     TEXT NOT NULL,
  ip_address     TEXT,
  user_agent     TEXT,
  details        TEXT,
  created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portal_accounts (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  token         TEXT NOT NULL UNIQUE,
  source        TEXT NOT NULL,
  external_ref  TEXT NOT NULL,
  customer_name TEXT,
  currency      TEXT NOT NULL DEFAULT 'TRY',
  balance       REAL NOT NULL DEFAULT 0,
  as_of         TEXT,
  statement_json TEXT NOT NULL,
  token_expires TEXT NOT NULL,
  revoked       INTEGER NOT NULL DEFAULT 0,
  view_count    INTEGER NOT NULL DEFAULT 0,
  last_view     TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  UNIQUE (source, external_ref)
);

CREATE TABLE IF NOT EXISTS portal_mirror_cari (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  cari_kodu TEXT NULL,
  unvan TEXT NULL,
  email TEXT NULL,
  telefon TEXT NULL,
  vergi_no TEXT NULL,
  aktif INTEGER NOT NULL DEFAULT 1,
  source_deleted INTEGER NOT NULL DEFAULT 0,
  sync_run TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (source, ext_id)
);
CREATE TABLE IF NOT EXISTS portal_mirror_cari_hareket (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  cari_ext_id TEXT NULL,
  tarihi TEXT NULL,
  vadesi TEXT NULL,
  evrak_no TEXT NULL,
  kaynak_tur TEXT NULL,
  borc REAL NOT NULL DEFAULT 0,
  alacak REAL NOT NULL DEFAULT 0,
  aciklama TEXT NULL,
  ilgili_ext_id TEXT NULL,
  source_deleted INTEGER NOT NULL DEFAULT 0,
  sync_run TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (source, ext_id)
);
CREATE TABLE IF NOT EXISTS portal_mirror_fatura (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  fatura_no TEXT NULL,
  tarihi TEXT NULL,
  vadesi TEXT NULL,
  cari_ext_id TEXT NULL,
  yon TEXT NULL,
  kaynak_durum TEXT NULL,
  iptal INTEGER NOT NULL DEFAULT 0,
  ara_toplam REAL NOT NULL DEFAULT 0,
  iskonto REAL NOT NULL DEFAULT 0,
  kdv REAL NOT NULL DEFAULT 0,
  genel_toplam REAL NOT NULL DEFAULT 0,
  doviz TEXT NULL,
  ek_bilgi TEXT NULL,
  aciklama TEXT NULL,
  source_deleted INTEGER NOT NULL DEFAULT 0,
  sync_run TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (source, ext_id)
);
CREATE TABLE IF NOT EXISTS portal_mirror_fatura_kalem (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  fatura_ext_id TEXT NOT NULL,
  stok_kodu TEXT NULL,
  stok_adi TEXT NULL,
  birim TEXT NULL,
  miktar REAL NOT NULL DEFAULT 0,
  fiyat REAL NOT NULL DEFAULT 0,
  kdv_orani REAL NOT NULL DEFAULT 0,
  tutar REAL NOT NULL DEFAULT 0,
  kdvli_tutar REAL NOT NULL DEFAULT 0,
  sira_no INTEGER,
  source_deleted INTEGER NOT NULL DEFAULT 0,
  sync_run TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (source, ext_id)
);
CREATE TABLE IF NOT EXISTS portal_mirror_stok (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  stok_kodu TEXT NULL,
  stok_adi TEXT NULL,
  birim TEXT NULL,
  kdv_orani REAL NOT NULL DEFAULT 0,
  aktif INTEGER NOT NULL DEFAULT 1,
  satis_fiyati REAL NOT NULL DEFAULT 0,
  miktar REAL NOT NULL DEFAULT 0,
  source_deleted INTEGER NOT NULL DEFAULT 0,
  sync_run TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE (source, ext_id)
);

CREATE TABLE IF NOT EXISTS portal_users (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  username       TEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,
  role           TEXT NOT NULL DEFAULT 'viewer',
  active         INTEGER NOT NULL DEFAULT 1,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until   TEXT,
  last_login     TEXT,
  created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portal_sync_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  source     TEXT,
  entity     TEXT,
  run        TEXT,
  action     TEXT NOT NULL,
  status     TEXT NOT NULL,
  received   INTEGER NOT NULL DEFAULT 0,
  added      INTEGER NOT NULL DEFAULT 0,
  updated    INTEGER NOT NULL DEFAULT 0,
  vanished   INTEGER NOT NULL DEFAULT 0,
  message    TEXT,
  ip_address TEXT
);
