# YZ 2 — Görev 16: Fiş Detay Ekranı Mockup Bazlı Yeniden Yazım

> **Dosya:** `src/desktop/ui/dialogs/transaction_document_dialog.py`  
> **Kural:** Mevcut dosyayı tamamen yeniden yaz. Tüm mevcut metodları koru.  
> **Referans:** Aşağıdaki mockup tasarımını 1:1 uygula.

---

## Hedef Layout

```
┌─────────────────────────────────────────────────────────────┐
│ TOP BAR (32px) — Tür | Firma | Şube | Depo | E-Belge | No  │
├──────────────────────────────────────────────────────────────┤
│ SEKMELER (26px) — 1 Genel | 2 Detay | 3 İskonto | 4 Ek | 5 │
├──────────┬───────────────────────────────────────────────────┤
│ SOL      │ ÜST BİLGİ PANELİ (tek ∧ butonu ile kapat/aç)    │
│ SIDEBAR  │ [CARİ KÜNYESİ] [BELGE & VADE] [FİNANS]          │
│          ├───────────────────────────────────────────────────┤
│ EVRAK    │ KALEMLER GRİD (flex:1, scroll)                    │
│ İŞLEM.   │                                                   │
│ SATIR    ├─────────────── [∨ Alt Panel F6] ─────────────────┤
│ İŞLEM.   │ [İndirim_Masraflar] [Notlar+Barkod] [Toplamlar]  │
│ GÖRÜNÜM  ├───────────────────────────────────────────────────┤
│          │ ALT BAR (38px) — kısayollar | Excel | F9 | Kaydet│
└──────────┴───────────────────────────────────────────────────┘
```

---

## 1. TOP BAR

```python
top_bar = QFrame()
top_bar.setFixedHeight(32)
top_bar.setStyleSheet("""
    QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
             stop:0 #1e3a8a, stop:1 #0f172a); }
    QComboBox, QLineEdit {
        background:#ffffff; color:#0f172a; font-weight:bold;
        font-size:10px; padding:1px 4px; border-radius:3px;
        min-height:20px;
    }
    QComboBox QAbstractItemView {
        background:#1e3a8a; color:#ffffff;
        selection-background-color:#3b82f6;
    }
    QLabel { color:#93c5fd; font-size:9px; font-weight:600; }
""")
lyt = QHBoxLayout(top_bar)
lyt.setContentsMargins(6, 2, 6, 2)
lyt.setSpacing(6)

# Sıra: badge | Tür | Firma | Şube | Depo | E-Belge | stretch | Belge No
badge = QLabel("[isl.doc.001]")
badge.setStyleSheet("background:#3b82f6;color:#fff;font-size:8px;padding:1px 4px;border-radius:2px;")

self.cmb_doc_type     # min-width:180px
self.cmb_depo_top     # min-width:120px  ← Depo buraya taşındı
self.cmb_efatura      # min-width:150px
self.txt_top_doc_no   # max-width:110px, beyaz bg, koyu mavi yazı
```

---

## 2. SEKMELER

```python
self.header_tabs = QTabWidget()
self.header_tabs.tabBar().setFixedHeight(26)
self.header_tabs.setStyleSheet("""
    QTabBar::tab { height:24px; padding:0 12px; font-size:10px; }
    QTabBar::tab:selected { color:#1e3a8a; border-top:2px solid #2563eb; }
    QTabWidget::pane { border:1px solid #e2e8f0; }
""")
```

---

## 3. SOL SIDEBAR

`EdgeTriggeredPanel(side="left")` — başlangıçta açık.

### Gruplar (CollapsibleSection):

**EVRAK İŞLEMLERİ:**
```
💾 Kaydet (F2)          → mavi bg
➕ Kaydet & Yeni        → yeşil bg
🖨️ Kaydet & Yazdır (F9) → açık mavi bg
📥 Kalemleri Aktar ▼    → dropdown menü
📤 Gönder / Paylaş      → mor bg
⚡ e-Fatura Gönder      → mor bg
🚪 Vazgeç (Esc)         → kırmızı bg
```

**SATIR İŞLEMLERİ:**
```
➕ Satır Ekle (Alt+Enter)
🗑️ Seçilenleri Sil (Ctrl+Del)  → kırmızı
⬆️ Satırı Yukarı (Alt+↑)
⬇️ Satırı Aşağı (Alt+↓)
```

**GÖRÜNÜM & SÜTUNLAR:**
```
[QComboBox profil seçici]
[💾 Kaydet] [⚙️ Sütunlar]  → yan yana
```

Tüm butonlar: `setFixedHeight(26)`, `font-size:10px`, `text-align:left`

---

## 4. ÜST BİLGİ PANELİ — TEK COLLAPSE BUTONU

### Kritik: Tek buton, 3 panel birden kapanır

```python
info_bar = QFrame()  # 3 panel yan yana
info_bar.setMaximumHeight(120)

# Sağ üst köşeye TEK collapse butonu
self.btn_collapse_info = QPushButton("∧")
self.btn_collapse_info.setFixedSize(20, 20)
self.btn_collapse_info.setStyleSheet("""
    QPushButton {
        background:#e2e8f0; border:none; border-radius:3px;
        font-size:10px; color:#64748b;
    }
    QPushButton:hover { background:#cbd5e1; }
""")
self.btn_collapse_info.clicked.connect(self.toggle_info_panel)
self._info_visible = True

def toggle_info_panel(self):
    self._info_visible = not self._info_visible
    # 3 widget birden göster/gizle
    for w in [self.grp_cari, self.grp_belge, self.grp_finans]:
        w.setVisible(self._info_visible)
    self.btn_collapse_info.setText("∧" if self._info_visible else "∨")
    # Kapalıyken info_bar min yükseklik
    self.info_bar.setMaximumHeight(120 if self._info_visible else 24)
```

### 4a. CARİ KÜNYESİ Paneli

```python
# Layout: QGridLayout, 3 satır
# Başlık
lbl_hdr = QLabel("👤 CARİ HESAP KÜNYESİ")
# font-weight:800, color:#1e3a8a, font-size:10px

# Satır 1: Cari Kodu / Ünvan: [input 🔍] [input 🔍]
# Tek satırda — QHBoxLayout
lbl_kod_unv = QLabel("Cari Kodu / Ünvan:")
# font-size:9px, color:#64748b

self.txt_cari_kodu   # max-width:100px, font-weight:bold
btn_kod_search       # 🔍 ikon, 20x20, input içine addAction ile
self.txt_cari_unvan  # flex:1, font-weight:bold
btn_unv_search       # 🔍 ikon, 20x20

# Satır 2: Vergi D./No: [input][input][💳 BAKİYE]
lbl_vd = QLabel("Vergi D./No:")
self.txt_vergi_daire   # max-width:100px
self.txt_vergi_no      # max-width:100px
self.btn_bakiye        # setFixedHeight(22), kırmızı stil

# Satır 3: Sevk Adr.: [input full width]
lbl_adres = QLabel("Sevk Adr.:")
self.txt_sevk_adres    # full width

# Tüm alanlar: setFixedHeight(22)
```

### 4b. BELGE & VADE Paneli

```python
# Başlık: "📅 BELGE & VADE DETAYLARI"

# Satır 1: Seri/No/Fiş: [S220165][TOY2026-001][00000056]
lbl_seri = QLabel("Seri/No/Fiş:")
self.txt_fatura_seri   # max-width:60px
self.txt_belge_no      # max-width:80px  ← YENİ ALAN
self.txt_fis_no        # max-width:70px  ← YENİ ALAN

# Satır 2: Tarih/Saat/Vade: [date][time][date][gün]
lbl_tarih = QLabel("Tarih/Saat/Vade:")
self.date_belge        # setFixedHeight(22)
self.txt_saat          # max-width:42px
self.date_vade         # setFixedHeight(22)
self.cmb_vade_gun      # max-width:58px, (30 Gün) vb.

# Satır 3: Ödeme Planı: [combobox full]
lbl_odeme = QLabel("Ödeme Planı:")
self.cmb_odeme_plani   # full width
```

### 4c. FİNANS Paneli

```python
# Başlık: "⚙️ HAREKET AYARLARI & FİNANS"

# Satır 1: Döviz/Kur/KDV: [TRY▼][1.0000][KDV Hariç▼]
lbl_dov = QLabel("Döviz/Kur:")
self.cmb_doviz         # max-width:70px
self.txt_doviz_kuru    # max-width:52px
self.cmb_kdv_durumu   # flex:1

# Satır 2: Şekil/Kasa: [Kapalı▼][K01▼]
lbl_sek = QLabel("Şekil/Kasa:")
self.cmb_fatura_sekli  # flex:1
self.cmb_kasa          # flex:1

# Satır 3: İşlemler: [✓ Cari] [✓ Stok]
lbl_isl = QLabel("İşlemler:")
self.chk_cari_islesin
self.chk_stok_islesin
```

---

## 5. KALEMLER GRİD — HareketKalemleriWidget

### Sütun Listesi (19 sütun)
```
0: checkbox (16px)
1: 🗑️ sil (20px)
2: TÜRÜ (80px, QComboBox)
3: STOK KODU (90px, QLineEdit + ... btn sağ tıkta)
4: AÇIKLAMA / ÜRÜN ADI (Stretch — direkt QLineEdit, sarmalayıcı YOK)
5: SATIR NOTU 2 (55px)
6: MİKTAR (45px, sağa hizalı)
7: BİRİM (40px)
8: B.FİYAT (60px, sağa hizalı, bold)
9: DÖVİZ (45px, QComboBox)
10: İSK 1% (38px)
11: İSK 1 TUTAR (45px, kırmızı)
12: İSK 2% (38px)
13: İSK 2 TUTAR (45px, kırmızı)
14: KDV% (38px, QComboBox)
15: TUTAR (60px, sağa hizalı, koyu mavi, bold)
```

### Kritik Kurallar
```python
# 1. Başlık yüksekliği
hheader.setFixedHeight(26)

# 2. Satır yüksekliği — ThemeManager'dan, HEPSİ EŞİT
ROW_H = ThemeManager().row_height  # ~26px
vheader.setDefaultSectionSize(ROW_H)
vheader.setMinimumSectionSize(ROW_H)
vheader.setMaximumSectionSize(ROW_H)

# Her satır eklenince:
self.table_items.setRowHeight(row, ROW_H)

# Her widget:
widget.setFixedHeight(ROW_H - 2)

# 3. Açıklama sütunu — SARMALAYICI YOK
# Sütun 4'e direkt QLineEdit koy:
txt_aciklama = QLineEdit(name)
txt_aciklama.setFixedHeight(ROW_H - 2)
self.table_items.setCellWidget(row, 4, txt_aciklama)

# Stretch:
hheader.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
hheader.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
hheader.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)

# 4. Çoklu seçim
self.table_items.setSelectionMode(
    QAbstractItemView.SelectionMode.ExtendedSelection
)
self.table_items.setSelectionBehavior(
    QAbstractItemView.SelectionBehavior.SelectRows
)

# 5. Dropdown renkleri — tüm QComboBox için:
COMBO_STYLE = """
    QComboBox {
        border:1px solid #cbd5e1; border-radius:3px;
        padding:0 3px; font-size:9px; background:#fff;
    }
    QComboBox QAbstractItemView {
        background:#1e293b; color:#ffffff;
        selection-background-color:#3b82f6;
    }
"""
```

---

## 6. ALT SPLITTER — F6 Toggle

```python
splitter_bar = QFrame()
splitter_bar.setFixedHeight(18)
splitter_bar.setStyleSheet("""
    QFrame { background:#f1f5f9; border-top:1px solid #e2e8f0;
             border-bottom:1px solid #e2e8f0; }
""")
bar_lyt = QHBoxLayout(splitter_bar)
bar_lyt.setContentsMargins(4, 0, 4, 0)

# Ortada ince çizgi
line = QFrame()
line.setFrameShape(QFrame.Shape.HLine)
line.setStyleSheet("color:#cbd5e1;")

# Sağda toggle butonu
self.btn_toggle_bottom = QPushButton("∨ Alt Panel (F6)")
self.btn_toggle_bottom.setFixedHeight(16)
self.btn_toggle_bottom.setStyleSheet("""
    QPushButton {
        background:#e2e8f0; border:none; border-radius:3px;
        font-size:9px; color:#64748b; padding:0 6px;
    }
    QPushButton:hover { background:#cbd5e1; }
""")
self.btn_toggle_bottom.clicked.connect(self.toggle_bottom_panel)

self._bottom_visible = True
self._bottom_height = 155

# F6 kısayolu
sc_f6 = QShortcut(QKeySequence("F6"), self)
sc_f6.activated.connect(self.toggle_bottom_panel)

def toggle_bottom_panel(self):
    self._bottom_visible = not self._bottom_visible
    self.bottom_panel.setVisible(self._bottom_visible)
    self.btn_toggle_bottom.setText(
        "∨ Alt Panel (F6)" if self._bottom_visible
        else "∧ Alt Panel (F6)"
    )
```

---

## 7. ALT PANEL

`QSplitter(Qt.Orientation.Horizontal)` — 3 bölüm:

### 7a. İndirim & Masraflar (stretch: 5)

**Sekmeler (24px):** A İndirim_Masraflar | B Seri-Lot | C Varyant | D Paketler

**Sütunlar:**
```
🗑️ | TÜR | TÜRÜ | DEĞER | DÖVİZ | KUR | KDV% | TUTAR | NOT | MALİYET ETKİLESİN | İLK DEĞER | FORMÜL
```

**Türü seçenekleri:**
```python
ISKONTO_TURLERI = [
    "Toplamdan % Düş", "Toplamdan Düş", "Toplamı Eşitle",
    "G.Toplamdan % Düş", "G.Toplamdan Düş", "G.Toplamı Eşitle",
]
```

**Özellikler:**
- `+ EKLE` butonu YOK — sağ tık menüsünde "➕ Satır Ekle"
- Satır yüksekliği ThemeManager'dan
- Sütun genişlikleri ayarlanabilir (Interactive)
- Satır üzerine gelinince tooltip

### 7b. Notlar & Barkod (stretch: 3)

```python
# En üstte barkod arama çubuğu
barcode_frame:
    🔍 [Barkod / Seri No / Lot No ile ürün çağır...]  [Barkod▼]
    # returnPressed → on_barcode_entered()
    # background: #f0fdf4, border: #86efac

# Altında notlar önizleme
self.lbl_note_preview

# En altta
btn_notlari_duzenle: "✏️ Notları Düzenle..."
```

### 7c. Toplamlar (stretch: 3, min-width: 170px)

**QGridLayout — 3 sütun: Etiket | TL | Döviz**

```
           TL          Döviz
Ara Top:   225,00 ₺    225,00 $
Masraf:    +0,00 ₺     +0,00 $
İndirim:   -0,00 ₺     -0,00 $
Toplam:    225,00 ₺    225,00 $
Özel V.:   +0,00 ₺     +0,00 $
KDV:       +45,00 ₺    +45,00 $
Tevkifat:  -0,00 ₺     -0,00 $
────────────────────────────────
G.TOPLAM: [270,00 ₺]  [-7,01 USD]
```

G. Toplam: `background:#1e3a8a; color:#ffffff; font-size:13px; font-weight:800`

---

## 8. ALT BAR

```python
bottom_bar = QFrame()
bottom_bar.setFixedHeight(38)
bottom_bar.setStyleSheet("background:#f8fafc; border-top:1px solid #e2e8f0;")

# Sol: kısayol bilgisi
lbl_keys = QLabel("F2: Kaydet | F9: Yazdır | Alt+Enter: Satır | "
                   "Ctrl+Del: Sil | F6: Alt Panel | Esc: Vazgeç")
lbl_keys.setStyleSheet("color:#94a3b8; font-size:9px;")

# Sağ butonlar (soldan sağa):
# Tümü setFixedHeight(28)
btn_vazgec   # fee2e2 bg, 991b1b text
btn_excel    # 0284c7 bg, white
btn_yazdir   # 0284c7 bg, white, F9
btn_yeni     # 059669 bg, white
btn_kaydet   # 1d4ed8 bg, white, F2, font-size:11px
```

---

## 9. Korunacak Tüm Metodlar

Şu metodlar aynen korunacak, sadece widget isimlerine dikkat:

```python
save_document()
save_and_new_document()
save_and_print_document()       # PDF motoru ile
export_to_excel()               # Excel motoru ile
open_share_dialog()             # Paylaşım dialog
open_notes_dialog()
add_item_row(...)
remove_item_row(row)
get_row_data(row) -> dict
set_row_data(row, data)
move_row_up(row)
move_row_down(row)
delete_selected_rows()
calculate_totals()
on_barcode_entered()
open_customer_lookup()
apply_customer_info(c)
open_stock_lookup_for_row(row)
apply_product_to_row(row, p)
show_items_body_context_menu(pos)
show_alt_iskonto_context_menu(pos)
add_alt_iskonto_row(...)
_get_current_teklif_data() -> dict
_get_report_service()
_calc_line_total(row_data) -> float
toggle_info_panel()
toggle_bottom_panel()
```

---

## 10. Widget İsimleri (Sabit — Değiştirme)

Aşağıdaki isimler kesinlikle korunacak — DB kayıt kodu bunlara bağlanacak:

```python
self.txt_cari_kodu
self.txt_cari_unvan
self.txt_vergi_daire
self.txt_vergi_no
self.txt_sevk_adres
self.date_belge
self.date_vade
self.txt_saat
self.txt_top_doc_no
self.cmb_doc_type
self.cmb_doviz
self.txt_doviz_kuru
self.cmb_kdv_durumu
self.cmb_fatura_sekli
self.cmb_kasa
self.chk_cari_islesin
self.chk_stok_islesin
self.table_items          # kalem grid
self.table_alt_iskonto    # indirim grid
self.lbl_subtotal
self.lbl_discount
self.lbl_expense_total
self.lbl_vat_total
self.lbl_grand_total
self.lbl_grand_total_doviz
self.doc_note1
self.doc_note2
self.cmb_odeme_plani
self.cmb_depo_top
```

---

## Test

```
1. Ekranı aç → compact görünüm, taşma yok
2. ∧ butonuna tıkla → 3 panel birden kapanır, grid büyür
3. F6 → alt panel kayar
4. Kalem ekle → satır yükseklikleri EŞİT
5. Açıklama sütununu sürükle → genişletilebilir
6. Checkbox ile çoklu seç → "Seçilenleri Sil" aktif
7. 1024x768 → taşma yok
8. 1920x1080 → iyi görünüm
```

---

## Özet

| # | Bölüm | Kritik Değişiklik |
|---|-------|------------------|
| 1 | Top bar | 32px, Depo buraya taşındı |
| 2 | Sekmeler | 26px tab bar |
| 3 | Sol sidebar | 3 grup, 26px butonlar |
| 4 | Üst bilgi | **Tek collapse butonu**, 3 panel birden |
| 5 | Kalem grid | Eşit satır yüksekliği, Açıklama Stretch |
| 6 | Splitter | F6 toggle, kayar animasyon |
| 7 | Alt panel | QSplitter, barkod üstte, TL+Döviz toplamlar |
| 8 | Alt bar | 38px, 5 buton |

> Widget isimlerini değiştirme — DB kayıt kodu bunlara bağlanacak.
