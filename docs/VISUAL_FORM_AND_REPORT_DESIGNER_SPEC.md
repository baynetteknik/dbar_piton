# 📐 TOYA ERP - Birleşik Görsel Tasarımcı & Rapor Motoru Şartnamesi (Master Specification)

Bu doküman, **TOYA ERP** sistemi içerisinde yer alacak **Bant Tabanlı Görsel Form & Rapor Tasarımcısı (Band-Based Report Engine)** ile **İnteraktif Ekran Tasarımcısı**'nın teknik mimarisini, veri modellerini, bileşen standartlarını ve render kurallarını belirler.

---

## 📑 İÇİNDEKİLER
1. [🏗️ Temel Mimari Prensipler](#1-temel-mimari-prensipler)
2. [🎛️ İki Ana Tasarım Modu](#2-iki-ana-tasarım-modu)
3. [📐 Genişletilmiş Bant (Band) Mimarisi & Hiyerarşisi](#3-genişletilmiş-bant-band-mimarisi--hiyerarşisi)
4. [🧩 Görsel Tasarımcı Bileşenleri (Visual Report Items)](#4-görsel-tasarımcı-bileşenleri)
5. [🌲 Sol Panel: Hiyerarşik Veri Ağacı (Data Tree)](#5-sol-panel-hiyerarşik-veri-ağacı)
6. [⚙️ Sağ Panel: Milimetrik Özellikler Denetçisi (Property Inspector)](#6-sağ-panel-milimetrik-özellikler-denetçisi)
7. [🧮 Formül, Fonksiyon & İfade Motoru (Expression Engine)](#7-formül-fonksiyon--ifade-motoru)
8. [📄 Kağıt, Yazıcı & Sürekli Form Yönetimi](#8-kağıt-yazıcı--sürekli-form-yönetimi)
9. [💾 Standart JSON Şablon Formatı (Template Schema)](#9-standart-json-şablon-formatı)
10. [🖨️ Baskı & PDF Render Motoru (Print Execution Engine)](#10-baskı--pdf-render-motoru)
11. [🤖 AI ile Kod & Şablon Üretim Entegrasyonu](#11-ai-ile-kod--şablon-üretim-entegrasyonu)

---

## 1. 🏗️ Temel Mimari Prensipler

1. **WYSIWYG (What You See Is What You Get):** Ekranda milimetrik olarak tasarlanan form, yazıcıdan veya PDF çıktısından birebir aynı oranda çıkar.
2. **Piksel Bağımsız Milimetrik Hassasiyet:** Tüm koordinatlar, bant yükseklikleri ve kenar boşlukları milimetre (`mm`) tabanlıdır. Ekran DPI değişimlerinden ve işletim sistemi çözünürlüklerinden etkilenmez.
3. **Mıknatıslı Izgara (Snap to Grid):** Çizim esnasında nesneler 5mm / 2.5mm / 1mm ızgara çizgilerine otomatik yapışır; nesneler arası otomatik hizalama kılavuzları (magnetic guidelines) bulunur.
4. **Çoklu Sayfa & Akıllı Taşma Yönetimi (Pagination & Overflow):** 
   - Kalem satırları sayfayı aştığında yeni sayfaya (`newPage()`) otomatik geçer.
   - Sayfa başlığı ve kolon başlıkları yeni sayfada yinelenir.
   - **Yetim Satır Koruması (Keep-Together):** Belge dip toplamı tek başına bir sonraki sayfaya öksüz/yetim olarak düşmez; en az 1-2 kalem satırı ile birlikte sonraki sayfaya taşınır.
5. **Dinamik İçerik Büyümesi (`can_grow` / `can_shrink`):** Uzun ürün açıklamaları veya sözleşme maddeleri için bantlar ve metin kutuları içeriğe göre otomatik uzar veya boş alanlar daralır.

---

## 2. 🎛️ İki Ana Tasarım Modu

Tasarımcı açılışında kullanıcıya iki çalışma modu sunulur:

| Mod | Kullanım Amacı | Temel Çıktı | Çıktı Hedefi |
| :--- | :--- | :--- | :--- |
| **🖥️ Ekran Tasarımı (UI Screen)** | ERP masaüstü kullanıcı arayüzü ekranları | `scr_*.json` + PyQt Ekranı | `ThreePanelBaseWidget`, Tablolar, Butonlar, Kartlar |
| **🖨️ Form & Rapor Tasarımı (Print / Document)** | Fatura, Teklif Mektubu, İrsaliye, Barkod Etiketi, Rapor | `tpl_*.json` + PDF/Baskı | `QPrinter`, Vektörel PDF, Lazer/Termal/Sürekli Form Yazıcı |

---

## 3. 📐 Genişletilmiş Bant (Band) Mimarisi & Hiyerarşisi

Endüstri standardı profesyonel ERP form ve rapor bant hiyerarşisi:

```text
+-------------------------------------------------------------------------------+
| 🌊 FİLİGRAN / ARKA PLAN (Overlay Band) [Baskı: Sayfa Altlığı / Taslak / İptal]|
|    - Arka plan taranmış matbu evrak kılavuzu veya "İPTAL / TASLAK" filigranı  |
+-------------------------------------------------------------------------------+
| 📜 RAPOR BAŞLIĞI (Report Title) [Baskı: Sadece 1. Sayfanın En Başında]       |
|    - Kurumsal Kapak Başlığı, Büyük Şirket Künyesi, Belge Tanıtımı             |
+-------------------------------------------------------------------------------+
| 🏷️ SAYFA ÜST BİLGİSİ (Page Header) [Baskı: Her Sayfanın En Üstünde]          |
|    - Firma Logosu, Şirket Ünvanı, Belge No, Belge Tarihi                      |
+-------------------------------------------------------------------------------+
| 👤 CARİ / MÜŞTERİ BİLGİ BANDI (Header Group)                                  |
|    - Müşteri Adı, Vergi Dairesi, Vergi No, Adres, Telefon, Yetkili            |
+-------------------------------------------------------------------------------+
| 🗂️ GRUP BAŞLIĞI (Group Header) [Baskı: Grup Değiştikçe Basılır]               |
|    - Örn: [KDV Oranı: %20] veya [Depo: Merkez Depo] veya [Kategori: Donanım]   |
+-------------------------------------------------------------------------------+
| 📋 KOLON BAŞLIĞI (Column Header) [Baskı: Tablo Kalemleri Üstünde]             |
|    - [Sıra] [Stok Kodu] [Malzeme Açıklaması] [Miktar] [Birim] [Fiyat] [Tutar] |
+-------------------------------------------------------------------------------+
| 📊 DETAY / SATIR BANDI (Data Detail Band) [Baskı: Her Kalem İçin Tekrarlar]  |
|    - [1]    [STK-001]   [Laptop Çantası]     [2]      [Adet]  [500]   [1000] |
+-------------------------------------------------------------------------------+
| 🔗 ALT / BAĞLI BANT (Child Band) [Baskı: Detay Satırına Ek Olarak Dinamik]   |
|    - Seri No/Lot Listesi, Ürün Resmi, Ek Açıklamalar veya Teknik Özellikler   |
+-------------------------------------------------------------------------------+
| 📑 GRUP ÖZETİ (Group Footer) [Baskı: Grup Bitiminde Ara Toplam]               |
|    - Kategori / KDV Grubu Bazlı Ara Toplamlar ve Kalem Adetleri               |
+-------------------------------------------------------------------------------+
| 🔄 KOLON ALT BİLGİSİ / NAKLİ YEKÛN (Column Footer) [Baskı: Sayfa Sonu Toplamı]|
|    - Sayfadan sayfaya devreden ara toplam (Nakli Yekûn / Sayfa İcmali)        |
+-------------------------------------------------------------------------------+
| 💰 RAPOR ÖZETİ / DİP TOPLAM (Report Summary) [Baskı: Son Sayfada]             |
|    - Ara Toplam, İskonto, KDV (%20), GENEL TOPLAM, Yazıyla Tutar, Banka IBAN  |
+-------------------------------------------------------------------------------+
| 📄 SAYFA ALTI (Page Footer) [Baskı: Her Sayfanın En Altında]                  |
|    - Kaşe / İmza Kutuları, Belge Dip Notu, Sayfa No: [Page#] / [TotalPages#]  |
+-------------------------------------------------------------------------------+
```

### Bant Davranış Kuralları:
1. **`report_title`:** Yalnızca belgenin 1. sayfasında, her şeyin en üstünde basılır. 2. ve sonraki sayfalarda yer almaz.
2. **`page_header`:** Her sayfanın tepesinde yer alır. İstenirse `print_on_first_page: false` verilerek ilk sayfada `report_title` ile çakışması önlenir.
3. **`group_header` / `group_footer`:** `group_by` ifadesine (örn: `kalem.kdv_orani`) bağlıdır. Grup alanı değiştikçe başlık ve ara toplam tetiklenir.
4. **`child_band`:** Bir detay satırına ek alt içerik basmak gerektiğinde (örn: çok satırlı ürün açıklaması, seri no listesi) kullanılır. Veri yoksa otomatik gizlenir (`can_shrink: true`).
5. **`overlay_band`:** Sayfanın arkasında sabit koordinatlarda asılı durur. Sayfalama akışını kaydırmaz; arka plan filigranı ve matbu form baskı kılavuzu olarak görev yapar.

---

## 4. 🧩 Görsel Tasarımcı Bileşenleri (Visual Report Items)

Form ve rapor tasarımında bantların içerisine sürüklenebilen görsel nesneler:

| Bileşen Tipi | Kod | Açıklama | Desteklenen Nitelikler |
| :--- | :--- | :--- | :--- |
| **Sabit Metin** | `text` / `label` | Değişmeyen başlık ve etiket metinleri | Font, Boyut, Renk, Çerçeve, Hizalama |
| **Dinamik Veri Alanı** | `data_field` | DB veya nesne modelinden gelen canlı veri | `field: "cari.unvan"`, Format, `can_grow` |
| **Resim & Logo** | `image` | Kurumsal logo, kaşe/imza, ürün görseli | `aspect_ratio: "keep"`, Base64, Dosya Yolu |
| **Barkod & Karekod** | `barcode` | 1D ve 2D barkodlar (GİB e-Belge QR Kod zorunludur) | `format: "qrcode" \| "code128" \| "ean13"` |
| **Çizgi & Ayırıcı** | `line` | Yatay ve dikey ayırıcı çizgiler | Çizgi stili (Solid, Dashed), Kalınlık, Renk |
| **Kutu / Çerçeve** | `box` / `shape` | Vurgu kutuları, imza çerçeveleri | Dolgu rengi, Kenarlık, Köşe yumuşatma (`radius`)|
| **Zengin Metin** | `richtext` | Sözleşme maddeleri, HTML içerikli uzun metinler | HTML formatlama, `can_grow: true` |
| **Alt Rapor** | `subreport` | Bağımsız ikinci tablo (örn: Teklif + Hizmet Kalemleri) | `dataset_ref`, Ayrı bant yapısı |
| **Sistem Bilgisi** | `system_var` | Sayfa no, toplam sayfa, baskı tarihi, kullanıcı | `[Page#]`, `[Date#]`, `[User#]` |

---

## 5. 🌲 Sol Panel: Hiyerarşik Veri Ağacı (Data Tree)

Sol panelde ERP veritabanından gelen veri alanları kategorize edilmiş ağaç olarak sunulur:

* **📁 Şirket Bilgileri (`sirket.*`)**
  * `sirket.unvan`, `sirket.ticaret_unvani`, `sirket.logo`, `sirket.vergi_dairesi`, `sirket.vergi_no`, `sirket.mersis_no`, `sirket.adres`, `sirket.telefon`, `sirket.eposta`, `sirket.iban_listesi`
* **📁 Cari / Müşteri Bilgileri (`cari.*`)**
  * `cari.kod`, `cari.unvan`, `cari.yetkili`, `cari.vergi_dairesi`, `cari.vergi_no`, `cari.adres`, `cari.bakiye`, `cari.telefon`, `cari.eposta`, `cari.sehir`, `cari.ulke`
* **📁 Belge Genel Parametreleri (`belge.*`)**
  * `belge.no`, `belge.tarih`, `belge.vade_tarihi`, `belge.para_birimi`, `belge.kur`, `belge.durum`, `belge.notlar`, `belge.ozel_kod`, `belge.plasiyer_adi`, `belge.barkod_no`, `belge.gib_karekod_data`
* **📁 Satır Kalemleri (`kalem.*`)** *(Detay Bandı İçin)*
  * `kalem.sira_no`, `kalem.stok_kodu`, `kalem.stok_adi`, `kalem.miktar`, `kalem.birim`, `kalem.birim_fiyat`, `kalem.iskonto_orani`, `kalem.iskonto_tutari`, `kalem.kdv_orani`, `kalem.kdv_tutari`, `kalem.satir_tutari`, `kalem.aciklama`, `kalem.seri_no_listesi`
* **📁 Finansal Dip Toplamlar (`finans.*`)**
  * `finans.ara_toplam`, `finans.iskonto_tutari`, `finans.kdv_matrahi`, `finans.kdv_tutari`, `finans.tevkifat_tutari`, `finans.genel_toplam`, `finans.yaziyla_tutar`
* **📁 Sistem Değişkenleri (`sistem.*`)**
  * `sistem.sayfa_no`, `sistem.toplam_sayfa`, `sistem.baski_tarihi`, `sistem.baski_saati`, `sistem.kullanici`

---

## 6. ⚙️ Sağ Panel: Milimetrik Özellikler Denetçisi

Seçilen herhangi bir bant veya çizim öğesi için aşağıdaki özellikler düzenlenir:

| Grup | Özellik Adı | Tip / Seçenekler | Açıklama |
| :--- | :--- | :--- | :--- |
| **Konum & Boyut** | `Sol (X)` | Sayı (mm) | Sayfanın solundan olan mesafe |
| | `Üst (Y)` | Sayı (mm) | Bulunduğu bandın üstünden olan mesafe |
| | `Genişlik (W)` | Sayı (mm) | Öğenin milimetrik genişliği |
| | `Yükseklik (H)` | Sayı (mm) | Öğenin milimetrik yüksekliği |
| | `Z-Index` | Tamsayı | Katman sıralaması (Ön/Arka) |
| **Tipografi** | `Font Ailesi` | Font Seçici | Segoe UI, Arial, Times New Roman, Roboto |
| | `Font Boyutu` | Sayı (pt) | 8pt, 9pt, 10pt, 12pt, 14pt, 18pt |
| | `Stil` | Toggle | Kalın (Bold), İtalik, Altı Çizili |
| | `Yazı Rengi` | Renk Seçici | HEX / RGB Renk Paleti |
| | `Hizalama` | Seçim | Sol, Orta, Sağ, İki Yana Yasla, Üst/Orta/Alt |
| **Çerçeve / Çizgi** | `Üst / Alt Çizgi`| Var / Yok | Kenarlık çizgileri |
| | `Sol / Sağ Çizgi`| Var / Yok | Yan kenarlıklar |
| | `Çizgi Kalınlığı`| Sayı (pt) | 0.5pt, 1pt, 1.5pt, 2pt |
| | `Çizgi Stili` | Seçim | Düz (Solid), Kesikli (Dashed), Noktalı (Dotted) |
| | `Çizgi Rengi` | Renk Seçici | Kenarlık rengi |
| | `Arka Plan Dolgu`| Renk Seçici | Zemin dolgu rengi |
| **Dinamik Davranış**| `Otomatik Genişle`| Boolean (`can_grow`) | Metin sığmazsa yüksekliği otomatik uzat |
| | `Boşsa Daralt` | Boolean (`can_shrink`)| Alan boşsa sıfır yüksekliğe indir |
| | `Metin Kaydır` | Boolean (`word_wrap`) | Metni alt satıra otomatik sar |
| | `Bölünme Engelle`| Boolean (`keep_together`)| Sayfa sınırında bandın bölünmesini önle |
| **Veri & Format** | `Veri Alanı` | ComboBox | `{cari.unvan}`, `{kalem.satir_tutari}` vb. |
| | `Format Tipi` | Seçim | Metin, Sayı (`#,##0.00`), Para (`#,##0.00 TL`), Tarih (`GG.AA.YYYY`), Yüzde (`%0.00`) |
| **Koşullu Mantık** | `Görünürlük Kuralı`| Formül Metni | Örn: `finans.iskonto_tutari > 0` |
| | `Koşullu Stil` | Stil Kuralı | Örn: `kalem.iskonto_orani > 15 ? red : black` |

---

## 7. 🧮 Formül, Fonksiyon & İfade Motoru (Expression Engine)

Statik veri alanlarının ötesinde, şablon içinde dinamik hesaplama ve manipülasyon sağlayan güvenli ifade motoru:

### 1. Toplama (Aggregate) Fonksiyonları:
- `[SUM(kalem.satir_tutari)]` $\rightarrow$ Detay satırlarının toplamını alır.
- `[COUNT(kalem.sira_no)]` $\rightarrow$ Kalem adedini sayar.
- `[AVG(kalem.birim_fiyat)]` $\rightarrow$ Aritmetik ortalama hesaplar.

### 2. Koşul & Mantık Fonksiyonları:
- `[IIF(kalem.iskonto_orani > 0, kalem.iskonto_orani, "-")]` $\rightarrow$ Koşula göre değer döndürür.
- `[ISNULL(cari.yetkili, "İlgili Belirtilmedi")]` $\rightarrow$ Boş değer kontrolü yapar.

### 3. ERP Finansal & Metin Fonksiyonları:
- `[YAZIYLA(finans.genel_toplam, "TL")]` $\rightarrow$ Rakamı Türkçe fatura metnine çevirir (*"Yalnız BirBinSekizYüzDoksanÜç Türk Lirasıdır"*).
- `[UPPER(cari.unvan)]` $\rightarrow$ Büyük harfe dönüştürür.
- `[FORMAT_DATE(belge.tarih, "DD.MM.YYYY")]` $\rightarrow$ Tarih formatlar.

---

## 8. 📄 Kağıt, Yazıcı & Sürekli Form Yönetimi

ERP süreçlerinde kullanılan farklı çıktı türlerini destekleyen sayfa yöneticisi:

| Kağıt Türü | Genişlik x Yükseklik | Birim | Kullanım Alanı | Hedef Donanım |
| :--- | :--- | :--- | :--- | :--- |
| **Standart A4** | 210.0 x 297.0 mm | mm | Fatura, Teklif Mektubu, İrsaliye | Standart Lazer/Mürekkep Yazıcı |
| **Standart A5** | 148.0 x 210.0 mm | mm | Kasa Makbuzu, Servis Fişi | Lazer / Masaüstü Yazıcı |
| **Sürekli Form (11")** | 240.0 x 279.4 mm (11 inç) | inç / mm | Matbu Fatura, Çok Nüshalı İrsaliye | Nokta Vuruşlu (Dot-Matrix Traktörlü) |
| **Sürekli Form (12")** | 240.0 x 304.8 mm (12 inç) | inç / mm | Eski Tip Matbu Faturalar | Nokta Vuruşlu (Epson, Oki) |
| **Termal Fiş (80mm)** | 80.0 mm x Sonsuz (Rulo) | mm | Perakende Satış Fişi, Adisyon | 80mm Termal POS Yazıcı |
| **Termal Etiket** | 50.0 x 30.0 mm (Özel) | mm | Ürün Barkodu, Raf Etiketi, Koli | Termal Barkod Yazıcı (Argox, Zebra) |

---

## 9. 💾 Standart JSON Şablon Formatı (Template Schema)

Tasarımcının ürettiği zengin `.json` şablon örneği (Karekod, Dinamik Büyüme ve Formül destekli):

```json
{
  "schema_version": "2.0",
  "template_id": "tpl_fatura_gib_kurumsal_a4",
  "title": "Kurumsal Satış Faturası A4 (Karekodlu)",
  "template_type": "print_report",
  "page": {
    "size": "A4",
    "orientation": "portrait",
    "width_mm": 210.0,
    "height_mm": 297.0,
    "margin_top_mm": 10.0,
    "margin_bottom_mm": 10.0,
    "margin_left_mm": 10.0,
    "margin_right_mm": 10.0
  },
  "bands": [
    {
      "id": "band_page_header",
      "type": "page_header",
      "height_mm": 35.0,
      "items": [
        {
          "id": "img_logo",
          "type": "image",
          "field": "sirket.logo",
          "x_mm": 0.0,
          "y_mm": 0.0,
          "w_mm": 45.0,
          "h_mm": 22.0
        },
        {
          "id": "txt_doc_title",
          "type": "text",
          "text": "SATIŞ FATURASI",
          "x_mm": 120.0,
          "y_mm": 0.0,
          "w_mm": 70.0,
          "h_mm": 10.0,
          "font_size": 16,
          "font_bold": true,
          "align": "right"
        },
        {
          "id": "qr_gib_code",
          "type": "barcode",
          "barcode_format": "qrcode",
          "field": "belge.gib_karekod_data",
          "x_mm": 165.0,
          "y_mm": 12.0,
          "w_mm": 22.0,
          "h_mm": 22.0
        }
      ]
    },
    {
      "id": "band_column_header",
      "type": "column_header",
      "height_mm": 7.0,
      "items": [
        {
          "id": "lbl_sira",
          "type": "text",
          "text": "Sıra",
          "x_mm": 0.0,
          "y_mm": 0.0,
          "w_mm": 10.0,
          "h_mm": 7.0,
          "font_bold": true,
          "align": "center",
          "border_bottom": true
        },
        {
          "id": "lbl_stok_adi",
          "type": "text",
          "text": "Mal / Hizmet Açıklaması",
          "x_mm": 12.0,
          "y_mm": 0.0,
          "w_mm": 95.0,
          "h_mm": 7.0,
          "font_bold": true,
          "align": "left",
          "border_bottom": true
        },
        {
          "id": "lbl_tutar",
          "type": "text",
          "text": "Satır Tutarı",
          "x_mm": 150.0,
          "y_mm": 0.0,
          "w_mm": 40.0,
          "h_mm": 7.0,
          "font_bold": true,
          "align": "right",
          "border_bottom": true
        }
      ]
    },
    {
      "id": "band_detail",
      "type": "detail_data",
      "dataset": "kalemler",
      "height_mm": 8.0,
      "can_grow": true,
      "items": [
        {
          "id": "col_sira",
          "type": "data_field",
          "field": "kalem.sira_no",
          "x_mm": 0.0,
          "y_mm": 0.0,
          "w_mm": 10.0,
          "h_mm": 8.0,
          "align": "center"
        },
        {
          "id": "col_stok_adi",
          "type": "data_field",
          "field": "kalem.stok_adi",
          "x_mm": 12.0,
          "y_mm": 0.0,
          "w_mm": 95.0,
          "h_mm": 8.0,
          "can_grow": true,
          "word_wrap": true,
          "align": "left"
        },
        {
          "id": "col_tutar",
          "type": "data_field",
          "field": "kalem.satir_tutari",
          "x_mm": 150.0,
          "y_mm": 0.0,
          "w_mm": 40.0,
          "h_mm": 8.0,
          "align": "right",
          "format": "currency"
        }
      ]
    },
    {
      "id": "band_report_summary",
      "type": "report_summary",
      "height_mm": 30.0,
      "keep_together": true,
      "items": [
        {
          "id": "txt_yaziyla",
          "type": "expression",
          "expression": "[YAZIYLA(finans.genel_toplam, 'TL')]",
          "x_mm": 0.0,
          "y_mm": 5.0,
          "w_mm": 110.0,
          "h_mm": 10.0,
          "font_size": 9,
          "font_italic": true
        },
        {
          "id": "val_genel_toplam",
          "type": "data_field",
          "field": "finans.genel_toplam",
          "x_mm": 140.0,
          "y_mm": 5.0,
          "w_mm": 50.0,
          "h_mm": 10.0,
          "font_size": 12,
          "font_bold": true,
          "align": "right",
          "format": "currency"
        }
      ]
    }
  ]
}
```

---

## 10. 🖨️ Baskı & PDF Render Motoru (Print Execution Engine)

Render motoru (`ReportPrinterEngine`) aşağıdaki çekirdek adımları icra eder:
1. **Veri Enjeksiyonu & Formül Değerlendirme:** JSON şablonundaki dinamik alanları (`{cari.unvan}`) ve formülleri (`[SUM(...)]`, `[YAZIYLA(...)]`) veri modellerinden okuyarak çözümler.
2. **Milimetre - DPI Vektörel Ölçekleme:** Ekran ve hedef yazıcı arasındaki çözünürlük farkını mm bazında vektörel hesaplayarak piksel bozulmasını önler.
3. **Otomatik Sayfalama & Yetim Satır Koruması:** 
   - Detay satırlarının milimetrik boylarını hesaplar.
   - Sayfa sonu marjına ulaşıldığında `newPage()` komutuyla yeni sayfa açar, sayfa başlığı ve kolon başlıklarını otomatik yineler.
   - Dip toplamın tek başına düşmesini engellemek için son kalem satırlarını dip toplamla birlikte yeni sayfaya taşır.
4. **Çoklu Çıktı Desteği:**
   - `QPrinter` ile doğrudan fiziksel yazıcıya gönderme.
   - `QPainter` / PDF Writer ile yüksek çözünürlüklü vektörel PDF üretme.
   - Ekranda interaktif **Baskı Önizleme Diyaloğu (Print Preview Dialog)** ile sayfa geçişleri, yakınlaştırma (zoom) ve yazdırma.

---

## 11. 🤖 AI ile Kod & Şablon Üretim Entegrasyonu

Kullanıcı görsel tasarımcı üzerinden şablonu oluşturduktan sonra tek bir komutla:
* *"Bu fatura şablonu için otomatik e-posta gönderme servisini bağla."*
* *"Bu liste şablonuna göre yeni bir Depo Stok Raporu ekranı üret."*
diyerek yapay zekaya doğrudan çalışır kod ve ekran bileşeni ürettirebilir.
