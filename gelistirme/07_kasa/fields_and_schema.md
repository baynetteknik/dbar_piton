# 07 - KASA MODÜLÜ (`KASALST001`, `KASATAH001`, `KASATED001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Kasa Kartı Liste Ekranı (Data Grid)
- `code` (Kasa Kodu: `KAS-TL-01`), `name` (Kasa Adı: Merkez TL Kasası), `currency` (TRY, USD, EUR), `balance` (Anlık Kasa Bakiyesi), `responsible_user` (Sorumlu), `status`.

### B. Kasa Hareket Fişleri (Tahsilat & Tediye)
- **Kasa Tahsilat Fişi (`KASATAH001` - Para Girişi):**
  - `receipt_no` (Makbuz No), `date` (Tarih), `cashbox_id` (Hangi Kasaya?), `customer_id` (Hangi Cariden?), `amount` (Tutar), `currency`, `exchange_rate`, `description` (Açıklama).
  - *Etki:* Kasa bakiyesi artar (+), Cari bakiye/borç düşer (-).
- **Kasa Tediye Fişi (`KASATED001` - Para Çıkışı):**
  - `receipt_no`, `date`, `cashbox_id` (Hangi Kasadan?), `customer_id` / `expense_id` (Hangi Cariye / Gidere?), `amount`, `currency`, `exchange_rate`, `description`.
  - *Etki:* Kasa bakiyesi azalır (-), Cari alacağı düşer / Masraf kaydedilir.

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `cashboxes` & `cashbox_transactions`
| Tablo | Kolonlar |
| :--- | :--- |
| **`cashboxes`** | `id`, `tenant_id`, `code`, `name`, `currency`, `responsible_user_id`, `opening_balance`, `current_balance`, `status`, `is_deleted`, `created_at` |
| **`cashbox_transactions`** | `id`, `tenant_id`, `cashbox_id`, `transaction_type` (TAHSILAT / TEDIYE / VIRMAN / FATURA), `receipt_no`, `transaction_date`, `customer_id`, `expense_id`, `amount`, `currency`, `exchange_rate`, `converted_amount`, `description`, `is_deleted`, `created_at` |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **07.01** Kasa kartı ve Tahsilat/Tediye hareket fişi alanları belirlendi
- [ ] **07.02** `Cashbox` ve `CashboxTransaction` SQLAlchemy modellerinin kodlanması
- [ ] **07.03** `CashboxService` (Kasa bakiyesi ve cari entegrasyonu)
- [ ] **07.04** Kasa Listesi (`KASALST001`), Tahsilat (`KASATAH001`) ve Tediye (`KASATED001`) UI entegrasyonu
