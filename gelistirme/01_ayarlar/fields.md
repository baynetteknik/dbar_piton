# 01 - AYARLAR & TANIMLAR MODÜLÜ (`GENELAYR001`, `DOVIZKUR001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Firma / Şube Tanımları Form Alanları
- `firma_kodu` (Text, Zorunlu, Max: 50) -> Örn: `FRM01`
- `unvan` (Text, Zorunlu, Max: 255) -> Resmi tam ticari ünvan
- `kisa_ad` (Text, Opsiyonel, Max: 100) -> Ekranda görünecek isim
- `sirket_turu` (Select: A.Ş., Ltd. Şti., Şahıs)
- `logo_path` (File Upload, Image)
- `calisma_yili` (Integer, Default: 2026)
- `vergi_dairesi` (Text, Max: 100)
- `vergi_no` (Text, Zorunlu, Max: 50) -> VKN / TCKN
- `ticaret_sicil_no` (Text, Max: 100)
- `mersis_no` (Text, Max: 100)
- `mali_musavir_bilgisi` (Text, Max: 255)
- `adres` (Textarea, Zorunlu)
- `il` (Text, Zorunlu, Max: 100), `ilce` (Text, Zorunlu, Max: 100), `posta_kodu` (Text, Max: 20), `ulke` (Text, Default: 'Türkiye')
- `telefon1` (Text, Zorunlu, Max: 50), `telefon2` (Text, Max: 50), `faks` (Text, Max: 50)
- `email` (Email, Zorunlu, Max: 150), `website` (Text, Max: 255), `kep_adresi` (Text, Max: 255)
- `varsayilan_para_birimi` (Select, Default: 'TRY')
- `varsayilan_kdv_orani` (Numeric, Default: 20.00)
- `efatura_aktif` (Boolean, Default: False)
- `entegrator_adi` (Select: Uyumsoft, Foriba, EDM, Trendyol, GİB)
- `entegrator_kullanici` (Text), `entegrator_sifre` (Password)

### B. Kullanıcı Tanımları Form Alanları
- `email` (Email, Zorunlu, Unique, Max: 150)
- `password` (Password, Hash: BCrypt)
- `ad_soyad` (Text, Zorunlu, Max: 150)
- `telefon` (Text, Max: 50)
- `departman` (Select: Yönetim, Muhasebe, Satış, Depo)
- `tenant_id` (ForeignKey -> tenants.id, Zorunlu)
- `rol` (Select: Admin, Muhasebe, Satis, Depo, Misafir)
- `is_active` (Boolean, Default: True)

### C. Merkezi Döviz & Kur Form Alanları
- `kod` (Text, Unique, Max: 10) -> TRY, USD, EUR, GBP
- `ad` (Text, Max: 50) -> Türk Lirası, ABD Doları, Euro
- `sembol` (Text, Max: 5) -> ₺, $, €, £
- `ondalik` (Integer, Default: 2)
- `alis_kuru` (Numeric 18,4, Default: 1.0000)
- `satis_kuru` (Numeric 18,4, Default: 1.0000)
- `efektif_alis` (Numeric 18,4)
- `efektif_satis` (Numeric 18,4)
- `is_main` (Boolean, Default: False) -> Ana para birimi (TRY)

### D. Dinamik Kısakod Form Alanları
- `ekran_adi` (Text, Zorunlu) -> Cari Kart Listesi
- `orijinal_kod` (Text, Max: 20) -> CAKALST001
- `ozel_kod` (Text, Unique, Max: 20) -> Kullanıcının değiştirdiği kod
- `modul_adi` (Text, Max: 50) -> Cari
- `hedef_url` (Text, Max: 255) -> /customers
