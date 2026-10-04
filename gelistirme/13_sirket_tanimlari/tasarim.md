# 13 - ŞİRKET TANIMLARI ZORUNLULUĞU VE FİRMAYA BAĞLI AYARLAR

## Kullanıcı isteği (2026-09-30, birebir)
"Sistem bir yerde ilk defa kurulum paketi ile kurulduğunda standart en yetkili kullanıcı ile program
başlamalı. Ondan sonra eğer yok ise şirket tanımlamaya kullanıcı zorunlu tutulmalı. Eğer tanımlamıyorsa
tüm modüller pasif olarak ekranda gözükmeli, işlem yapılmamalı; işlem yapmayı denerse ilk önce şirket
tanımlarını yapın bölümüne aktarılmalı. Her şirketin kendi ayarları olmalı: KDV, birim, şube, depo, döviz
vs — ama en öncede dönem tanımları olmalı."

## Mevcut durum tespiti (uygulamaya başlamadan önce, araştırma ile doğrulandı)
- Kurulum sihirbazı (`src/desktop/ui/setup_wizard.py`) zaten var, içinde bir Firma sayfası da var — ama
  **zorunlu değil**: iptal edilebiliyor, `admin/admin` veritabanı boşken her zaman otomatik açılıyor
  (`src/core/database.py::_ensure_default_admin`), sihirbaz atlanırsa uygulama yine de açılıyor.
- `Company` modeli çok-şirketliliğe uygun ama kod tabanı tutarsız: `Customer`'da `company_id` kolonu hiç
  yok, `Product`'ta var ama çoğu çağrı yeri kullanmıyor, `Quotation`'da sabit `company_id=1` varsayılıyor.
- KDV ve Birim'in İKİŞER, birbirinden habersiz kaynağı vardı (catalog_picker/SystemSetting JSON vs Genel
  Ayarlar'daki ayrı generic tablo/gerçek model).
- Şube'nin gerçek bir veritabanı tablosu yoktu — sahte/serbest metin bir grid ("İlgili Firma" bile gerçek
  bir bağlantı değil, düz yazıydı).
- Depo ve Döviz'de `company_id` kolonu yoktu.
- **Dönem tanımları İKİ, birbirinden TAMAMEN BAĞIMSIZ kaynaktaydı**: biri Firma kartındaki gerçek
  `periods_json` (firmaya bağlı ama JSON blob, sorgulanamaz), diğeri Genel Ayarlar'daki tamamen sahte,
  company_id'siz, bununla hiç ilgisi olmayan ayrı bir panel (`generic_table.calisma_donemleri`).
- Modülleri pasifleştirecek İKİ ayrı altyapı var: izin bazlı `gate()` (canlı, `PermissionManager` sinyaliyle
  güncellenir) ve statik `IMPLEMENTED_MODULES` (sadece menü grid'ini kapsıyor, canlı değil, dar kapsamlı).
  "Şirket yok" durumu için ikisi de doğrudan yeterli değil, ayrı bir mekanizma gerekiyor.

## Mimari karar
Sistem "**tek aktif firma**" modeliyle çalışacak (Logo/Mikro tarzı): birden çok `Company` tanımlanabilir,
ama çalışma anında yalnızca biri aktiftir, `CompanyService.aktif_firma()` ile okunur/`aktif_firma_sec()` ile
değiştirilir (`SystemSetting` anahtarı `sistem.aktif_firma_id`). Gerçek eşzamanlı çoklu-firma (birden fazla
firmanın verisi aynı anda ayrı ayrı görünür) kapsam dışı bırakıldı — kod tabanı zaten tek-firma varsayımına
yakın, bu çok daha büyük bir iş olurdu.

**Düzeltme (2026-09-30, kullanıcı):** "Tek aktif firma" — dönem için GEÇERLİ DEĞİL. Bir firmanın AYNI ANDA
birden fazla dönemi aktif/açık olabilir (ör. yıl sonu kapanışında hem eski dönem düzeltme kayıtları hem yeni
dönemin ilk kayıtları birlikte girilebilmeli). `Donem.durum="aktif"` tekilliği ZORLANMAZ; her dönem bağımsız
açılır/kapatılır (`DonemService.aktif_yap`/`kapat`). Yeni bir belge/fiş için TEK bir varsayılan dönem önermek
gerektiğinde `DonemService.guncel_donem()` kullanılır (açık dönemler içinden bugünün tarihini kapsayanı, yoksa
en son başlayanı seçer) — ama bu yalnızca bir ÖNERİ/varsayılandır, kullanıcı başka açık bir döneme de
kaydedebilir.

## Aşamalar
- [x] **13.01 — Dönem tanımları (Faz 1, TAMAMLANDI 2026-09-30, kullanıcının açıkça en öncelikli dediği madde):**
  Gerçek, firmaya bağlı (`company_id` FK'li) `Donem` modeli (`src/core/models.py`) + `DonemService`
  (`src/desktop/services/donem_service.py`: `liste`, `kaydet`, `aktif_yap` — firma başına yalnızca bir dönem
  aktif kalır, `gizle`, Firma kartı alt-tablosu köprüsü `to_subtable`/`senkron_subtable`). `CompanyService`
  artık "periods" alanını bu servis üzerinden okuyup yazıyor (`periods_json` kolonu artık kullanılmıyor, ama
  geriye dönük uyumluluk için modelde duruyor). Genel Ayarlar'daki "Çalışma Dönemi Tanımları" paneli
  (`settings.py::build_calisma_donemi_panel` + yeni `_load_donem_tablosu`/`_save_donem_tablosu`) artık AYNI
  `Donem` tablosunu okuyup yazıyor — Firma kartındaki "Dönemler" ile ikilik bitti, tek gerçek kaynak var.
  `CompanyService.aktif_firma()`/`aktif_firma_sec()` eklendi (Faz 2-4'ün temeli). Esnek dönem (3 aylık/aylık)
  yapısal olarak zaten destekleniyor (serbest başlangıç/bitiş tarihi, yıl zorunluluğu yok). Ekran görüntüsüyle
  doğrulandı; mevcut testler (`test_firma_definition.py`, `test_general_settings_screen.py`,
  `test_settings_menu.py`, `test_yerel_para.py`) tek tek çalıştırılıp temiz geçti.
- [x] **13.02 — Şube/Depo/KDV/Birim firmaya bağlandı (TAMAMLANDI 2026-09-30), Döviz ERTELENDİ:**
  - **Şube:** Yeni `SubeTanimi` modeli (`company_id` FK, NOT NULL — yeni tablo) + `SubeService`
    (`src/desktop/services/sube_service.py`). Genel Ayarlar panelindeki sahte "İlgili Firma" serbest metin
    sütunu tamamen kaldırıldı (artık örtük: sadece aktif firmanın şubeleri gösteriliyor).
  - **Birim:** `UnitDefinition`'a `company_id` eklendi (nullable=True — MEVCUT tabloya eklenen sütun, geriye
    dönük uyumluluk için nullable; `DatabaseManager._ensure_compatibility_columns()` bir sonraki açılışta
    otomatik `ALTER TABLE` ile ekleyecek, elle migration gerekmiyor). `settings.py::_load_birimler_from_db`/
    `_save_birimler` aktif firmaya göre filtreleniyor; firmanın hiç birimi yoksa 12 varsayılan örnek
    (kaydedilmeden) öneriliyor.
  - **Depo:** `WarehouseDefinition`'a aynı şekilde nullable `company_id` eklendi, Genel Ayarlar paneli
    firmaya bağlandı. **BİLİNÇLİ SINIRLAMA:** `Product.warehouse_id` ve stok fişleri hâlâ TÜM depoları
    (firma filtrelemeden) görüyor — `stok_kart_editor.py::_load_warehouses()` bu aşamada değiştirilmedi
    (kapsamı büyük, riski yüksek; en riskli alt-adım olarak ayrı ele alınmalı).
  - **KDV:** Yeni `KdvTanimi` modeli (Kod/Açıklama/Oran/Durum, `company_id` FK, NOT NULL — yeni tablo),
    Genel Ayarlar "KDV Oranları" paneli buna bağlandı. **BİLİNÇLİ SINIRLAMA:** Stok Kartı'ndaki KDV %
    seçim kutuları hâlâ AYRI, global bir katalog kaynağı kullanıyor (`urun.kdv_tanimlari`,
    `catalog_picker.py`) — iki kaynağın birleştirilmesi `stok_kart_editor.py`'yi de değiştirmeyi
    gerektireceğinden bu aşamanın dışında bırakıldı, ayrı bir görev olarak ele alınmalı.
  - **Döviz — ERTELENDİ:** `Currency.rate`/`CurrencyRateHistory` TCMB/Serbest Piyasa'dan gelen, objektif
    piyasa verisi — firmaya göre ÇOĞALTILMAMALI (aynı USD/TRY kuru her firma için geçerli). Firmaya
    bağlanabilecek olan yalnızca "bu firma hangi dövizleri takip ediyor" seçimi; bu, diğerlerinden farklı
    bir tasarım gerektiriyor (basit `company_id` eklemek yanlış olur). Ayrı ele alınacak.
  - Ortak yardımcı `SettingsWidget._aktif_firma_uyar(ne_icin)` eklendi: hiç firma yoksa ve birden çok firma
    olup hiçbiri seçilmemişse FARKLI, doğru mesaj gösteriyor.
  - Tüm değişiklikler uçtan uca test edildi (gerçek kayıt/yükleme, firma değiştirince doğru izolasyon).
- [x] **13.03 — Modül pasifleştirme + "şirket tanımlarını yapın" yönlendirmesi (TAMAMLANDI 2026-09-30):**
  - **Sert engelleme (tek çıkış noktası):** `main_window.py::open_module_in_tab()` — yetki kontrolünden hemen
    sonra, `menu_name` `MODUL_FIRMA_MUAF` kümesinde değilse ve `CompanyService.aktif_firma() is None` ise
    modül AÇILMAZ; `_firma_tanimlamaya_yonlendir()` çağrılır. Bu tek dispatch noktası menü/kısayol/hızlı
    döşeme gibi TÜM yollardan geçtiği için gerçek engelleme buradan garanti ediliyor.
  - **Muaf modüller:** Ana Panel, Bildirimler, Genel Ayarlar (Firma Bilgileri'ne ulaşmak için gerekli),
    Görevler, Takvim, Geliştirme, İşlem Günlükleri — şirket verisiyle ilgisi olmayan kişisel/sistem araçları.
  - **Yönlendirme mantığı** (`_firma_tanimlamaya_yonlendir`): hiç firma yoksa `FirmaEditorDialog` açılır,
    kaydedilince otomatik aktif firma seçilir. Firma(lar) var ama hiçbiri aktif değilse (nadir: kullanıcı
    birden fazla firma tanımlamış ama seçmemiş) basitçe ilkini aktif yapar — ayrı bir "firma seç" ekranı
    bilinçli olarak bu aşamanın dışında bırakıldı.
  - **Görsel "pasif" gösterim** (`MenuPopup`, footer menü popup'ları — her açılışta yeniden kurulduğu için
    otomatik canlı): firma gerektiren ama tanımlı/aktif firma olmayan modüller `🔒 <isim>` etiketiyle, soluk
    renkte ama TIKLANABİLİR kalır (tıklanınca yönlendirme çalışsın diye) — mevcut, ayrı "(Yakında)" (henüz
    hiç geliştirilmemiş modül) mekanizmasıyla KARIŞTIRILMADI, ikisi birlikte doğru çalışıyor (test edildi).
  - `veri_bus.KONULAR`'a `"Company": ("firma",)` eklendi (ileride canlı yenileme gereken başka ekranlar için).
  - Yeni test dosyası `tests/test_firma_gating.py` (7 test) + mevcut 4 test dosyasında (`test_main_window.py`,
    `test_stok_kart_dialog.py` [2 test], `test_permission_gating.py`) modül açan testlere firma kurulumu
    eklendi (yeni ön koşul: bu testler artık aktif firma gerektiriyor — Görev 28 "onar" prensibiyle,
    testin ÖLÇTÜĞÜ özellik korunarak).
- [ ] **13.04 — Kurulum akışının gerçekten zorunlu hale getirilmesi (EN RİSKLİ adım, en sona bırakıldı):**
  `setup_wizard.py`'deki Firma sayfasının atlanamaz hale getirilmesi / `main.py` açılış akışına "aktif firma
  yoksa devam etme" kontrolü eklenmesi. Yanlış yapılırsa kullanıcıyı sistemin dışında bırakabilir — 13.02 ve
  13.03 sağlamca oturup test edildikten sonra yapılacak.

## ✅ 13.05 — Dönem UX + Firma Detayı yeniden düzenleme (TAMAMLANDI 2026-09-30)
Kullanıcı isteği: standart dbgrid, popup ile kayıt ekleme, takvim destekli tarih alanları (elle de yazılabilir),
Firma Detayı'nda Şube/Depo'nun gerçek tanımlardan dinamik çekildiği bir tab, Dönemler'in Logo/Kaşe-İmza ile
aynı satıra (2 sütun) inmesi, Adres & İletişim'in ayrı tab olmaktan çıkıp "3." bölüm olarak Kimlik tabına
sayfadaki diğer bölümlerle aynı düzende (numaralı başlık + çok sütunlu) gelmesi.

- **`DonemEkleDialog`** (`src/desktop/ui/widgets/donem_ekle_dialog.py`, yeni): Dönem Adı/Kodu + `QDateEdit`
  (takvim açılır pencereli `apply_calendar_style`, ama elle yazmaya da açık) başlangıç/bitiş + Aktif onay
  kutusu. HEM Genel Ayarlar'daki "Çalışma Dönemi Tanımları" panelinin "➕ Yeni Dönem Ekle" aksiyonu HEM Firma
  Detayı'ndaki "➕ Yeni Dönem" aksiyonu artık grid'e boş satır düşürmek yerine bu TEK popup'ı açıyor.
- **Firma Detayı "Kimlik" tabı yeniden düzenlendi** (`firma_editor.py::_build_firma_tabs`):
  - "3. Dönemler" + "4. Logo & Kaşe/İmza" ayrı satırlardan, TEK satırda 2 sütun (aynı bantta iki section) oldu
    (şimdi "4. Dönemler" | "5. Logo & Kaşe/İmza").
  - Eskiden AYRI bir "Adres & İletişim" tabı vardı; artık o tab YOK — içeriği "3. Adres ve İletişim" olarak
    Kimlik tabına, "1. Firma Kimliği"/"2. Vergi & Sicil Bilgileri" ile AYNI düzende (numaralı başlık, 2 sütun,
    Açık Adres `span:2`) taşındı. Alan adları (`address`, `city` vb.) değişmedi, sadece yerleşim değişti —
    geriye dönük veri uyumluluğu korundu.
- **Yeni "Şube & Depo Tanımları" tabı** (`_build_sube_depo_tab`, `editor.tabw.addTab(...)` ile eklendi —
  `DefinitionEditorScreen`'in JSON alan-şeması sistemine değil, CANLI DB sorgusuna dayanıyor çünkü Şube/Depo
  artık gerçek, ayrı tablolar — bkz. 13.02): iki sütun (Şube | Depo), her biri `standart_grid` (aynı standart
  `FilterableTableView`/`EntryTableView` çekirdeği), "➕ Yeni Şube"/"➕ Yeni Depo" küçük popup'larla
  (`_KayitEkleDialog`, genel amaçlı metin-alanlı mini form) AYNI ANDA hem bu firmaya hem Genel Ayarlar'daki
  ortak tanımlara yazıyor (aynı `SubeService`/`WarehouseDefinition`). Firma henüz kaydedilmemişse (yeni kart)
  ekleme düğmeleri kullanıcıyı "önce kaydedin" diye uyarır, çökmez. "Kaydet ve Yeni" sonrası liste doğru
  şekilde temizleniyor.
- Ekran görüntüleriyle doğrulandı (Kimlik tabı yeni düzen, Dönem popup, Şube & Depo tabı). 4 yeni test
  (`test_firma_definition.py`) + 1 yeni test (`test_settings_menu.py`) eklendi, tüm ilgili test dosyaları
  tek tek çalıştırılıp temiz geçti.

## ✅ 13.06 — Firma Detayı ikinci tur istekler (TAMAMLANDI 2026-09-30)
- **Logo & Kaşe/İmza** bölümü içi tekrar 2 sütun (Logo | Kaşe-İmza yan yana) — Dönemler ile aynı satırı
  paylaşması bunu bozmuyor, iç içe 2 sütun + dış 2 sütun bir arada çalışıyor.
- **Çalışma Para Birimi**: "💱 Döviz Tanımlarını Yönet" aksiyonu eklendi (sol İŞLEMLER paneli) — Genel
  Ayarlar'ın "Döviz & Kur" panelini maksimize bir diyalogda açar (`GeneralSettingsScreen(...).switch_panel
  ("doviz_kur")`), kullanıcı o ekranın TÜM işlemlerini yapıp kapattığında "Çalışma Para Birimi" combosu
  güncel aktif döviz listesiyle otomatik tazelenir.
- **`DefinitionEditorScreen`'e genel, yeniden kullanılabilir "date" alan tipi eklendi** (`_make_field`/
  `set_data`/`collect`, `QDateEdit` + `apply_calendar_style` — takvimden seç VEYA elle yaz, ikisi de çalışır).
  Modülün kendi docstring'i zaten bu tipi "desteklenen" diye listeliyordu ama hiç uygulanmamıştı — bu hem
  eksikliği giderdi hem TÜM `DefinitionEditorScreen` tabanlı ekranlarda (Cari, Stok, Kullanıcı, Rol, Finans
  Hesap) kullanılabilir hale geldi. "Kuruluş Tarihi" (`founded_at`) bu yeni tipi kullanan ilk alan.
- **Dönemler**: silme artık onay istiyor ("...tüm bilgiler silinecek, devam edilsin mi?" — gerçek DB silme
  değil, mevcut `senkron_subtable` soft-delete akışına Kaydet'te bağlanıyor); grid içi Başlangıç/Bitiş
  sütunları artık `DateDelegate`, Aktif sütunu `ComboDelegate` (Evet/Hayır) — HEM Firma Detayı'ndaki
  alt-tabloda HEM Genel Ayarlar'daki "Çalışma Dönemi Tanımları" panelinde (Aktif/Kapalı) aynı delegeler.
  `_SubTableField`'e genel `delete_confirm` parametresi ve kolon başına `"type": "date"|"combo"` desteği
  eklendi (yalnız Dönemler kullanıyor, Yetkililer/Ortaklar/Banka Hesapları eskisi gibi düz metin kalıyor).
- **Şube & Depo Tanımları tabı**: artık "✏️ Düzenle" ve "🗑️ Sil" de var (önceden yalnız "➕ Ekle" vardı) —
  gerçek `SubeService`/`WarehouseDefinition` kayıtlarını günceller/gizler, aynı `_KayitEkleDialog` popup'ı
  önceden doldurulmuş olarak düzenleme için de kullanılıyor.
- **Yetkililer/Ortaklar/Banka Hesapları**: kontrol edildi, DÜZENLEME (hücreler zaten editable) ve SİLME
  (işaretle + "Seçili Satırları Sil" / sağ tık) zaten vardı — yeni bir şey eklenmedi, doğrulandı.
- **"Kaydet" artık ekranı kapatmıyor** — kaydedip aynı kartta kalınıyor ("Kaydet ve Yeni" hâlâ formu
  temizliyor, değişmedi). Yeni kayıt ilk kaydedilince `company_id` otomatik set edilip ikinci "Kaydet" artık
  GÜNCELLEME yapıyor (yeni bir firma OLUŞTURMUYOR); "Firma Kodu" alanı ilk kayıttan sonra kilitleniyor
  (`lock_on_edit`, tam `set_data(is_edit=True)` çağırmadan, girilen diğer alanlar kaybolmadan). Bu değişiklik
  `main_window.py::_firma_tanimlamaya_yonlendir()`'i de etkiledi — artık `dlg.exec()`'in kapanış sonucuna
  değil, `dlg.saved_company_id`'nin dolu olup olmadığına bakıyor (kaydedip pencereyi açık bırakan kullanıcı
  da aktif firma olarak doğru seçiliyor).
- 9 yeni test eklendi (`test_firma_definition.py`), gerçek bir regresyon da bu süreçte yakalanıp düzeltildi:
  Genel Ayarlar'daki Dönem grid delegeleri yanlışlıkla `self.tbl_donem.table_view` üzerinden kuruluyordu
  (`_new_grid` zaten doğrudan `EntryTableView` döndürüyor, `.table_view` diye bir öznitelik yok) — bu,
  "Genel Ayarlar" (muaf modül) her açıldığında `AttributeError` ile çökerdi; geniş regresyon taraması
  (`test_firma_gating.py`) sayesinde yakalandı, `self.tbl_donem` doğrudan kullanılarak düzeltildi.

## ✅ 13.07 — Genel Ayarlar menüsü sadeleştirme (TAMAMLANDI 2026-10-01)
- Kullanıcı isteği: "Şube ve Depo Tanımları, Çalışma Dönemi Ayrı menuler olarak olmadı onları kaldıralım,
  Firma Tanımları içinde zaten var, genel bir tanım değil. Döviz Tanımları Finansal Ayarlar bölümüne alınsın."
  Gerekçe: Şube/Depo/Dönem artık (13.05/13.06) Firma Detayı ekranındaki "Şube & Depo Tanımları" tabı ve
  "Dönemler" alt-tablosu üzerinden, FİRMAYA ÖZGÜ olarak yönetiliyor — Genel Ayarlar'da AYRICA genel/ortak bir
  menü olarak durmaları kafa karıştırıcı ve gereksiz tekrar.
- **`settings.py`**: `MENU_STRUCTURE`'dan "Şube Tanımları"/"Depo Tanımları"/"Çalışma Dönemi" kaldırıldı
  (ŞİRKET TANIMLARI grubu artık yalnız "Firma Bilgileri"); "Döviz & Kur" FİNANS TANIMLARI grubuna taşındı
  (artık o grubun ilk öğesi). İlgili panel builder'lar (`build_sube_panel`, `build_calisma_donemi_panel`,
  `build_depo_panel` + yardımcı metodları + `_VARSAYILAN_DEPOLAR`), sidebar hızlı-işlem grupları, kayıt
  ekle/sil `panel_table_map` girişleri ve kullanılmayan `WarehouseDefinition` import'u silindi.
  `DonemService`/`SubeService`/`KdvTanimi` servisleri DOKUNULMADI (Firma Detayı hâlâ kullanıyor).
- **`settings_menu.py`**: `ITEM_CODES`'tan `sube_tanimlari`/`depo_tanimlari`/`calisma_donemi` kaldırıldı;
  `doviz_kur` kodu FİNANS TANIMLARI grubundaki yeni konumunu yansıtacak şekilde yeniden numaralandırıldı
  (`sys.set.300`), `banka_tanimlari`/`odeme_planlari`/`fiyat_listeleri` buna göre kaydırıldı.
- **`settings_hub_widget.py`** (Genel Ayarlar'ın ikonlu karşılama panosu — "Ayarlar Panosu"): aynı 3 kart
  kaldırıldı, "Döviz & Kur" kartı "BANKA & FİNANS TANIMLARI" bölümüne taşındı.
- **Varsayılan açılış ekranı değişti**: `GeneralSettingsScreen.__init__` artık `switch_panel("firma_bilgileri")`
  yerine `switch_panel("settings_hub")` çağırıyor — kullanıcının asıl şikayeti ("Genel Ayarlara girdiğimde
  hala eski şekilde geliyor") buydu: ikonlu pano zaten vardı ve "🏠 Ayarlar Panosu" düğmesiyle manuel
  ulaşılabiliyordu ama ekran AÇILIŞTA eski (düz liste + Firma Bilgileri) görünümde başlıyordu. `switch_panel`
  zaten "settings_hub" için özel davranıyordu (sol/sağ panelleri kapatıp geniş/sade görünüm veriyordu) — bu
  mekanizma hazırdı, sadece varsayılan olarak kullanılmıyordu.
- **Testler**: `test_calisma_donemi_yeni_donem_ekle_grid_e_bos_satir_degil_popup_acar` silindi (artık var
  olmayan bir özelliği test ediyordu — Dönem ekleme akışı zaten `test_firma_definition.py`'de Firma Detayı
  üzerinden test ediliyor). `test_every_menu_has_a_unique_code_and_every_group_too` ve
  `test_all_definition_tables_are_standard_entry_grids_with_theme_style` yeni menü/tablo kümesine göre
  güncellendi. `test_settings_menu.py`, `test_general_settings_screen.py`, `test_firma_definition.py`,
  `test_firma_gating.py`, `test_master_definitions.py` tek tek çalıştırılıp temiz geçti.

## Dokunulmayan / bilinçli kapsam dışı
- Gerçek eşzamanlı çoklu-firma (aynı anda birden fazla firmanın verisi ayrı pencerelerde/oturumlarda) —
  yukarıda gerekçelendirildi.
- `Customer`/`Product`/`Quotation` gibi modellerin `company_id` tutarsızlıklarının TAMAMI bu kapsamda
  düzeltilmiyor; yalnızca Dönem (ve Faz 2'de Şube/Depo/KDV/Birim/Döviz) ele alınıyor.
