# TOYA ortak tasarım modülü

Tek geliştirme kaynağı: `C:/toya_erp/shared/toya-design`.
Mevcut Aidat GrapesJS ve slider stüdyolarından çıkarılmıştır. İki ayrı editör geliştirilmez.

- `views/page.php`: ortak sayfa editörü ve bloklar.
- `views/slider.php`: ortak slider/katman editörü.
- `lib/templates.php`: mevcut hazır şablon kütüphanesi.
- `assets/js/toya-grapes-free-layout.js`: ortak serbest yerleşim eklentisi.
- `lib/PageStore.php`: dosya tabanlı hostlar için sürümlü kayıt; Aidat mevcut DB kaydını kullanır.

`python scripts/sync_design_module.py --host both` iki uygulamanın dağıtım kopyalarını üretir.
`--check` hiçbir şey yazmadan kaynak ile kopyaların birebir aynı olduğunu kontrol eder.
Dağıtım klasörlerinde elle geliştirme yapmayın. Kullanıcı içeriği bu modüle konulmaz.

Aidat: `site-admin/sayfa-builder-grapes.php`, `site-admin/slider-builder.php` mevcut
oturum/DB adaptörleridir. URL ve kayıt formatları korunur. Finans/aidat tabloları ile bağlantı kurulmaz.
Şablon uyumluluk dosyası `includes/vitrin_template_library.php` ortak kütüphaneyi yükler.

ERP: `/public/design.php` ve `/public/design-slider.php` yalnız portal yöneticisine açıktır.
Kaydedilen ana sayfa alan adı kökünde gösterilir; henüz kayıt yoksa eski karşılama korunur.
İçerik, bir önceki kayıt ve yüklenen görseller `portal/storage/site-design/` altında tutulur;
bu klasör güncelleme paketine girmez. Yedeklemede bu klasörü de koruyun.
Sayfa tasarımında Slider bloğu son kaydedilen etkin slaydı gösterir.

Ortak tema varlıkları mevcut satın alınmış Smarty dağıtımından gelir; lisans hakları değişmez.
Harici GrapesJS/jQuery/font CDN bağımlılıkları mevcut editörden devralınmıştır.
E-ticaret şablonları görseldir; sepet, ödeme veya ERP stok entegrasyonu sağlamaz.

Geri dönüş: adaptörlerin önceki kopyaları ilk geçişte `backups/design-module-*`
altında tutulur. Bunları eski yollarına geri koymak Aidat'ın önceki editörünü geri getirir.
ERP için kayıtlı `storage/site-design/home.json` dosyasını yedek bir ada taşımak
eski karşılama sayfasını geri getirir; müşteri portalı bağlantıları değişmez.
