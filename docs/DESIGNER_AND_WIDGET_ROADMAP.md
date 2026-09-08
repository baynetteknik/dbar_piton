# 🗺️ TOYA ERP - Görsel Tasarımcı & Widget Entegrasyonu Yol Haritası (Master Roadmap)

Bu doküman, **Bant Tabanlı Görsel Form & Rapor Tasarımcısı** ile TOYA ERP'nin **Merkezi Widget Kayıt Defteri (`WIDGET_REGISTRY`)** mimarisinin birleştirilmesi sürecini, tamamlanan aşamaları ve yarın devam edilecek adımları belirler.

---

## 📌 1. Mevcut Durum Özeti (Tamamlananlar)

### ✅ Aşama 1: Çekirdek Render Motoru, Vektörel PDF & Baskı Önizleme
- **Milimetrik Çizim Motoru (`printer_engine.py`):** DPI bazlı doğrudan piksel dönüşümü (`font.setPixelSize`, `QRectF`), font deformasyonunu ve aşırı büyüme hatasını ortadan kaldıran vektörel çizim mimarisi.
- **Formül & İfade Motoru (`expression_engine.py`):** Dinamik alanlar, para formatlaması (`#,##0.00 ₺`) ve Türk ticaret mevzuatına uygun `[YAZIYLA(toplam, 'TL')]` fonksiyonu.
- **Gelişmiş Baskı Önizleme Penceresi (`preview_dialog.py`):**
  - **📄 Sayfaya Sığdır (Tümünü Göster):** A4 sayfasının tamamını (başlıktan imza alanına kadar) kaydırma yapmadan tek ekranda gösteren varsayılan mod.
  - Genişletilmiş zoom skalası (`%25`, `%35`, `%50`, `%75`, `%100`, `%125`, `%150`, `%200`, `↔️ Genişliğe Sığdır`).
  - Dinamik pencere boyutlandırma (`resizeEvent`) desteği.
  - Vektörel PDF kaydetme ve fiziksel yazıcıya gönderme butonları.
- **Kurumsal A4 Teklif Mektubu Şablonu (`tpl_teklif_kurumsal_a4.json`):** Firma künyesi, müşteri kutusu, kolon başlıkları, detay satırları, dip toplam, KDV icmali, teslimat notları, yazıyla tutar ve kaşe/imza kutuları.

### ✅ Aşama 2: Bant Tabanlı Görsel Tasarım Editörü (`ReportDesignerWindow`)
- **Milimetrik Cetveller & Tuval (`ruler_widget.py`, `designer_canvas.py`):** Üst ve sol tarafta scroll senkronlu mm cetvelleri, A4 sayfa sınırları ve mıknatıslı nokta ızgarası (`1.0 mm`, `2.5 mm`, `5.0 mm`).
- **İnteraktif Bant Mimarisi (`designer_band.py`):** Sayfa Başı, Müşteri Künyesi, Kolon Başlığı, Detay Satırı, Dip Toplam ve Sayfa Altı bantları; alt kenardan fareyle tutarak canlı milimetrik yükseklik ayarlama.
- **Sürükle-Bırak & Boyutlandırma (`designer_item.py`):** Nesneleri fareyle milimetrik taşıma, 8 mavi tutamaç (handle) ile boyutlandırma.
- **Sol Panel Araçları (`toolbox_widget.py`, `data_tree_widget.py`):** Tek tıkla görsel nesne ekleme paleti ve ERP hiyerarşik veri alanları ağacı.
- **Sağ Panel Özellik Denetçisi (`property_inspector.py`):** Konum (X, Y), Boyut (W, H), Tipografi, Kenarlıklar, Dolgu rengi ve veri formatlarını anlık düzenleme.
- **Entegre Çalışma Döngüsü (`designer_window.py`):** `💾 Kaydet` ile JSON güncelleme ve `👁️ Canlı Önizle (F9)` ile yapılan değişiklikleri anında baskı formatında test etme.

---

## 🎯 2. Devam Eden Aşama: Widget Mimarisi Entegrasyonu

TOYA ERP'nin `src/desktop/ui/widgets/widget_registry.py` merkezi kataloğu ile tasarımcıyı tam entegre etmek üzere planlanan adımlar:

### ✅ Adım 1: Tasarımcı Bileşenlerini `WIDGET_REGISTRY`'ye Dahil Etme (Seviye 1) — TAMAMLANDI
1. **`ReportDesignerWidget` (`designer/ui/designer_widget.py`):** Tasarımcının tüm işlevi (3 panel, milimetrik toolbar, durum şeridi) artık bir `QWidget`. `ReportDesignerWindow` yalnızca onu saran ince bir `QMainWindow` kabuğu (bağımsız başlatıcı + "ayrı pencerede aç" için); eski `.template` / `.canvas` proxy'leri korundu.
2. **`ReportPreviewWidget` (`designer/ui/preview_widget.py`):** Baskı önizleme tuvali gömülebilir `QWidget`. `compact=True` modunda yazdır/PDF butonları gizli, varsayılan zoom "genişliğe sığdır" (evrak ekranı sağ paneli için). `set_document(template, data|datas)` ile canlı yeniden besleme. `ReportPreviewDialog` artık bu widget'ı saran ince bir modal kabuk.
3. `widget_registry.py`'ye eklendi: `widget_report_designer` (body) ve `widget_report_preview` (right_sidebar). `tests/test_designer_widgets.py` ile doğrulandı.

### ✅ Adım 2: Teklif Formu & Belge Detay Ekranı Entegrasyonu — TAMAMLANDI
1. `DocumentDetailScreen` sağ paneline **"CANLI BASKI ÖNİZLEME"** katlanır bölümü eklendi — içinde `ReportPreviewWidget(compact=True)`. Varsayılan kapalı; ilk açılışta çizilir, `⤢` düğmesi tam ekran modal önizlemeyi açar.
2. Form değiştikçe (kalem / cari / durum / belge türü / not / şablon seçimi) önizleme ~400 ms gecikmeli (debounce, `QTimer`) ve yalnızca bölüm açıkken `set_document()` ile tazelenir — `_build_print_data()` zaten modal önizleme ile aynı veri şemasını üretiyordu.
3. F9 / "📄 Önizle-Yazdır" hâlâ tam ekran modalı açar (detaylı inceleme + fiziksel yazdırma / PDF için).
4. Testler: `tests/test_document_detail_screen.py` içine mini önizleme (kapalı-varsayılan, açılışta render, debounce + guard) testleri eklendi.

### 🔹 Adım 3: Ekran Tasarımcısı (UI Screen Designer) Modu (Seviye 2)
1. Tasarımcının sol panelindeki Araç Kutusuna *"Masaüstü Ekran Tasarımı"* sekmesinin eklenmesi.
2. `WIDGET_REGISTRY` içerisindeki atomik parçaların (`widget_cari_kunyesi`, `widget_belge_vade`, `widget_hareket_kalemleri`, `widget_finans` vb.) listelenmesi.
3. Kullanıcının bu widget'ları tuvale sürükleyip bırakarak kendi özel ekran şablonunu (`scr_evrak_ozel.json`) oluşturabilmesi.

### ✅ Adım 4: Yeni Hazır Belge Şablonları — TAMAMLANDI
1. **`tpl_fatura_kurumsal_a4.json`** — e-Fatura A4: senaryo / fatura tipi / ETTN künyesi, sağ üstte karekod (`barcode` öğesi — motor şu an QR yer tutucu kutusu çiziyor), alıcı VKN/vergi dairesi, kalem tablosunda iskonto + KDV sütunları, KDV matrahı → ödenecek tutar icmali, YAZIYLA.
2. **`tpl_irsaliye_kurumsal_a4.json`** — Sevk İrsaliyesi: irsaliye no / düzenleme + fiili sevk tarihi, alıcı ve sevk bilgileri (adres, taşıyıcı/plaka, ilgili sipariş) kutuları, sade kalem tablosu (kod / cins / miktar / birim), teslim eden & teslim alan imza kutuları.
3. **`tpl_perakende_fis_80mm.json`** — 80 mm termal fiş: özel kağıt boyutu (80×200 mm, `_resolve_page_size` mm'den üretir), ortalanmış firma künyesi, iki satırlı kompakt kalem düzeni (açıklama + `miktar × B.Fiyat`), GENEL TOPLAM vurgusu, YAZIYLA, "KDV DAHİLDİR", fiş no barkodu.

Üçü de `TeklifPrintService.available_templates()` ile belge ekranındaki baskı formu seçicisinde listelenir. `printer_engine`: `data_field` öğesinde `text` verilince etiket öneki olarak kullanılır ("VKN: 852…"), değer boşsa dangling etiket basılmaz. Testler: `tests/test_designer_templates.py`.

> **Not:** `barcode` öğesi hâlâ gerçek QR/Code128 üretmiyor (yer tutucu kutu). Gerçek karekod için ileride bir kodlayıcı (ör. `segno` / `python-barcode`) eklenmeli.

---

## 🚀 3. Hızlı Başlatıcılar Listesi

Proje kök dizininde hazır bulunan çalıştırıcılar:
- **`TOYA_Teklif_Tasarimci.bat`:** Görsel Form & Rapor Tasarımcısı (Aşama 2 PoC).
- **`TOYA_Teklif_Baski_Onizleme.bat`:** Tam sayfa vektörel baskı önizleme ve PDF çıktısı (Aşama 1 PoC).

---
> **Not:** Tüm geliştirmeler `feat/gorsel-tasarimci-ve-widget-katalogu` branch'inde izole olarak korunmaktadır.
