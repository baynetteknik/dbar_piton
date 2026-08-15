# 06 - FATURA & İRSALİYE MODÜLÜ (`FATLIST001`, `YNSATFAT001`, `YNALFAT001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Liste Ekranı (Data Grid) Sütunları
1. `invoice_no` (Fatura No) -> Örn: `TOY20260000001`
2. `invoice_type` (Tür) -> Satış Faturası, Alış Faturası, Satış İade, Alış İade
3. `customer_name` (Cari Ünvanı) -> Arama filtreli
4. `invoice_date` (Fatura Tarihi), `due_date` (Vade Tarihi)
5. `gross_total` (Brüt Tutar), `vat_total` (KDV Tutarı), `net_total` (Ödenecek Tutar)
6. `currency` (Para Birimi), `payment_status` (Ödendi, Kısmi Ödendi, Açık Hesap)
7. `efatura_status` (GİB Durumu: Taslak, Gönderildi, Onaylandı, Hata)

### B. Tam Ekran Form Alanları
- **Üst Bilgiler:** `invoice_type` (Zorunlu), `invoice_no` (Otomatik Seri/Sıra), `customer_id` (+ `➕ Hızlı Cari`), `customer_name`, `invoice_date`, `due_date`, `payment_plan_id`, `warehouse_id` (Stok Düşülecek Depo), `currency`, `exchange_rate`, `tevkifat_kodu` (Varsa), `e_arsiv_senaryo` (Temel/Ticari/Kamu), `notlar`.
- **Satır Kalemleri Izgarası:** `product_id` (+ `➕ Hızlı Stok`), `product_name`, `qty`, `unit`, `unit_price`, `discount_pct`, `tax_rate`, `tevkifat_orani`, `line_total`.
- **Ödeme & Kasa Dağıtımı:** Peşin ödeme yapıldıysa `kasa_id` / `banka_id` seçimi ile anında tahsilat kaydı oluşturma.
- **İşlem Tetikleyicileri (Transactions):**
  1. *Stok Hareketi:* Satışta stok eksilir, alışta stok artar (Reçeteli ürünse alt bileşenler düşer).
  2. *Cari Hareketi:* Cari hesabına borç/alacak işlenir, taksit planına göre vade günleri bölünür.
  3. *Finans Hareketi:* Peşin tahsilat/ödeme varsa Kasa/Banka bakiyesi anında güncellenir.

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `invoices` & `invoice_items` & `invoice_installments`
| Tablo | Kolonlar |
| :--- | :--- |
| **`invoices`** | `id`, `tenant_id`, `invoice_no`, `invoice_type`, `customer_id`, `customer_name`, `invoice_date`, `due_date`, `payment_plan_id`, `warehouse_id`, `currency`, `exchange_rate`, `gross_total`, `discount_total`, `vat_total`, `withholding_total` (Tevkifat), `net_total`, `payment_status`, `efatura_uuid`, `efatura_status`, `notes`, `is_deleted`, `version_id`, `created_at` |
| **`invoice_items`** | `id`, `invoice_id`, `line_no`, `product_id`, `product_name`, `qty`, `unit`, `unit_price`, `discount_pct`, `tax_rate`, `withholding_rate`, `line_total` |
| **`invoice_installments`** | `id`, `invoice_id`, `customer_id`, `installment_no`, `due_date`, `amount`, `paid_amount`, `is_paid` |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **06.01** Fatura ekran alanları, tevkifat, taksit ve transaction kuralları modellendi
- [ ] **06.02** `Invoice`, `InvoiceItem`, `InvoiceInstallment` SQLAlchemy modellerinin kodlanması
- [ ] **06.03** `InvoiceService` (Atomik transaction: Fatura + Stok Hareketi + Cari Hareketi + Kasa Tahsilatı)
- [ ] **06.04** Fatura Listesi (`FATLIST001`) ve Satış/Alış Faturası Tam Ekran Formu (`YNSATFAT001`) UI entegrasyonu
