# 02 - CARİ HESAPLAR MODÜLÜ (`CAKALST001`, `YNCARK001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. 3-Bölmeli Liste Ekranı (Data Grid) Sütunları
1. `customer_code` (Cari Kodu) -> Arama filtreli, Genişlik: 120px
2. `fullname` (Cari Ünvanı / Adı) -> Arama filtreli, Genişlik: 280px
3. `group_name` (Cari Grubu: ALICI, SATICI vb.) -> Dropdown filtreli, Genişlik: 130px
4. `balance` (Anlık Bakiye) -> Sayısal filtreli (`>0`, `<0`), Koşullu Renkli (Borç=Kırmızı, Alacak=Yeşil), Genişlik: 140px
5. `phone` (Telefon) -> Arama filtreli, Genişlik: 130px
6. `city` (İl) -> Dropdown filtreli, Genişlik: 110px
7. `tax_number` (Vergi No / TCKN) -> Arama filtreli, Genişlik: 130px
8. `status` (Durum: 1=Aktif, 0=Pasif) -> Genişlik: 80px

### B. Tam Ekran Form Alanları (Gruplandırılmış)
1. **Genel Künye:**
   - `customer_code` (Text, Zorunlu, Max: 100) -> Örn: `CAR-00101`
   - `customer_type` (Select: Müşteri, Tedarikçi, Müşteri & Tedarikçi, Personel, Ortak)
   - `fullname` (Text, Zorunlu, Max: 255) -> Tam ticari ünvan veya Şahıs adı
   - `authorized_person` (Text, Max: 255) -> Yetkili kişi
   - `nickname` (Text, Max: 255) -> Kısa ad / Lakap
2. **Vergi & E-Fatura:**
   - `tax_office` (Text, Max: 100) -> Vergi Dairesi
   - `tax_number` (Text, Max: 50) -> Vergi No / TCKN
   - `is_efatura` (Boolean, Default: False) -> E-Fatura Mükellefi
   - `efatura_mailbox` (Text, Max: 255) -> Posta Kutusu Etiketi (`urn:mail:...`)
3. **İletişim & Adresler:**
   - `address` (Textarea) -> Fatura Adresi
   - `address2` (Textarea) -> Sevk / Teslimat Adresi
   - `city` (Text, Max: 100), `district` (Text, Max: 100), `country` (Text, Default: 'Türkiye'), `postcode` (Text, Max: 20)
   - `phone` (Text, Max: 50), `phone2` (Text, Max: 50), `phone_home` (Text, Max: 50), `fax` (Text, Max: 50)
   - `email` (Email, Max: 150), `website` (Text, Max: 255)
4. **Finansal Koşullar & Ödeme Planı:**
   - `currency` (Select: TRY, USD, EUR)
   - `payment_plan_id` (ForeignKey -> payment_plans.id) -> Varsayılan Ödeme Planı
   - `risk_limit` (Numeric 18,2, Default: 0) -> Açık Hesap Kredi Limiti
   - `default_discount` (Numeric 5,2, Default: 0) -> Varsayılan İskonto (%)
   - `price_list_id` (ForeignKey -> price_lists.id) -> Varsayılan Fiyat Listesi
   - `bank_accounts_info` (Textarea) -> Banka & IBAN Bilgileri
5. **Gruplama & Özel Kodlar:**
   - `group_name` (Text, Max: 150) -> ALICI, SATICI vb.
   - `sub_group_1` (Text, Max: 150), `sub_group_2` (Text, Max: 150)
   - `special_code_1` (Text, Max: 100), `special_code_2` (Text, Max: 100), `special_code_3` (Text, Max: 100)
   - `notes` (Textarea)
