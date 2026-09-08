# YZ 2 — Görev 12: Fiş Detay Kapsamlı İyileştirmeler

> **Dosya:** `transaction_document_dialog.py`  
> **Kural:** Sadece bu dosyayı değiştir.  
> **Hedef:** 1920x1080 ve 1024x768 dahil tüm ekran boyutlarında çalışsın.

---

## 12.1 — Sol Sidebar: Satır İşlemleri Grubu

"SATIR EKLE" ve "SEÇİLENLERİ SİL" butonlarını grid üstünden **kaldır**, sol sidebar'a CollapsibleSection olarak ekle. Sağ tık menüsünde de aynı aksiyonlar kalacak.

```python
# Sol sidebar'a yeni grup ekle:
self.sec_row_actions = CollapsibleSection("SATIR İŞLEMLERİ", is_expanded=True)

btn_add_row = QPushButton("➕ Satır Ekle (Alt+Enter)")
btn_add_row.clicked.connect(lambda: self.add_item_row(item_type="Malzeme"))

btn_del_selected = QPushButton("🗑️ Seçilenleri Sil (Ctrl+Del)")
btn_del_selected.setStyleSheet(self.sidebar_btn_style("#fee2e2", "#991b1b"))
btn_del_selected.clicked.connect(self.delete_selected_rows)

btn_move_up = QPushButton("⬆️ Satırı Yukarı (Alt+↑)")
btn_move_up.clicked.connect(self.move_row_up)

btn_move_down = QPushButton("⬇️ Satırı Aşağı (Alt+↓)")
btn_move_down.clicked.connect(self.move_row_down)

self.sec_row_actions.add_widget(btn_add_row)
self.sec_row_actions.add_widget(btn_del_selected)
self.sec_row_actions.add_widget(btn_move_up)
self.sec_row_actions.add_widget(btn_move_down)
left_lyt.addWidget(self.sec_row_actions)

# Grid üstündeki eski butonları KALDIR (görünmez yap):
# btn_add_row_top.setVisible(False)
# btn_bulk_delete_top.setVisible(False)
```

---

## 12.2 — Üst Menü Yazı Rengi (Beyaz)

E-Belge ve Fiş Türü dropdown menüsü açılınca yazılar beyaz olsun:

```python
DARK_DROPDOWN_STYLE = """
    QComboBox QAbstractItemView {
        background-color: #1e3a8a;
        color: #ffffff;
        border: 1px solid #3b82f6;
    }
    QComboBox QAbstractItemView::item {
        min-height: 24px;
        padding: 4px 10px;
        color: #ffffff;
    }
    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {
        background-color: #3b82f6;
        color: #ffffff;
    }
"""
# cmb_doc_type ve cmb_efatura_scenario stillerine ekle
```

---

## 12.3 — Tüm Alan Yükseklikleri: 24px

Tüm form alanlarına sabit yükseklik uygula:

```python
FIELD_H = 24  # px

# CariKunyeWidget alanları:
self.txt_cari_kodu.setFixedHeight(FIELD_H)
self.txt_cari_unvan.setFixedHeight(FIELD_H)
self.txt_vergi_daire.setFixedHeight(FIELD_H)
self.txt_vergi_no.setFixedHeight(FIELD_H)
self.txt_sevk_adres.setFixedHeight(FIELD_H)
self.btn_bakiye.setFixedHeight(FIELD_H)

# BelgeVadeWidget alanları:
self.date_belge.setFixedHeight(FIELD_H)
self.date_vade.setFixedHeight(FIELD_H)
self.txt_saat.setFixedHeight(FIELD_H)
self.cmb_vade_formul.setFixedHeight(FIELD_H)
self.cmb_odeme_plani.setFixedHeight(FIELD_H)
self.txt_fatura_seri.setFixedHeight(FIELD_H)

# HareketFinansWidget alanları:
self.cmb_doviz.setFixedHeight(FIELD_H)
self.txt_doviz_kuru.setFixedHeight(FIELD_H)
self.cmb_kdv_durumu.setFixedHeight(FIELD_H)
self.cmb_fatura_sekli.setFixedHeight(FIELD_H)
self.cmb_kasa.setFixedHeight(FIELD_H)

# Grup frame maksimum yükseklik:
grp_cari.setMaximumHeight(115)
grp_belge.setMaximumHeight(115)
grp_finans.setMaximumHeight(115)
self.header_tabs.setMaximumHeight(130)
```

---

## 12.4 — CariKunyeWidget: Etiketler + Bakiye + Büyüteç + Cari Seçim

### Alan Etiketleri Ekle
Her alanın soluna küçük etiket:
```
Cari Kodu: [YOLSIM    🔍]  Ünvanı: [YOLSIM MÜHENDİSLİK...  🔍]
Vergi D.:  [Seyhan VD.]   Vergi No: [9820411127] [💳 BAKİYE]
Sevk Adr.: [SANCAK MAH. S41 SOKAK NO:1/12                        ]
```

### Büyüteç Input İçine
```python
from PyQt6.QtWidgets import QStyle
from PyQt6.QtGui import QAction as GuiAction

# Cari Kodu input'una sağdan büyüteç ikonu:
search_icon = self.style().standardIcon(
    QStyle.StandardPixmap.SP_FileDialogContentsView
)
act_search_kod = GuiAction(search_icon, "", self)
act_search_kod.triggered.connect(self.open_customer_lookup)
self.txt_cari_kodu.addAction(
    act_search_kod,
    QLineEdit.ActionPosition.TrailingPosition
)

# Ünvan input'una da aynısı
act_search_unv = GuiAction(search_icon, "", self)
act_search_unv.triggered.connect(self.open_customer_lookup)
self.txt_cari_unvan.addAction(
    act_search_unv,
    QLineEdit.ActionPosition.TrailingPosition
)
```

### Cari Seçim → Tam Liste Dialog
```python
def open_customer_lookup(self):
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout,
        QTableWidget, QTableWidgetItem
    )
    dlg = QDialog(self)
    dlg.setWindowTitle("👤 Cari Seçim Listesi")
    dlg.setMinimumSize(800, 500)
    lyt = QVBoxLayout(dlg)

    # Arama
    search_box = QLineEdit()
    search_box.setPlaceholderText("Cari kodu veya ünvan ara...")
    search_box.setFixedHeight(28)
    lyt.addWidget(search_box)

    # Tablo
    tbl = QTableWidget(len(self.customers_catalog), 4)
    tbl.setHorizontalHeaderLabels(["Kod", "Ünvan", "Vergi No", "Adres"])
    tbl.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )
    tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    for r, c in enumerate(self.customers_catalog):
        tbl.setItem(r, 0, QTableWidgetItem(c.get("code", "")))
        tbl.setItem(r, 1, QTableWidgetItem(c.get("name", "")))
        tbl.setItem(r, 2, QTableWidgetItem(c.get("tax_no", "")))
        tbl.setItem(r, 3, QTableWidgetItem(c.get("address", "")))
    lyt.addWidget(tbl)

    # Arama filtrele
    def filter_table(text):
        for r in range(tbl.rowCount()):
            match = any(
                text.lower() in (tbl.item(r, c).text().lower() if tbl.item(r, c) else "")
                for c in range(tbl.columnCount())
            )
            tbl.setRowHidden(r, not match)
    search_box.textChanged.connect(filter_table)

    # Çift tıkla seç
    tbl.doubleClicked.connect(lambda idx: (
        self.apply_customer_info(self.customers_catalog[idx.row()]),
        dlg.accept()
    ))

    # Alt butonlar
    btn_lyt = QHBoxLayout()
    btn_yeni = QPushButton("➕ Yeni Cari Ekle")
    btn_yeni.clicked.connect(lambda: QMessageBox.information(
        dlg, "Yeni Cari", "Cari kart formu açılacak."
    ))
    btn_sec = QPushButton("✅ Seç")
    btn_sec.clicked.connect(lambda: (
        self.apply_customer_info(
            self.customers_catalog[tbl.currentRow()]
        ) if tbl.currentRow() >= 0 else None,
        dlg.accept()
    ))
    btn_kapat = QPushButton("Kapat")
    btn_kapat.clicked.connect(dlg.reject)
    btn_lyt.addWidget(btn_yeni)
    btn_lyt.addStretch()
    btn_lyt.addWidget(btn_sec)
    btn_lyt.addWidget(btn_kapat)
    lyt.addLayout(btn_lyt)
    dlg.exec()
```

---

## 12.5 — Tarih: Takvim İkonu Input İçinde

```python
DATE_STYLE = """
    QDateEdit {
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        min-height: 24px;
        background: white;
        color: #0f172a;
    }
    QDateEdit::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 22px;
        border-left: 1px solid #cbd5e1;
    }
"""
self.date_belge.setStyleSheet(DATE_STYLE)
self.date_vade.setStyleSheet(DATE_STYLE)
self.date_belge.setDisplayFormat("dd.MM.yyyy")
self.date_vade.setDisplayFormat("dd.MM.yyyy")
```

---

## 12.6 — HareketKalemleriWidget: Başlık + Açıklama + Satır Yüksekliği

### Başlık Satırı Küçült
```python
hheader = self.table_items.horizontalHeader()
hheader.setFixedHeight(26)
font = hheader.font()
font.setPointSize(9)
hheader.setFont(font)
```

### Satır Yüksekliği Tekrar Ayarlanabilir
```python
vheader = self.table_items.verticalHeader()
vheader.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
vheader.setDefaultSectionSize(ThemeManager().row_height)
vheader.setMinimumSectionSize(20)
```

### Açıklama Sütunu Stretch Düzelt
```python
# add_item_row içinde — sarmalayıcı widget KALDIR:
# Sadece QLineEdit koy, ... butonu yok
self.table_items.setCellWidget(row, 4, txt_name)  # Direkt QLineEdit
hheader.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
```

---

## 12.7 — Alt Bar Buton Yüksekliği

```python
BTN_H = 28
self.btn_bottom_cancel.setFixedHeight(BTN_H)
self.btn_bottom_save_print.setFixedHeight(BTN_H)
self.btn_bottom_save_new.setFixedHeight(BTN_H)
self.btn_bottom_save.setFixedHeight(BTN_H)
bottom_action_bar.setFixedHeight(42)
```

---

## 12.8 — İndirim Masraf Grid: HareketKalemleri ile Aynı

```python
# 1. Satır yüksekliği ayarlanabilir
self.table_alt_iskonto.verticalHeader().setSectionResizeMode(
    QHeaderView.ResizeMode.Interactive
)
self.table_alt_iskonto.verticalHeader().setDefaultSectionSize(
    ThemeManager().row_height
)

# 2. Sütun ayarlanabilir
self.table_alt_iskonto.horizontalHeader().setSectionResizeMode(
    QHeaderView.ResizeMode.Interactive
)

# 3. Sağ tık menüsü
self.table_alt_iskonto.setContextMenuPolicy(
    Qt.ContextMenuPolicy.CustomContextMenu
)
self.table_alt_iskonto.customContextMenuRequested.connect(
    self.show_alt_iskonto_context_menu
)

def show_alt_iskonto_context_menu(self, pos):
    menu = QMenu(self)
    act_add = QAction("➕ Satır Ekle", self)
    act_del = QAction("🗑️ Satırı Sil", self)
    act_add.triggered.connect(self.add_alt_iskonto_row)
    act_del.triggered.connect(
        lambda: self.remove_alt_iskonto_row(
            self.table_alt_iskonto.currentRow()
        )
    )
    menu.addAction(act_add)
    menu.addAction(act_del)
    menu.exec(self.table_alt_iskonto.viewport().mapToGlobal(pos))

# 4. + EKLE butonunu gizle (sağ tıkta var)
btn_add_alt_isk.setVisible(False)

# 5. Satır tooltip
# add_alt_iskonto_row içinde:
cmb_type.setToolTip(
    "İndirim → Toplam tutardan düşülür\n"
    "Masraf → Toplam tutara eklenir\n"
    "Nakliye, Sigorta → Masraf olarak işlenir"
)
```

---

## 12.9 — Toplam Daralt + İndirim Alanı Genişlet

```python
totals_frame.setMaximumWidth(280)

# Oran değiştir:
bottom_box.addWidget(grp_alt_iskonto, 5)  # Genişlet
bottom_box.addWidget(notes_frame, 2)
bottom_box.addWidget(totals_frame, 3)     # Daralt
```

---

## 12.10 — Barkod/Seri/Lot Çağırma Alanı

Notlar & Şartlar bölümünün **üstüne** ekle:

```python
# Barkod/Seri/Lot arama çubuğu
barcode_frame = QFrame()
barcode_frame.setStyleSheet(
    "background:#f0fdf4; border:1px solid #86efac; border-radius:4px;"
)
bc_lyt = QHBoxLayout(barcode_frame)
bc_lyt.setContentsMargins(4, 2, 4, 2)
bc_lyt.setSpacing(4)

lbl_bc = QLabel("🔍")
lbl_bc.setStyleSheet("font-size:13px;")

self.txt_barcode_input = QLineEdit()
self.txt_barcode_input.setPlaceholderText(
    "Barkod / Seri No / Lot No ile ürün çağır..."
)
self.txt_barcode_input.setFixedHeight(24)
self.txt_barcode_input.returnPressed.connect(self.on_barcode_entered)

self.cmb_barcode_type = QComboBox()
self.cmb_barcode_type.addItems(["Barkod", "Seri No", "Lot No"])
self.cmb_barcode_type.setFixedHeight(24)
self.cmb_barcode_type.setFixedWidth(80)

bc_lyt.addWidget(lbl_bc)
bc_lyt.addWidget(self.txt_barcode_input, 1)
bc_lyt.addWidget(self.cmb_barcode_type)

# notes_lyt'a en üste ekle:
notes_lyt.insertWidget(0, barcode_frame)

def on_barcode_entered(self):
    barcode = self.txt_barcode_input.text().strip()
    if not barcode:
        return
    found = next(
        (p for p in self.products_catalog
         if p.get("barcode") == barcode or p.get("code") == barcode),
        None
    )
    if found:
        self.add_item_row(
            item_type="Malzeme",
            barcode=found.get("barcode", ""),
            code=found.get("code", ""),
            name=found.get("name", ""),
            unit=found.get("unit", "Adet"),
            price=found.get("price", 0.0),
            vat=found.get("vat", 20),
        )
    else:
        # Bulunamadı — serbest satır ekle
        self.add_item_row(item_type="Serbest Giriş", barcode=barcode)
    self.txt_barcode_input.clear()
    self.txt_barcode_input.setFocus()
```

---

## Özet Tablo

| # | Görev | Açıklama |
|---|-------|----------|
| 12.1 | Sol sidebar satır işlemleri | SATIR EKLE/SİL sidebar'a taşı |
| 12.2 | Menü yazı rengi beyaz | Dropdown okunabilir |
| 12.3 | Alan yükseklikleri 24px | Responsive, tüm ekranlar |
| 12.4 | CariKunyeWidget | Etiketler, büyüteç içe, cari seçim dialog |
| 12.5 | Tarih ikonu | DİA tarzı takvim |
| 12.6 | Grid başlık + açıklama + satır | 26px başlık, Stretch düzelt |
| 12.7 | Alt bar 28px | Kompakt |
| 12.8 | İndirim grid | Sağ tık, ayarlanabilir, EKLE gizle, tooltip |
| 12.9 | Toplam daralt | İndirim alanı genişle |
| 12.10 | Barkod/Seri/Lot | Notlar üstüne ekle |

> **Test:** 1920x1080 ve 1024x768'de çalıştır — taşma olmamalı.
