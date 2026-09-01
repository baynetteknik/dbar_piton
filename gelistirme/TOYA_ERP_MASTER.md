# TOYA ERP — MASTER GELİŞTİRME DOKÜMANI

> **Hazırlayan:** Baynet Bilişim Teknolojileri | Alparslan Bey  
> **Son Güncelleme:** 27 Ağustos 2026  
> **Kullanım:** Yeni chat/oturum açıldığında bu dosyayı ver → kaldığın yerden devam et.

---

## 1. Genel Mimari Kararlar

### 1.1 Geliştirme Felsefesi

- **DRY:** Her ekran tipi için tek şablon — tüm modüller bunu kullanır
- **MVP Önce:** Bir modülü bitir → kullan → sonrakine geç
- **Komponent Önce:** Her widget ayrı yazılır, test edilir, şablona eklenir
- **Şablon Önce Kod Sonra:** screen_definition_dialog ile tanımla, sonra kodla
- **JSON Driven UI:** Ekran tanımları screen_registry'de — masaüstü/web/mobil aynı tanımı okur
- **Yetki Entegrasyonu:** Her widget rol bazlı gösterilir/gizlenir

### 1.2 Yapay Zeka Sürekliliği

| Plan | Fiyat | Ne Zaman |
|------|-------|----------|
| Claude Pro | $20/ay | 10 saat/hafta için yeterli |
| Claude Pro Max | $100/ay | Çok yoğun çalışmak için |
| API (kullandıkça) | Token başına | Cursor ile entegre için ideal |

| Görev | Araç |
|-------|------|
| Mimari kararlar, iş mantığı, karmaşık kod | Claude |
| Mevcut kodu düzenle, refactor, hata bul | Cursor + Claude API |
| Yardım metinleri, tooltip, hata mesajları | ChatGPT / Gemini |
| Form/ekran hızlı mockup | v0.dev / Bolt.new |

---

## 2. Ekran Mimarisi — 3 Ana Şablon

| Şablon | Kod Dosyası | Kullanım Yeri |
|--------|------------|---------------|
| `ListeŞablonu` | BaseListScreen + DIA3PanelBase | Teklif/Fatura/İrsaliye/Sipariş/Stok/Cari listeleri |
| `FişDetayŞablonu` | TransactionDocumentDialog | Teklif/Fatura/İrsaliye/Sipariş detayları |
| `KasaBankaŞablonu` | Henüz yok — yapılacak | Kasa/Banka/Cari fiş ekranları |

### 2.1 Liste Şablonu Yapısı

| Bölge | Komponent | Açıklama |
|-------|-----------|----------|
| Sol EdgePanel | `ActionBarWidget` | Ekle/Düzelt/Kopyala/Sil/TopluSil/PasifAl/Kapat |
| Orta | `DbGridWidget` | FilterableTableView — checkbox/çöp/filtre satırı/sayfalama |
| Sağ EdgePanel üst | `FilterWidget` | Metin/Durum/Tarih/Grup filtreleri |
| Sağ EdgePanel alt | `ExportWidget` | Yazdır/Excel/PDF/Import/Rapor |
| Alt bar | `PaginationWidget` | İlk/Önceki/Sonraki/Son + kayıt sayısı |

### 2.2 Fiş Detay Şablonu Yapısı

| Bölge | Komponent | Açıklama |
|-------|-----------|----------|
| En üst bar | `FisHeaderWidget` | Tür/Firma/Şube/E-Belge/Belge No |
| Sekmeler | `TabWidget` | Genel/Detay/İskontolar/Ek Alanlar/Kümülatif KDV |
| Tab 1 sol üst | `CariKunyeWidget` | Cari Kodu/Ünvan/Vergi/Sevk Adresi |
| Tab 1 orta üst | `BelgeVadeWidget` | Seri-No/Tarih/Vade/Çıkış Deposu |
| Tab 1 sağ üst | `HareketFinansWidget` | Döviz/KDV/Şekil-Kasa/İşlemler |
| Tab 1 orta | `HareketGridWidget` | Fiş satırları — Tür/Barkod/Stok/Miktar/Fiyat/İskonto |
| Alt sol | `AltIskontoWidget` | Alt iskonto & masraf tablosu |
| Alt orta | `NotlarWidget` | Notlar & Şartlar |
| Alt sağ | `ToplamWidget` | Ara Toplam/İskonto/KDV/Genel Toplam |

---

## 3. Komponent Kataloğu ve Yapılacaklar

### 3.1 ActionBarWidget (Sol EdgePanel)

| Özellik | Detay | Durum |
|---------|-------|-------|
| Ekle | F3, rol: doc.create | ✅ Mevcut |
| Düzenle | F4, rol: doc.edit | ✅ Mevcut |
| Kopyala | rol: doc.create | ✅ Mevcut |
| Sil | Del, onay kutusu | ✅ Mevcut |
| **Toplu Sil** | Seçili satırları sil | ❌ Yapılacak |
| **Pasife Al / Aktife Al** | Durum toggle | ❌ Yapılacak |
| Dönüştür | Siparişe/Faturaya | ✅ Mevcut |
| Kapat | Tab'ı kapat | ✅ Mevcut |
| Açılır/Kapanır | EdgeTriggeredPanel | ✅ Mevcut |
| **İlk açılış durumu** | Açık/Kapalı ayarı | ❌ Yapılacak |
| **Genişlik ayarı** | px — screen_definition'dan | ❌ Yapılacak |

### 3.2 DbGridWidget (Orta Panel)

| Özellik | Durum |
|---------|-------|
| En sol: Checkbox (çoklu seçim) | ✅ Mevcut |
| İkinci: Çöp sepeti (tek satır sil) | ✅ Mevcut |
| Üst filtre satırı + çöp=temizle | ✅ Mevcut |
| Sütun sıralama | ✅ Mevcut |
| Sütun gizle/göster + profil | ✅ Mevcut |
| Koşullu renklendirme | 🔶 Kısmen |
| Sayfalama 25/50/100 | ✅ Mevcut |

### 3.3 FilterWidget (Sağ EdgePanel üst)

| Özellik | Durum |
|---------|-------|
| Metin arama | ✅ Mevcut |
| Durum filtresi | ✅ Mevcut |
| **Tarih aralığı filtresi** | ❌ Yapılacak |
| **Grup filtresi** | ❌ Yapılacak |
| Filtreleri temizle | ✅ Mevcut |
| **Filtre sayacı** | ❌ Yapılacak |

### 3.4 ExportWidget (Sağ EdgePanel alt)

| Özellik | Durum |
|---------|-------|
| Excel dışa aktar | ✅ Mevcut |
| **PDF dışa aktar** | ❌ Yapılacak |
| **Excel'den içe aktar** | ❌ Yapılacak |
| **Yazdır** | ❌ Yapılacak |

### 3.5 Fiş Detay Komponentleri

Tümü `transaction_document_dialog.py` içinde mevcut:
- `FisHeaderWidget` ✅
- `CariKunyeWidget` ✅
- `BelgeVadeWidget` ✅
- `HareketFinansWidget` ✅
- `HareketGridWidget` ✅
- `AltIskontoWidget` ✅
- `NotlarWidget` ✅
- `ToplamWidget` ✅

---

## 4. Ekran Tasarımcısı — screen_definition_dialog.py

### 4.1 Mevcut Özellikler (35KB, çalışıyor)
- 5 sekme: Genel / Panel Düzeni / Grid-Sütun / Eylemler / Canlı Önizleme
- Grid preset seçimi, yükseklik ayarı, eylem yönetimi
- screen_registry'e kayıt, F2 kaydet / F5 önizle

### 4.2 Eklenecek Özellikler

| Özellik | Öncelik |
|---------|---------|
| Komponent seçimi (hangi butonlar aktif) | P0 |
| Sidebar ilk durum (açık/kapalı) | P0 |
| Filtre widget ayarları | P0 |
| Toplu sil + Pasife al butonları | P0 |
| Sidebar genişlik px ayarı | P1 |
| Export widget ayarları | P1 |
| Tarih aralığı filtresi | P1 |

---

## 5. Modül Yol Haritası

### 🔴 Faz 1 — Ticari Temel (MVP) — 8 Hafta

| Hafta | Görev | Çıktı |
|-------|-------|-------|
| 1 | ActionBarWidget: TopluSil + PasifAl ekle | Sol panel tam |
| 2 | FilterWidget: Tarih + Grup filtresi ekle | Sağ panel tam |
| 3 | Teklif Listesi veri bağlantısı | TEKLIST001 tam |
| 4 | Teklif Detay bağlantısı | Teklif CRUD tam |
| 5 | Cari + Stok listesi | CAKALST001 + STKLIST001 |
| 6 | Sipariş + İrsaliye | Tekliften dönüşüm |
| 7 | Fatura | FATLIST001 tam |
| 8 | Test + hata + demo | **FAZ 1 TESLİM ✅** |

### 🟠 Faz 2 — Finans
Kasa, Banka, Çek/Senet

### 🟡 Faz 3 — Operasyon
Görevler/Notlar, Projeler, Chat

### 🔵 Faz 4 — Entegrasyon
WooCommerce ✅ temel var | Akınsoft ✅ temel var | Logo ✅ temel var | E-Fatura

---

## 6. Mevcut Kod Durumu (27 Ağustos 2026)

### ✅ Tamamlanmış Altyapı

| Dosya | Boyut | Açıklama |
|-------|-------|----------|
| `src/core/models.py` | 26KB | DB modelleri |
| `src/desktop/ui/components/filterable_table.py` | 32KB | DbGrid + filtre + profil |
| `src/desktop/ui/components/base_list_screen.py` | 9.4KB | Liste şablonu |
| `src/desktop/ui/components/dia_3_panel_base.py` | 7.3KB | 3 panel layout |
| `src/desktop/ui/components/edge_panel.py` | 9.4KB | Açılır/kapanır panel |
| `src/desktop/core/screen_registry.py` | Mevcut | Ekran tanımları |
| `src/desktop/core/grid_presets.py` | Mevcut | Grid presetleri |
| `src/desktop/ui/dialogs/screen_definition_dialog.py` | 35KB | Ekran tasarımcısı |
| `src/desktop/ui/dialogs/transaction_document_dialog.py` | 79KB | Fiş detay şablonu |

### 🔶 Kısmen Hazır

| Dosya | Yapılacak |
|-------|----------|
| `quotations.py` (31KB) | Veri bağlantısı eksik |
| `customers.py` (90KB) | Yeni şablona bağlanacak |
| `main_window.py` (35KB) | Modül bağlantıları |

### ❌ Başlanmadı
Stok, Sipariş, İrsaliye, Fatura, Kasa, Banka, Görevler

---

## 7. Yapay Zeka Kullanım Kılavuzu

### Yeni Chat Açıldığında Ver
1. Bu dosya (`TOYA_ERP_MASTER.md`)
2. İlgili modülün `gelistirme/` MD dosyaları
3. İlgili `.py` kod dosyaları

### Hangi Dosyalar Hangi Konuya

| Konu | İlgili Dosyalar |
|------|----------------|
| Liste ekranı sorunu | `quotations.py` + `dia_3_panel_base.py` + `screen_registry.py` |
| Grid sorunu | `filterable_table.py` + `grid_presets.py` |
| Fiş detay sorunu | `transaction_document_dialog.py` |
| Ekran tanımı | `screen_definition_dialog.py` + `screen_registry.py` |
| Komponent ekle | İlgili `*_widget.py` + `quotations.py` |

### Komut Örnekleri
```
"ActionBarWidget'a TopluSil butonu ekle. quotations.py ekte."
"Teklif listesi veri gelmiyor. quotations.py + screen_registry.py ekte."
"Stok Kart Listesi yapacağız. ListeŞablonu kullan. gelistirme/03_stok/ ekte."
"screen_definition_dialog'a komponent seçim özelliği ekle."
```

---

> Bu döküman her yeni modül veya komponent eklendikçe güncellenmelidir.

---

## 10. ToyaUI — Uzun Vadeli Vizyon

> **Şimdilik:** TOYA ERP içinde komponentler ayrı dosyalara yazılır, düzgün çalışır.  
> **Faz 1 bitince:** `toya-ui` adıyla ayrı Python paketine çıkarılır.

### 10.1 Vizyon

```
toya-ui (PyPI paketi)
    ↓
pip install toya-ui
    ↓
TOYA ERP          → from toya_ui import ListeSablonu
Restoran Otomasyon → from toya_ui import ListeSablonu  
Otel Yönetimi     → from toya_ui import ListeSablonu
Her yeni proje    → from toya_ui import ListeSablonu
```

### 10.2 Hedef Paket Yapısı

```
toya_ui/
├── components/
│   ├── action_bar_widget.py     # Ekle/Sil/Düzelt/TopluSil/PasifAl
│   ├── db_grid_widget.py        # FilterableTableView wrapper
│   ├── filter_widget.py         # Metin/Durum/Tarih/Grup filtreleri
│   ├── export_widget.py         # Excel/PDF/Import/Yazdır
│   └── pagination_widget.py     # Sayfalama
├── templates/
│   ├── liste_sablonu.py         # Tüm liste ekranları için
│   ├── fis_detay_sablonu.py     # Tüm fiş detayları için
│   └── kasa_banka_sablonu.py    # Kasa/Banka fişleri için
├── designer/
│   └── screen_definition_dialog.py  # Görsel ekran tasarımcısı
└── themes/
    └── theme_manager.py         # Merkezi tema yönetimi
```

### 10.3 Kazanımlar

| Konu | Şimdi | ToyaUI ile |
|------|-------|-----------|
| Yeni proje UI | Sıfırdan yaz | pip install + şablon seç |
| Hata düzeltme | Her projede ayrı | Bir yerde düzelt, hepsi düzelir |
| Yapay zeka verimliliği | Her seferinde anlat | "ToyaUI kullan" de, direkt kodla |
| Satılabilirlik | Sadece TOYA ERP | Her PyQt6 projesi için pazarlanabilir |

### 10.4 Aşamalar

**Aşama 1 (Şimdi — TOYA ERP ile paralel):**
- Komponentleri ayrı dosyalara yaz
- TOYA ERP içinde çalışsın
- Soyutlamayı düşünerek kodla

**Aşama 2 (Faz 1 bitince):**
- `toya_ui/` klasörü ayrı repoya çıkar
- `pyproject.toml` ile paketlenebilir hale getir
- Versiyon: v0.1.0

---

## 11. Paralel Yapay Zeka Stratejisi

### 11.1 İş Bölümü

| Yapay Zeka | Görev | Ne Vereceksin |
|-----------|-------|---------------|
| **Claude (sen)** | TOYA ERP ana geliştirme — iş mantığı, DB, karmaşık modüller | MASTER döküman + ilgili .py dosyaları |
| **YZ 2** | ToyaUI komponent geliştirme — ActionBar/DbGrid/Filter widget'ları | MASTER döküman Bölüm 3 + mevcut widget dosyaları |
| **YZ 3** | Yardım metinleri, tooltip, kullanıcı kılavuzu, hata mesajları | Ekran görüntüleri + alan listesi |

### 11.2 YZ 2'ye Verilecek Görevler (ToyaUI Komponentleri)

```
Görev 1: ActionBarWidget
- quotations.py'deki mevcut buton kodunu al
- Ayrı action_bar_widget.py dosyasına çıkar
- TopluSil ve PasifAl butonlarını ekle
- Sidebar ilk durum (açık/kapalı) ve genişlik ayarı ekle
- İlgili dosyalar: quotations.py + edge_panel.py + collapsible_section.py

Görev 2: FilterWidget  
- quotations.py'deki filtre kodunu al
- Ayrı filter_widget.py dosyasına çıkar
- Tarih aralığı ve grup filtresi ekle
- Filtre sayacı ekle
- İlgili dosyalar: quotations.py

Görev 3: ExportWidget
- quotations.py'deki export kodunu al
- Ayrı export_widget.py dosyasına çıkar
- PDF ve Import ekle
- İlgili dosyalar: quotations.py + excel_exporter.py

Görev 4: PaginationWidget
- quotations.py'deki sayfalama kodunu al
- Ayrı pagination_widget.py dosyasına çıkar
- İlgili dosyalar: quotations.py
```

### 11.3 YZ 2'ye Verilecek MASTER Prompt

```
Sen TOYA ERP projesinin UI komponent geliştiricisin.
Görevin: quotations.py içindeki mevcut koddan 
ayrı widget dosyaları oluşturmak.

Kurallar:
- DRY prensibi — her komponent tek dosyada
- PyQt6 kullan
- DIA3PanelBaseWidget şablonuna uygun
- Türkçe yorum satırları
- Her widget bağımsız çalışabilmeli

MASTER döküman ekte. Bölüm 3'e bak.
Görev 1: ActionBarWidget — quotations.py ekte.
```

### 11.4 Paralel Çalışma Takvimi

```
Claude (sen)        YZ 2                    YZ 3
─────────────       ─────────────────       ──────────────
Hafta 1:            ActionBarWidget          Tooltip metinleri
Teklif veri fix     FilterWidget             Hata mesajları

Hafta 2:            ExportWidget             Kullanıcı kılavuzu
Teklif Detay        PaginationWidget         Bölüm 1: Cari

Hafta 3:            ListeSablonu paketleme   Kullanıcı kılavuzu
Cari + Stok         FişDetayŞablonu          Bölüm 2: Teklif

Hafta 4:            screen_definition        Kullanıcı kılavuzu
Sipariş+İrsaliye    komponent seçim ekleme   Bölüm 3: Fatura
```

---

> **Öncelik:** TOYA ERP önce biter. ToyaUI paralelde ilerler ama ERP'yi bekletmez.  
> Bu döküman her yeni modül veya komponent eklendikçe güncellenmelidir.
