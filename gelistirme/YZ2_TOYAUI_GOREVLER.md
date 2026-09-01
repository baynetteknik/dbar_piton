# YZ 2 — ToyaUI Komponent Geliştirme Görevi

> **Bu dosya sadece YZ 2 içindir.**  
> TOYA ERP ana geliştirmesine dokunma.  
> Görevin: Mevcut koddan bağımsız widget dosyaları oluşturmak.

---

## Önce Bunu Oku

Sen **ToyaUI** projesinin komponent geliştiricisisin.

TOYA ERP adında çalışan bir PyQt6 masaüstü ERP uygulaması var.
Bu uygulamanın içinde bazı UI kodları tek büyük dosyalarda gömülü durumda.
Senin görevin bu kodları **ayrı, bağımsız, yeniden kullanılabilir widget dosyalarına** çıkarmak.

**Temel kural:** Her widget kendi dosyasında, bağımsız çalışabilmeli.
Bir widget başka bir widget'a bağımlı olmamalı.

---

## Proje Klasör Yapısı

```
C:\toya_erp\
├── src\
│   └── desktop\
│       └── ui\
│           ├── components\          ← Mevcut component'lar burada
│           │   ├── edge_panel.py
│           │   ├── collapsible_section.py
│           │   ├── filterable_table.py
│           │   └── dia_3_panel_base.py
│           ├── widgets\             ← YENİ KLASÖR — senin çıktıların buraya
│           │   ├── action_bar_widget.py     (Görev 1)
│           │   ├── filter_widget.py         (Görev 2)
│           │   ├── export_widget.py         (Görev 3)
│           │   └── pagination_widget.py     (Görev 4)
│           └── quotations.py        ← Kaynak dosya — DOKUNMA, sadece oku
```

---

## ÖNEMLİ — BUNLARA DOKUNMA

```
❌ quotations.py          → Sadece oku, değiştirme
❌ customers.py           → Hiç açma
❌ main_window.py         → Hiç açma
❌ transaction_document_dialog.py → Hiç açma
❌ screen_registry.py     → Hiç açma
❌ models.py              → Hiç açma
❌ database.py            → Hiç açma
```

**Sadece şu klasöre yaz:**
```
✅ src\desktop\ui\widgets\   ← Burası senin alanın
```

---

## Görev 1: ActionBarWidget

### Ne Yapacaksın
`quotations.py` içindeki sol sidebar buton kodunu al,
`src/desktop/ui/widgets/action_bar_widget.py` dosyasına çıkar.
**Toplu Sil** ve **Pasife Al** butonlarını ekle.
Sidebar'ın ilk açılış durumu (açık/kapalı) ve genişlik ayarı ekle.

### Kaynak Dosyalar (sadece oku)
- `src/desktop/ui/quotations.py` → `init_base_ui` metodundaki sol panel kodu
- `src/desktop/ui/components/edge_panel.py` → EdgeTriggeredPanel sınıfı
- `src/desktop/ui/components/collapsible_section.py` → CollapsibleSection sınıfı

### Çıktı Dosya
```
src/desktop/ui/widgets/action_bar_widget.py
```

### Widget Özellikleri

**Butonlar (sırasıyla):**
| Buton | Kısayol | Sinyal | Stil |
|-------|---------|--------|------|
| ➕ Yeni | F3 | `new_clicked` | default |
| ✏️ Değiştir | F4 | `edit_clicked` | default |
| 📋 Kopyala | — | `duplicate_clicked` | default |
| ❌ Sil | Del | `delete_clicked` | danger (kırmızı) |
| 🗑️ Toplu Sil | — | `bulk_delete_clicked` | danger (kırmızı) |
| ⏸️ Pasife Al | — | `passive_clicked` | warning (sarı) |
| 🔄 Dönüştür | — | `convert_clicked` | default |
| 🖨️ Yazdır/Excel | F9 | `excel_clicked` | default |
| 🚪 Kapat | — | `close_clicked` | kapat (pembe) |

**Ayarlar (constructor parametreleri):**
```python
ActionBarWidget(
    group_title="TEKLİF İŞLEMLERİ",  # Sol panelin başlığı
    convert_label="Siparişe Dönüştür",  # Dönüştür butonu etiketi
    show_buttons=None,  # None = hepsi, liste = sadece bunlar
                        # Örn: ["new", "edit", "delete"]
    hide_buttons=None,  # Gizlenecek butonlar
                        # Örn: ["convert", "bulk_delete"]
    initial_open=False,  # True = açık başlar, False = kapalı
    panel_width=220,     # px cinsinden genişlik
    parent=None
)
```

**Sinyaller:**
```python
new_clicked = pyqtSignal()
edit_clicked = pyqtSignal()
duplicate_clicked = pyqtSignal()
delete_clicked = pyqtSignal()
bulk_delete_clicked = pyqtSignal()
passive_clicked = pyqtSignal()
convert_clicked = pyqtSignal()
excel_clicked = pyqtSignal()
close_clicked = pyqtSignal()
```

**Kullanım örneği (test için):**
```python
bar = ActionBarWidget(
    group_title="TEKLİF İŞLEMLERİ",
    convert_label="Siparişe Dönüştür",
    hide_buttons=["bulk_delete"],  # Toplu Sil gizle
    initial_open=True,
    panel_width=220,
)
bar.new_clicked.connect(lambda: print("Yeni tıklandı"))
bar.delete_clicked.connect(lambda: print("Sil tıklandı"))
```

---

## Görev 2: FilterWidget

### Ne Yapacaksın
`quotations.py` içindeki sağ sidebar filtre kodunu al,
`src/desktop/ui/widgets/filter_widget.py` dosyasına çıkar.
**Tarih aralığı** ve **Grup filtresi** ekle.
**Filtre sayacı** ekle (kaç filtre aktif).

### Kaynak Dosyalar (sadece oku)
- `src/desktop/ui/quotations.py` → `init_base_ui` metodundaki sağ panel filtre kodu
- `src/desktop/ui/components/edge_panel.py`
- `src/desktop/ui/components/collapsible_section.py`

### Çıktı Dosya
```
src/desktop/ui/widgets/filter_widget.py
```

### Widget Özellikleri

**Filtreler:**
| Filtre | Tip | Parametre adı |
|--------|-----|---------------|
| Ünvan / Kod arama | QLineEdit | `search` |
| Durum | QComboBox | `status` |
| Tarih başlangıç | QDateEdit | `date_from` |
| Tarih bitiş | QDateEdit | `date_to` |
| Grup | QComboBox | `group` |

**Ayarlar (constructor parametreleri):**
```python
FilterWidget(
    show_filters=None,   # None = hepsi, liste = sadece bunlar
                         # Örn: ["search", "status"]
    status_options=None, # Durum filtresi seçenekleri
                         # Örn: ["Tümü", "Açık", "Kapalı"]
    group_options=None,  # Grup filtresi seçenekleri
    initial_open=False,
    panel_width=220,
    parent=None
)
```

**Sinyaller:**
```python
filter_changed = pyqtSignal(dict)
# Örn: {"search": "tatu", "status": "Açık", "date_from": "2026-01-01"}

filters_cleared = pyqtSignal()
```

**Filtre sayacı:** Kaç filtre aktifse "🔍 3 Filtre Aktif" şeklinde göster.

---

## Görev 3: ExportWidget

### Ne Yapacaksın
`quotations.py` içindeki export butonlarını al,
`src/desktop/ui/widgets/export_widget.py` dosyasına çıkar.
**PDF** ve **İçe Aktar** butonlarını ekle.

### Kaynak Dosyalar (sadece oku)
- `src/desktop/ui/quotations.py` → sağ paneldeki DOSYA & AKTARIM kodu

### Çıktı Dosya
```
src/desktop/ui/widgets/export_widget.py
```

### Widget Özellikleri

**Butonlar:**
| Buton | Sinyal |
|-------|--------|
| 📤 Dışa Aktar (Excel) | `export_excel_clicked` |
| 📄 PDF Olarak Kaydet | `export_pdf_clicked` |
| 📥 Excel'den İçe Aktar | `import_excel_clicked` |
| 🖨️ Yazdır | `print_clicked` |
| 📊 Detaylı Rapor | `report_clicked` |

**Ayarlar:**
```python
ExportWidget(
    show_buttons=None,   # None = hepsi
    hide_buttons=None,   # Gizlenecekler
    initial_open=False,
    parent=None
)
```

---

## Görev 4: PaginationWidget

### Ne Yapacaksın
`quotations.py` içindeki sayfalama kodunu al,
`src/desktop/ui/widgets/pagination_widget.py` dosyasına çıkar.
Bağımsız, her listede kullanılabilir hale getir.

### Kaynak Dosyalar (sadece oku)
- `src/desktop/ui/quotations.py` → `pagination_layout` kodu

### Çıktı Dosya
```
src/desktop/ui/widgets/pagination_widget.py
```

### Widget Özellikleri

**Ayarlar:**
```python
PaginationWidget(
    page_sizes=[25, 50, 100],  # Kayıt sayısı seçenekleri
    parent=None
)
```

**Sinyaller:**
```python
page_changed = pyqtSignal(int)        # Sayfa numarası
page_size_changed = pyqtSignal(int)   # Kayıt sayısı
```

**Metodlar:**
```python
widget.set_total(total_records: int)  # Toplam kayıt sayısını set et
widget.current_page() -> int          # Mevcut sayfa
widget.current_page_size() -> int     # Mevcut kayıt sayısı
widget.reset()                        # Sayfa 1'e dön
```

**Görünüm:**
```
⏮️  ⬅️  Sayfa 2 / 10 (Toplam: 243)  ➡️  ⏭️    Adet: [25 kayıt ▼]
```

---

## Genel Kodlama Kuralları

```python
# 1. Her dosyanın başına docstring ekle
"""
ToyaUI — ActionBarWidget
Sol EdgePanel aksiyonlar widget'ı.
Tüm liste ekranlarında kullanılabilir.
"""

# 2. Türkçe yorum satırları
self.btn_new = QPushButton("➕ Yeni (F3)")  # Yeni kayıt ekleme butonu

# 3. Her widget bağımsız import
from PyQt6.QtWidgets import ...
from PyQt6.QtCore import pyqtSignal, Qt
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.collapsible_section import CollapsibleSection

# 4. Constructor'da parent=None
def __init__(self, ..., parent=None):
    super().__init__(parent)

# 5. Sinyaller sınıf seviyesinde tanımla
class ActionBarWidget(QWidget):
    new_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
```

---

## Görev Sırası

```
Önce Görev 4 (PaginationWidget) — en basit, ısınma turu
Sonra Görev 1 (ActionBarWidget) — en kritik
Sonra Görev 3 (ExportWidget) — orta
Son Görev 2 (FilterWidget) — en karmaşık
```

---

## Test Etme

Her widget'ı bitirince şunu yap:

```python
# Widget'ı doğrudan çalıştır — main_window'a bağlamadan
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    widget = ActionBarWidget(
        group_title="TEST",
        initial_open=True
    )
    widget.new_clicked.connect(lambda: print("✅ Yeni çalışıyor"))
    widget.show()
    sys.exit(app.exec())
```

---

## Bitince Ne Yapacaksın

Her görev bitince şunu söyle:
```
✅ Görev [N] tamamlandı.
Dosya: src/desktop/ui/widgets/[dosya_adı].py
Test: Çalıştırıldı, [sinyal] sinyali doğrulandu.
Sonraki: Görev [N+1]'e geçiyorum.
```

---

## Sorularını Nereye Sor

- `quotations.py` içinde anlamadığın bir şey varsa sor
- `edge_panel.py` veya `collapsible_section.py` içinde anlamadığın varsa sor
- **Ana ERP koduna (main_window, models, database) dair soru sorma** — o senin alanın değil

---

> **Özet:** `quotations.py` oku → `src/desktop/ui/widgets/` içine yaz → test et → bildir.  
> TOYA ERP'nin geri kalanına dokunma.
