# 12 - SİTE / SAYFA TASARIM ARACI (ERTELENDİ — sonraya planlandı)

Durum: kullanıcı bilinçli olarak erteledi ("biz yolumuza devam edelim"). Bu dosya, konu tekrar açıldığında
bağlamı kaybetmemek içindir. Kod yazılmadı.

## Hedef (kullanıcının tarifi)
- Tek başına bir slider aracı DEĞİL; WoodMart tadında hazır tema (header / footer seçenekleri, e-ticaret şablonları)
  + Elementor / Slider Revolution kolaylığında sürükle-bırak sayfa tasarımı; WordPress olmadan, PHP bilmeden kullanılabilir.
- Header, body, footer birlikte ele alınır. Header/footer bir kez tasarlanır, sayfalara koşullarla atanır.
- Başlangıç: mevcut (satın alınmış) bir HTML şablondan hazır olan her şeyi alıp üzerinde kolayca oynanabilmesi.
- E-ticaret sayfaları için ayrı şablonlar (ürün listesi, ürün detayı, sepet); müşteri girişi ve sipariş.
- Slider Revolution birinci tercih: zaman çizelgeli katman editörü, çıkış animasyonu, mobil/tablet ayrı yerleşim.
  Slider Revolution'ın tamamı kopyalanmayacak (video/3B/parçacık/eklenti kapsam dışı).

## Bulgular (TOYA aidat projesi, `C:\xampp\htdocs\toya`, kod okunarak; tarayıcıda çalıştırılıp görülmedi)
- `site-admin/slider-builder.php`: sıfırdan yazılmış katman editörü (tuval, sürükle/boyutlandır, katman listesi),
  veri `vitrin_slider.layers_json`. Sınırlar: katman başına tek giriş animasyonu (8 hazır CSS efekti) + gecikme + süre;
  zaman çizelgesi, çıkış animasyonu, easing, ara kare ve mobil/tablet ayrı yerleşim yok.
- Sayfa tasarımı GrapesJS ile (`sayfa-builder-grapes.php`, ayrıca `sayfa-builder.php`, `gorsel-studyo.php`,
  `assets/js/toya-builder-engine.js`). Kullanıcı sonucu beğenmedi; nedeni netleşmedi (kullanıcı GrapesJS'e bakıp bilgi verecek).
- Web araştırması: Slider Revolution / LayerSlider / Smart Slider 3 zaman çizelgeli ama WordPress'e bağlı ticari eklentiler;
  bağımsız olgun açık kaynak karşılığı bulunamadı. Sayfa oluşturucu tarafında GrapesJS, Puck (React), Webstudio var.

## Önerilen yön (kullanıcı onaylamadı, sadece görüş)
- Mimari: tema ayarları (CSS değişkenleri) + global header/footer varyantları + sayfa şablonları + bölüm→sütun→bileşen
  hiyerarşisi. Sayfa JSON ağacı olarak saklanır, PHP hızlı/SEO uyumlu HTML+CSS üretir (cPanel uyumlu).
- Editör çekirdeği: GrapesJS mantıklı; sorun motor değil çıplak arayüz ve yapısız bileşenler. Üzerine Elementor benzeri
  paneller (İçerik/Stil/Gelişmiş), kendi bileşen kütüphanesi ve tema ayarları yazılır. Slider stüdyosu özel bir bileşen olur.
- Hazır HTML şablon: rastgele HTML'i otomatik temiz bileşenlere çevirmek güvenilir DEĞİL. İki katman: (1) her şablonda
  "her şeyi düzenlenebilir yap" (metin/görsel/bağlantı/bölüm sürükleme), (2) seçilen 1-2 şablon elle bileşen tabanlı
  hazır temaya dönüştürülür.
- Editör ile site AYNI slider oynatıcısını kullanmalı (şimdi editörde CSS animasyon, sitede farklı çalışıyor).
- E-ticaret: ürün verisi Wolvox ayna tablosundaki stok/fiyattan (`mirror_stok`), müşteri girişi ve sipariş portaldan.
  Ödeme altyapısı (iyzico/PayTR vb.) sonraki aşama.

## Aşamalar (her biri tek başına kullanılabilir olmalı)
- A. Temel: JSON sayfa modeli, PHP çıktı üretici, tema ayarları, global header/footer, temel bileşenler, editör iskeleti,
  bir şablonun düzenlenebilir içe aktarımı.
- B. Slider stüdyosu: zaman çizelgesi, çıkış animasyonları, mobil ayrı yerleşim, ortak oynatıcı, mevcut `layers_json` göçü.
- C. E-ticaret şablonları ve bileşenleri (stok aynasına bağlı).
- D. Şablon kütüphanesi, WoodMart tarzı header/footer varyantları.

## Teknik kısıtlar / ortam
- Bu makinede Node.js/npm YOK → derleme gerektirmeyen düz JavaScript (ES modülleri) yazılmalı (cPanel için de uygun).
- Chrome ve Edge kurulu; Playwright (pip) mevcut Chrome'u sürerek editörün gerçek tarayıcıda test edilmesini sağlar
  (henüz kurulmadı: `pip install playwright`, `channel="chrome"`). Tarayıcı testi olmadan görsel editör doğrulanmış sayılmaz.
- Hedef barındırma cPanel (PHP + MySQL, paylaşımlı).

## Kullanıcıdan beklenenler
1. GrapesJS builder'a bakıp neyi beğenmediğini söylemesi (mümkünse ekran görüntüsü).
2. Satın aldığı HTML şablonun yeri (kullanıcı: "toya klasöründe"; tam yol henüz verilmedi) ve lisans kullanım koşulları.
3. Hedef site: mevcut TOYA/Baynet vitrin sitesi mi, yeni site mi.
4. E-ticaret ödeme altyapısı tercihi (sonraki aşama).

## Yerine dönüş
Bu plan ertelendi; şu an sıradaki iş portal deploy adımları (FTP ile gönderme, kurulum sihirbazı, yedek, Softaculous).
Konu yeniden açılınca önce yukarıdaki "Kullanıcıdan beklenenler" sorulmalı.
