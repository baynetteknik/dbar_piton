# 02 - CARİ HESAPLAR VERİTABANI ŞEMASI

## 🗄️ TABLOLAR

### 1. `customers` (Cari Kartları)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Cari Tekil No |
| `tenant_id` | INTEGER | FK -> tenants.id, INDEX | Firma No |
| `customer_code` | VARCHAR(100)| INDEX, NULL | Cari Kodu |
| `customer_type` | VARCHAR(50) | DEFAULT 'Müşteri' | Müşteri, Tedarikçi, Personel |
| `fullname` | VARCHAR(255) | NOT NULL, INDEX | Cari Ünvanı / Adı |
| `authorized_person`| VARCHAR(255)| NULL | Yetkili Kişi |
| `nickname` | VARCHAR(255) | NULL | Kısa Ad |
| `group_name` | VARCHAR(150) | INDEX, NULL | Cari Grubu |
| `sub_group_1` | VARCHAR(150) | NULL | Alt Grup 1 |
| `sub_group_2` | VARCHAR(150) | NULL | Alt Grup 2 |
| `special_code_1`| VARCHAR(100) | NULL | Özel Kod 1 |
| `special_code_2`| VARCHAR(100) | NULL | Özel Kod 2 |
| `special_code_3`| VARCHAR(100) | NULL | Özel Kod 3 |
| `status` | INTEGER | DEFAULT 1, INDEX | 1: Aktif, 0: Pasif |
| `phone` | VARCHAR(50) | NULL | Telefon 1 |
| `phone2` | VARCHAR(50) | NULL | Telefon 2 |
| `phone_home` | VARCHAR(50) | NULL | Sabit Telefon |
| `fax` | VARCHAR(50) | NULL | Faks |
| `email` | VARCHAR(150) | INDEX, NULL | E-Posta |
| `website` | VARCHAR(255) | NULL | Web Sitesi |
| `address` | TEXT | NULL | Fatura Adresi |
| `address2` | TEXT | NULL | Sevk Adresi |
| `city` | VARCHAR(100) | INDEX, NULL | İl |
| `district` | VARCHAR(100) | NULL | İlçe |
| `country` | VARCHAR(100) | DEFAULT 'Türkiye' | Ülke |
| `postcode` | VARCHAR(20) | NULL | Posta Kodu |
| `tax_office` | VARCHAR(100) | NULL | Vergi Dairesi |
| `tax_number` | VARCHAR(50) | INDEX, NULL | Vergi No / TCKN |
| `is_efatura` | BOOLEAN | DEFAULT FALSE | e-Fatura Durumu |
| `efatura_mailbox`| VARCHAR(255)| NULL | Posta Kutusu Etiketi |
| `currency` | VARCHAR(10) | DEFAULT 'TRY' | Para Birimi |
| `payment_plan_id`| INTEGER | FK -> payment_plans.id, NULL | Varsayılan Ödeme Planı |
| `price_list_id` | INTEGER | FK -> price_lists.id, NULL | Varsayılan Fiyat Listesi |
| `risk_limit` | NUMERIC(18,2)| DEFAULT 0 | Açık Hesap Üst Sınırı |
| `default_discount`| NUMERIC(5,2)| DEFAULT 0 | Varsayılan İskonto (%) |
| `balance` | NUMERIC(18,2)| DEFAULT 0 | Anlık Bakiye (Borç - Alacak) |
| `notes` | TEXT | NULL | Notlar |
| `marketplace` | VARCHAR(50) | DEFAULT 'local', INDEX | Senkron Kaynağı |
| `remote_id` | VARCHAR(100) | NULL | Dış ERP/Sistem ID'si |
| `is_deleted` | BOOLEAN | DEFAULT FALSE | Soft Delete |
| `version_id` | INTEGER | DEFAULT 1 | Optimistic Lock |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Kayıt Tarihi |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Güncelleme Tarihi |
