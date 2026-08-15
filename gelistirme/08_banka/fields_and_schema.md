# 08 - BANKA & POS & VİRMAN MODÜLÜ (`BNKLIST001`, `VRMTRAN001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Banka & POS Kartı Liste Ekranı (Data Grid)
- `bank_name` (Banka Adı), `account_name` (Hesap Tanımı), `account_type` (Vadesiz, Kredi Kartı, POS), `iban` (IBAN), `currency` (TRY, USD, EUR), `balance` (Bakiye), `status`.

### B. Banka & Virman Hareket Fişleri
- **Gelen Havale / EFT:** Müşteriden bankaya tahsilat (`Cari bakiye düşer`, `Banka bakiyesi artar`).
- **Gönderilen Havale / EFT:** Tedarikçiye/Gidere bankadan ödeme (`Cari alacak düşer`, `Banka bakiyesi azalır`).
- **Virman Fişi (`VRMTRAN001` - Hesaplar Arası Transfer):**
  - `source_type` (Kaynak: Kasa / Banka), `source_id` (Kaynak Hesap)
  - `target_type` (Hedef: Kasa / Banka), `target_id` (Hedef Hesap)
  - `amount` (Tutar), `exchange_rate` (Gerekirse kur çevrimi), `fee` (Banka Masrafı), `description`.

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `bank_accounts` & `bank_transactions`
| Tablo | Kolonlar |
| :--- | :--- |
| **`bank_accounts`** | `id`, `tenant_id`, `bank_name`, `account_name`, `account_type`, `branch_name`, `branch_code`, `account_no`, `iban`, `currency`, `pos_merchant_no`, `pos_commission_rate`, `pos_valour_days`, `opening_balance`, `current_balance`, `status`, `is_deleted`, `created_at` |
| **`bank_transactions`** | `id`, `tenant_id`, `bank_account_id`, `transaction_type` (GELEN_HAVALE / GIDEN_HAVALE / POS_TAHSILAT / VIRMAN / KREDI_KARTI_ODEME), `receipt_no`, `transaction_date`, `customer_id`, `expense_id`, `amount`, `currency`, `exchange_rate`, `fee_amount`, `description`, `is_deleted`, `created_at` |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **08.01** Banka, POS ve Virman transfer alanları modellendi
- [ ] **08.02** `BankAccount` ve `BankTransaction` SQLAlchemy modellerinin kodlanması
- [ ] **08.03** `BankService` (Hesap hareketleri, virman transfer transaction motoru)
- [ ] **08.04** Banka Listesi (`BNKLIST001`) ve Virman Ekranı (`VRMTRAN001`) UI entegrasyonu
