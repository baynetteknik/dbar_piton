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

## ✅ BANKA & POS KARTI (uygulanan) — 08.02 kısmen
- [x] Banka & POS Kartı editörü ve liste ekranı: Banka Hesabı, Kredi Kartı, POS (banka, şube adı/kodu, hesap no, IBAN, üye işyeri/terminal no, komisyon %, valör günü, açılış bakiyesi). Veri `finans_hesap` tablosunda; ayrı `bank_accounts` tablosu yerine ortak tablo kullanıldı.
- [x] Yetkiler: `kasa.*` ve `banka.*` yetki grupları (Muhasebe rolüne tanımlı)
- [ ] Banka hareketleri, virman (`VRMTRAN001`), POS komisyon/valör mahsubu ve anlık bakiye
- [ ] Cari fişindeki Araç=Banka/Kredi Kartı/POS satırlarından otomatik banka hareketi üretimi

## ✅ BANKA HAREKETLERİ (uygulanan)
- [x] Aynı `FinansFis`/`FinansHareket` altyapısı; ekran **Banka Hareketleri**, fiş penceresi `FinansFisDialog(grup="banka")`.
- [x] Fiş türleri: Gelen/Giden Havale (F2/F3), Gelen/Giden EFT, Virman, Açılış. Fiş no `B000001…`; banka fişlerinde hesap Banka / POS / Kredi Kartı olabilir.
- [x] Kasa'dan banka hesabına virman banka listesinde "← KSA… " girişi olarak görünür.
- [x] Banka & POS Kartları listesi sol paneli "HAREKET GİRİŞİ" ve sağ tık menüsü.
- [x] POS komisyon/valör mahsubu (bkz. gelistirme/04_odeme_planlari/tasarim.md, 04.09 + 2026-10-03 güncellemesi).
- [ ] Banka ekstresi içe aktarma, kredi kartı ekstre kapama (sonraki aşama).

## ✅ 2026-10-03: Kart ekranı taşma düzeltmeleri + POS zorunluluğu + Kredi Kartı alanları + POS Mahsup Takip
Kullanıcı isteği: "banka kartları tanımlaması olmadan POS tanımlanamasın yada aktif olmasın", "Banka kart
tanımları ekrana sığmıyor sağ tarafa doğru taşıyor", "Banka/Cari/Stok tanımlama ekranlarında sol ve sağ
paneller 1366x768 gibi ekranlarda sığmadığı için açılır kapanır paneller olsun", "Kredi kartı seçilir ise
Kart Numarası/Son Ödeme Tarihi/faiz oranı gibi alanlar olmalı", "Kredi Kartı ve POS tanımlarını banka ödeme
planlarına bağlayabilir miyiz?", "POS hareketi bir banka fişi oluşturacak, bu fişler ayrı bir ekranda takip
edilip ya otomatik ya da sorularak tahsil edilerek aktarılacak".

- **Kök neden teşhisi (taşma):** iki ayrı sorun bulundu. (1) `QComboBox` varsayılan boyutlandırma
  politikası uzun seçenek metnine göre kapalı kutunun kendisini de büyütüyordu (`DefinitionEditorScreen.
  _make_field`, tüm ekranları etkiler — ortak altyapı, tek yerden düzeltildi: `AdjustToMinimumContentsLengthWithIcon`
  + `setMinimumContentsLength`). (2) Asıl büyük suçlu: `QCheckBox` metni Qt'de SARMAZ — "Döviz Kısıtı" ve
  "Otomatik Mahsup" alanlarının tek satırlık paragraf uzunluğundaki açıklama metni, o alanın bulunduğu
  bölümü (ve dolayısıyla yan yana duran diğer bölümü) ekran dışına itiyordu. Çözüm: checkbox metni kısa
  tutulur, ayrıntı `tooltip`'e taşınır — `DefinitionEditorScreen` alan şemasına genel bir `"tooltip"` anahtarı
  eklendi (artık her alan tipi için kullanılabilir, dialog `__init__`'inde elle `setToolTip` çağırmaya gerek yok).
- **Sağ "ÖZET" paneli artık isteğe bağlı:** `DefinitionEditorScreen(right_panel=False)` — Banka/Kasa Kartı
  editöründe zaten header'da aynı bilgi (kod · ad · para birimi) tekrar gösterildiğinden tamamen kaldırıldı.
- **Sol/sağ paneller açılır-kapanır:** `DefinitionEditorScreen` artık her paneli ince bir ok tuşuyla
  (‹ ›) sarıyor; 1366px ve altı ekranlarda ikisi de VARSAYILAN KAPALI başlıyor (Cari/Stok/Firma editörlerini
  de kapsar — ortak altyapı).
- **POS, banka hesabı olmadan aktif edilemez:** `FinansHesapService.kaydet()`/`pasif_yap()` artık en az bir
  aktif `tur="banka"` hesabı yoksa POS'u aktif kaydetmeyi/aktifleştirmeyi reddeder (`FinansHesapError`).
  Pasif olarak kaydetmek hâlâ serbest (örn. önce kartı tanımlayıp sonra banka hesabı eklemek istenirse).
- **Kredi Kartı Bilgileri (yeni bölüm):** Kart Numarası (maskeli girilmesi önerilir — gerçek PAN saklanmaz),
  Hesap Kesim Günü, Son Ödeme Günü, Aylık Gecikme Faiz Oranı (%). `FinansHesap.kk_kart_no/kk_hesap_kesim_gunu/
  kk_son_odeme_gunu/kk_faiz_orani`.
- **Kredi Kartı / POS → Varsayılan Banka Ödeme Planı:** `FinansHesap.varsayilan_banka_odeme_plani_id`
  (yeni FK, `BankaOdemePlani`'ye). Şimdilik yalnız SAKLANIR/seçilir — `PaymentPlanLine.banka_odeme_plani_id`
  gibi otomasyonda (net tutar/komisyon düşümü) henüz TÜKETİLMİYOR; bu zaten var olan, henüz sarmalanmamış
  bir boşluk (`BankaOdemePlani.net_tutar()` hiçbir otomasyon akışından çağrılmıyor) — bilinçli olarak bu
  fazın kapsamı dışında bırakıldı, "formülasyonu yolda geliştiririz" ilkesiyle ayrı bir faz olacak.
- **POS Mahsup Takip ekranı (yeni, `pos_mahsup_takip_dialog.py`):** Banka Hareketleri ekranının "DİĞER
  İŞLEMLER" bölümünden açılır. Her POS hesabının vadesi gelmiş/gelmemiş bekleyen bakiyesini listeler;
  `pos_otomatik_mahsup` KAPALI hesaplar için daha önce HİÇBİR yolu olmayan manuel "Tahsil Et" (onay
  sorarak) aksiyonunu sağlar — açık hesaplarda erken/elle tetiklemek için de kullanılabilir.
  `pos_mahsup_servisi.py`'ye `bekleyen_bakiyeler()` ve `tek_hesabi_mahsup_et()` eklendi; otomatik tarama
  (`vadesi_gelenleri_tara`) ve manuel tetikleme artık ortak `_hesabi_mahsup_et()` çekirdeğini paylaşıyor.
- 15 yeni test (`test_finans_hesap_cards.py` +4, `test_pos_mahsup_servisi.py` +4, `test_pos_mahsup_takip_dialog.py`
  +4 yeni dosya, `test_definition_editor_screen.py` +3) + 3 mevcut testte ("POS artık banka hesabı
  gerektiriyor" davranış değişikliğine göre) kasıtlı güncelleme. Regresyon: `test_finans_hesap_cards.py`,
  `test_pos_mahsup_servisi.py`, `test_pos_mahsup_takip_dialog.py`, `test_definition_editor_screen.py`,
  `test_cari_stok_editors.py`, `test_firma_definition.py`, `test_firma_gating.py`, `test_stok_kart_dialog.py`,
  `test_finans_fis.py`, `test_odeme_plani_otomasyon_servisi.py`, `test_odeme_formul_motoru.py`,
  `test_document_detail_screen.py`, `test_general_settings_screen.py`, `test_settings_menu.py` — tek tek
  çalıştırıldı, hepsi temiz (tek bilinen, bu çalışmadan bağımsız `test_doviz_kisiti_...` hariç — eşzamanlı
  `cari_hareket_service.py` değişikliğinden kaynaklanıyor, daha önce de raporlandı).
- Ekran görüntüsüyle doğrulandı: Banka & POS Kartı (Kredi Kartı Bilgileri bölümü artık taşmadan görünüyor),
  POS Mahsup Takip, Cari Kartı (paneller varsayılan kapalı/1366px altı + toggle ile aç/kapa çalışıyor).
- **Dokunulmadı / bilinçli kapsam dışı:** Banka ödeme planının otomasyonda gerçek tutar düşümü (yukarıda
  açıklandı), gerçek arka plan zamanlayıcısı (hâlâ "ekran açılışında tara" modeli), Cari/Stok ekranlarının
  KENDİ alan şemalarında benzer "uzun checkbox metni" taraması yapılmadı (yalnız bu oturumda dokunulan Banka
  kartı ekranında somut bir örnek bulunup düzeltildi; aynı deseni başka ekranlarda da arayıp düzeltmek ayrı
  bir "temizlik" görevi olabilir).
