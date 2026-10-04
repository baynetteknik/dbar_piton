# Portal ve Wolvox Aynası — Kaldığımız Yer (2026-09-19, 2026-09-22'de gözden geçirildi, 2026-09-23'te canlıya alındı)

**2026-09-23 güncellemesi — GERÇEK CANLI KURULUM TAMAMLANDI:** `erp.baynetbilisim.tr` (kullanıcının gerçek cPanel barındırması) üzerinde portal artık çalışıyor. FTP ile `portal/` dizini sunucudaki `/erp.baynetbilisim.tr` köküne gönderildi (39 dosya), gerçek MySQL veritabanına (`iletkene_toyaerp`) kurulum sihirbazıyla (`install.php`) kuruldu, `.htaccess` korumaları gerçek Apache'de doğrulandı (SIZE komutu ASCII/Binary modu farkı dışında sorunsuz). Kurulum sihirbazının ürettiği `agent_api_key` ve `update_secret` sohbette kullanıcıya iletildi (bu dosyaya ya da git'e YAZILMADI — sadece sunucudaki `config.local.php`'de ve kullanıcının TOYA Genel Ayarlar'ına gireceği yerde duracak). Kalan adım: kullanıcının bu iki anahtarı kendi TOYA ERP'sinde Genel Ayarlar → Online Portal (base_url + agent_api_key) ve Portal Yayın (update_secret) panellerine girmesi.

**2026-09-22 güncellemesi:** Kullanıcı yalnızca **online teklif portalını** aktifleştirmek istiyor (Wolvox Aynası değil). Kod tarafı incelendi: teklif yayınlama/karar çekme akışı (Python + PHP) zaten tamdı ve commit edilmişti (`ad2a89b` — üstteki "commit edilmedi" notu artık geçersiz). Tek gerçek eksik bulundu ve giderildi: "ONLİNE TEKLİF (PORTAL)" bölümü `DocumentDetailScreen`'de tüm 8 belge türünde (sipariş, irsaliye, fatura dahil) görünüyor ve bir teklif dışındaki belgeler bile portala yayınlanabiliyordu (`PortalService::publish` sunucu tarafında da tür kontrolü yok). Artık yalnız "TEKLİF: Verilen Satış Teklifi"nde görünüyor (`belge_turu=='teklif' and yon=='satis'`); diğer 7 türde bölüm tamamen gizli. Bkz. `document_detail_screen.py::_refresh_summary`.

**Aktifleştirmek için kalan tek şey: gerçek bir cPanel barındırma.** Kod tarafında yapılabilecek bir şey kalmadı; sıradaki adım kullanıcının bir alan adı + cPanel hesabı sağlaması, kurulum sihirbazını (`portal/public/install.php`) çalıştırması ya da Ayarlar'daki "Portal Yayın" panelinden FTP ile dağıtması, sonra TOYA'da Genel Ayarlar → Online Portal'a adres + `agent_api_key` girmesi. Wolvox alanları boş bırakılırsa (Aynası) hiç devreye girmiyor — otomatik hiçbir şey çalıştırmıyor, yalnız elle "Wolvox'u Senkronla" tıklanırsa aktif olur.

Karar: Yarın **TOYA'daki cari ve stok işlemlerini bitirmeye** dönülecek. Portal işi aşağıdaki noktada bekliyor.

## Tamamlananlar (yol haritası 1-5)
1. İmzalı paket + Migrator + sertleştirilmiş uzaktan güncelleyici (`portal/src/Updater.php`, `portal_package.py`)
2. Masaüstünden FTP/FTPS ile yayın (`portal_deploy.py`, Portal Yayın paneli)
3. Kurulum sihirbazı (`portal/public/install.php`, `Installer.php`) — **ana kurulum yolu**
4. Yedekleme (`BackupService.php`, `bin/backup.php`, TOYA'da Portal Yedekleme paneli)
5. Softaculous paketi — **ikinci seçenek** (`portal/softaculous/`, "Softaculous Paketi Üret" düğmesi)

Testler: PHP 259/259 (MariaDB), portal/paket/dağıtım/widget Python testleri 46/46.
Tam Python paketinde daha önceden var olan 18 ilgisiz başarısız test duruyor (bu işle ilgisiz).

## Doğrulanmamış / dikkat
- Gerçek Softaculous'ta denenmedi (info.xml / install.xml biçimi ve `$__settings['softpath']` varsayım).
- Gerçek cPanel/Apache (.htaccess) ve gerçek cPanel FTP denenmedi; portal sayfaları gerçek tarayıcıda bakılmadı.
- Yedekler şifresiz; TOYA'nın yedeği düzenli çekmesi için zamanlayıcı yok (düğmeyle).
- Wolvox fatura yön eşlemesi (durum 1,3,6 satış; 2,4,5 alış) doğrulanmamış varsayım; gerçek teklif verisi yok.
- Bu turdaki değişiklikler **commit edilmedi** (`portal/`, portal servisleri, widget'lar, testler).

## 2026-09-22 (2. tur): C:\xampp\htdocs\toya (TOYA Aidat) sisteminden alınan FTP/sürüm takibi incelemesi

Kullanıcının isteğiyle, bu makinede zaten kurulu **ayrı, ilgisiz bir proje** olan "TOYA Apartman Aidat Yönetim Sistemi"nin
(`C:\xampp\htdocs\toya`, farklı bir repo — `github.com/baynetteknik/toya-aidat`) FTP dağıtım / sürüm takip altyapısı incelendi;
buradan alınabilecek fikirler TOYA ERP'nin kendi `portal_deploy.py`/`portal_deploy_widget.py`'sine (sadece bu proje) uygulandı.

**Bulunanlar (aidat sistemi):**
- `admin/ftp-profilleri.php`: çoklu, adlandırılmış FTP profili (host/port/kullanıcı/parola/uzak yol/TLS/pasif), CoreFTP/FileZilla'ya dışa aktarma.
- `src/Service/DeltaSyncManager.php`: dosya `boyut+mtime` imzasıyla yerel↔sunucu farkını hesaplar, yalnız değişen dosyaları içeren küçük "delta" paket üretir, `ftp_deploy_snapshots`/`ftp_deploy_history` tablolarında sürüm/dağıtım geçmişi tutar.
- `src/Service/RemoteFtpDeployer.php::navigateToPath`: cPanel'in "jailed" (kilitli) FTP hesaplarında `public_html/www/htdocs` gibi kök takma adlarını tolere eden dizin gezinme algoritması.
- **Güvenlik sorunu:** FTP parolaları `ftp_connections.pass` sütununda **düz metin** tutuluyor, dışa aktarma dosyalarına (.cfx/.xml) da düz metin gömülüyor. Şifreleme yok.

**TOYA ERP'ye uygulanan (Faz 1 — TAMAMLANDI):**
- `portal_deploy.py`: `PortalFtpProfile` + `PortalFtpProfileStore` — birden çok adlandırılmış FTP profili. Profil BİLGİLERİ (host/port/kullanıcı/klasör/TLS) ayarlarda JSON, **PAROLA `keyring` (Windows Kimlik Bilgisi Yöneticisi) üzerinden** — `disk_registry.DiskStore` / yedekleme bulut hedefleri (`remote_providers.secret_name`) ile AYNI, zaten test edilmiş desen. **Bilerek aidat sistemindeki düz metin yaklaşımı alınmadı** — TOYA ERP'nin kendi eski `portal_deploy.py`'sinde de (bu incelemeyle ortaya çıktı) parola düz metin ayarlarda tutuluyordu; o da düzeltildi. İlk kullanımda eski tekli düz metin profil otomatik yeni depoya taşınır ve düz metin ayar silinir (`PortalFtpProfileStore._migrate_legacy`, idempotent).
- `portal_deploy_widget.py`: profil seçici (aç. kutu) + Kaydet/Sil; "Portal Yayın" artık birden çok sunucu (ör. "Canlı Sunucu", "Test Sunucusu") arasında geçiş yapabiliyor.
- `_cwd_or_make`: cPanel jailed-hesap toleransı eklendi (yalnızca ilk denemenin TAMAMI başarısız olursa `public_html/www/htdocs/httpdocs` kök takma adını atlayıp yeniden dener) — mevcut testlerin davranışını DEĞİŞTİRMİYOR (yalnız gerçek jailed cPanel senaryosunda devreye girer).
- Testler: `tests/test_portal_deploy.py`'ye 8 yeni test (profil deposu, parola/keyring, tekilleştirme, göç, cwd toleransı, arayüz çoklu profil); dosyadaki 32 test de (yenileriyle) geçiyor, hiçbir mevcut test bozulmadı.

**Bilerek yapılmayan / ertelenen (kapsamı büyük, ayrı bir iş):**
- **Delta/parça paketleme:** aidat sistemindeki gibi yalnız değişen dosyaları FTP ile göndermek bant genişliğini ciddi azaltır, ANCAK bizim `Updater.php` şu an paketin (ZIP'in) izinli her dosyayı **birebir** içermesini zorunlu kılıyor (bütünlük/imza garantisi bunun üzerine kurulu — "sertleştirilmiş" tasarım notu). Bunu bozmadan delta desteklemek için `Updater.php::verify()`'nin "manifest'te olup pakette olmayan dosya" kuralını, o yol sunucuda ZATEN manifestteki hash ile eşleşiyorsa hataya düşürmeyecek şekilde GÜVENLİ biçimde gevşetmek gerekiyor — güvenlik-kritik bir dosyada dikkatli, kendi testleriyle yapılacak ayrı bir iş (Faz 2 adayı).
- **Sürüm/dağıtım geçmişi ekranı:** aidat sistemindeki `admin/surum-takibi.php`/`ftp_deploy_history` benzeri bir "Portal Dağıtım Geçmişi" penceresi TOYA ERP'de henüz yok; `sync_log_service` (zaten her dağıtımı `DIR_DEPLOY` ile günlüğe yazıyor) üzerine kurulabilir (bkz. `BackupRestoreHistoryDialog` deseni) — Faz 3 adayı.
- **Sunucu tarafı sıfırlama/yedekleme:** portal'ın kendi `BackupService.php`/`bin/backup.php`'si zaten var (aidat sistemininkiyle aynı fikir); TOYA'nın bunu DÜZENLİ (zamanlanmış) çekmesi eksik — bu doğrudan "Sıradaki portal işleri" listesindeki "Zamanlanmış ajan" maddesiyle örtüşüyor, ayrı bir madde açılmadı.

## Portal Yayın ekranı yeniden tasarlandı + otomatik kurulum (2026-09-29)
Kullanıcı geri bildirimi: ekran diğer standart ekranlar gibi olmalı (dbgrid + ekle/düzenle/sil sağdaki
İŞLEMLER'den), detay formu her zaman açık durmamalı (satıra çift tıklayınca popup'ta açılsın), FTP
klasörü Windows Gezgini gibi dolaşarak seçilebilsin, test/gönderim aşamalı log gösteren popup'larla
yapılsın, ve en önemlisi: paket gönderildikten sonra `erp.baynetbilisim.tr`'ye elle girip `update.php`'de
"Kur"a basmaya gerek kalmadan **otomatik kurulsun**.

Yapılanlar:
- **`PortalDeployWidget`** tamamen yeniden yazıldı: FTP profilleri artık standart dbgrid'de listeleniyor;
  form alanları (host/kullanıcı/parola/klasör/tls) ayrı bir popup diyalogda (satıra çift tıklayınca ya da
  "Yeni Profil Ekle"). Klasör alanının yanında "📁 Gözat…" düğmesi `_FtpBrowserDialog` açıyor (FTP `MLSD`/
  `LIST` ile alt klasörleri listeleyip dolaşarak seçim). "Bağlantıyı Test Et" ve "Paketi Üret ve Gönder"
  artık arka planda çalışıp adım adım günlük gösteren bir `_ProgressLogDialog` açıyor (UI donmuyor).
  "❓ Yardım" ve "🗂️ Sürüm Geçmişi" (sync_log_service kayıtlarından) yeni popup'lar. İŞLEMLER paneli
  4 anlaşılır alt gruba ayrıldı: Profil İşlemleri / Gönderim / Güncelleme Anahtarı / Yardım & Geçmiş.
- **Otomatik kurulum (yeni, sunucu tarafı dahil):** `bootstrap.php::portal_route`'a `/update/apply`
  ucu eklendi — mevcut `agent_api_key` (Online Portal ayarındaki, `update_secret`'tan AYRI) ile
  korunuyor, `update_inbox/`'taki paketi `Updater::apply()` ile kurup `storage/applied/`'a taşıyor.
  Masaüstü tarafında `portal_sync_service.trigger_apply()` gönderim başarılı olunca bunu çağırıyor.
  **Online Portal (API adresi/anahtarı) tanımlı değilse bu adım sessizce atlanır** — paket yine
  sunucuda durur, `update.php`'den elle kurulum her zaman geçerli kalır (geriye dönük uyumlu).
- `Updater.php`'ye `root()` public metodu eklendi (route handler kendi yol hesaplamak yerine Updater'ın
  kendi kök dizinini kullanıyor — testte gerçek repo dizinine yanlışlıkla yazmayı da önledi).
- Testler: PHP 275/275 (5 yeni: yetkili/yetkisiz/geçersiz-ad/paket-yok/Updater-yok senaryoları),
  Python: `test_portal_deploy.py` (61), `test_portal_sync_service.py` (24, `trigger_apply` dahil),
  `test_settings_menu.py` yeniden gruplandırılmış İŞLEMLER'i doğruluyor. Ekran görüntüsüyle doğrulandı.
- Bilinen, önceden var olan (bu işle ilgisiz) ortam kırılganlıkları: `test_widget_copies_the_update_secret`
  ve `test_set_secret_validates_length...` bu makinenin headless/offscreen ortamında pano (clipboard)
  okuma/yazmasının güvenilmemesinden başarısız oluyor — orijinal (değişiklik öncesi) kodda da aynı
  şekilde başarısız olduğu doğrulandı, bu turun bir regresyonu değil.

## Kök dizin 404 → karşılama sayfası (2026-09-29)
`erp.baynetbilisim.tr` köküne FTP ile `portal/` klasörünün TAMAMI gönderildiği için (bkz. yukarıdaki 2026-09-23 notu — `public/`
değil `portal/` kök alındı) ve kökte bir `index.php` olmadığı için alan adının kökü 404 dönüyordu; asıl sayfalar yalnızca
`/public/...` altında çalışıyordu. Bağımlılıksız (bootstrap.php/DB gerektirmeyen), TOYA logolu, "Portala Giriş Yap" düğmesi
`public/login.php`'ye giden sade bir `portal/index.php` eklendi + logo `portal/public/assets/toya_logo.png` (küçültülmüş kopya,
masaüstü uygulamasının `assets/logo/toya_logo.png` dosyasından). **Önemli:** bu yeni kök dosyalar `Updater.php`/`portal_package.py`
imzalı paketleme izin listesine (`ALLOWED_ROOT_FILES`) eklenmezse uygulamanın "Portal Yayın" aracı onları hiç sunucuya göndermezdi —
`index.php` her iki dosyada da (PHP + Python, birebir aynı kalmalı) listeye eklendi; `assets/toya_logo.png` zaten izinli `public/`
altında olduğu için ayrıca izin gerekmedi. Kullanıcının bunu canlıya alması için normal "Portal Yayın" (yeni paket üret + gönder)
akışını bir kez daha çalıştırması yeterli. Testler: `tests/test_portal_package.py` (9/9, değişiklik sonrası hâlâ geçiyor).

## Sıradaki portal işleri (ertelendi)
- TOYA'da Wolvox Aynası ekranları: cari bakiye, ekstre, fatura listesi, dashboard, Aktarım Günlüğü ekranı
- Zamanlanmış ajan (sync_and_push + portal yedeği için küçük giriş noktası)
- ~~Portal cari özeti aynadan gelsin; cari ekranında "Hesap Özetini Portala Gönder"~~ **Tamam (2026-09-28).** Bkz. aşağıdaki not.
- TOYA'nın kendi cari hareket defteri + mutabakat motoru
- Silme = gizleme (tüm programda, EN SON) + deneme verisi temizleme
- Site/sayfa tasarım aracı (bkz. `gelistirme/12_site_tasarim/notlar.md`; kullanıcı GrapesJS'i inceleyip şablonu verecek)
- Akınsoft WWB9 / resmi web servisi sorusu (kullanıcı Akınsoft'a soracak)

## Canlı uçtan uca teklif denemesi (2026-09-25) — 14/14 geçti
Geçici (bellek içi) veritabanı + canlı portal (gerçek verilere dokunulmadı). 4 "DENEME" teklifi yayınlandı, müşteri tarafı portal API'siyle çalıştırıldı, sonunda hepsi geri çekildi:
- A: yayın → müşteri sayfası verisi → karşı teklif → ikinci karşı teklif `counter_already_sent` → kabul → karar sonrası ikinci karar `already_decided` → TOYA çekince durum `accepted`, not ve karşı teklif tutarı teklif notuna işlendi → karar sonrası yeniden yayın reddedildi.
- B: ret → çekince `rejected`.
- C: geri çekme → müşteri sayfası 410 `revoked` → yeniden yayın başarılı.
- D: geçmiş tarihli teklif → kabul `expired` → çekince durum `expired`.
- Bildirimler üretildi: karşı teklif, kabul, ret, süre doldu.
Not: API'de silme yok; canlı portalda 4 geri çekilmiş `DENEME-…` kaydı kalır (yönetim ekranından temizlenebilir).


## "Hesap Özetini Portala Gönder" (2026-09-28)
`build_customer_account_payload` artık `Customer.balance` yerine gerçek `CariHareketService` defterinden (`cari_bakiye`/`ekstre`) besleniyor;
para birimi `money_service.yerel_para(db)`. Cari Hareketleri ekranının sağ panelinde "DİĞER İŞLEMLER" altında yeni "🌐 Hesap Özetini
Portala Gönder" düğmesi: seçili/filtrelenen cariyi onay sorup `/accounts` uç noktasına yayınlar, dönen bağlantıyı panoya kopyalar ve
gösterir (mevcut token varsa günceller — `portal_accounts` tablosu zaten `source+external_ref` üzerinden upsert ediyordu). Sunucu tarafı
(`PortalService::publishAccount`, `account.php`) zaten hazırdı, yalnızca masaüstü tarafı gerçek veriye ve bir düğmeye kavuştu.
Testler: `tests/test_portal_sync_service.py` (+3), `tests/test_cari_hareket_screen.py` (+2). Ekran görüntüsüyle görsel doğrulandı.
Not: tam geçmiş gönderiliyor (sayfalama/tarih penceresi yok) — çok hareketli carilerde sayfa büyürse ayrı bir iş olarak ele alınabilir.
