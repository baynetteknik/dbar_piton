# 05 - TEKLİF & SİPARİŞ MODÜLÜ (`TEKLIST001`, `YNTEKF001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Liste Ekranı (Data Grid) Sütunları
1. `quote_no` (Teklif No) -> Örn: `T-202608-0001`
2. `customer_name` (Cari Ünvanı) -> Arama filtreli
3. `quote_date` (Teklif Tarihi) -> Tarih filtreli
4. `valid_until` (Geçerlilik Tarihi)
5. `total_amount` (Toplam Tutar) -> Sayısal filtreli
6. `currency` (Para Birimi) -> TRY, USD, EUR
7. `status` (Durum) -> Taslak, Gönderildi, Kabul Edildi, Reddedildi, Siparişe/Faturaya Çevrildi
8. `payment_plan` (Ödeme Planı Adı)

### B. Tam Ekran Form Alanları
- **Üst Bilgiler:** `quote_no` (Otomatik), `customer_id` (Cari Seçici + `➕ Hızlı Cari Ekle` butonu), `customer_name` (Serbest manuel cari yazabilme), `quote_date`, `valid_until`, `currency`, `exchange_rate` (Anlık TCMB kuru), `payment_plan_id`, `notes`.
- **Satır Kalemleri Izgarası (Data Grid):**
  - `product_id` (Stok Seçici + `➕ Hızlı Stok Ekle` butonu)
  - `product_name` (Serbest manuel ürün yazabilme)
  - `qty` (Miktar), `unit` (Birim), `unit_price` (Birim Fiyat)
  - `discount_pct` (Kalem İskontosu %), `tax_rate` (KDV %)
  - `line_total` (Satır Tutarı - Canlı hesaplanır)
  - `[x] Kartlara da kaydet` onay kutusu
- **Dip Toplamlar:** Ara Toplam, Kalem İskontoları, Genel İskonto, KDV Toplamları (%1, %10, %20), Genel Toplam.
- **Aksiyonlar:** `Kaydet`, `Kopyala (/copy)`, `Excel'e Aktar (2 Sayfa Kurumsal openpyxl)`, `Faturaya Dönüştür`.

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `quotations` & `quotation_items`
| Tablo | Kolonlar |
| :--- | :--- |
| **`quotations`** | `id`, `tenant_id`, `quote_no`, `customer_id`, `customer_name`, `quote_date`, `valid_until`, `status`, `currency`, `exchange_rate`, `payment_plan_id`, `discount`, `total_amount`, `notes`, `is_deleted`, `version_id`, `created_at` |
| **`quotation_items`** | `id`, `quotation_id`, `line_no`, `product_id`, `product_name`, `qty`, `unit`, `unit_price`, `discount_pct`, `tax_rate`, `line_total` |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **05.01** Teklif & Sipariş alanları, satır kalemleri ve kurumsal Excel export kuralları belirlendi
- [ ] **05.02** `Quotation` ve `QuotationItem` modellerinin güncellenmesi (Ödeme planı ve döviz kuru eklenerek)
- [ ] **05.03** `QuotationService` (Dinamik tutar hesaplayıcı, kopyalama, Excel ihracı)
- [ ] **05.04** Teklif Listesi (`TEKLIST001`) ve Tam Ekran Teklif Editörü (`YNTEKF001`) UI entegrasyonu
- [ ] **05.05** Kabul edilen teklifin tek tıkla faturaya dönüştürülmesi servisi
