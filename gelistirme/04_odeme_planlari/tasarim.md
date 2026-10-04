# 04 - ÖDEME PLANLARI: "CANLI" OTOMASYON SİSTEMİ

## Kullanıcı isteği (2026-10-02, birebir)
"ÖDEME planlarına bakalım istersen fatura irsaliye gibi yerlerde dinamik olarak tanımlardan getirmesini
sağlayalım ama ödeme planları sisteminin yaşayan bir sistem olması lazım faturada nakit ödeme seçilmiş ise
(genelde muhasebe programları nakit fatura işlemini kasa işlemlerinin içinden takip etmeyi tercih etmişler)
kasa işlemde fatura kaydedildikten hemen sonra otomatik olarak yapılarak kullanıcının işlemleri
kolaylaştırılıyor. Gelen Havale Giden Havale gibi işlemlerde banka ödeme planları da dahil edilerek banka
fişi de arka planda otomatik oluşuyor; kredi kartı ile ödeme ise yine banka ödeme planı ile banka fişi
oluşturuluyor. POS işlemlerinde yapılan yine banka ödeme planı ile POS fiş listesine alınıyor; parametrik
yapı ile otomatik ödeme ile banka hesabından pos hesabına aktarılması sağlanıyor. Şimdi aklıma gelmeyen
ödeme tiplerini yine araştırırım ama ödeme planları widget'ını bu yönde geliştirmek için sen ne dersin."

## Mevcut durum tespiti (uygulamaya başlamadan önce, kod taraması ile doğrulandı)
- `PaymentPlan` (`src/core/models.py:811-819`, tablo `payment_plans`) **zaten gerçek bir model** — sadece
  5 alanı var: `code`, `description`, `days`, `payment_type` (serbest metin), `is_active`. Genel Ayarlar'ın
  "Ödeme Planları" paneli (`settings.py::build_odeme_planlari_panel`) zaten bu tabloyu okuyup yazıyor —
  düz bir metin grid'i olsa da altyapı sahte değil, gerçek tablo.
- `Quotation.payment_plan` (teklif/sipariş/irsaliye/fatura'nın hepsini kapsayan tek model) **sadece serbest
  metin** — `PaymentPlan` tablosuna FK DEĞİL. Fatura/İrsaliye ekranındaki "Ödeme Planı" kombosu
  (`transaction_document_dialog.py`, `cmb_odeme_plani`) Ödeme Planları satırlarından metin listesi besleniyor
  ama seçilen şey kaydedilirken yalnız `currentText()` string'i yazılıyor — hangi plana ait olduğu kayıt
  sonrası kaybediliyor, yapılandırılmış bir bağlantı yok.
- **Kasa/Banka/Kredi Kartı/POS hesapları zaten TEK ortak tabloda:** `FinansHesap` (`models.py:1113-1136`,
  `tur`: kasa|banka|kredi_karti|pos). POS'a özel alanlar (`komisyon_orani`, `uye_isyeri_no`, `valor_gun`)
  **zaten var** — bu çalışma bunları sıfırdan tanımlamaz, kullanır.
- **Kasa/Banka hareket altyapısı da zaten var ve ÇALIŞIYOR** (manuel giriş için): `FinansFis` + `FinansHareket`
  (`models.py:1218-1266`) + `FinansFisService` (`src/desktop/services/finans_fis_service.py`). Fiş satırı bir
  hesaba girer/çıkar (`yon`); **virman satırı zaten var** — `hesap_id`'den çıkıp `karsi_hesap_id`'ye giren tek
  satır (`gelistirme/08_banka/fields_and_schema.md`'de "Kasa'dan banka hesabına virman" olarak doğrulanmış).
  Yani **POS→Banka aktarımı için yeni bir model GEREKMİYOR** — mevcut virman satırını otomatik üretmek yeterli.
- Cari hareket tarafında da zemin hazır: `CariHareket.odeme_araci` alanı zaten
  `nakit|banka|cek|senet|kredi_karti` değerlerini öngörüyor (yorum satırında belgelenmiş), `fin_hesap_id` ile
  `FinansHesap`'a bağlanabiliyor.
- **Kullanıcı ön koşulu (2026-10-02): "virman işlemlerinde alan/veren taraf — borç girilmişse alacak
  zorunlu olsun" kontrolü.** Kod taramasıyla doğrulandı: bu kural CARİ virman fişinde (`virman_borc`/
  `virman_alacak` satır türleri, `cari_hareket_service.py::fis_kaydet`, satır ~223) **ZATEN VAR ve test
  edilmiş** (`tests/test_cari_hareket_screen.py::test_virman_fisi_borc_alacak_esit_olmali_acilis_ve_cari_turleri`)
  — borç/alacak toplamları `0.01`den fazla farklıysa (ya da alacak satırı hiç girilmemişse) "Virman
  fişinde borç ve alacak toplamları eşit olmalıdır" hatasıyla kaydetmeyi engelliyor; `FisDialogBase` bunu
  `QMessageBox` ile kullanıcıya gösteriyor. KASA/BANKA virman'da (`FinansHareket`, `kasa_virman`/
  `banka_virman`) ise risk zaten yapısal olarak yok — tek satır, tek tutar, `hesap_id`→`karsi_hesap_id`
  otomatik simetrik (ayrı borç/alacak girişi yok, dolayısıyla dengesizlik mümkün değil). Ek bir değişiklik
  gerekmedi; 04.09'daki otomatik POS→Banka virman'ı da bu simetrik tek-satır deseniyle üretileceği için
  aynı güvenceyi doğal olarak taşıyacak.
- **Eksik olan, net:** Fatura/İrsaliye kaydedilince hiçbir otomatik kasa/banka/POS hareketi üretilmiyor —
  bu "sonraki adım" daha önce de 07_kasa ve 08_banka dokümanlarında ayrı ayrı not düşülmüş
  ("Cari fişindeki Araç=Kasa/Banka satırlarından otomatik hareket üretimi" — ikisi de `[ ]` işaretli,
  hâlâ yapılmamış) ama hiçbir yerde kodlanmamış. `money_service.py` ve `cari_hareket_service.py`'de bu
  yönde hiçbir çağrı yok.
- **Çek/Senet: sıfırdan.** `gelistirme/09_cek_senet/fields_and_schema.md`'de tam bir tasarım var ama kod
  tarafında hiçbir model/servis/ekran yok — bu, bu çalışmanın kapsamı DIŞINDA, kendi ayrı, büyük bir iş.
- **POS→Banka parametrik otomatik aktarım: hiç yok.** `valor_gun` alanı kartta duruyor ama onu okuyup
  gerçekten bir virman üreten hiçbir kod/zamanlayıcı yok.

## Mimari karar
Yeni bir "kasa/banka modülü" kurulmuyor — **var olan `FinansHesap`/`FinansFis`/`FinansHareket`/
`FinansFisService` altyapısı üzerine, onu TETİKLEYEN bir otomasyon katmanı ekleniyor.** Bu hem daha az riskli
(mevcut, test edilmiş, manuel akışla aynı kod yolunu kullanıyor — iki paralel "kasa hareketi yaratma" yolu
olmuyor) hem de DRY (bkz. pinned "DRY/metadata mimarisi" kuralı).

Üç parça:
1. **`PaymentPlan` genişletilir** (mevcut tabloya nullable kolon eklenir — `DatabaseManager.
   _ensure_compatibility_columns()` otomatik `ALTER TABLE` yapar, elle migration gerekmez):
   - `odeme_tipi` (yapılandırılmış, serbest metin DEĞİL): `nakit | havale_eft | kredi_karti | pos |
     acik_hesap | cek | senet`. (`cek`/`senet` seçilebilir ama Faz 6'ya kadar otomatik fiş üretmez —
     aşağıda açıklanıyor.)
   - `hedef_finans_hesap_id` (FK → `finans_hesap.id`, nullable) — bu plan seçildiğinde hangi kasa/banka/POS
     hesabına düşeceği varsayılanı. Boş bırakılabilir; o zaman kullanıcı fatura ekranında hesabı seçer.
   - `otomatik_fis_olustur` (bool, varsayılan True) — bazı firmalar otomasyonu açıkça istemeyebilir; plan
     bazında kapatılabilir.
2. **`Quotation`'a `payment_plan_id` (FK → `payment_plans.id`, nullable) eklenir.** Mevcut `payment_plan`
   (string) alanı SİLİNMEZ — geriye dönük uyumluluk ve eski kayıtların görünümü için kalır, ama yeni
   kayıtlarda asıl kaynak artık FK olur (`Donem`/`SubeTanimi` ile aynı "yeni tabloya FK, eskiyi bozma"
   deseni — bkz. `13_sirket_tanimlari/tasarim.md` 13.01-13.02).
3. **Yeni, paylaşılan `OdemePlaniOtomasyonServisi`** (`src/desktop/services/odeme_plani_otomasyon_servisi.py`):
   belge kaydedildikten SONRA çağrılır (fatura ekranındaki `save_document()`'ın sonunda, tek çağrı noktası —
   `main_window.py::open_module_in_tab()`'daki "tek dispatch noktası" deseniyle aynı mantık: işin UI tarafına
   her ekrana ayrı ayrı yazmak yerine TEK yerden). `Quotation.payment_plan_id` → `PaymentPlan.odeme_tipi`'ne
   bakar, `otomatik_fis_olustur` açıksa `FinansFisService` üzerinden (AYNI servis, manuel girişle birebir
   aynı kod yolu) uygun fişi oluşturur:
   - `nakit` → Kasa Tahsilat fişi (hedef hesap: `hedef_finans_hesap_id` veya kullanıcıya sor).
   - `havale_eft`, `kredi_karti` → Banka fişi (Gelen Havale / Kredi Kartı tahsilatı türünde).
   - `pos` → Banka fişi (hesap `tur=pos`) + aşağıdaki parametrik virman.
   - `acik_hesap` → **hiçbir otomatik fiş yok** (bugünkü davranışla aynı, sadece cari borç kalır).
   - `cek`, `senet` → Faz 6'ya kadar otomatik fiş YOK; yalnızca bilgi notu ("Çek/Senet modülü henüz
     gerçek kayıt tutmuyor, cari borç olarak işlendi") gösterilir — sessizce yok sayılmaz.
   - Her otomatik oluşan fişe, kaynağı olan belgeye geri referans (`FinansFis`'e yeni nullable
     `kaynak_belge_id` kolonu → `quotations.id`) yazılır — **tersine çevrilebilirlik** için şart (pinned
     "audit log ve tersine çevrilebilirlik" kuralı): fatura iptal/silinirse otomatik fiş de bulunup
     gizlenebilsin, kullanıcı otomatik oluşan fişi açıp düzenleyebilsin.
   - Otomasyon SESSİZ ÇALIŞMAZ: fatura kaydedilince "✅ Fatura kaydedildi — K000045 nolu Kasa Tahsilat fişi
     otomatik oluşturuldu" gibi açık bir bildirim gösterilir (toast/durum çubuğu), kullanıcı fişi tek tıkla
     açabilir.

**POS→Banka parametrik otomatik aktarım** (kullanıcının "parametrik yapı" dediği kısım): yeni model
gerekmiyor — `FinansHareket`'in zaten var olan virman deseni (`hesap_id`=POS hesabı → `karsi_hesap_id`=banka
hesabı) kullanılır. Parametre: `FinansHesap.valor_gun` (zaten kartta var) — "N gün sonra POS hesabındaki
bakiye otomatik bankaya aktarılsın" switch'i Genel Ayarlar'da (Finans Tanımları altında, bkz. 13.07) açılır/
kapanır; gerçekleştirme ya uygulama açılışında "vadesi gelenleri kontrol et" taraması ile ya da kullanıcı
"POS Mahsup" ekranından elle tetikleyerek olur (gerçek bir arka plan zamanlayıcısı — uygulama kapalıyken
çalışan bir servis — bu masaüstü uygulamada yok ve bu çalışmanın kapsamında KURULMUYOR; "uygulama her
açıldığında / Kasa-Banka ekranı her girildiğinde vadesi gelmiş POS mahsupları var mı diye bak" modeli
kullanılacak).

## Aşamalar
- [x] **04.05 — `PaymentPlan` genişletme (TAMAMLANDI 2026-10-02):** `odeme_tipi` (yapılandırılmış kod:
  nakit|havale_eft|kredi_karti|pos|acik_hesap|cek|senet), `hedef_finans_hesap_id` (FK → `finans_hesap.id`),
  `otomatik_fis_olustur` (bool, varsayılan True) kolonları eklendi — mevcut tabloya nullable sütun, elle
  migration gerekmedi (`_ensure_compatibility_columns()` otomatik `ALTER TABLE` yapar; bool default'un
  `DEFAULT 1` olarak ALTER'a düştüğü doğrulandı). Genel Ayarlar'daki "Ödeme Planları" paneli
  `DefinitionEditorScreen`'e TAŞINMADI (o kadar büyütmeye gerek yoktu) — bunun yerine mevcut `_new_grid`
  dbgrid'ine Dönem/Şube'de de kullanılan `ComboDelegate` ile 3 yeni sütun eklendi: "Ödeme Tipi" (artık
  serbest metin değil, 7 sabit seçenekten biri), "Hedef Hesap" ("KOD — Ad" biçiminde, `FinansHesap`'tan
  canlı sorgulanır, boşsa "(Seçilmedi)"), "Otomatik Fiş" (Evet/Hayır). Mevcut 7 varsayılan plan eşlendi
  (`NAKIT`→`nakit`, `60GUNKK`/`CF3TAK`→`kredi_karti` — taksit bilgisi `description`'da kalıyor, diğerleri
  →`acik_hesap`). Ekran görüntüsüyle doğrulandı, yeni test eklendi
  (`test_odeme_planlari_odeme_tipi_hedef_hesap_banka_plani_ve_otomatik_fis_kaydedip_geri_yuklenir`), ilgili
  test dosyaları (`test_settings_menu.py`, `test_general_settings_screen.py`, `test_cari_stok_editors.py`)
  temiz geçti.
- [x] **04.05b — Popup ekleme + Banka Ödeme Planları (TAMAMLANDI 2026-10-02, kullanıcı isteği):** Kullanıcı:
  "ödeme planları tanımlamaları popup pencere ile olsun ayrıca liste üzerinde de hızlı düzenlemede kalsın
  ... banka ödeme planları ... ayrı bir menü ile olsun."
  - **Popup ekleme:** `OdemePlaniEkleDialog` (`src/desktop/ui/widgets/odeme_plani_ekle_dialog.py`) —
    `DonemEkleDialog` ile AYNI desen (form + Kaydet/Vazgeç, `deger()` dict döner, grid'e satır olarak
    eklenir/günceller). "➕ Yeni Plan Ekle" artık bunu açıyor, YENİ "✏️ Seçiliyi Düzenle" seçili satırı
    önceden doldurup açıyor. Grid hücreleri DOĞRUDAN hâlâ düzenlenebilir — popup EK bir giriş yolu, var
    olan hızlı düzenlemeyi kaldırmadı.
  - **`BankaOdemePlani` modeli (yeni tablo, `banka_odeme_planlari`):** `kod`, `aciklama`,
    `finans_hesap_id` (FK, opsiyonel), `taksit_sayisi`, `komisyon_orani` (%), `bsmv_orani` (%, varsayılan
    5.0), `hizmet_bedeli` (sabit TL), `is_active`. `net_tutar(brut_tutar)` metodu: BSMV, KOMİSYON TUTARI
    üzerinden hesaplanır (Türkiye'de banka/finans kuruluşu komisyonlarının standart vergilendirme biçimi —
    araştırıldı), hizmet bedeli sabit kesinti. `FinansHesap.komisyon_orani` (tek, sabit oran) ile
    KARIŞTIRILMAMALI — bu model TAKSİT SAYISINA göre değişen, daha ayrıntılı bir yapı.
  - **Dinamik bağlantı:** `PaymentPlan.banka_odeme_plani_id` (FK, nullable) eklendi — Ödeme Planları
    grid'ine "Banka Ödeme Planı" sütunu (ComboDelegate, `BankaOdemePlani`'dan canlı) geldi; yalnız Kredi
    Kartı/POS/Havale gibi banka ile ilgili tiplerde anlamlı (UI düzeyinde zorunlu kılınmadı — isteğe
    bağlı).
  - **Ayrı menü:** "Banka Ödeme Planları" (`banka_odeme_planlari`), FİNANS TANIMLARI grubunda Ödeme
    Planları'nın hemen altında (`sys.set.303`, Fiyat Listeleri `sys.set.304`'e kaydı); kendi popup'ı
    (`BankaOdemePlaniEkleDialog`) ve grid'i (Kod/Açıklama/Hesap/Taksit Sayısı/Komisyon %/BSMV %/Hizmet
    Bedeli/Durum) var. Ayarlar Panosu'ndaki ikonlu karşılama ekranına da kart olarak eklendi.
  - Ekran görüntüleriyle doğrulandı (panel + iki popup). 2 yeni test eklendi. Bir test, tam takım
    `test_settings_menu.py` koşusunda (42 test) dosyanın EN SONUNDA çalışınca `pytest-timeout` ile 30s'de
    kesilen bir "teardown hang" ortaya çıkardı (conftest'teki bilinen "çok widget birikince" sınıfı sorun —
    bkz. `_cleanup_qt_widgets` docstring'i); testin içine `qapp.processEvents()` eklenerek (ComboDelegate'in
    `self`/ekranı canlı tuttuğu `s.close()` sonrası gerçek Qt temizliğinin işlenmesi için) giderildi, 3 kez
    art arda tam takım koşusu temiz geçti.
- [x] **04.06 — `Quotation.payment_plan_id` FK + ekran bağlantısı (TAMAMLANDI 2026-10-02):** Kod taramasında
  önemli bir şey ortaya çıktı: Fatura/İrsaliye'nin ASIL/VARSAYILAN ekranı artık `DocumentDetailScreen`
  (`TransactionDocumentDialog` yalnız `TOYA_OLD_DOC_DIALOG=1` ortam değişkeniyle açılan eski/opsiyonel
  ekran — bkz. `quotations.py:48-56`). `DocumentDetailScreen`'in Ödeme Planı kombosu
  (`BelgeVadeWidget._get_plans()`) **zaten** `PaymentPlan` tablosundan CANLI okuyordu — kullanıcının
  "dinamik olarak tanımlardan getirmesini sağlayalım" isteği o ekranda ZATEN karşılanmıştı, eksik olan
  yalnızca gerçek ID'nin kaydedilmesiydi.
  - `Quotation.payment_plan_id` (FK → `payment_plans.id`, nullable) eklendi; eski `payment_plan` (string)
    alanı AYNEN kalıyor (ikisi birden yazılır, FK asıl kaynak — `Donem`/`SubeTanimi` ile aynı "yeni FK,
    eskiyi bozma" deseni).
  - `BelgeVadeWidget._get_plans()`'ın döndürdüğü dict'e `"id": r.id` eklendi; `get_data()` artık
    `"odeme_plani_id"` de döndürüyor; `set_data()` ÖNCE ID'ye göre (yeni kayıtlar), bulamazsa metne göre
    (eski kayıtlar) kombo satırını seçiyor.
  - `QuotationSaveService.save_payload`/`load_payload` (DocumentDetailScreen'in kullandığı dict tabanlı
    yol) ve `_set_belge`/dönüştürme (teklif→sipariş) akışı `payment_plan_id`'yi okuyup yazacak şekilde
    güncellendi.
  - **Eski/opsiyonel `TransactionDocumentDialog` da tutarlılık için düzeltildi:** `ODEME_PLANLARI` sabit
    listesi artık yalnızca DB'ye erişilemediğinde devreye giren bir YEDEK — yeni `_odeme_planlari_yukle()`
    metodu `BelgeVadeWidget._get_plans()` ile AYNI deseni kullanıp DB'den canlı okuyor, "id" alanını da
    taşıyor; `save_from_dialog` da `payment_plan_id`'yi yazıyor.
  - 3 yeni test eklendi (`test_document_detail_screen.py`, `test_quotation_save_service.py`); ilgili test
    dosyaları (`test_quotation_save_service.py` 7/7, `test_document_detail_screen.py` 32/32) temiz geçti.
  - **Bulunan ama DOKUNULMAYAN, kapsam dışı bir bulgu:** `tests/test_gorev20.py` ve `test_gorev21.py`
    `TransactionDocumentDialog.cari_widget`/`._sc_f6` gibi, ne bu dosyada ne de son commit'te (HEAD) hiç
    var olmamış öznitelikler bekliyor — bu çalışmadan ÖNCE de kırıktı (HEAD karşılaştırmasıyla doğrulandı,
    benim değişikliğimle ilgisi yok), muhtemelen bu dosya üzerinde eş zamanlı yürüyen başka bir işin
    (Numara Şablonları/`DocumentSeries` ile ilgili, git status'ta aynı dosya değişiklik listesinde görünüyor)
    yarım kalmış bir parçası. Dokunmadım — onların işini bozmamak için.
- [x] **04.07 — `OdemePlaniOtomasyonServisi` + Nakit akışı (TAMAMLANDI 2026-10-02):** Fatura (ya da iade
  faturası — `belge_turleri.CARI_ETKILI`) kaydedilip Ödeme Planı'nın `odeme_tipi="nakit"` ise, kayıttan
  HEMEN SONRA otomatik Kasa Tahsilat fişi oluşuyor — tam olarak kullanıcının tarif ettiği "nakit fatura
  işlemini kasa işlemlerinin içinden takip etme" akışı.
  - `FinansFis.kaynak_belge_id` eklendi (FK → `quotations.id`, nullable) — fişin hangi belgeden otomatik
    doğduğunu izler; tersine çevrilebilirlik için şart.
  - Yeni `OdemePlaniOtomasyonServisi` (`src/desktop/services/odeme_plani_otomasyon_servisi.py`):
    manuel girişle AYNI `FinansFisService.fis_kaydet()` kod yolunu kullanıyor (iki paralel "fiş yaratma"
    yolu yok). Tekrar kaydedilince AYNI fişi/satırı GÜNCELLİYOR (yeni satır eklemiyor, eskisini
    soft-delete ile gizlemiyor) — gereksiz fiş geçmişi şişmiyor. Koşullar artık sağlanmıyorsa (ödeme tipi
    nakitten başka bir şeye çevrildi, hedef hesap kaldırıldı, tutar sıfırlandı) önceki otomatik fiş
    `fis_gizle()` ile GERİ ALINIYOR — otomasyon asla geçersiz bir fişi ortada bırakmıyor.
  - `DocumentDetailScreen._persist()` (TEK gerçek kayıt noktası — save/save-and-stay/save-and-new/
    save-and-print hepsi buradan geçiyor) kayıt başarılı olduktan sonra otomasyonu çalıştırıyor.
    **Sessiz otomasyon değil:** oluşan/güncellenen fiş varsa alt bardaki durum mesajına
    ("✓ Kaydedildi · K000001 nolu Kasa Tahsilat fişi otomatik oluşturuldu") ekleniyor, mesaj normalden
    daha uzun (5sn) ekranda kalıyor.
  - 7 yeni test eklendi (`test_odeme_plani_otomasyon_servisi.py`: oluşturma, tekrar kaydedince güncelleme/
    duplicate olmaması, tip değişince geri alma, plan yok/otomatik kapalı/hedef hesap yok senaryoları,
    irsaliye'de çalışmaması; `test_document_detail_screen.py`: uçtan uca kaydet→fiş oluştu→bildirim).
    İlgili test dosyaları (`test_odeme_plani_otomasyon_servisi.py`, `test_document_detail_screen.py`,
    `test_finans_fis.py`) toplam 58 test, temiz geçti.
- [x] **04.08 — Havale/EFT + Kredi Kartı akışı (TAMAMLANDI 2026-10-02):** 04.07'de yazılan tek-tip
  (`_kasa_tahsilat`) kod paylaşılabilir bir desene (`_fis_olustur_veya_guncelle(q, plan, mevcut, grup, tur,
  etiket)`) refactor edildi; `_AKIŞLAR` eşlemesi (`odeme_tipi` → (grup, fiş/satır türü, etiket)) ile
  `havale_eft` ve `kredi_karti` eklendi — ikisi de `FinansFisService`'in `"havale_gelen"` ("Gelen Havale")
  türüyle Banka fişine düşüyor (kredi kartı tahsilatı için ayrı bir fiş türü kodu yok; hangi hesaba
  düştüğü zaten `FinansHesap.tur` ile ayrışıyor — `kredi_karti` türü `GRUP_HESAP_TURLERI["banka"]` içinde
  kabul ediliyor). Kullanıcıya gösterilen etiket farklı ("Gelen Havale" / "Kredi Kartı Tahsilatı") ama
  altta aynı mekanizma — design doc'taki "kredi kartı ile ödeme ise yine banka ödeme planı ile banka fişi
  oluşturuluyor" isteğiyle birebir örtüşüyor. 2 yeni test eklendi (toplam 60 test, ilgili 3 test dosyası
  temiz).
- [x] **04.09 — POS akışı + parametrik POS→Banka virman (TAMAMLANDI 2026-10-02):**
  - **Fatura→POS akışı:** `_AKIŞLAR`'a `"pos": ("banka", "havale_gelen", "POS Tahsilatı")` eklendi —
    04.08'deki kredi kartı akışıyla birebir aynı desen, hedef hesap POS türünde bir `FinansHesap`.
  - **Parametrik POS→Banka otomatik mahsup:** Tasarımda "Genel Ayarlar'a parametre anahtarı" planlanmıştı
    ama uygulamaya geçerken DAHA DOĞRU bir yer bulundu — tek bir global anahtar yerine, `FinansHesap`'a
    (zaten POS'a özel `komisyon_orani`/`valor_gun` alanlarını taşıyan tabloya) iki yeni alan eklendi:
    `pos_otomatik_mahsup` (bool) ve `pos_hedef_hesap_id` (FK, hangi banka hesabına aktarılacağı) — böylece
    BİRDEN FAZLA POS hesabı olan bir firma her birini AYRI hedefe yönlendirebiliyor (tek global anahtarla
    mümkün olmazdı). Alanlar, POS kartının zaten var olan "3. POS / Kart Bilgileri" bölümüne eklendi
    (`finans_hesap_editor.py`) — ayrı bir ekran açmaya gerek kalmadı.
  - **`FinansHareket.mahsup_virman_id`** (self-FK, nullable) eklendi — bir POS tahsilat satırının hangi
    virman hareketiyle bankaya aktarıldığını işaretler; dolu ise o satır ARTIK taranmaz (idempotent).
  - **`pos_mahsup_servisi.py::vadesi_gelenleri_tara(db)`**: her POS hesabı için valörü (hareket tarihi +
    `valor_gun`) geçmiş, henüz mahsup edilmemiş tahsilat satırlarını PARA BİRİMİ bazında toplayıp TEK bir
    virman fişiyle (`FinansFisService` — manuel girişle aynı kod yolu) hedef banka hesabına aktarır;
    katkıda bulunan tüm satırları `mahsup_virman_id` ile işaretler.
  - **Tetikleyici:** Gerçek bir arka plan zamanlayıcısı YOK (tasarımda da öngörülmemişti) — "Banka
    Hareketleri" ekranı (`finans_hareket_screen.py`, `grup="banka"`) her açıldığında tarama bir kez
    çalışır; bir hata olursa ekranın açılmasını ASLA engellemez (sessizce loglanır, kullanıcı manuel
    mahsup edebilir).
  - 9 yeni test eklendi (`test_pos_mahsup_servisi.py`: oluşturma/valör gelmemiş/kapalı/idempotent/
    gruplama; `test_odeme_plani_otomasyon_servisi.py`: POS akışı; `test_finans_hesap_cards.py`: kart
    editöründe yeni alanların kayıt/geri yükleme). İlgili 4 test dosyası (48 test) çalıştırıldı — 1 test
    **BENİMLE İLGİSİZ** bir nedenle kırık bulundu (ayrıntı aşağıda), geri kalan 47 temiz.
  - **Bulunan ama DOKUNULMAYAN bulgu:** `test_doviz_kisiti_kapaliysa_kasa_her_dovizle_calisir_aciksa_yalniz_kendi_dovizini_kabul_eder`
    (`test_finans_hesap_cards.py`) başarısız — `cari_hareket_service.py`'deki döviz kısıtı kontrolü
    `git diff HEAD` ile doğrulandığı üzere BAŞKA bir (benim değişikliğim değil, uncommitted/eş zamanlı)
    değişiklikle `hesap_para != yerel` istisnası eklenerek bozulmuş (kısıtlı bir TRY kasası, hesabın parası
    yerel parayla aynı olduğu için YABANCI PARA işlemini de kabul eder hale gelmiş — muhtemelen yanlışlıkla).
    Dokunmadım; bu dosya üzerinde eş zamanlı başka bir iş var.
- [ ] **04.10 (kapsam dışı, kendi ayrı fazı) — Çek/Senet gerçek modülü:** `09_cek_senet/fields_and_schema.md`
  dokümanındaki tasarım koda dökülür; ancak koda dökülünce `PaymentPlan.odeme_tipi=cek|senet` akışı da
  04.07-04.09'daki örüntüyle otomatik fiş üretir hale getirilir.
- [x] **04.11 — Çok Satırlı (Karma Tipli) Ödeme Planı + TOYA Formül Motoru (TAMAMLANDI 2026-10-02):**
  Kullanıcı DIA/Logo/Zirve/Kursoft ekran görüntüleri paylaşıp karşılaştırmamızı istedi; sonra netleştirdi:
  "sadece çok satırlı olması önemli değil bir de farklı ödeme türlerini de desteklemeli ... formülasyon
  TOYA'ya özgün olsun, yolda da geliştiririz, ortaya bir şey çıksın." Yani DIA'nın G/T/K/M'si ya da Logo'nun
  $P1/$P2'si DEĞİL, kendi değişken sözlüğümüz; ve tam formül-dili mükemmelliği yerine ÇALIŞAN bir ilk sürüm.
  - **Model (geriye dönük TAM uyumlu, additive):** Yeni `PaymentPlanLine` tablosu (`payment_plan_id` FK,
    `sira_no`, `odeme_tipi`, `tutar_formulu`, `gun`, `hedef_finans_hesap_id`, `banka_odeme_plani_id`).
    `PaymentPlan`'ın KENDİ eski alanları (04.05) HİÇ DOKUNULMADAN duruyor — `satirlar` BOŞ olan (çoğu/basit)
    plan hâlâ onları kullanır; `satirlar` DOLU olan plan onları yok sayıp her satırdan AYRI bir fiş üretir.
    `FinansFis.kaynak_belge_satir_no` eklendi — tek belgeden çok fiş doğunca hangisinin hangi satırdan
    geldiğini ayırt eder (yeniden kaydedilince doğru fişi günceller, duplicate üretmez).
  - **TOYA Formül Motoru (`odeme_formul_motoru.py`):** Değişkenler `TUTAR`/`ARATOPLAM`/`KDV`/`KALAN`
    (KALAN = bu plandaki önceki satırlardan arta kalan — "son satır genelde boş bırakılır, kalanı alır"
    deseni rounding hatalarını önler). **Önemli mimari bulgu:** kod taramasında zaten mevcut, test edilmiş,
    AST tabanlı güvenli bir ifade motoru (`formula_service.py::FormulaService` — Görünüm Profilleri kural
    motoru için yazılmış) bulundu; sıfırdan ikinci bir "güvenli eval" yazmak yerine BUNUN üzerine ince bir
    katman (TOYA'nın değişken adları + KALAN varsayılanı + bilinmeyen-değişken/sözdizimi hatalarının
    FormulaService'in "sessizce 0 dön" davranışının aksine AÇIKÇA raporlanması) eklendi — DRY. Fonksiyon
    adları (`round`/`abs`/`min`/`max`/`sum`) de motorun kendisininkiyle aynı; ayrı bir Türkçe takma ad
    (ör. YUVARLA) kırılgan kaynak-metni değişimi gerektireceğinden eklenmedi — "yolda geliştiririz" ilkesi.
  - **Otomasyon servisi yeniden yazıldı:** `OdemePlaniOtomasyonServisi.belge_kaydedildi()` artık HER ZAMAN
    bir `OtomasyonSonucu` LİSTESİ döner (0, 1 ya da N). Hem eski "tek tip" plan HEM yeni çok satırlı plan
    AYNI iç döngüden geçer (tek tip plan, tek bir `"TUTAR"` formüllü "sanal satır" gibi davranır) — iki ayrı
    kod yolu yok. Tanınmayan bir `odeme_tipi` (ör. "acik_hesap") fiş üretmez ama `KALAN` hesabından düşülür
    — "bir bölümü açık hesap, kalanı kredi kartı" senaryosu doğru çalışır. Bozuk/sıfıra-bölen bir formül o
    satırı sessizce atlar (0 ya da hatalı tutar → fiş üretilmez), diğer satırlar etkilenmez.
  - **`DocumentDetailScreen`** artık çoklu fiş bildirimini birleştiriyor: "K000012 (Kasa Tahsilat) +
    B000034 (Kredi Kartı Tahsilatı) fişleri otomatik oluşturuldu".
  - **UI — `OdemePlaniSatirlariDialog`** (yeni popup, Ödeme Planları panelinde "📑 Çok Türlü Satırları
    Düzenle" aksiyonuyla açılır): seçili planın satırlarını listeleyen bir grid (Sıra/Ödeme Tipi/Tutar
    Formülü/Gün/Hedef Hesap/Banka Ödeme Planı), satır ekle/sil, formül sözdizimini anlatan bir ipucu
    kutusu. Plan önce kaydedilmemişse ("kod DB'de yok") kullanıcı önce kaydetmeye yönlendirilir.
  - 20 yeni test (`test_odeme_formul_motoru.py`, `test_odeme_plani_satirlari_dialog.py`, 5 yeni çok-satırlı
    senaryo `test_odeme_plani_otomasyon_servisi.py`'de, 1 uçtan uca entegrasyon `test_document_detail_screen.py`'de,
    1 UI kablolama testi `test_settings_menu.py`'de) + `test_formula_engine.py` (dokunulmadı, hâlâ geçiyor)
    dahil 109 test tek seferde çalıştırılıp temiz geçti.
  - **Bilinçli ertelenen (yolda geliştirilecek):** DIA/Logo'daki tam Gün/Ay/Yıl/Hafta tarih-formülü
    (ör. "ayın son Cuma'sı") — v1'de yalnız düz `gun` (fatura tarihinden +N gün) var; "Ödeme Yapılabilen
    Günler" + resmi tatil dahil etme kısıtları da henüz yok. Cari bazlı varsayılan ödeme planı
    (Kursoft/Logo blog'unda görülen, `Customer.payment_plan_id` zaten var — kolay bir sonraki adım) da bu
    fazın kapsamına alınmadı.

## Açık sorular / kullanıcının "araştırırım" dediği kısım
Muhasebe pratiğinde sık görülen, bu listede henüz yer almayan ödeme tipleri (kullanıcı kendi araştırmasını
yapana kadar yalnızca bilgi amaçlı not): **kapora/avans mahsubu** (faturadan önce alınmış avansın bu faturaya
düşülmesi — cari hareket tarafında zaten `tahsilat`/`alacak_dekontu` türleri var, yeni bir ödeme tipinden
çok mahsup mantığı), **yurt dışı havale (SWIFT/döviz transferi)** (muhtemelen `havale_eft`'in döviz bazlı bir
alt kümesi, `FinansHareket` zaten `para_birimi`/`kur` taşıyor), **barter/mal mukabili mahsup**. Bunlar ayrı
bir `odeme_tipi` değeri mi yoksa mevcut tiplerin bir varyasyonu mu olmalı — kullanıcı netleştirdikten sonra
karara bağlanacak.

## 04.12 — Yardım paneli ve bağlamsal ipuçları (2026-10-02)
Kullanıcı isteği: "bugüne kadar yapılmış olan bölümler ile ilgili yardım hazırlamak gerekir diye
düşünüyorum sen ne dersin" → "ikisi birden" (hem bağlamsal tooltip'ler hem ayrı bir Yardım ekranı).

- **`YardimWidget`** (yeni, `src/desktop/ui/widgets/yardim_widget.py`): Genel Ayarlar → SİSTEM grubuna
  "📖 Yardım" olarak eklendi (alt menüsüz, düz madde — Güvenlik/Sürüm & Git ile aynı seviyede). Arama
  kutusu + 6 konuluk katlanır (`CollapsibleSection`) liste: Genel Ayarlar Panosu, Şirket Tanımları, Ödeme
  Planları (otomatik kasa/banka fişi), Çok Türlü Ödeme Planları (satırlar/formül), Banka Ödeme Planları
  (BSMV/komisyon), POS Otomatik Mahsup. Arama hem başlıkta hem gövde metninde çalışır
  (`settings_menu.matches`, Türkçe harf-duyarsız), eşleşen bölüm otomatik açılır, boşaltılınca hepsi
  tekrar kapanır. Varsayılan: tüm bölümler kapalı (sayfa kalabalık görünmesin).
- **Bağlamsal tooltip'ler** (4 dosya): `finans_hesap_editor.py` (POS hedef hesabı — otomatik mahsup
  açıklaması), `banka_odeme_plani_ekle_dialog.py` (komisyon/BSMV/hizmet bedeli — BSMV'nin KOMİSYON
  TUTARI üzerinden hesaplandığı özellikle vurgulandı, çünkü bankaların standart uygulaması sezgisel değil),
  `odeme_plani_ekle_dialog.py` (ödeme tipi/hedef hesap/banka ödeme planı seçimlerinin otomasyonu nasıl
  tetiklediği), `odeme_plani_satirlari_dialog.py` (Tutar Formülü sütun başlığı — değişken/fonksiyon
  özeti).
- 4 yeni test (`test_yardim_widget.py`): varsayılan kapalı durum, arama eşleşen bölümü açıp
  eşleşmeyeni gizler, arama gövde metninde de çalışır, arama temizlenince eski duruma döner. Qt notu:
  bir widget ağacı hiç `.show()` edilmediyse `isVisible()` her zaman `False` döner (üst pencere
  görünürlüğüne bağlı) — bu yüzden testler `isHidden()` kullanıyor.
  **Gerçek regresyon bulundu ve düzeltildi:** SİSTEM grubunun düz (alt menüsüz) öğe listesini test eden
  `test_system_group_is_split_into_...` testi, "Yardım" eklenince beklenen listeyi güncellemek
  gerektiriyordu (`["Güvenlik", "Sürüm & Git"]` → `["Güvenlik", "Sürüm & Git", "Yardım"]`) — düzeltildi.
- Ekran görüntüsüyle doğrulandı (kapalı ve açık durum, Türkçe HTML doğru render oluyor).
- Son toplu regresyon (`test_settings_menu.py` + `test_master_definitions.py` + `test_yardim_widget.py`):
  59 test, hepsi geçti.
- Not: Bu bölüm teknik olarak yalnız Ödeme Planları'na özgü değil (Şirket Tanımları gibi başka modülleri
  de kapsıyor) ama en yakın "canlı tasarım dokümanı" burası olduğu için buraya işlendi.

## Dokunulmayan / bilinçli kapsam dışı
- Gerçek arka plan zamanlayıcısı (uygulama kapalıyken POS mahsubu otomatik yapan bir servis) — masaüstü
  uygulama mimarisine uymuyor, "uygulama/ekran açılışında tara" modeli yeterli kabul edildi.
- Çek/Senet'in gerçek kodlanması (04.10) — kendi büyük, bağımsız fazı, bu çalışmanın asıl kapsamı değil.
- Banka ekstresi içe aktarma, kredi kartı ekstre kapama — 08_banka dokümanında zaten "sonraki aşama" olarak
  ayrı not edilmiş, bu çalışmaya dahil değil.
