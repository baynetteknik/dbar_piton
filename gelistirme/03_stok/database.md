# 03 - STOK, FİYAT & ÜRÜN AĞACI VERİTABANI ŞEMASI

## 🗄️ TABLOLAR

### 1. `products` (Stok / Ürün / Hizmet Kartları)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Stok Tekil No |
| `tenant_id` | INTEGER | FK -> tenants.id, INDEX | Firma No |
| `product_type` | VARCHAR(50) | DEFAULT 'Ticari Mal' | Ürün, Hizmet, Masraf, Set/BOM |
| `sku` | VARCHAR(100)| INDEX, NULL | Stok Kodu |
| `barcode` | VARCHAR(100)| INDEX, NULL | Barkod |
| `name` | VARCHAR(255) | NOT NULL, INDEX | Ürün / Hizmet Adı |
| `category` | VARCHAR(150) | INDEX, NULL | Kategori |
| `brand` | VARCHAR(150) | NULL | Marka |
| `unit` | VARCHAR(20) | DEFAULT 'adet' | Birim |
| `buy_price` | NUMERIC(18,2)| DEFAULT 0 | Alış Fiyatı |
| `sell_price` | NUMERIC(18,2)| DEFAULT 0 | Satış Fiyatı |
| `tax_rate` | NUMERIC(5,2) | DEFAULT 20.00 | KDV Oranı (%) |
| `currency` | VARCHAR(10) | DEFAULT 'TRY' | Fiyat Para Birimi |
| `stock_qty` | NUMERIC(18,4)| DEFAULT 0 | Mevcut Stok Miktarı |
| `min_qty` | NUMERIC(18,4)| DEFAULT 0 | Kritik Minimum Stok |
| `max_qty` | NUMERIC(18,4)| DEFAULT 0 | Azami Stok |
| `warehouse_id` | INTEGER | FK -> warehouses.id, NULL | Varsayılan Depo |
| `shelf_code` | VARCHAR(50) | NULL | Raf Kodu |
| `has_bom` | BOOLEAN | DEFAULT FALSE | Ürün Ağacı Var mı? |
| `is_ecommerce` | BOOLEAN | DEFAULT FALSE | E-Ticarette Yayınla |
| `status` | INTEGER | DEFAULT 1, INDEX | 1: Aktif, 0: Pasif |
| `notes` | TEXT | NULL | Açıklama / Notlar |
| `marketplace` | VARCHAR(50) | DEFAULT 'local', INDEX | Senkron Kaynağı |
| `remote_id` | VARCHAR(100) | NULL | Dış Sistem ID |
| `is_deleted` | BOOLEAN | DEFAULT FALSE | Soft Delete |
| `version_id` | INTEGER | DEFAULT 1 | Optimistic Lock |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Kayıt Tarihi |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Güncelleme Tarihi |

### 2. `product_bom` & `product_bom_items` (Ürün Ağacı / Reçete)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Reçete No |
| `parent_product_id`| INTEGER | FK -> products.id | Ana Mamul / Set Ürün |
| `child_product_id` | INTEGER | FK -> products.id | Alt Bileşen / Hammadde |
| `qty` | NUMERIC(18,4)| NOT NULL | Gerekli Miktar |
| `unit` | VARCHAR(20) | NOT NULL | Bileşen Birimi |
| `waste_rate` | NUMERIC(5,2) | DEFAULT 0 | Fire Oranı (%) |
| `line_cost` | NUMERIC(18,4)| DEFAULT 0 | Hesaplanan Kalem Maliyeti |

### 3. `price_lists` & `price_list_items` (Gelişmiş Fiyat Listeleri)
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Fiyat Listesi No |
| `name` | VARCHAR(100) | NOT NULL | Liste Adı (Örn: Toptan Fiyat) |
| `currency` | VARCHAR(10) | DEFAULT 'TRY' | Liste Para Birimi |
| `is_vat_included`| BOOLEAN | DEFAULT FALSE | KDV Dahil mi? |
| `product_id` | INTEGER | FK -> products.id | Ürün |
| `price` | NUMERIC(18,2)| NOT NULL | Özel Liste Fiyatı |
| `discount_pct` | NUMERIC(5,2) | DEFAULT 0 | Liste İskonto Oranı (%) |
