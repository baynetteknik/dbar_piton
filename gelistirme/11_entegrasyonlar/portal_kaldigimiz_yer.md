# Portal ve Wolvox Aynası — Kaldığımız Yer (2026-09-19)

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

## Sıradaki portal işleri (ertelendi)
- TOYA'da Wolvox Aynası ekranları: cari bakiye, ekstre, fatura listesi, dashboard, Aktarım Günlüğü ekranı
- Zamanlanmış ajan (sync_and_push + portal yedeği için küçük giriş noktası)
- Portal cari özeti aynadan gelsin; cari ekranında "Hesap Özetini Portala Gönder"
- TOYA'nın kendi cari hareket defteri + mutabakat motoru
- Silme = gizleme (tüm programda, EN SON) + deneme verisi temizleme
- Site/sayfa tasarım aracı (bkz. `gelistirme/12_site_tasarim/notlar.md`; kullanıcı GrapesJS'i inceleyip şablonu verecek)
- Akınsoft WWB9 / resmi web servisi sorusu (kullanıcı Akınsoft'a soracak)
