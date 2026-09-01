# YZ 2 — Görev 14: Genel Ayarlar Ekranı Yeniden Yapılandırma

> **Dosya:** `src/desktop/ui/settings.py`  
> **Kural:** Sadece bu dosyayı değiştir.  
> **Referans:** `transaction_document_dialog.py` — sol sidebar + alt bar yapısı aynı olacak.

---

## Hedef Yapı

```
┌─────────────────────────────────────────────────────────┐
│ ⚙️ [sys.set.001] Genel Ayarlar                         │
├──────────────────┬──────────────────────────────────────┤
│ SOL SIDEBAR      │ BODY (QStackedWidget)                │
│ ──────────────── │                                      │
│ İŞLEMLER grubu   │ Seçilen menüye göre panel açılır     │
│  💾 Kaydet (F2)  │                                      │
│  ➕ Yeni         │                                      │
│  ❌ Sil          │                                      │
│  ↩️ Vazgeç       │                                      │
│ ──────────────── │                                      │
│ ▼ FİRMA          │                                      │
│    Firma Bilgileri│                                     │
│    Şube Tanımları│                                      │
│ ▼ KULLANICI      │                                      │
│    Kullanıcılar  │                                      │
│    Roller        │                                      │
│    Yetkiler      │                                      │
│ ▼ FİNANS         │                                      │
│    Döviz & Kur   │                                      │
│    Ödeme Planları│                                      │
│    Fiyat Listesi │                                      │
│ ▼ STOK           │                                      │
│    Kategoriler   │                                      │
│    Markalar      │                                      │
│    Birimler      │                                      │
│    Depolar       │                                      │
│    Özel Alanlar  │                                      │
│ ▼ CARİ           │                                      │
│    Cari Grupları │                                      │
│    Özel Alanlar  │                                      │
│ ▼ SİSTEM         │                                      │
│    Görünüm       │                                      │
│    Ekran Grid    │                                      │
│    Sürüm & Git   │                                      │
├──────────────────┴──────────────────────────────────────┤
│ 💡 F2: Kaydet | Del: Sil | Esc: Kapat                  │
│                        [↩️ Vazgeç] [💾 KAYDET (F2)]    │
└─────────────────────────────────────────────────────────┘
```

---

## Ana Yapı Kodu

```python
class GeneralSettingsScreen(QWidget):
    """
    Genel Ayarlar Ana Ekranı — sys.set.001
    Sol sidebar (menü + işlemler) + Body (QStackedWidget) + Alt bar
    """

    toast_requested = pyqtSignal(str, str)

    # Menü yapısı — (grup_adı, ikon, [(menü_adı, panel_id), ...])
    MENU_STRUCTURE = [
        ("FİRMA", "🏢", [
            ("Firma Bilgileri",   "firma_bilgileri"),
            ("Şube Tanımları",    "sube_tanimlari"),
        ]),
        ("KULLANICI & YETKİ", "👤", [
            ("Kullanıcılar",      "kullanicilar"),
            ("Rol Tanımları",     "roller"),
            ("Yetki Matrisi",     "yetkiler"),
        ]),
        ("FİNANS TANIMLARI", "💱", [
            ("Döviz & Kur",       "doviz_kur"),
            ("Ödeme Planları",    "odeme_planlari"),
            ("Fiyat Listeleri",   "fiyat_listeleri"),
        ]),
        ("STOK TANIMLARI", "📦", [
            ("Kategoriler",       "stok_kategoriler"),
            ("Markalar",          "stok_markalar"),
            ("Birim Tanımları",   "birim_tanimlari"),
            ("Depo Tanımları",    "depo_tanimlari"),
            ("Özel Alanlar",      "stok_ozel_alanlar"),
        ]),
        ("CARİ TANIMLARI", "👥", [
            ("Cari Grupları",     "cari_gruplari"),
            ("Özel Alanlar",      "cari_ozel_alanlar"),
        ]),
        ("SİSTEM", "🖥️", [
            ("Görünüm Profilleri","gorunum_profilleri"),
            ("Ekran Grid Tanım.", "ekran_grid"),
            ("Sürüm & Git",       "surum_git"),
        ]),
    ]

    def __init__(self, db_session=None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.active_panel_id = None
        self.panels: dict[str, QWidget] = {}
        self.menu_buttons: dict[str, QPushButton] = {}
        self.init_ui()
        # İlk panel — Firma Bilgileri
        self.switch_panel("firma_bilgileri")
```

---

## Sol Sidebar

```python
def build_left_sidebar(self) -> QWidget:
    """Sol sidebar — EdgeTriggeredPanel içinde."""
    self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

    frame = QFrame()
    frame.setStyleSheet("background:transparent; border:none;")
    lyt = QVBoxLayout(frame)
    lyt.setContentsMargins(0, 0, 0, 0)
    lyt.setSpacing(6)

    # ── İŞLEMLER GRUBU ──
    self.sec_actions = CollapsibleSection("İŞLEMLER", is_expanded=True)

    self.btn_save = QPushButton("💾 Kaydet (F2)")
    self.btn_save.setShortcut("F2")
    self.btn_save.setStyleSheet(self.btn_style("#2563eb", "#ffffff"))
    self.btn_save.clicked.connect(self.save_current_panel)

    self.btn_new = QPushButton("➕ Yeni")
    self.btn_new.setStyleSheet(self.btn_style())
    self.btn_new.clicked.connect(self.new_current_panel)

    self.btn_delete = QPushButton("❌ Sil")
    self.btn_delete.setStyleSheet(self.btn_style("#fee2e2", "#991b1b"))
    self.btn_delete.clicked.connect(self.delete_current_panel)

    self.btn_cancel = QPushButton("↩️ Vazgeç")
    self.btn_cancel.setStyleSheet(self.btn_style())
    self.btn_cancel.clicked.connect(self.cancel_current_panel)

    self.sec_actions.add_widget(self.btn_save)
    self.sec_actions.add_widget(self.btn_new)
    self.sec_actions.add_widget(self.btn_delete)
    self.sec_actions.add_widget(self.btn_cancel)
    lyt.addWidget(self.sec_actions)

    # ── MENÜ GRUPLARI ──
    for grup_adi, ikon, menuler in self.MENU_STRUCTURE:
        sec = CollapsibleSection(f"{ikon} {grup_adi}", is_expanded=False)
        for menu_adi, panel_id in menuler:
            btn = QPushButton(f"  {menu_adi}")
            btn.setStyleSheet(self.menu_btn_style())
            btn.setCheckable(True)
            btn.clicked.connect(
                lambda _, pid=panel_id, b=btn: self.on_menu_clicked(pid, b)
            )
            self.menu_buttons[panel_id] = btn
            sec.add_widget(btn)
        lyt.addWidget(sec)

    lyt.addStretch()
    scroll.setWidget(frame)
    self.left_panel.set_content(scroll)
    return self.left_panel

def on_menu_clicked(self, panel_id: str, btn: QPushButton):
    """Menü butonuna tıklanınca panel değiştir."""
    # Aktif butonu işaretle
    for b in self.menu_buttons.values():
        b.setChecked(False)
        b.setStyleSheet(self.menu_btn_style())
    btn.setChecked(True)
    btn.setStyleSheet(self.menu_btn_style(active=True))
    self.switch_panel(panel_id)

def btn_style(self, bg="#ffffff", fg="#1e293b"):
    return f"""
        QPushButton {{
            background:{bg}; color:{fg};
            border:1px solid #cbd5e1; border-radius:4px;
            padding:4px 8px; font-size:11px; font-weight:600;
            text-align:left; min-height:24px;
        }}
        QPushButton:hover {{ background:#f1f5f9; }}
    """

def menu_btn_style(self, active=False):
    if active:
        return """
            QPushButton {
                background:#eff6ff; color:#1d4ed8;
                border:none; border-left:3px solid #2563eb;
                padding:4px 8px; font-size:11px; font-weight:600;
                text-align:left; min-height:22px;
            }
        """
    return """
        QPushButton {
            background:transparent; color:#475569;
            border:none; border-left:3px solid transparent;
            padding:4px 8px; font-size:11px;
            text-align:left; min-height:22px;
        }
        QPushButton:hover {
            background:#f8fafc; color:#1e293b;
        }
    """
```

---

## Body — QStackedWidget

```python
def build_body(self) -> QStackedWidget:
    """Sağ body — paneller burada gösterilir."""
    self.stack = QStackedWidget()

    # Panelleri oluştur ve stack'e ekle
    panel_builders = {
        "firma_bilgileri":   self.build_firma_bilgileri_panel,
        "sube_tanimlari":    self.build_sube_panel,
        "kullanicilar":      self.build_kullanicilar_panel,
        "roller":            self.build_roller_panel,
        "yetkiler":          self.build_yetkiler_panel,
        "doviz_kur":         self.build_doviz_panel,
        "odeme_planlari":    self.build_odeme_planlari_panel,
        "fiyat_listeleri":   self.build_fiyat_listeleri_panel,
        "stok_kategoriler":  self.build_stok_kategoriler_panel,
        "stok_markalar":     self.build_stok_markalar_panel,
        "birim_tanimlari":   self.build_birim_panel,
        "depo_tanimlari":    self.build_depo_panel,
        "stok_ozel_alanlar": self.build_ozel_alan_panel,
        "cari_gruplari":     self.build_cari_gruplari_panel,
        "cari_ozel_alanlar": self.build_cari_ozel_alan_panel,
        "gorunum_profilleri":self.build_gorunum_panel,
        "ekran_grid":        self.build_ekran_grid_panel,
        "surum_git":         self.build_surum_panel,
    }

    for panel_id, builder in panel_builders.items():
        panel = builder()
        self.panels[panel_id] = panel
        self.stack.addWidget(panel)

    return self.stack

def switch_panel(self, panel_id: str):
    """Aktif paneli değiştir."""
    self.active_panel_id = panel_id
    if panel_id in self.panels:
        self.stack.setCurrentWidget(self.panels[panel_id])
    # Üst başlığı güncelle
    menu_name = next(
        (m for _, _, ml in self.MENU_STRUCTURE for m, pid in ml if pid == panel_id),
        panel_id
    )
    if hasattr(self, "lbl_breadcrumb"):
        self.lbl_breadcrumb.setText(f"⚙️ Genel Ayarlar > {menu_name}")
```

---

## Alt Bar

```python
def build_bottom_bar(self) -> QFrame:
    """Alt sabit aksiyon barı."""
    bar = QFrame()
    bar.setFixedHeight(42)
    bar.setStyleSheet("""
        QFrame {
            background:#f8fafc;
            border-top:1px solid #cbd5e1;
        }
    """)
    lyt = QHBoxLayout(bar)
    lyt.setContentsMargins(10, 4, 10, 4)
    lyt.setSpacing(8)

    # Kısayol bilgisi
    lbl = QLabel("💡 <b>F2:</b> Kaydet | <b>Del:</b> Sil | <b>Esc:</b> Kapat")
    lbl.setStyleSheet("color:#64748b; font-size:10px;")

    # Sağ taraf butonlar
    btn_cancel = QPushButton("↩️ Vazgeç")
    btn_cancel.setFixedHeight(28)
    btn_cancel.setStyleSheet(self.btn_style("#fee2e2", "#991b1b"))
    btn_cancel.clicked.connect(self.cancel_current_panel)

    btn_save = QPushButton("💾 KAYDET (F2)")
    btn_save.setShortcut("F2")
    btn_save.setFixedHeight(28)
    btn_save.setStyleSheet(self.btn_style("#2563eb", "#ffffff"))
    btn_save.clicked.connect(self.save_current_panel)

    lyt.addWidget(lbl)
    lyt.addStretch()
    lyt.addWidget(btn_cancel)
    lyt.addWidget(btn_save)
    return bar
```

---

## Paneller

### Döviz & Kur Paneli
```python
def build_doviz_panel(self) -> QWidget:
    """
    Para birimleri ve güncel kur girişi.
    Teklif/Fatura'da cmb_doviz bu tablodan okur.
    """
    w = QWidget()
    lyt = QVBoxLayout(w)
    lyt.setContentsMargins(12, 12, 12, 12)

    # Başlık
    lbl = QLabel("💱 Döviz & Kur Tanımları")
    lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
    lyt.addWidget(lbl)

    # Açıklama
    lbl_info = QLabel(
        "Tanımlanan para birimleri Teklif, Fatura ve Stok "
        "ekranlarında otomatik kullanılır."
    )
    lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
    lbl_info.setWordWrap(True)
    lyt.addWidget(lbl_info)

    # Grid — para birimleri listesi
    self.tbl_doviz = QTableWidget(0, 5)
    self.tbl_doviz.setHorizontalHeaderLabels([
        "Kod", "Açıklama", "Sembol", "Güncel Kur (TL)", "Durum"
    ])
    self.tbl_doviz.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )
    self.tbl_doviz.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )

    # Varsayılan para birimleri
    DEFAULT_CURRENCIES = [
        ("TRY", "Türk Lirası",    "₺", "1.0000",   "Aktif"),
        ("USD", "Amerikan Doları","$", "38.5000",   "Aktif"),
        ("EUR", "Euro",           "€", "41.2000",   "Aktif"),
        ("GBP", "İngiliz Sterlini","£","48.9000",   "Aktif"),
    ]
    for row_data in DEFAULT_CURRENCIES:
        r = self.tbl_doviz.rowCount()
        self.tbl_doviz.insertRow(r)
        for c, val in enumerate(row_data):
            self.tbl_doviz.setItem(r, c, QTableWidgetItem(val))

    lyt.addWidget(self.tbl_doviz, 1)

    # DB'den yükle (varsa)
    self._load_doviz_from_db()
    return w

def _load_doviz_from_db(self):
    """DB'de doviz tablosu varsa yükle."""
    if not self.db:
        return
    try:
        from src.core.models import Currency
        currencies = self.db.scalars(
            select(Currency).where(Currency.is_deleted == False)
        ).all()
        if currencies:
            self.tbl_doviz.setRowCount(0)
            for c in currencies:
                r = self.tbl_doviz.rowCount()
                self.tbl_doviz.insertRow(r)
                self.tbl_doviz.setItem(r, 0, QTableWidgetItem(c.code or ""))
                self.tbl_doviz.setItem(r, 1, QTableWidgetItem(c.name or ""))
                self.tbl_doviz.setItem(r, 2, QTableWidgetItem(c.symbol or ""))
                self.tbl_doviz.setItem(r, 3, QTableWidgetItem(
                    f"{float(c.rate or 1):.4f}"
                ))
                self.tbl_doviz.setItem(r, 4, QTableWidgetItem(
                    "Aktif" if c.is_active else "Pasif"
                ))
    except Exception:
        pass  # Model yoksa varsayılan liste kalır
```

### Birim Tanımları Paneli
```python
def build_birim_panel(self) -> QWidget:
    """
    Birim tanımları.
    Stok kartında cmb_unit bu tablodan okur.
    """
    w = QWidget()
    lyt = QVBoxLayout(w)
    lyt.setContentsMargins(12, 12, 12, 12)

    lbl = QLabel("📏 Birim Tanımları")
    lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
    lyt.addWidget(lbl)

    self.tbl_birim = QTableWidget(0, 3)
    self.tbl_birim.setHorizontalHeaderLabels(["Kod", "Açıklama", "Durum"])
    self.tbl_birim.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )

    DEFAULT_UNITS = [
        ("ADET",    "Adet",           "Aktif"),
        ("KG",      "Kilogram",       "Aktif"),
        ("GR",      "Gram",           "Aktif"),
        ("LT",      "Litre",          "Aktif"),
        ("MT",      "Metre",          "Aktif"),
        ("M2",      "Metrekare",      "Aktif"),
        ("M3",      "Metreküp",       "Aktif"),
        ("PKT",     "Paket",          "Aktif"),
        ("KTN",     "Karton",         "Aktif"),
        ("KLI",     "Koli",           "Aktif"),
        ("HZM",     "Hizmet",         "Aktif"),
        ("SFR",     "Sefer",          "Aktif"),
    ]
    for row_data in DEFAULT_UNITS:
        r = self.tbl_birim.rowCount()
        self.tbl_birim.insertRow(r)
        for c, val in enumerate(row_data):
            self.tbl_birim.setItem(r, c, QTableWidgetItem(val))

    lyt.addWidget(self.tbl_birim, 1)
    return w
```

### Özel Alan Tanımları Paneli
```python
def build_ozel_alan_panel(self, modul="stok") -> QWidget:
    """
    Özel alan etiketlerini kullanıcı değiştirebilir.
    
    Örn: Özel Kod 1 → "Çağrı Numarası"
         Özel Kod 2 → "Proje Kodu"
    """
    w = QWidget()
    lyt = QVBoxLayout(w)
    lyt.setContentsMargins(12, 12, 12, 12)
    lyt.setSpacing(10)

    lbl = QLabel("🏷️ Özel Alan Tanımları")
    lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
    lyt.addWidget(lbl)

    lbl_info = QLabel(
        "Özel kod ve alan etiketlerini sektörünüze göre özelleştirin.\n"
        "Değişiklikler Stok Kartı formunda anında yansır."
    )
    lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
    lbl_info.setWordWrap(True)
    lyt.addWidget(lbl_info)

    # Form grid
    form = QGridLayout()
    form.setSpacing(8)
    form.setColumnStretch(1, 1)
    form.setColumnStretch(3, 1)

    OZEL_ALANLAR = [
        ("Özel Kod 1",  "ozel_kod_1",  "Metin"),
        ("Özel Kod 2",  "ozel_kod_2",  "Metin"),
        ("Özel Kod 3",  "ozel_kod_3",  "Metin"),
        ("Özel Alan 1", "ozel_alan_1", "Metin"),
        ("Özel Alan 2", "ozel_alan_2", "Sayı"),
        ("Özel Alan 3", "ozel_alan_3", "Tarih"),
    ]

    lbl_style = "font-size:11px; font-weight:600; color:#475569;"
    self.ozel_alan_inputs = {}

    for i, (varsayilan, key, tip) in enumerate(OZEL_ALANLAR):
        r = i // 2
        c_offset = (i % 2) * 2

        # Etiket (değiştirilebilir alan adı)
        lbl_alan = QLabel(f"{varsayilan}:")
        lbl_alan.setStyleSheet(lbl_style)
        txt = QLineEdit()
        txt.setPlaceholderText(f"{varsayilan} (boş bırakırsanız varsayılan kullanılır)")
        txt.setFixedHeight(24)
        txt.setToolTip(
            f"Varsayılan: '{varsayilan}'\n"
            f"Tip: {tip}\n"
            f"Örn: 'Çağrı Numarası', 'Proje Kodu', 'Garanti Süresi'"
        )
        self.ozel_alan_inputs[key] = txt

        form.addWidget(lbl_alan, r, c_offset)
        form.addWidget(txt, r, c_offset + 1)

    lyt.addLayout(form)
    lyt.addStretch()

    # Mevcut ayarları yükle
    self._load_ozel_alanlar(modul)
    return w

def _load_ozel_alanlar(self, modul: str):
    """Kayıtlı özel alan etiketlerini yükle."""
    if not self.db:
        return
    try:
        from src.core.models import SystemSetting
        for key, txt in self.ozel_alan_inputs.items():
            setting = self.db.scalar(
                select(SystemSetting).where(
                    SystemSetting.key == f"{modul}.{key}.label"
                )
            )
            if setting:
                txt.setText(setting.value or "")
    except Exception:
        pass
```

### Depo Tanımları Paneli
```python
def build_depo_panel(self) -> QWidget:
    """
    Depo tanımları.
    Teklif/Fatura üst barındaki Depo seçicisi buradan okur.
    """
    w = QWidget()
    lyt = QVBoxLayout(w)
    lyt.setContentsMargins(12, 12, 12, 12)

    lbl = QLabel("🏭 Depo Tanımları")
    lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
    lyt.addWidget(lbl)

    self.tbl_depo = QTableWidget(0, 4)
    self.tbl_depo.setHorizontalHeaderLabels([
        "Depo Kodu", "Depo Adı", "Adres", "Durum"
    ])
    self.tbl_depo.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )

    DEFAULT_DEPOLAR = [
        ("2001", "MERKEZ DEPO",   "Merkez", "Aktif"),
        ("2002", "ŞUBE DEPOSU",   "Şube",   "Aktif"),
        ("2003", "TEŞHİR DEPOSU", "Mağaza", "Aktif"),
    ]
    for row_data in DEFAULT_DEPOLAR:
        r = self.tbl_depo.rowCount()
        self.tbl_depo.insertRow(r)
        for c, val in enumerate(row_data):
            self.tbl_depo.setItem(r, c, QTableWidgetItem(val))

    lyt.addWidget(self.tbl_depo, 1)
    return w
```

### Ödeme Planları Paneli
```python
def build_odeme_planlari_panel(self) -> QWidget:
    """
    Ödeme planları tanımları.
    transaction_document_dialog'daki cmb_odeme_plani buradan okur.
    """
    w = QWidget()
    lyt = QVBoxLayout(w)
    lyt.setContentsMargins(12, 12, 12, 12)

    lbl = QLabel("💳 Ödeme Planı Tanımları")
    lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
    lyt.addWidget(lbl)

    self.tbl_odeme = QTableWidget(0, 5)
    self.tbl_odeme.setHorizontalHeaderLabels([
        "Kod", "Açıklama", "Gün", "Ödeme Tipi", "Durum"
    ])
    self.tbl_odeme.horizontalHeader().setSectionResizeMode(
        1, QHeaderView.ResizeMode.Stretch
    )

    DEFAULT_PLANLAR = [
        ("30GVD",   "30 GÜN VADE",           "30",  "Açık Hesap",  "Aktif"),
        ("45GVD",   "45 GÜNLÜK VADE",         "45",  "Açık Hesap",  "Aktif"),
        ("60GVD",   "60 GÜNLÜK VADE",         "60",  "Açık Hesap",  "Aktif"),
        ("60GUNKK", "60 GÜN KREDİ KARTI",     "60",  "Kredi Kartı", "Aktif"),
        ("AH",      "AÇIK HESAP",              "0",   "Açık Hesap",  "Aktif"),
        ("NAKIT",   "NAKİT",                   "0",   "Nakit",       "Aktif"),
        ("CF3TAK",  "CARDFINANS 3 TAKSİT",     "90",  "Taksit",      "Aktif"),
    ]
    for row_data in DEFAULT_PLANLAR:
        r = self.tbl_odeme.rowCount()
        self.tbl_odeme.insertRow(r)
        for c, val in enumerate(row_data):
            self.tbl_odeme.setItem(r, c, QTableWidgetItem(val))

    lyt.addWidget(self.tbl_odeme, 1)
    return w
```

---

## Kaydet / Yeni / Sil Metodları

```python
def save_current_panel(self):
    """Aktif paneldeki veriyi kaydet."""
    panel_save_map = {
        "doviz_kur":      self._save_doviz,
        "birim_tanimlari":self._save_birimler,
        "depo_tanimlari": self._save_depolar,
        "odeme_planlari": self._save_odeme_planlari,
        "stok_ozel_alanlar": lambda: self._save_ozel_alanlar("stok"),
        "cari_ozel_alanlar": lambda: self._save_ozel_alanlar("cari"),
    }
    fn = panel_save_map.get(self.active_panel_id)
    if fn:
        fn()
        self.toast_requested.emit("Kaydedildi.", "success")
    else:
        QMessageBox.information(self, "Bilgi", "Bu panel için kaydet işlemi uygulanmadı.")

def new_current_panel(self):
    """Aktif panele yeni satır ekle."""
    panel_table_map = {
        "doviz_kur":       "tbl_doviz",
        "birim_tanimlari": "tbl_birim",
        "depo_tanimlari":  "tbl_depo",
        "odeme_planlari":  "tbl_odeme",
    }
    tbl_attr = panel_table_map.get(self.active_panel_id)
    if tbl_attr and hasattr(self, tbl_attr):
        tbl = getattr(self, tbl_attr)
        tbl.insertRow(tbl.rowCount())

def delete_current_panel(self):
    """Aktif panelden seçili satırı sil."""
    panel_table_map = {
        "doviz_kur":       "tbl_doviz",
        "birim_tanimlari": "tbl_birim",
        "depo_tanimlari":  "tbl_depo",
        "odeme_planlari":  "tbl_odeme",
    }
    tbl_attr = panel_table_map.get(self.active_panel_id)
    if tbl_attr and hasattr(self, tbl_attr):
        tbl = getattr(self, tbl_attr)
        row = tbl.currentRow()
        if row >= 0:
            reply = QMessageBox.question(
                self, "Sil", "Seçili kayıt silinecek. Emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                tbl.removeRow(row)

def cancel_current_panel(self):
    """Değişiklikleri iptal et — paneli yenile."""
    self.switch_panel(self.active_panel_id)
```

---

## Mevcut Panelleri Taşı

Mevcut settings.py'deki şu sekmelerin içeriğini ilgili panel builder metoduna taşı:

| Mevcut Sekme | Yeni Panel |
|-------------|-----------|
| Firma Tanımları | `build_firma_bilgileri_panel()` |
| Kullanıcı Tanımları | `build_kullanicilar_panel()` |
| Görünüm Profilleri | `build_gorunum_panel()` |
| Sürüm & Git Takibi | `build_surum_panel()` |
| Ekran Grid Tanımları | `build_ekran_grid_panel()` |

---

## DB Modelleri (Gerekirse Ekle)

```python
# models.py'e ekle (eğer yoksa):

class Currency(BaseModel):
    """Döviz & Kur tanımları."""
    __tablename__ = "currencies"
    code:      Mapped[str]
    name:      Mapped[str | None]
    symbol:    Mapped[str | None]
    rate:      Mapped[float | None] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    is_deleted:Mapped[bool] = mapped_column(Boolean, default=False)

class UnitDefinition(BaseModel):
    """Birim tanımları."""
    __tablename__ = "unit_definitions"
    code:      Mapped[str]
    name:      Mapped[str]
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    is_deleted:Mapped[bool] = mapped_column(Boolean, default=False)

class WarehouseDefinition(BaseModel):
    """Depo tanımları."""
    __tablename__ = "warehouse_definitions"
    code:      Mapped[str]
    name:      Mapped[str]
    address:   Mapped[str | None]
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    is_deleted:Mapped[bool] = mapped_column(Boolean, default=False)

class PaymentPlan(BaseModel):
    """Ödeme planı tanımları."""
    __tablename__ = "payment_plans"
    code:         Mapped[str]
    description:  Mapped[str]
    days:         Mapped[int | None] = mapped_column(Integer, default=0)
    payment_type: Mapped[str | None]
    is_active:    Mapped[bool | None] = mapped_column(Boolean, default=True)
    is_deleted:   Mapped[bool] = mapped_column(Boolean, default=False)

class SystemSetting(BaseModel):
    """Sistem ayarları — key/value."""
    __tablename__ = "system_settings"
    key:   Mapped[str]
    value: Mapped[str | None]
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

---

## Test Senaryosu

```
1. Ayarlar ekranı aç
   → Sol sidebar menüler görünüyor mu?

2. FİNANS → Döviz & Kur tıkla
   → Para birimleri tablosu açılıyor mu?

3. Yeni butonu → satır ekleniyor mu?
4. Kaydet → veri kaydediliyor mu?

5. STOK → Birim Tanımları tıkla
   → Birimler listesi açılıyor mu?

6. STOK → Özel Alanlar tıkla
   → Özel Kod 1 etiketini "Çağrı Numarası" yap → Kaydet
   → Stok kartında "Çağrı Numarası" yazıyor mu?

7. 1024x768 ekranda test et → taşma var mı?
```

---

## Özet

| # | Görev | Açıklama |
|---|-------|----------|
| 14.1 | Ana yapı | Sol sidebar + QStackedWidget + Alt bar |
| 14.2 | Mevcut paneller taşı | Sekme → panel dönüşümü |
| 14.3 | Döviz & Kur paneli | Para birimi + kur tablosu |
| 14.4 | Birim Tanımları | Stok kartında kullanılacak |
| 14.5 | Depo Tanımları | Teklif/Fatura üst barında |
| 14.6 | Ödeme Planları | Teklif/Fatura'da seçim |
| 14.7 | Özel Alan Tanımları | Dinamik etiket sistemi |
| 14.8 | DB modelleri | Currency, UnitDef, Warehouse, PaymentPlan |

> **Önce 14.1 ve 14.2** — mevcut işlevsellik korunsun.  
> Sonra yeni paneller sırasıyla eklensin.
