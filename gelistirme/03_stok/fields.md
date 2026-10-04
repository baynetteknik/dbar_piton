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
6. **Hizmet Tanımları (2026-09-29):** Stok kartıyla aynı `Product` tablosu, `product_type = "Hizmet"` seçildiğinde anlamlı olan ek alanlar — Stok Kartı ekranının "7. Muhasebe & Hizmet" bölümünde ve "3. Stok Takibi" / "5. KDV" bölümlerinde yer alır:
   - `tracks_stock` (Boolean, Default: True) -> "Stok takibi yapılır" — Hizmet/Masraf kartlarında kapatılır; kapalıyken bu ürünü içeren fiş satırları stok hareketi üretmez ve depo seçimi istemez (bkz. `BelgeHareketService.isle()`)
   - `sales_account_code` (Text, Max: 20) -> Satış Hesap Kodu (ör. "600 Yurtiçi Satışlar")
   - `purchase_account_code` (Text, Max: 20) -> Alış/Gider Hesap Kodu (ör. "770 Genel Yönetim Giderleri")
   - `vat_withholding_rate` (Select/Katalog: "9/10", "7/10", "5/10", "3/10", "2/10", "1/2") -> KDV Tevkifatı (KDVK Md. 9)
   - `nondeductible_expense` (Boolean, Default: False) -> KKEG (Kanunen Kabul Edilmeyen Gider)
   - `invoice_description_template` (Text, Max: 255) -> Fatura Açıklama Şablonu (ör. "{ay} dönemi danışmanlık hizmet bedeli")
7. **Masraf Tanımları (2026-09-30):** `product_type = "Masraf"` kartlarına özel, Stok Kartı ekranının "8. Masraf Tekrarı" bölümünde yer alan alanlar:
   - `is_recurring_expense` (Boolean, Default: False) -> "Düzenli Ödenen" (ör. kira, abonelik — her ay tekrar eder)
   - `recurring_due_day` (Integer, 1-31) -> Ödeme Günü (ayın kaçı)
   - `recurring_reminder_days_before` (Integer, 0-30, Default: 3) -> Kaç gün önce hatırlatılsın
   - İşaretlendiğinde Görevler modülünde aylık tekrarlı bir hatırlatma görevi otomatik açılır/güncellenir (bkz. `gelistirme/10_gorevler_notlar/fields_and_schema.md` → "Masraf Tanımları Entegrasyonu").

### Ekran ayrımı (2026-09-30)
Hizmet ve Masraf tanımları artık Stok Kartı ile AYNI tabloyu ve kart editörünü paylaşır ama STOK menüsü altında AYRI, `product_type`'a
göre önceden filtrelenmiş liste ekranları olarak açılır — mimari tekilleştirilmiş (DRY), ekranlar ayrı:
- **STOK › Ürün Yönetimi** — `product_type` "Hizmet"/"Masraf" DIŞINDAKİ kartlar (`StokListScreen(kart_modu="stok")`), etiketler "Stok Kodu/Stok Adı"
- **STOK › Hizmet Tanımları** — yalnız `product_type = "Hizmet"` (`StokListScreen(kart_modu="hizmet")`), etiketler "Ürün Kodu/Ürün Adı"
- **STOK › Masraf Tanımları** — yalnız `product_type = "Masraf"` (`StokListScreen(kart_modu="masraf")`), etiketler "Ürün Kodu/Ürün Adı"

Uygulama: `src/desktop/ui/stok_list_screen.py::KART_MODU_AYARLARI` (filtre + modül adı + profil anahtarı + sütun başlığı),
`src/desktop/ui/screens/stok_kart_editor.py::_KART_MODU_AYARLARI` (pencere başlığı + alan etiketleri + yeni kayıtta varsayılan tip).
