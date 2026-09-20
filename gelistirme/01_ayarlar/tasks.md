# 01 - AYARLAR & TANIMLAR GÖREV TAKİBİ

## 📋 GÖREV LİSTESİ

- [x] **01.01** Firma/Şube alanları ve veri tipleri belirlendi (`fields.md`)
- [x] **01.02** Kullanıcı ve Rol alanları belirlendi (`fields.md`)
- [x] **01.03** Merkezi Döviz Motoru alanları ve TCMB entegrasyon kuralı belirlendi
- [x] **01.04** Dinamik Kısakod (`screen_shortcuts`) mimarisi ve tablosu tasarlandı
- [x] **01.05** Kullanıcı Grid & Renk Tercihleri (`user_grid_settings`) tablosu tasarlandı
- [ ] **01.06** `tenants`, `users`, `currencies`, `screen_shortcuts`, `user_grid_settings` SQLAlchemy modellerinin kodlanması
- [x] **01.07** `MoneyService` (TCMB Kur Çekici & Çapraz Kur Hesaplayıcı) — Kur Çekici tarafı `currency_rate_service.py` ile zaten kodluydu; Çapraz Kur Hesaplayıcı tarafı `src/desktop/services/money_service.py` (`get_rate`/`cross_rate`/`convert`) ile tamamlandı. `Currency.rate` ("1 birim = rate TRY") üzerinden herhangi iki döviz arası çevrim TRY pivotuyla hesaplanıyor.
- [ ] **01.08** Genel Ayarlar & Kısakod Yönetim Ekranı UI (`GENELAYR001`) tasarımının bağlanması

## 📝 GELİŞTİRİCİ NOTLARI
- Döviz kurları TCMB üzerinden çekilirken `aiosonic` veya `httpx` kullanılacak.
- Kısakod arama çubuğu (`Ctrl+K`), `screen_shortcuts` tablosunu yerel bellekte (cache) tutarak sıfır gecikmeyle sonuç döndürecek.

## ✅ TAMAMLANDI — 2026-09-17: Döviz & Kur ekranı UI restructuring
- [x] **01.09** `btn_style()` hover bug'ı düzeltildi — beyaz metinli renkli butonlarda (Getir, Toplu Kur Çek) hover'da metin okunmaz oluyordu; artık buton kendi renginin koyu tonuna geçiyor.
- [x] **01.10** Tekrarlı panel başlığı/açıklama paragrafı kaldırıldı; açıklama üst çubuktaki ℹ️ ikonunun tooltip'ine taşındı.
- [x] **01.11** Serbest Piyasa "Adres" alanı serbest metinden `CatalogSearchField`'e (kayıtlı/eklenip-silinebilir adres kataloğu, `src/desktop/ui/widgets/catalog_picker.py`) çevrildi, sonra üst çubuktan tamamen kaldırılıp sağ panel > "💱 Döviz İşlemleri" bölümüne taşındı (bkz. `_build_doviz_sag_panel_islemler`).
- [x] **01.12** "Toplu Kur Çek" / "Aralığı Sil" (sık kullanılmayan toplu işlemler) üst araç çubuğundan sağ panele ve sağ tık context menüsüne ("⚡ Toplu Kur Çek / Adres Yönetimi...") taşındı.
- [x] **01.13** Sağ panelde "📊 KUR RAPORLARI" bölümü yer tutucu olarak eklendi — içerik ayrı bir rapor widget'ı olarak sonra eklenecek (TOYA ERP widget mimarisi konvansiyonuna uygun, bkz. hangi rapor hangi bölümde gösterilecek kararı ayrı widget kataloğunda verilecek).
- [x] **01.14** Hiç döviz tanımlı değilse (TRY hariç) `_maybe_prompt_initial_currencies` ile "kullanmak istediğiniz dövizleri seçin" popup'ı gösteriliyor; standart liste `STANDART_DOVIZLER` sabitinde. TRY, panel ilk açıldığında `_ensure_try_currency` ile otomatik oluşturuluyor (henüz genel `_ensure_default_admin` yanına taşınan kapsamlı bir seed_service değil — bkz. aşağıdaki bekleyen madde).
- [x] **01.13b** "📊 KUR RAPORLARI" yer tutucusu, `src/desktop/ui/widgets/currency_rate_report_widget.py` içindeki bağımsız `CurrencyRateReportWidget` ile dolduruldu: döviz kodu + tarih aralığı seçilip `CurrencyRateHistory`'den M.B./S.P. alış-satış tablosu ve min/maks/ortalama özeti gösteriliyor. Panel her aktifleştiğinde ve toplu kur çek/sil sonrası otomatik `refresh()` ile tazeleniyor.

## ✅ TAMAMLANDI — 2026-09-17 (devam): Döviz seçim/kaynak/rapor iyileştirmeleri
- [x] **01.20** `src/desktop/services/currency_catalog.py` — ISO 4217 tabanlı, 125 para birimlik statik katalog (kod/ülke/isim/sembol; bayrak, ülke kodundan Unicode "regional indicator" ile anlık üretilir, internet/ikon indirme gerekmez). "Yeni Döviz Ekle" ve ilk kurulum "kullanmak istediğiniz dövizleri seçin" popup'ı artık serbest metin değil, `CurrencyPickerDialog` (`src/desktop/ui/widgets/currency_picker_dialog.py`) ile bu katalogdan aranıp seçiliyor. Firma editöründeki "Döviz Birimi" alanının (henüz hiç döviz tanımlanmamışsa düşülen) yedek listesi de aynı kataloğa bağlandı (`firma_editor.py::CURRENCIES`).
- [x] **01.21** `Currency` modeline `flag` alanı eklendi (seçilen bayrak emojisi); mevcut SQLite veritabanlarına `database.py::_ensure_compatibility_columns` self-healing migration'ı ile otomatik eklenir.
- [x] **01.22** Serbest Piyasa kaynak yönetimi: tekil/adsız adres alanı yerine `SerbestPiyasaKaynakField` + `SerbestPiyasaYonetimDialog` (`src/desktop/ui/widgets/serbest_piyasa_kaynak_widget.py`) ile adlandırılmış kayıtlarda Ekle/Düzenle/Test Et/Sil geldi ("Test Et", `currency_rate_service.fetch_rates` ile DB'ye yazmadan salt okunur deneme çekimi yapar). Depolama: `currency_rate_service.list_serbest_sources` / `save_serbest_sources` (`doviz.serbest_piyasa_kaynaklari` ayarı).
- [x] **01.23** "📊 KUR RAPORLARI" artık sağ panele gömülü değil — "🔍 Tam Ekran Görüntüle" butonu, `CurrencyRateReportWidget`'ı bağımsız, maximized bir popup pencerede açıyor (bkz. `_open_doviz_rapor_popup`).
- [x] **01.24** Döviz & Kur gridindeki sayısal sütunlar (M.B./S.P. Alış-Satış, Güncel Kur) sağa yaslandı (`_rate_item`). "Kur Gir" formundaki alanlar `QDoubleSpinBox`'tan `MaskedDecimalField`'e taşındı — sabit 4 ondalık hane (kur hassasiyeti, Genel Ayarlar'daki fiyat/tutar ondalık hane tercihinden bağımsız tutuldu).

## 🧭 BEKLEYEN — Program Geneli Sayı Biçimi
- [ ] **01.25** Sayıların sağa yaslanması ve `MaskedDecimalField` maskesinin (ondalık hane sayısı Genel Ayarlar'dan) PROGRAM GENELİNDE (Teklif/Fatura/İrsaliye kalem gridleri, Cari, Stok, hareket ekranları vb.) uygulanması — kullanıcı bu oturumda kapsamı bilinçli olarak yalnız Döviz & Kur ekranıyla sınırladı (01.24); geri kalanı ayrı, daha büyük kapsamlı bir görev olarak bir sonraki oturuma bırakıldı.

## 🧭 BEKLEYEN — Kurulum Sihirbazı / Seed Data / Gating (tasarım hazır, kodlanmadı)
Kullanıcı bilinçli olarak bunu ERTELEDİ: "genel tanımlar bölümü bitmedi, bu setup onları tetikleyecek" — yani seed data ve sihirbaz, ilgili tanım ekranları (KDV, Hesap Planı, Belge Serileri UI'ları) olgunlaşmadan kodlanmayacak. Bu bölüm yalnız gelecekteki oturum için hafıza notu.

- [ ] **01.15** `seed_service.py` — TRY/Adet gibi standart tanımları + KDV oranları + Tek Düzen Hesap Planı + roller + belge serilerini `database.py::_ensure_default_admin()` yanına ekler (bkz. yeni tablolar: `VatRate`, `ChartOfAccount`, `DocumentSeries`; `Currency`/`UnitDefinition`'a `is_system: bool` eklenmeli).
- [ ] **01.16** `setup_wizard.py` mevcut 6 adımdan (Hoş Geldin/Firma/Admin Güvenliği/Kurtarma Kodu/SMTP/Bitti) 8 adıma genişletilecek: + Dil/Lisans, + Veritabanı Bağlantısı, + Mali Dönem ve Para Birimi, + Modül Seçimi, + KDV/Numaralandırma; "Bitti" sayfası özet ekranına dönüşecek.
- [ ] **01.17** `main_window.py`'ye `SetupCompleted=false` gating eklenecek — admin, kurulum bitmeden yalnız "Kurulum Sihirbazı" + "Sistem Ayarları" menülerini görür.
- [ ] **01.18** [AÇIK SORU] Çoklu şirket mimarisi — her firmanın kendi mali dönemi, kasası, bankası olacağı düşünülürse, bunların DB'de (muhtemelen `company_id` FK ile) nasıl ayrıştırılacağı netleşmeli; bir sonraki oturumda ayrıca değerlendirilecek.
- [ ] **01.19** [AÇIK SORU] Her SQL yazma işleminde ekranın sağ alt köşesinde kısa bir bildirim/popup gösterme fikri (kullanıcı şeffaflığı) — hangi katmanda (ORM event listener mı, servis katmanı mı) uygulanacağı netleşmeli; henüz tasarlanmadı.
