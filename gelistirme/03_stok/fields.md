# 03 - STOK, FİYAT & ÜRÜN AĞACI MODÜLÜ (`STKLIST001`, `YNSTK001`, `URUNAGAC001`, `FIYATLST001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. 3-Bölmeli Stok Liste Ekranı (Data Grid) Sütunları
1. `sku` (Stok Kodu) -> Arama filtreli, Genişlik: 120px
2. `barcode` (Barkod) -> Arama filtreli, Genişlik: 130px
3. `name` (Ürün / Hizmet Adı) -> Arama filtreli, Genişlik: 280px
4. `category` (Kategori) -> Dropdown filtreli, Genişlik: 130px
5. `unit` (Birim: Adet, Kg, Metre vb.) -> Genişlik: 80px
6. `stock_qty` (Mevcut Stok) -> Sayısal filtreli, Koşullu Renkli (Kritik altı=Turuncu), Genişlik: 110px
7. `buy_price` (Alış Fiyatı) -> Sayısal filtreli, Genişlik: 120px
8. `sell_price` (Satış Fiyatı) -> Sayısal filtreli, Genişlik: 120px
9. `tax_rate` (KDV Oranı: %20, %10, %1, %0) -> Genişlik: 80px
10. `status` (Durum: 1=Aktif, 0=Pasif) -> Genişlik: 80px

### B. Stok Tam Ekran Form Alanları
1. **Genel Bilgiler:**
   - `product_type` (Select: Ticari Mal, Hammadde, Hizmet, Masraf, Set/Paket Ürün)
   - `sku` (Text, Zorunlu, Max: 100) -> Stok Kodu (Örn: `STK-00201`)
   - `barcode` (Text, Max: 100) -> Barkod
   - `name` (Text, Zorunlu, Max: 255) -> Ürün / Hizmet Adı
   - `category` (Text, Max: 150), `brand` (Text, Max: 150), `model` (Text, Max: 150)
   - `unit` (Select: Adet, Kg, Metre, Litre, Koli, Paket, Saat)
   - `photo_path` (File Upload, Image)
2. **Fiyat & Vergi:**
   - `tax_rate` (Select: %0, %1, %10, %20, Zorunlu)
   - `buy_price` (Numeric 18,2, Default: 0) -> Alış Fiyatı
   - `sell_price` (Numeric 18,2, Default: 0) -> Perakende Satış Fiyatı
   - `currency` (Select: TRY, USD, EUR)
3. **Stok & Depo Parametreleri:**
   - `warehouse_id` (ForeignKey -> warehouses.id) -> Varsayılan Depo
   - `min_qty` (Numeric 18,4, Default: 0) -> Kritik Minimum Stok
   - `max_qty` (Numeric 18,4, Default: 0) -> Azami Stok
   - `shelf_code` (Text, Max: 50) -> Raf / Konum Kodu
4. **Ürün Ağacı / Reçete (BOM) Bilgisi:**
   - `has_bom` (Boolean, Default: False) -> Bu ürün bir set/reçete mi?
   - `bom_items` (Grid: Alt Ürün Seçimi, Miktar, Birim, Fire Oranı, Satır Maliyeti)
5. **E-Ticaret & Notlar:**
   - `is_ecommerce` (Boolean, Default: False) -> WooCommerce/Trendyol Senkronu
   - `weight` / `desi` (Numeric 8,2) -> Ağırlık / Desi
   - `description` (Textarea)
