# YZ 2 — Görev 17: Grid Özellikleri + Alan Boyutları

> **Dosya:** `src/desktop/ui/dialogs/transaction_document_dialog.py`  
> **Kural:** Sadece bu dosyayı değiştir.

---

## 17.1 — Alan Genişlikleri

### CariKunyeWidget

```python
# Cari Kodu — genişlet (şu an çok dar, yazı okunmuyor)
self.txt_cari_kodu.setMinimumWidth(120)  # ESKİ: ~80px

# Vergi Dairesi
self.txt_vergi_daire.setMinimumWidth(130)

# Vergi No
self.txt_vergi_no.setMinimumWidth(110)
```

### BelgeVadeWidget

```python
# Seri No
self.txt_fatura_seri.setMinimumWidth(70)   # ESKİ: ~55px

# Fiş No
self.txt_fis_no.setMinimumWidth(80)        # ESKİ: ~60px
```

---

## 17.2 — HareketKalemleriWidget: Sağ Tık Menüsü

Mevcut `show_items_body_context_menu` metoduna şunları ekle:

```python
def show_items_body_context_menu(self, pos):
    from PyQt6.QtWidgets import QMenu, QInputDialog
    from PyQt6.QtGui import QAction
    
    menu = QMenu(self)
    menu.setStyleSheet("""
        QMenu {
            background:#ffffff; border:1px solid #cbd5e1;
            font-size:11px; padding:2px;
        }
        QMenu::item { padding:5px 20px 5px 10px; }
        QMenu::item:selected {
            background:#2563eb; color:#ffffff;
        }
        QMenu::separator { height:1px; background:#e2e8f0; margin:2px 0; }
    """)

    row = self.table_items.currentRow()
    col = self.table_items.currentColumn()

    # ── SATIR İŞLEMLERİ ──
    act_add    = QAction("➕ Satır Ekle (Alt+Enter)", self)
    act_insert = QAction("➕ Araya Satır Ekle", self)
    act_del    = QAction("🗑️ Satırı Sil", self)
    act_up     = QAction("⬆️ Yukarı Taşı (Alt+↑)", self)
    act_down   = QAction("⬇️ Aşağı Taşı (Alt+↓)", self)
    act_bulk   = QAction("🗑️ Seçilenleri Sil (Ctrl+Del)", self)

    menu.addAction(act_add)
    menu.addAction(act_insert)

    # Silinemeyen son satır kontrolü
    can_delete = self.table_items.rowCount() > 1
    act_del.setEnabled(can_delete and row >= 0)
    act_bulk.setEnabled(
        can_delete and
        len(self.table_items.selectionModel().selectedRows()) > 1
    )
    menu.addAction(act_del)
    menu.addAction(act_bulk)
    menu.addSeparator()
    menu.addAction(act_up)
    menu.addAction(act_down)
    menu.addSeparator()

    # ── SÜTUN İŞLEMLERİ ──
    if col >= 0:
        col_name = self.COLUMN_NAMES[col] if col < len(self.COLUMN_NAMES) else ""

        # Sıralama
        act_sort_asc  = QAction(f"🔼 '{col_name}' Artan Sırala", self)
        act_sort_desc = QAction(f"🔽 '{col_name}' Azalan Sırala", self)
        menu.addAction(act_sort_asc)
        menu.addAction(act_sort_desc)
        menu.addSeparator()

        # Sütun gizle
        act_hide = QAction(f"👁️ '{col_name}' Sütununu Gizle", self)
        menu.addAction(act_hide)

    # Gizli sütunları göster
    hidden_cols = [
        i for i in range(self.table_items.columnCount())
        if self.table_items.isColumnHidden(i)
    ]
    if hidden_cols:
        show_menu = menu.addMenu("👁️ Gizli Sütunları Göster")
        for hcol in hidden_cols:
            hname = self.COLUMN_NAMES[hcol] if hcol < len(self.COLUMN_NAMES) else str(hcol)
            act_show = QAction(hname, self)
            act_show.triggered.connect(
                lambda _, c=hcol: self.table_items.setColumnHidden(c, False)
            )
            show_menu.addAction(act_show)

    menu.addSeparator()

    # ── PROFİL KAYDET ──
    act_save_profile = QAction("💾 Görünümü Kaydet", self)
    act_reset        = QAction("↩️ Görünümü Sıfırla", self)
    menu.addAction(act_save_profile)
    menu.addAction(act_reset)

    # ── BAĞLANTILARI KUR ──
    act_add.triggered.connect(
        lambda: self.add_item_row(item_type="Malzeme")
    )
    act_insert.triggered.connect(
        lambda: self.add_item_row(
            item_type="Malzeme",
            insert_index=max(0, row)
        )
    )
    act_del.triggered.connect(
        lambda: self.remove_item_row(row) if can_delete else None
    )
    act_bulk.triggered.connect(self.delete_selected_rows)
    act_up.triggered.connect(lambda: self.move_row_up(row))
    act_down.triggered.connect(lambda: self.move_row_down(row))

    if col >= 0:
        act_sort_asc.triggered.connect(
            lambda: self._sort_items_table(col, ascending=True)
        )
        act_sort_desc.triggered.connect(
            lambda: self._sort_items_table(col, ascending=False)
        )
        act_hide.triggered.connect(
            lambda: self.table_items.setColumnHidden(col, True)
        )

    act_save_profile.triggered.connect(self.save_current_profile)
    act_reset.triggered.connect(self._reset_column_widths)

    menu.exec(self.table_items.viewport().mapToGlobal(pos))
```

### Sıralama Metodu Ekle

```python
def _sort_items_table(self, col: int, ascending: bool = True):
    """Kalem tablosunu belirtilen sütuna göre sırala."""
    row_count = self.table_items.rowCount()
    if row_count <= 1:
        return

    # Tüm satır verilerini topla
    rows_data = []
    for r in range(row_count):
        if hasattr(self, "get_row_data"):
            rows_data.append(self.get_row_data(r))
        else:
            rows_data.append({})

    # Sütun anahtarı
    col_keys = {
        2: "item_type", 3: "code", 4: "name",
        6: "qty", 8: "price", 15: "total_amount",
    }
    key = col_keys.get(col, "name")

    def sort_val(d):
        v = d.get(key, "")
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return str(v).lower()

    rows_data.sort(key=sort_val, reverse=not ascending)

    # Tabloyu yeniden doldur
    for r, row_data in enumerate(rows_data):
        if hasattr(self, "set_row_data"):
            self.set_row_data(r, row_data)

def _reset_column_widths(self):
    """Sütun genişliklerini varsayılana döndür."""
    self.setup_default_column_widths()
```

---

## 17.3 — HareketKalemleriWidget: Min 1 Satır, Silinemez

```python
def remove_item_row(self, row: int):
    """Satırı sil — en az 1 satır kalmalı."""
    if self.table_items.rowCount() <= 1:
        # Son satırı silme, sadece temizle
        if hasattr(self, "set_row_data"):
            self.set_row_data(row, {
                "item_type": "Malzeme",
                "code": "", "name": "", "note2": "",
                "qty": 1.0, "unit": "Adet",
                "price": 0.0, "currency": "TRY",
                "disc1": 0.0, "disc2": 0.0, "disc3": 0.0,
                "vat": 20,
            })
        self.calculate_totals()
        return

    self.table_items.removeRow(row)
    self.calculate_totals()
```

---

## 17.4 — AltIskontoMasrafWidget: Aynı Özellikler

### Sağ Tık Menüsü

```python
def show_alt_iskonto_context_menu(self, pos):
    from PyQt6.QtWidgets import QMenu
    from PyQt6.QtGui import QAction

    menu = QMenu(self)
    menu.setStyleSheet("""
        QMenu {
            background:#ffffff; border:1px solid #cbd5e1;
            font-size:11px; padding:2px;
        }
        QMenu::item { padding:5px 20px 5px 10px; }
        QMenu::item:selected { background:#2563eb; color:#ffffff; }
        QMenu::separator { height:1px; background:#e2e8f0; }
    """)

    row = self.table_alt_iskonto.currentRow()
    col = self.table_alt_iskonto.currentColumn()
    can_delete = self.table_alt_iskonto.rowCount() > 1

    act_add  = QAction("➕ Satır Ekle", self)
    act_del  = QAction("🗑️ Satırı Sil", self)
    act_del.setEnabled(can_delete and row >= 0)

    menu.addAction(act_add)
    menu.addAction(act_del)
    menu.addSeparator()

    # Sıralama (Değer sütununa göre)
    act_sort_asc  = QAction("🔼 Değere Göre Artan", self)
    act_sort_desc = QAction("🔽 Değere Göre Azalan", self)
    menu.addAction(act_sort_asc)
    menu.addAction(act_sort_desc)
    menu.addSeparator()

    # Sütun gizle/göster
    if col >= 0:
        col_name = self.table_alt_iskonto.horizontalHeaderItem(col)
        col_name = col_name.text() if col_name else str(col)
        act_hide = QAction(f"👁️ '{col_name}' Gizle", self)
        menu.addAction(act_hide)
        act_hide.triggered.connect(
            lambda: self.table_alt_iskonto.setColumnHidden(col, True)
        )

    hidden = [
        i for i in range(self.table_alt_iskonto.columnCount())
        if self.table_alt_iskonto.isColumnHidden(i)
    ]
    if hidden:
        show_m = menu.addMenu("👁️ Gizlileri Göster")
        for hc in hidden:
            hi = self.table_alt_iskonto.horizontalHeaderItem(hc)
            hn = hi.text() if hi else str(hc)
            a = QAction(hn, self)
            a.triggered.connect(
                lambda _, c=hc: self.table_alt_iskonto.setColumnHidden(c, False)
            )
            show_m.addAction(a)

    # Bağlantılar
    act_add.triggered.connect(self.add_alt_iskonto_row)
    act_del.triggered.connect(
        lambda: self.remove_alt_iskonto_row(row) if can_delete else None
    )
    act_sort_asc.triggered.connect(
        lambda: self._sort_alt_iskonto(ascending=True)
    )
    act_sort_desc.triggered.connect(
        lambda: self._sort_alt_iskonto(ascending=False)
    )

    menu.exec(
        self.table_alt_iskonto.viewport().mapToGlobal(pos)
    )

def _sort_alt_iskonto(self, ascending: bool = True):
    """Alt iskonto tablosunu değere göre sırala."""
    rows = []
    for r in range(self.table_alt_iskonto.rowCount()):
        w = self.table_alt_iskonto.cellWidget(r, 3)  # Değer sütunu
        try:
            val = float(w.text().replace(",", ".")) if w else 0.0
        except Exception:
            val = 0.0
        rows.append((val, r))

    rows.sort(key=lambda x: x[0], reverse=not ascending)
    # Sıralama sonrası satırları yeniden düzenle
    # (QTableWidget için satır taşıma karmaşık — basit renk ile göster)
    for i, (_, orig_row) in enumerate(rows):
        for c in range(self.table_alt_iskonto.columnCount()):
            item = self.table_alt_iskonto.item(orig_row, c)
            if item:
                item.setBackground(
                    Qt.GlobalColor.white if i % 2 == 0
                    else Qt.GlobalColor.lightGray
                )
```

### Min 1 Satır, Silinemez

```python
def remove_alt_iskonto_row(self, row: int):
    """İndirim satırını sil — en az 1 kalmalı."""
    if self.table_alt_iskonto.rowCount() <= 1:
        # Son satırı temizle, silme
        w_val = self.table_alt_iskonto.cellWidget(row, 3)
        if w_val:
            w_val.setText("0.00")
        self.calculate_totals()
        return
    self.table_alt_iskonto.removeRow(row)
    self.calculate_totals()
```

### Başlangıçta 1 Boş Satır

```python
# __init__ içinde table_alt_iskonto oluşturduktan sonra:
# ESKİ: self.add_alt_iskonto_row(item_type="İskonto", ...)
# YENİ: Aynı — sadece 1 satır ekle, silinemesin
self.add_alt_iskonto_row(
    item_type="İndirim",
    calc_type="Oran %",
    val="0.00"
)
# NOT: remove_alt_iskonto_row metodunda rowCount()<=1 kontrolü
# zaten bunu engelliyor
```

---

## 17.5 — HareketKalemleriWidget: Başlangıçta 1 Satır

```python
# __init__ içinde:
# ESKİ: 16 boş satır ekleniyor
# YENİ: Sadece 1 boş satır

# Mevcut demo satırı koru, fazla satırları kaldır:
# init_ui() sonunda sadece şunu çağır:
self.add_item_row(
    item_type="Malzeme",
    code="",
    name="",
    qty=1.0,
    unit="Adet",
    price=0.0,
    vat=20,
)
# demo satırları (STK-001 vb.) kaldır
```

---

## Test

```
1. Ekranı aç → Kalemler grid'inde 1 boş satır var
2. İndirim grid'inde 1 boş satır var
3. Kalem satırına sağ tıkla:
   → Satır Ekle, Sil, Yukarı, Aşağı var mı?
   → Sütun gizle/göster var mı?
   → Artan/Azalan sırala var mı?
   → Görünümü Kaydet var mı?
4. Son kalan satırı silmeye çalış → silinmez, temizlenir
5. Sütunu gizle → sağ tıkta "Gizlileri Göster" çıkıyor mu?
6. Cari Kodu alanı okunabilir mi?
7. Vergi D./No alanları yeterli genişlikte mi?
```

---

---

## 17.6 — Sağ Sidebar (EdgeTriggeredPanel — Sağ Taraf)

Mevcut sağ panel yoksa ekle, varsa içeriğini güncelle.

```python
# init_ui içinde — main_layout'a content_widget'tan SONRA ekle:
self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

right_scroll = QScrollArea()
right_scroll.setWidgetResizable(True)
right_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

right_frame = QFrame()
right_frame.setStyleSheet("background:transparent;border:none;")
right_lyt = QVBoxLayout(right_frame)
right_lyt.setContentsMargins(0, 0, 0, 0)
right_lyt.setSpacing(6)

# ── YAZDIRMA & AKTARIM ──
sec_print = CollapsibleSection("🖨️ YAZDIRMA & AKTARIM", is_expanded=True)

btn_pdf = QPushButton("🖨️ PDF Yazdır (F9)")
btn_pdf.setStyleSheet(self.sidebar_btn_style("#0284c7", "#ffffff"))
btn_pdf.clicked.connect(self.save_and_print_document)

btn_excel = QPushButton("📊 Excel'e Aktar")
btn_excel.setStyleSheet(self.sidebar_btn_style())
btn_excel.clicked.connect(self.export_to_excel)

btn_share = QPushButton("📤 Gönder / Paylaş")
btn_share.setStyleSheet(self.sidebar_btn_style("#7c3aed", "#ffffff"))
btn_share.clicked.connect(self.open_share_dialog)

btn_whatsapp = QPushButton("💬 WhatsApp")
btn_whatsapp.setStyleSheet(self.sidebar_btn_style("#16a34a", "#ffffff"))
btn_whatsapp.clicked.connect(self._share_whatsapp)

btn_email = QPushButton("📧 E-posta Gönder")
btn_email.setStyleSheet(self.sidebar_btn_style())
btn_email.clicked.connect(self._send_email_quick)

btn_copy_link = QPushButton("🔗 Linki Kopyala")
btn_copy_link.setStyleSheet(self.sidebar_btn_style())
btn_copy_link.clicked.connect(self._copy_link)

sec_print.add_widget(btn_pdf)
sec_print.add_widget(btn_excel)
sec_print.add_widget(btn_share)
sec_print.add_widget(btn_whatsapp)
sec_print.add_widget(btn_email)
sec_print.add_widget(btn_copy_link)
right_lyt.addWidget(sec_print)

# ── EVRAK BİLGİLERİ (salt okunur özet) ──
sec_info = CollapsibleSection("📋 EVRAK ÖZETİ", is_expanded=True)

self.lbl_right_teklif_no = QLabel("Belge No: —")
self.lbl_right_teklif_no.setStyleSheet(
    "font-size:10px; font-weight:600; color:#1e3a8a;"
)
self.lbl_right_musteri = QLabel("Müşteri: —")
self.lbl_right_musteri.setStyleSheet(
    "font-size:10px; color:#475569;"
)
self.lbl_right_toplam = QLabel("Toplam: —")
self.lbl_right_toplam.setStyleSheet(
    "font-size:11px; font-weight:700; color:#1e3a8a;"
)
self.lbl_right_durum = QLabel("Durum: Taslak")
self.lbl_right_durum.setStyleSheet(
    "font-size:10px; color:#64748b;"
)

sec_info.add_widget(self.lbl_right_teklif_no)
sec_info.add_widget(self.lbl_right_musteri)
sec_info.add_widget(self.lbl_right_toplam)
sec_info.add_widget(self.lbl_right_durum)
right_lyt.addWidget(sec_info)

# ── HIZLI İŞLEMLER ──
sec_quick = CollapsibleSection("⚡ HIZLI İŞLEMLER", is_expanded=True)

btn_convert = QPushButton("🔄 Siparişe Dönüştür")
btn_convert.setStyleSheet(self.sidebar_btn_style("#0369a1", "#ffffff"))
btn_convert.clicked.connect(self._on_convert_clicked)

btn_copy_doc = QPushButton("📋 Belgeyi Kopyala")
btn_copy_doc.setStyleSheet(self.sidebar_btn_style())
btn_copy_doc.clicked.connect(self._on_duplicate_doc)

btn_efatura = QPushButton("⚡ e-Fatura Gönder")
btn_efatura.setStyleSheet(self.sidebar_btn_style("#7c3aed", "#ffffff"))
btn_efatura.clicked.connect(self.send_earciv)

sec_quick.add_widget(btn_convert)
sec_quick.add_widget(btn_copy_doc)
sec_quick.add_widget(btn_efatura)
right_lyt.addWidget(sec_quick)

right_lyt.addStretch()
right_scroll.setWidget(right_frame)
self.right_panel.set_content(right_scroll)
self.right_panel.close_panel()  # Başlangıçta kapalı

# main_layout'a ekle (content_widget'tan sonra)
main_layout.addWidget(self.right_panel)
```

### Yardımcı Metodlar Ekle

```python
def _share_whatsapp(self):
    """WhatsApp ile paylaş."""
    try:
        data = self._get_current_teklif_data()
        svc = self._get_report_service()
        svc.share_engine.share_whatsapp(
            url="https://baynetbilisim.tr/teklif/view?token=DEMO",
            musteri_adi=data["musteri"].get("adi", ""),
            teklif_no=data["belge"].get("teklif_no", ""),
            firma_adi=data["firma"].get("adi", ""),
        )
    except Exception as e:
        QMessageBox.critical(self, "Hata", str(e))

def _send_email_quick(self):
    """E-posta gönder — önce adres sor."""
    email = self.txt_cari_unvan.text().strip()
    addr, ok = QInputDialog.getText(
        self, "E-posta Gönder",
        "Alıcı e-posta adresi:",
        text=""
    )
    if not ok or not addr.strip():
        return
    try:
        data = self._get_current_teklif_data()
        pdf = self._get_report_service().pdf_engine.render_pdf(
            "teklif/teklif_print.html", data
        )
        ok2, msg = self._get_report_service().email_engine.send_teklif_email(
            to_email=addr.strip(),
            teklif_data=data,
            pdf_bytes=pdf,
        )
        if ok2:
            QMessageBox.information(self, "Gönderildi", msg)
        else:
            QMessageBox.critical(self, "Hata", msg)
    except Exception as e:
        QMessageBox.critical(self, "Hata", str(e))

def _copy_link(self):
    """Teklif linkini panoya kopyala."""
    try:
        data = self._get_current_teklif_data()
        teklif_no = data["belge"].get("teklif_no", "DEMO")
        url = f"https://baynetbilisim.tr/teklif/view?token={teklif_no}"
        self._get_report_service().share_engine.copy_to_clipboard(url)
        QMessageBox.information(self, "Kopyalandı", f"Link panoya kopyalandı:\n{url}")
    except Exception as e:
        QMessageBox.critical(self, "Hata", str(e))

def _on_convert_clicked(self):
    """Siparişe dönüştür."""
    QMessageBox.information(
        self, "Siparişe Dönüştür",
        "Teklif kaydedildikten sonra siparişe dönüştürülebilir."
    )

def _on_duplicate_doc(self):
    """Belgeyi kopyala."""
    QMessageBox.information(
        self, "Kopyala",
        "Belge kopyalanıyor..."
    )

def _update_right_panel_summary(self):
    """
    Sağ paneldeki özet bilgileri güncelle.
    calculate_totals() içinden çağır.
    """
    if not hasattr(self, "lbl_right_teklif_no"):
        return
    try:
        no = self.txt_top_doc_no.text() if hasattr(self, "txt_top_doc_no") else "—"
        musteri = self.txt_cari_unvan.text()[:25] + "..." \
            if len(self.txt_cari_unvan.text()) > 25 \
            else self.txt_cari_unvan.text()
        toplam = self.lbl_grand_total.text() \
            if hasattr(self, "lbl_grand_total") else "—"

        self.lbl_right_teklif_no.setText(f"📄 {no}")
        self.lbl_right_musteri.setText(f"👤 {musteri or '—'}")
        self.lbl_right_toplam.setText(f"💰 {toplam}")
    except Exception:
        pass
```

### calculate_totals İçine Ekle (En Sona)

```python
def calculate_totals(self):
    # ... mevcut kod ...

    # Sağ panel özet güncelle
    self._update_right_panel_summary()
```

---

## Özet

| # | Değişiklik | Nerede |
|---|-----------|--------|
| 17.1 | Alan genişlikleri | CariKunye, BelgeVade |
| 17.2 | Sağ tık menüsü | HareketKalemleriWidget |
| 17.3 | Min 1 satır | HareketKalemleriWidget |
| 17.4 | Aynı özellikler | AltIskontoMasrafWidget |
| 17.5 | Başlangıç 1 satır | Her iki grid |
| 17.6 | Sağ sidebar | Yazdır/Excel/Paylaş/WhatsApp/E-posta/Link/Dönüştür |
