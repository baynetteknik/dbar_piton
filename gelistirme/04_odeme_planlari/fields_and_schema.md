# 04 - ÖDEME PLANLARI & VADE MODÜLÜ (`ODMPLN001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Liste Ekranı (Data Grid)
- `code` (Plan Kodu) -> Örn: `VADE-30`, `TAKSIT-3`
- `name` (Plan Adı) -> Örn: `30 Gün Açık Hesap`, `Peşin + 30/60/90 Gün Taksit`
- `downpayment_pct` (Peşinat Oranı %) -> Örn: `%25`
- `installment_count` (Taksit Sayısı) -> Örn: `3`
- `status` (Durum: Aktif/Pasif)

### B. Form Alanları (Taksit Matrisi)
- `name` (Text, Zorunlu, Max: 100) -> Plan Adı
- `description` (Textarea) -> Açıklama
- `terms` (Dinamik Tablo):
  - `term_no` (Sıra No: 1, 2, 3...)
  - `days_after` (Gün Sayısı: 0=Peşin, 30=30 Gün Sonra, 60=60 Gün Sonra)
  - `percentage` (Taksit Payı %: Toplamı %100 olmalıdır)

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `payment_plans` & `payment_plan_terms`
| Kolon | Tip | Özellikler | Açıklama |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY, AUTO | Plan No |
| `tenant_id` | INTEGER | FK -> tenants.id | Firma No |
| `name` | VARCHAR(100) | NOT NULL | Plan Adı |
| `plan_id` | INTEGER | FK -> payment_plans.id | Taksit Satırı |
| `term_no` | INTEGER | NOT NULL | Taksit Sırası |
| `days_after` | INTEGER | NOT NULL | Vade Gün Sayısı |
| `percentage` | NUMERIC(5,2) | NOT NULL | Taksit Yüzdesi (%) |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **04.01** Ödeme planı alanları ve taksit şablon matrisi modellendi
- [ ] **04.02** `PaymentPlan` ve `PaymentPlanTerm` SQLAlchemy modellerinin kodlanması
- [ ] **04.03** `PaymentPlanService` (Fatura tutarını taksitlere bölen servis) kodlanması
- [ ] **04.04** Ödeme Planları UI ekranının (`ODMPLN001`) 3-bölmeli şablona bağlanması
