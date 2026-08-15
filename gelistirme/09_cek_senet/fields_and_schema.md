# 09 - ÇEK & SENET PORTFÖY MODÜLÜ (`CEKLIST001`, `YNCEK001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Çek/Senet Liste Ekranı (Data Grid)
- `portfolio_no` (Portföy No), `document_type` (Müşteri Çeki, Kendi Çekimiz, Senet), `customer_name` (Keşideci / Cari), `due_date` (Vade Tarihi), `amount` (Tutar), `currency`, `bank_name`, `cheque_no`, `status` (Portföyde, Bankaya Tahsile Verildi, Ciro Edildi, Tahsil Edildi, Karşılıksız/Protestolu).

### B. Form & Hareket İşlemleri
- `document_type` (Select: Müşteri Çeki, Kendi Çekimiz, Müşteri Senedi, Kendi Senedimiz)
- `customer_id` (Cari Bağlantısı)
- `due_date` (Vade Tarihi - Zorunlu), `amount` (Tutar), `currency`
- `bank_name`, `branch_name`, `account_no`, `cheque_no`, `drawer_name` (Keşideci)
- **Durum Değiştirme Aksiyonları:**
  - *Bankaya Tahsile Çıkış:* Banka hesabı seçilerek tahsile gönderilir.
  - *Ciro Etme:* Başka bir cari (tedarikçi) seçilerek çek devredilir.
  - *Tahsil Edildi:* Kasa veya Banka seçilerek nakde dönüştürülür.
  - *Karşılıksız / İade:* Çek cariye geri iade edilir, bakiye yeniden borçlandırılır.

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `cheques_promissory` & `cheque_history`
| Tablo | Kolonlar |
| :--- | :--- |
| **`cheques_promissory`** | `id`, `tenant_id`, `portfolio_no`, `doc_type`, `customer_id`, `drawer_name`, `bank_name`, `branch_name`, `account_no`, `cheque_no`, `issue_date`, `due_date`, `amount`, `currency`, `status`, `target_bank_id`, `endorsed_customer_id`, `notes`, `is_deleted`, `created_at` |
| **`cheque_history`** | `id`, `cheque_id`, `action_date`, `action_type` (PORTFOY / TAHSILE_VERILDI / CIRO / TAHSIL / KARSILIKSIZ), `description`, `created_by` |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **09.01** Çek ve Senet alanları, portföy durumları ve ciro akışları modellendi
- [ ] **09.02** `Cheque` ve `ChequeHistory` SQLAlchemy modellerinin kodlanması
- [ ] **09.03** `ChequeService` (Durum değiştirme, ciro ve kasa/banka tahsilat servisi)
- [ ] **09.04** Çek/Senet Listesi (`CEKLIST001`) ve Kart Giriş Formu (`YNCEK001`) UI entegrasyonu
