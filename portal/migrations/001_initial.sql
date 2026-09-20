-- TOYA Portal - MySQL/MariaDB şeması (cPanel)

CREATE TABLE IF NOT EXISTS portal_publications (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  token         CHAR(64)     NOT NULL,
  source        VARCHAR(30)  NOT NULL,            -- 'toya', 'wolvox' ...
  external_ref  VARCHAR(100) NOT NULL,            -- kaynaktaki teklif no
  title         VARCHAR(255) NULL,
  customer_name VARCHAR(255) NULL,
  customer_email VARCHAR(150) NULL,
  currency      VARCHAR(10)  NOT NULL DEFAULT 'TRY',
  grand_total   DOUBLE       NOT NULL DEFAULT 0,
  valid_until   DATETIME     NULL,
  snapshot_json MEDIUMTEXT   NOT NULL,            -- kalemler + ek alanlar
  status        VARCHAR(20)  NOT NULL DEFAULT 'published', -- published|accepted|rejected|revoked
  allow_counter TINYINT(1)   NOT NULL DEFAULT 1,
  token_expires DATETIME     NOT NULL,
  view_count    INT          NOT NULL DEFAULT 0,
  last_view     DATETIME     NULL,
  action_taken  VARCHAR(20)  NULL,                -- accepted|rejected|countered
  action_date   DATETIME     NULL,
  counter_amount DOUBLE      NULL,
  counter_note  TEXT         NULL,
  decision_note TEXT         NULL,
  created_at    DATETIME     NOT NULL,
  updated_at    DATETIME     NOT NULL,
  UNIQUE KEY uq_portal_token (token),
  UNIQUE KEY uq_portal_ref (source, external_ref)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS portal_events (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  publication_id INT          NOT NULL,
  event_type     VARCHAR(30)  NOT NULL,           -- publish|view|accept|reject|counter|revoke
  ip_address     VARCHAR(45)  NULL,
  user_agent     VARCHAR(255) NULL,
  details        TEXT         NULL,
  created_at     DATETIME     NOT NULL,
  KEY idx_portal_events_pub (publication_id),
  KEY idx_portal_events_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Cari borç/alacak özeti (salt okunur bağlantı; karar/olay yok)
CREATE TABLE IF NOT EXISTS portal_accounts (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  token         CHAR(64)     NOT NULL,
  source        VARCHAR(30)  NOT NULL,
  external_ref  VARCHAR(100) NOT NULL,            -- kaynaktaki cari kodu/id
  customer_name VARCHAR(255) NULL,
  currency      VARCHAR(10)  NOT NULL DEFAULT 'TRY',
  balance       DOUBLE       NOT NULL DEFAULT 0,  -- + borç (bize borçlu), - alacak
  as_of         DATETIME     NULL,
  statement_json MEDIUMTEXT  NOT NULL,            -- hareket/belge satırları
  token_expires DATETIME     NOT NULL,
  revoked       TINYINT(1)   NOT NULL DEFAULT 0,
  view_count    INT          NOT NULL DEFAULT 0,
  last_view     DATETIME     NULL,
  created_at    DATETIME     NOT NULL,
  updated_at    DATETIME     NOT NULL,
  UNIQUE KEY uq_portal_acc_token (token),
  UNIQUE KEY uq_portal_acc_ref (source, external_ref)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- Harici sistem ayna tabloları (ajan gönderir; kaynak = source, kaynaktaki kimlik = ext_id)
-- sync_run: bir tam senkron turunun kimliği; turda görülmeyen kayıtlar "finish" ile source_deleted olur.
CREATE TABLE IF NOT EXISTS portal_mirror_cari (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source VARCHAR(30) NOT NULL,
  ext_id VARCHAR(64) NOT NULL,
  cari_kodu VARCHAR(30) NULL,
  unvan VARCHAR(250) NULL,
  email VARCHAR(60) NULL,
  telefon VARCHAR(30) NULL,
  vergi_no VARCHAR(20) NULL,
  aktif TINYINT(1) NOT NULL DEFAULT 1,
  source_deleted TINYINT(1) NOT NULL DEFAULT 0,
  sync_run VARCHAR(40) NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_portal_mirror_cari (source, ext_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS portal_mirror_cari_hareket (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source VARCHAR(30) NOT NULL,
  ext_id VARCHAR(64) NOT NULL,
  cari_ext_id VARCHAR(64) NULL,
  tarihi DATETIME NULL,
  vadesi DATETIME NULL,
  evrak_no VARCHAR(40) NULL,
  kaynak_tur VARCHAR(30) NULL,
  borc DOUBLE NOT NULL DEFAULT 0,
  alacak DOUBLE NOT NULL DEFAULT 0,
  aciklama VARCHAR(250) NULL,
  ilgili_ext_id VARCHAR(64) NULL,
  source_deleted TINYINT(1) NOT NULL DEFAULT 0,
  sync_run VARCHAR(40) NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_portal_mirror_cari_hareket (source, ext_id),
  KEY idx_portal_mirror_cari_hareket_cari_ext_id (source, cari_ext_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS portal_mirror_fatura (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source VARCHAR(30) NOT NULL,
  ext_id VARCHAR(64) NOT NULL,
  fatura_no VARCHAR(30) NULL,
  tarihi DATETIME NULL,
  vadesi DATETIME NULL,
  cari_ext_id VARCHAR(64) NULL,
  yon VARCHAR(10) NULL,
  kaynak_durum VARCHAR(30) NULL,
  iptal TINYINT(1) NOT NULL DEFAULT 0,
  ara_toplam DOUBLE NOT NULL DEFAULT 0,
  iskonto DOUBLE NOT NULL DEFAULT 0,
  kdv DOUBLE NOT NULL DEFAULT 0,
  genel_toplam DOUBLE NOT NULL DEFAULT 0,
  doviz VARCHAR(4) NULL,
  ek_bilgi VARCHAR(50) NULL,
  aciklama VARCHAR(100) NULL,
  source_deleted TINYINT(1) NOT NULL DEFAULT 0,
  sync_run VARCHAR(40) NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_portal_mirror_fatura (source, ext_id),
  KEY idx_portal_mirror_fatura_cari_ext_id (source, cari_ext_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS portal_mirror_fatura_kalem (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source VARCHAR(30) NOT NULL,
  ext_id VARCHAR(64) NOT NULL,
  fatura_ext_id VARCHAR(64) NOT NULL,
  stok_kodu VARCHAR(30) NULL,
  stok_adi VARCHAR(250) NULL,
  birim VARCHAR(15) NULL,
  miktar DOUBLE NOT NULL DEFAULT 0,
  fiyat DOUBLE NOT NULL DEFAULT 0,
  kdv_orani DOUBLE NOT NULL DEFAULT 0,
  tutar DOUBLE NOT NULL DEFAULT 0,
  kdvli_tutar DOUBLE NOT NULL DEFAULT 0,
  sira_no INT NULL,
  source_deleted TINYINT(1) NOT NULL DEFAULT 0,
  sync_run VARCHAR(40) NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_portal_mirror_fatura_kalem (source, ext_id),
  KEY idx_portal_mirror_fatura_kalem_fatura_ext_id (source, fatura_ext_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS portal_mirror_stok (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source VARCHAR(30) NOT NULL,
  ext_id VARCHAR(64) NOT NULL,
  stok_kodu VARCHAR(30) NULL,
  stok_adi VARCHAR(250) NULL,
  birim VARCHAR(15) NULL,
  kdv_orani DOUBLE NOT NULL DEFAULT 0,
  aktif TINYINT(1) NOT NULL DEFAULT 1,
  satis_fiyati DOUBLE NOT NULL DEFAULT 0,
  miktar DOUBLE NOT NULL DEFAULT 0,
  source_deleted TINYINT(1) NOT NULL DEFAULT 0,
  sync_run VARCHAR(40) NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_portal_mirror_stok (source, ext_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Portal kullanıcıları (üst sınır config'teki max_users; parola yalnızca password_hash ile saklanır)
CREATE TABLE IF NOT EXISTS portal_users (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  username       VARCHAR(60)  NOT NULL,
  password_hash  VARCHAR(255) NOT NULL,
  role           VARCHAR(10)  NOT NULL DEFAULT 'viewer',   -- admin | viewer
  active         TINYINT(1)   NOT NULL DEFAULT 1,
  failed_attempts INT         NOT NULL DEFAULT 0,
  locked_until   DATETIME     NULL,
  last_login     DATETIME     NULL,
  created_at     DATETIME     NOT NULL,
  UNIQUE KEY uq_portal_users_name (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Veri aktarım günlüğü: ajanın her gönderim/tur kapatma çağrısı (silinmez, incelenebilir)
CREATE TABLE IF NOT EXISTS portal_sync_log (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME     NOT NULL,
  source     VARCHAR(30)  NULL,
  entity     VARCHAR(30)  NULL,
  run        VARCHAR(40)  NULL,
  action     VARCHAR(10)  NOT NULL,                       -- ingest | finish
  status     VARCHAR(10)  NOT NULL,                       -- ok | error
  received   INT          NOT NULL DEFAULT 0,
  added      INT          NOT NULL DEFAULT 0,
  updated    INT          NOT NULL DEFAULT 0,
  vanished   INT          NOT NULL DEFAULT 0,
  message    VARCHAR(255) NULL,
  ip_address VARCHAR(45)  NULL,
  KEY idx_portal_sync_log_created (created_at),
  KEY idx_portal_sync_log_source (source, entity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
