# 01 - AYARLAR & TANIMLAR VERİTABANI ŞEMASI

## 🗄️ TABLOLAR

### 1. `tenants` (Firmalar / Şubeler)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER / UUID | PRIMARY KEY, AUTO | Firma Tekil No |
| `code` | VARCHAR(50) | UNIQUE, NOT NULL | Firma Kodu |
| `name` | VARCHAR(255) | NOT NULL | Resmi Ünvanı |
| `short_name` | VARCHAR(100) | NULL | Kısa Adı |
| `tax_office` | VARCHAR(100) | NULL | Vergi Dairesi |
| `tax_number` | VARCHAR(50) | NOT NULL | VKN / TCKN |
| `trade_registry_no`| VARCHAR(100) | NULL | Ticaret Sicil No |
| `mersis_no` | VARCHAR(100) | NULL | Mersis No |
| `address` | TEXT | NOT NULL | Merkez Adresi |
| `city` | VARCHAR(100) | NOT NULL | İl |
| `district` | VARCHAR(100) | NOT NULL | İlçe |
| `phone` | VARCHAR(50) | NOT NULL | Telefon |
| `email` | VARCHAR(150) | NOT NULL | E-Posta |
| `currency` | VARCHAR(10) | DEFAULT 'TRY' | Varsayılan Para Birimi |
| `vat_rate` | NUMERIC(5,2) | DEFAULT 20.00 | Varsayılan KDV Oranı |
| `is_efatura` | BOOLEAN | DEFAULT FALSE | e-Fatura Durumu |
| `integrator_name` | VARCHAR(50) | NULL | Entegratör Adı |
| `integrator_config`| JSON / TEXT | NULL | Şifrelenmiş API Ayarları |
| `is_deleted` | BOOLEAN | DEFAULT FALSE | Soft Delete |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Kayıt Tarihi |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Güncelleme Tarihi |

### 2. `users` (Kullanıcılar)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Kullanıcı No |
| `tenant_id` | INTEGER | FK -> tenants.id | Bağlı Olduğu Firma |
| `email` | VARCHAR(150) | UNIQUE, NOT NULL | Giriş E-Postası |
| `password_hash` | VARCHAR(255) | NOT NULL | BCrypt Şifre Hash'i |
| `fullname` | VARCHAR(150) | NOT NULL | Ad Soyad |
| `phone` | VARCHAR(50) | NULL | Telefon |
| `role` | VARCHAR(50) | DEFAULT 'Admin' | Kullanıcı Rolü |
| `is_active` | BOOLEAN | DEFAULT TRUE | Aktif/Pasif Durumu |
| `is_deleted` | BOOLEAN | DEFAULT FALSE | Soft Delete |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Kayıt Tarihi |

### 3. `currencies` (Merkezi Döviz Tanımları)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `code` | VARCHAR(10) | PRIMARY KEY | TRY, USD, EUR, GBP |
| `name` | VARCHAR(50) | NOT NULL | Türk Lirası, Dolar vb. |
| `symbol` | VARCHAR(5) | NOT NULL | ₺, $, €, £ |
| `digits` | INTEGER | DEFAULT 2 | Ondalık Basamak |
| `buy_rate` | NUMERIC(18,4)| DEFAULT 1.0000 | Alış Kuru |
| `sell_rate` | NUMERIC(18,4)| DEFAULT 1.0000 | Satış Kuru |
| `is_main` | BOOLEAN | DEFAULT FALSE | Ana Para Birimi |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Son Kur Güncellemesi |

### 4. `screen_shortcuts` (Dinamik Ekran Kısakodları)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Kısakod No |
| `screen_name` | VARCHAR(100) | NOT NULL | Ekran Adı |
| `default_code` | VARCHAR(20) | NOT NULL | Sistem Varsayılan Kodu |
| `custom_code` | VARCHAR(20) | UNIQUE, NOT NULL | Kullanıcının Verdiği Kod |
| `target_url` | VARCHAR(255) | NOT NULL | Yönlendirilecek URL |
| `module_name` | VARCHAR(50) | NOT NULL | Modül Grubu |

### 5. `user_grid_settings` (Kullanıcı Sütun & Renk Ayarları)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Ayar No |
| `user_id` | INTEGER | FK -> users.id | Kullanıcı |
| `grid_id` | VARCHAR(50) | NOT NULL | Tablo Tanımı (Örn: 'customers_grid') |
| `column_widths` | JSON / TEXT | NOT NULL | Sütun Genişlikleri |
| `hidden_columns`| JSON / TEXT | NULL | Gizlenen Sütunlar |
| `column_order` | JSON / TEXT | NULL | Sütun Sıralaması |
| `color_rules` | JSON / TEXT | NULL | Koşullu Renklendirme Kuralları |
