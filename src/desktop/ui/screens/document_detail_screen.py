"""
TOYA ERP - DocumentDetailScreen (Belge / Fiş Detay Ekranı)

Teklif · Sipariş · İrsaliye · Fatura gibi ticari belgelerin tek çatı altında
girildiği tam-ekran sekme. Belge türü sadece bir parametredir.

Yerleşim:
    sol panel : EVRAK İŞLEMLERİ · SATIR İŞLEMLERİ · GÖRÜNÜM & SÜTUNLAR   (EdgeTriggeredPanel)
    header    : belge türü / no / durum
    üst form  : CariKunyeWidget | BelgeVadeWidget | HareketFinansWidget   (katlanır, F7)
    gövde     : DocumentLinesGrid  (kalemler)
    alt panel : sekmeler [A İndirim & Masraflar · B Seri/Lot · C Varyant · D Paketler]
                + Notlar + ToplamWidget                                   (katlanır, F6)
    sağ panel : YAZDIRMA & AKTARIM · EVRAK ÖZETİ · HIZLI İŞLEMLER
                · KDV DAĞILIMI · ÖZEL KODLAR & EK ALANLAR                  (EdgeTriggeredPanel)
    footer    : Kaydet / Vazgeç

Her iki sidebar'a `widget_registry` kataloğundan widget eklenebilir ("+ Widget Ekle").
Mevcut TransactionDocumentDialog parite gelene kadar yan yana durur.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QKeySequence,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.quotation_save_service import QuotationSaveService
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.widgets.belge_vade_widget import BelgeVadeWidget
from src.desktop.ui.widgets.cari_kunye_widget import CariKunyeWidget
from src.desktop.ui.widgets.document_expenses_grid import DocumentExpensesGrid
from src.desktop.ui.widgets.document_form.belge_notlari_widget import BelgeNotlariWidget
from src.desktop.ui.widgets.document_lines_grid import DocumentLinesGrid, fmt_num
from src.desktop.ui.widgets.hareket_finans_widget import HareketFinansWidget
from src.desktop.ui.widgets.toplam_widget import ToplamWidget

try:
    from src.desktop.ui.widgets.widget_registry import (
        WIDGET_REGISTRY,
        create_widget_by_id,
    )
except Exception:  # pragma: no cover - katalog opsiyonel
    WIDGET_REGISTRY, create_widget_by_id = {}, None

logger = logging.getLogger(__name__)

DOCUMENT_TYPES = [
    "TEKLİF: Verilen Satış Teklifi",
    "TEKLİF: Alınan Teklif",
    "SİPARİŞ: Alınan Müşteri Siparişi",
    "SİPARİŞ: Verilen Tedarikçi Siparişi",
    "İRSALİYE: Sevk / Satış İrsaliyesi",
    "İRSALİYE: Alış İrsaliyesi",
    "FATURA: Yurt İçi Satış Faturası",
    "FATURA: Alış Faturası",
]

KDV_HEADERS = {0: ("%", "oran"), 1: ("Matrah", "matrah"), 2: ("Tutar", "kdv")}

OZEL_KOD_ALANLARI = [
    ("proje", "Proje"),
    ("plasiyer", "Plasiyer"),
    ("ozel_kod_1", "Özel Kod 1"),
    ("ozel_kod_2", "Özel Kod 2"),
    ("ozel_kod_3", "Özel Kod 3"),
    ("referans_no", "Referans / Sipariş No"),
]

_SIDEBAR_BTN = (
    # qt_material genel temasi QPushButton icin sabit "height: 36px" (yogunluk-olcekli)
    # tanimliyor; burada da acikca "height" verilmezse global kural kazaniyor ve buton
    # padding kucultmeye ragmen yuksek kaliyor.
    "QPushButton{{background:{bg};color:{fg};border:1px solid {bd};border-radius:4px;"
    "padding:0 8px;font-size:10px;font-weight:600;text-align:left;height:24px;}}"
    "QPushButton:hover{{background:{hv};}}"
    "QPushButton:disabled{{color:#94a3b8;background:#f8fafc;}}"
)


def _btn(text: str, bg="#ffffff", fg="#1e293b", bd="#cbd5e1", hv="#f1f5f9") -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(_SIDEBAR_BTN.format(bg=bg, fg=fg, bd=bd, hv=hv))
    return b


def _tr_date(iso: str) -> str:
    """'YYYY-MM-DD' -> 'DD.MM.YYYY' (baskı formatı). Tanınmayan girdiyi olduğu gibi döndürür."""
    parts = (iso or "").split("-")
    if len(parts) == 3 and all(parts):
        y, m, d = parts
        return f"{d}.{m}.{y}"
    return iso or ""


class WidgetCatalogDialog(QDialog):
    """widget_registry kataloğundan bir widget seçtiren basit liste."""

    def __init__(self, region: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Widget Kataloğu")
        self.setMinimumWidth(420)
        self.selected_id: str | None = None
        lyt = QVBoxLayout(self)
        lyt.addWidget(QLabel(f"'{region}' bölümüne eklenecek widget:"))
        self.lst = QListWidget()
        for wid, meta in WIDGET_REGISTRY.items():
            it = QListWidgetItem(f"{meta.get('name', wid)}  —  {meta.get('description', '')}")
            it.setData(Qt.ItemDataRole.UserRole, wid)
            self.lst.addItem(it)
        self.lst.itemDoubleClicked.connect(lambda _i: self._accept())
        lyt.addWidget(self.lst, 1)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lyt.addWidget(bb)

    def _accept(self):
        it = self.lst.currentItem()
        if it:
            self.selected_id = it.data(Qt.ItemDataRole.UserRole)
            self.accept()


class DocumentDetailScreen(QWidget):
    """Evrensel belge/fiş detay ekranı."""

    document_saved = pyqtSignal(dict)
    closed = pyqtSignal()

    def __init__(self, db_session=None, doc_id: int | None = None,
                 initial_type_idx: int = 0, company_id: int = 1, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.doc_id = doc_id
        self.company_id = company_id
        self.initial_type_idx = initial_type_idx
        self.service = QuotationSaveService(db_session=db_session, company_id=company_id)
        self._expenses = {"indirim": 0.0, "masraf": 0.0, "kdv": 0.0, "kdv_dagilim": {}}
        self._last_line_totals: dict = {}
        self._ozel_kod_inputs: dict[str, QLineEdit] = {}
        self._extra_left: list[QWidget] = []
        self._extra_right: list[QWidget] = []

        self._build_ui()
        self._load_products()
        self._wire()

        if self.doc_id:
            self._load_document()
        else:
            self.lines.add_row()
            self.expenses.add_row()
        self.lines._emit_totals()

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # ── Ana içerik (önce kur: sidebar butonları self.lines'a bağlanıyor) ──
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        root.addWidget(self._build_header())

        self.sec_ust_form = CollapsibleSection("ÜST BİLGİLER (F7)", is_expanded=True, compact=True)
        self.sec_ust_form.add_widget(self._build_top_form())
        root.addWidget(self.sec_ust_form)

        self.lines = DocumentLinesGrid(profile_key="belge_kalemleri")
        root.addWidget(self.lines, 1)

        self.sec_alt = CollapsibleSection("ALT PANEL (F6)", is_expanded=True, compact=True)
        self.sec_alt.add_widget(self._build_bottom_area())
        # Pencere kısaldığında QVBoxLayout, stretch'li kalem gridine alan verip
        # alt paneli minimumunun altına iterek Toplam widget'ının KDV / Genel
        # Toplam satırlarını kırpıyordu. Alt panele (açıkken) sert bir dikey
        # taban veriyoruz: artık yer kalmayınca kalem gridi küçülür, toplamlar
        # her zaman tam okunur kalır.
        self._sec_alt_min_h = self.toplam.minimumHeight() + 44
        self.sec_alt.setMinimumHeight(self._sec_alt_min_h)
        self.sec_alt.toggled.connect(
            lambda expanded: self.sec_alt.setMinimumHeight(
                self._sec_alt_min_h if expanded else 0,
            ),
        )
        root.addWidget(self.sec_alt)

        root.addWidget(self._build_footer())

        # ── Sol panel (docked/pinned — layout içinde normal davransın) ──
        self.left_panel = EdgeTriggeredPanel(side="left", default_width=190, parent=self)
        self.left_panel.set_content(self._build_left_panel())
        self._dock_panel(self.left_panel)
        outer.addWidget(self.left_panel)

        outer.addWidget(content, 1)

        # ── Sağ panel ──
        self.right_panel = EdgeTriggeredPanel(side="right", default_width=260, parent=self)
        self.right_panel.set_content(self._build_right_panel())
        self._dock_panel(self.right_panel)
        outer.addWidget(self.right_panel)

        # Kısayollar
        QShortcut(QKeySequence("F7"), self, activated=lambda: self.sec_ust_form.toggle())
        QShortcut(QKeySequence("F6"), self, activated=lambda: self.sec_alt.toggle())
        QShortcut(QKeySequence("F2"), self, activated=self._on_save_close)   # Kaydet ve Kapat
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._on_save)     # Kaydet ve Devam
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._on_save_new)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._on_save_new)
        QShortcut(QKeySequence("F9"), self, activated=self._on_save_print)
        QShortcut(QKeySequence("Esc"), self, activated=self.closed.emit)
        QShortcut(QKeySequence("Alt+Return"), self.lines.grid.table_view,
                  activated=lambda: self.lines.add_row(focus=True))
        QShortcut(QKeySequence("Alt+Enter"), self.lines.grid.table_view,
                  activated=lambda: self.lines.add_row(focus=True))
        QShortcut(QKeySequence("Ctrl+Delete"), self.lines.grid.table_view,
                  activated=self.lines.remove_checked_rows)
        QShortcut(QKeySequence("Alt+Up"), self.lines.grid.table_view,
                  activated=self.lines.move_selected_up)
        QShortcut(QKeySequence("Alt+Down"), self.lines.grid.table_view,
                  activated=self.lines.move_selected_down)

        # Sağ tık: belge eylemleri menüsü. Boş alanlarda ekran menüsü;
        # kalem gridinde ise grid kendi menüsüne bu eylemleri ekler.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_actions_menu)
        self.lines.document_actions_provider = self._populate_document_actions

    # ------------------------------------------------------------------
    def _populate_document_actions(self, menu: QMenu):
        """Verilen menüye belge düzeyi eylemleri (kaydet/yazdır/önizle) ekler."""
        act_save = QAction("💾 Kaydet", menu)
        act_save.triggered.connect(self._on_save)
        act_save_new = QAction("💾 Kaydet ve Yeni", menu)
        act_save_new.triggered.connect(self._on_save_new)
        act_save_print = QAction("🖨️ Kaydet ve Yazdır (F9)", menu)
        act_save_print.triggered.connect(self._on_save_print)
        act_preview = QAction("👁️ Önizle ve Yazdır", menu)
        act_preview.triggered.connect(self._on_preview)
        act_pdf = QAction("📄 PDF'e Aktar", menu)
        act_pdf.triggered.connect(self._on_export_pdf)
        act_cancel = QAction("🚪 Vazgeç", menu)
        act_cancel.triggered.connect(self.closed.emit)
        for a in (act_save, act_save_new):
            menu.addAction(a)
        menu.addSeparator()
        for a in (act_preview, act_save_print, act_pdf):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_cancel)

    def _show_actions_menu(self, pos):
        menu = QMenu(self)
        self._populate_document_actions(menu)
        menu.exec(self.mapToGlobal(pos))

    @staticmethod
    def _dock_panel(panel: EdgeTriggeredPanel):
        """EdgeTriggeredPanel'i overlay yerine layout-docklu (pinned, açık) yapar."""
        panel.is_pinned = True
        panel.pin_btn.setText("📍 Serbest")
        panel.is_open = True
        panel.panel_frame.show()
        panel.update_trigger_strip_icon()

    # ---- Header ----
    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("DocHeaderBar")
        # TransactionDocumentDialog'daki (eski) lacivert->siyah gradyanlı üst bar ile
        # aynı kurumsal görünüm — düz soluk gri yerine.
        # qt_material genel teması QComboBox/QLineEdit için sabit "height: 36px"
        # (yoğunluk-ölçekli) tanımlıyor. min-height/max-height farklı bir kural
        # olduğundan bu sabiti gerçek anlamda ezmiyor — bu yüzden her alan burada
        # AÇIKÇA "height" ile verilir (aksi halde alanlar birbirinden farklı,
        # global kuralın belirlediği yükseklikte kalır).
        # Not: QSS content-box modelinde "height" iç içerik yüksekliğidir, dikey
        # padding + kenarlık ÜSTÜNE eklenir (toplam ~ height + 2*padding + border).
        # 22 + 2*2 + 2 ≈ 28px — sekme çubuğu (28px) ve alt butonlarla aynı aile.
        hdr_h = 22
        bar.setStyleSheet(f"""
            QFrame#DocHeaderBar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                           stop:0 #1e3a8a, stop:1 #0f172a);
                border-radius: 6px;
            }}
            QFrame#DocHeaderBar QLineEdit {{
                background: #ffffff;
                color: #0f172a;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 8px;
                border-radius: 4px;
                height: {hdr_h}px;
            }}
            QFrame#DocHeaderBar QLabel {{
                color: #93c5fd;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(10, 4, 10, 4)
        lyt.setSpacing(8)

        # Tüm "bilgi rozeti" alanları (belge kodu, belge türü) aynı dolgu-mavi
        # kart görünümünü paylaşır — Durum rozeti de aynı yükseklik/şekli kullanır,
        # sadece duruma göre rengi değişir (bilgi taşıdığı için kasıtlı istisna).
        # Metin ile çerçeve arasında nefes payı olsun diye dikey padding de var
        # (height tek başına verilince içerik kenara yapışıyordu).
        chip_style = (
            "background:#3b82f6;color:#ffffff;font-weight:800;font-size:11px;"
            f"padding:2px 10px;border-radius:4px;height:{hdr_h}px;"
        )

        badge = QLabel("📄 [isl.doc.001]")
        badge.setStyleSheet(chip_style)
        lyt.addWidget(badge)

        lyt.addWidget(QLabel("🧾"))
        self.cmb_doc_type = QComboBox()
        self.cmb_doc_type.addItems(DOCUMENT_TYPES)
        self.cmb_doc_type.setCurrentIndex(min(self.initial_type_idx, len(DOCUMENT_TYPES) - 1))
        self.cmb_doc_type.setMinimumWidth(240)
        self.cmb_doc_type.setStyleSheet(f"QComboBox{{{chip_style}}}")
        self.cmb_doc_type.currentTextChanged.connect(lambda _t: self._refresh_summary())
        lyt.addWidget(self.cmb_doc_type)

        lyt.addWidget(QLabel("🔖 Belge No:"))
        self.txt_doc_no = QLineEdit()
        self.txt_doc_no.setPlaceholderText("(kayıtta atanır)")
        self.txt_doc_no.setMaximumWidth(160)
        lyt.addWidget(self.txt_doc_no)

        lyt.addStretch()
        lyt.addWidget(QLabel("🚦 Durum:"))
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["🔵 Taslak", "✅ Kabul Edildi", "❌ Reddedildi"])
        self.cmb_status.setMinimumWidth(140)
        self.cmb_status.currentTextChanged.connect(self._on_status_changed)
        lyt.addWidget(self.cmb_status)
        self._on_status_changed(self.cmb_status.currentText())
        return bar

    _HDR_CHIP_H = 22

    # Teklif durumu rozeti: seçime göre renklenir (Taslak mavi, Kabul Edildi yeşil, Reddedildi kırmızı).
    _STATUS_COLORS = {
        "Taslak": ("#dbeafe", "#1d4ed8"),
        "Kabul Edildi": ("#dcfce7", "#15803d"),
        "Reddedildi": ("#fee2e2", "#b91c1c"),
    }

    def status_label(self) -> str:
        """Emoji önekini ayıklanmış hâliyle güncel Teklif Durumu metnini döner."""
        text = self.cmb_status.currentText()
        return text.split(" ", 1)[1] if " " in text else text

    def set_status_label(self, label: str):
        """Durum kombosunu, verilen düz metne (emoji'siz) en yakın seçeneğe ayarlar."""
        for i in range(self.cmb_status.count()):
            if self.cmb_status.itemText(i).endswith(label):
                self.cmb_status.setCurrentIndex(i)
                return

    def _on_status_changed(self, text: str):
        label = text.split(" ", 1)[1] if " " in text else text
        bg, fg = self._STATUS_COLORS.get(label, ("#dbeafe", "#1d4ed8"))
        self.cmb_status.setStyleSheet(
            f"QComboBox{{background:{bg};color:{fg};font-weight:700;"
            f"padding:2px 10px;border-radius:{self._HDR_CHIP_H // 2}px;font-size:11px;"
            f"height:{self._HDR_CHIP_H}px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}",
        )
        self._refresh_summary()

    def _build_top_form(self) -> QWidget:
        w = QWidget()
        top = QHBoxLayout(w)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        self.cari = CariKunyeWidget(db_session=self.db)
        self.belge_vade = BelgeVadeWidget(db_session=self.db)
        self.finans = HareketFinansWidget(db_session=self.db)
        top.addWidget(self.cari, 4)
        top.addWidget(self.belge_vade, 3)
        top.addWidget(self.finans, 3)
        return w

    # ---- Alt panel (sekmeler + notlar + toplam) ----
    def _build_bottom_area(self) -> QWidget:
        w = QWidget()
        lyt = QHBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(6)

        self.bottom_tabs = QTabWidget()
        # qt_material'da QTabBar::tab yüksekliği yoğunluk-ölçekli hesaplanıp
        # burada beklenenden büyük çıkıyordu; header'daki bilgi rozetleriyle
        # (hdr_h=26) aynı görünsün diye açıkça sabitliyoruz.
        self.bottom_tabs.setStyleSheet(
            "QTabBar::tab{height:26px;padding:0 12px;font-size:10px;font-weight:700;}"
            "QTabWidget::pane{border:1px solid #e2e8f0;}",
        )
        self.expenses = DocumentExpensesGrid(profile_key="belge_masraflar")
        self.bottom_tabs.addTab(self.expenses, "A  İndirim & Masraflar")
        for name in ("B  Seri / Lot", "C  Varyant", "D  Paketler"):
            ph = QLabel(f"  {name} — sonraki adımda widget'lanacak")
            ph.setStyleSheet("color:#94a3b8;padding:16px;")
            self.bottom_tabs.addTab(ph, name)
        # AlignTop: QHBoxLayout hücreleri varsayılan olarak dikey ortalar; satır
        # bu üç widget'ın en uzununa göre yükseklik alınca kısa kalanlar (masraflar,
        # notlar, toplamlar) ortada değil, kendi alanının en üstünde durmalı.
        lyt.addWidget(self.bottom_tabs, 4, Qt.AlignmentFlag.AlignTop)

        # Notlar iki kısa metin kutusundan ibaret; geniş ekranda büyüyüp masraf
        # gridini ve Toplam panelini ezmesin diye üst sınır veriyoruz. Fazla
        # yatay alan masraf/indirim gridine (stretch=4) gitsin.
        self.notlar = BelgeNotlariWidget()
        self.notlar.setMaximumWidth(560)
        lyt.addWidget(self.notlar, 2, Qt.AlignmentFlag.AlignTop)

        # Sabit genişlik: pencere daraltıldığında satırlardaki tutar/döviz
        # etiketleri birbirinin üzerine binmesin ve Toplam paneli belirli bir
        # enin altına düşmesin diye (min == max == 264).
        self.toplam = ToplamWidget()
        self.toplam.setFixedWidth(264)
        lyt.addWidget(self.toplam, 0, Qt.AlignmentFlag.AlignTop)

        # Üç bölümün yüksekliğini Toplam (ödeme) widget'ıyla eşitle: masraf gridi
        # tek satıra sıkışmasın, Notlar metin kutuları da aynı yüksekliği doldursun.
        alt_h = self.toplam.minimumHeight()
        self.toplam.setFixedHeight(alt_h)
        self.bottom_tabs.setFixedHeight(alt_h)
        self.notlar.setFixedHeight(alt_h)
        return w

    # ---- Sol panel ----
    def _build_left_panel(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet("background:transparent;border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(4, 4, 4, 4)
        lyt.setSpacing(6)

        # EVRAK İŞLEMLERİ  (Kaydet varyantları alt bardaki "Kaydet ▾" menüsünde)
        sec1 = CollapsibleSection("EVRAK İŞLEMLERİ", is_expanded=True)
        b_import = _btn("📥 Kalemleri Aktar")
        b_import.clicked.connect(lambda: self._stub("Kalemleri Aktar"))
        b_efatura = _btn("⚡ E-Fatura Gönder", "#7c3aed", "#ffffff", "#6d28d9", "#6d28d9")
        b_efatura.clicked.connect(lambda: self._stub("E-Fatura Gönder"))
        b_cancel = _btn("🚪 Vazgeç (Esc)", "#fee2e2", "#991b1b", "#fca5a5", "#fca5a5")
        b_cancel.clicked.connect(self.closed.emit)
        for b in (b_import, b_efatura, b_cancel):
            sec1.add_widget(b)
        lyt.addWidget(sec1)

        # SATIR İŞLEMLERİ
        sec2 = CollapsibleSection("SATIR İŞLEMLERİ", is_expanded=True)
        b_row_add = _btn("➕ Satır Ekle (Alt+Enter)")
        b_row_add.clicked.connect(lambda: self.lines.add_row(focus=True))
        b_row_del = _btn("🗑️ Seçilenleri Sil (Ctrl+Del)", "#fee2e2", "#991b1b", "#fca5a5", "#fca5a5")
        b_row_del.clicked.connect(self.lines.remove_checked_rows)
        b_row_up = _btn("⬆️ Satırı Yukarı (Alt+↑)")
        b_row_up.clicked.connect(self.lines.move_selected_up)
        b_row_down = _btn("⬇️ Satırı Aşağı (Alt+↓)")
        b_row_down.clicked.connect(self.lines.move_selected_down)
        for b in (b_row_add, b_row_del, b_row_up, b_row_down):
            sec2.add_widget(b)
        lyt.addWidget(sec2)

        # GÖRÜNÜM & SÜTUNLAR — kalem gridinin sütun görünüm profili
        sec3 = CollapsibleSection("GÖRÜNÜM & SÜTUNLAR", is_expanded=True)
        sec3.add_widget(QLabel("Aktif Profil:"))
        self.cmb_profile = QComboBox()
        self.cmb_profile.currentTextChanged.connect(self._on_column_profile_changed)
        sec3.add_widget(self.cmb_profile)
        b_prof_save = _btn("💾 Profili Kaydet")
        b_prof_save.clicked.connect(self._on_save_column_profile)
        b_cols = _btn("⚙️ Sütunlar")
        b_cols.clicked.connect(
            lambda: self.lines.grid.open_column_manager_dialog(),
        )
        sec3.add_widget(b_prof_save)
        sec3.add_widget(b_cols)
        lyt.addWidget(sec3)
        self._reload_column_profiles()

        self._left_sections_layout = lyt
        b_add_widget = _btn("➕ Widget Ekle…", "#eef2ff", "#4338ca", "#c7d2fe", "#e0e7ff")
        b_add_widget.clicked.connect(lambda: self._open_widget_catalog("left"))
        lyt.addWidget(b_add_widget)
        lyt.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        scroll.setWidget(frame)
        return scroll

    # ---- Sağ panel ----
    def _build_right_panel(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet("background:transparent;border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(4, 4, 4, 4)
        lyt.setSpacing(6)

        # YAZDIRMA & AKTARIM
        sec_print = CollapsibleSection("YAZDIRMA & AKTARIM", is_expanded=True)

        # Baskı formu seçici — görsel tasarımcı tamamlanana kadar kullanıcı
        # hazır şablonlar arasından (varsayılan A4 dışında) seçim yapabilir.
        sec_print.add_widget(QLabel("Baskı Formu:"))
        self._tpl_selector = QComboBox()
        self._populate_template_selector()
        sec_print.add_widget(self._tpl_selector)

        # Baskı işlemleri cyan, tasarım mor, paylaşım mor, WhatsApp yeşil — geri kalanı nötr.
        _print_colors = {
            "📄 Önizle-Yazdır (F9)": ("#0284c7", "#ffffff", "#0369a1", "#0369a1"),
            "📝 Baskı Formunu Düzenle": ("#7c3aed", "#ffffff", "#6d28d9", "#6d28d9"),
            "📤 Gönder / Paylaş": ("#7c3aed", "#ffffff", "#6d28d9", "#6d28d9"),
            "🟢 WhatsApp": ("#16a34a", "#ffffff", "#15803d", "#15803d"),
        }
        _print_actions = {
            "📄 Önizle-Yazdır (F9)": self._on_preview,
            "📝 Baskı Formunu Düzenle": self._open_form_designer,
            "📄 PDF'e Aktar": self._on_export_pdf,
            "📊 Excel'e Aktar": self._on_export_excel,
            "📤 Gönder / Paylaş": self._on_share,
            "🟢 WhatsApp": self._on_whatsapp,
            "✉️ E-Posta Gönder": self._on_email,
            "🔗 Linki Kopyala": self._on_copy_link,
        }
        for label in ("📄 Önizle-Yazdır (F9)", "📄 PDF'e Aktar", "📝 Baskı Formunu Düzenle",
                      "📊 Excel'e Aktar", "📤 Gönder / Paylaş",
                      "🟢 WhatsApp", "✉️ E-Posta Gönder", "🔗 Linki Kopyala"):
            b = _btn(label, *_print_colors.get(label, ("#ffffff", "#1e293b", "#cbd5e1", "#f1f5f9")))
            act = _print_actions.get(label)
            if act:
                b.clicked.connect(lambda _c=False, a=act: a())
            else:
                b.clicked.connect(lambda _c=False, ll=label: self._stub(ll))
            sec_print.add_widget(b)
        lyt.addWidget(sec_print)

        # CANLI BASKI ÖNİZLEME — seçili şablon + ekrandaki güncel veri.
        # Varsayılan kapalı: açılınca ilk kez çizilir, açıkken form değiştikçe
        # (kalem / cari / durum / not) ~%400 ms gecikmeli tazelenir.
        from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

        self.sec_mini_preview = CollapsibleSection(
            "CANLI BASKI ÖNİZLEME", is_expanded=False,
        )
        self.mini_preview = ReportPreviewWidget(compact=True)
        self.mini_preview.setMinimumHeight(340)
        b_expand = _btn("⤢", "#0284c7", "#ffffff", "#0369a1", "#0369a1")
        b_expand.setToolTip("Tam ekran önizleme ve yazdırma")
        b_expand.setFixedWidth(30)
        b_expand.clicked.connect(self._on_preview)
        self.mini_preview.add_toolbar_widget(b_expand)
        self.sec_mini_preview.add_widget(self.mini_preview)
        self.sec_mini_preview.toggled.connect(self._on_mini_preview_toggled)
        lyt.addWidget(self.sec_mini_preview)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(400)
        self._preview_timer.timeout.connect(self._refresh_mini_preview)
        self._tpl_selector.currentIndexChanged.connect(
            lambda _i: self._schedule_preview_refresh(),
        )

        # EVRAK ÖZETİ
        self.sec_summary = CollapsibleSection("EVRAK ÖZETİ", is_expanded=True)
        self.lbl_sum_cari = QLabel("👤 —")
        self.lbl_sum_total = QLabel("💰 0,00 ₺")
        self.lbl_sum_status = QLabel("Durum: Taslak")
        for lab in (self.lbl_sum_cari, self.lbl_sum_total, self.lbl_sum_status):
            lab.setStyleSheet("font-size:11px;color:#334155;padding:2px 0;")
            lab.setWordWrap(True)
            self.sec_summary.add_widget(lab)
        lyt.addWidget(self.sec_summary)

        # HIZLI İŞLEMLER
        sec_quick = CollapsibleSection("HIZLI İŞLEMLER", is_expanded=True)
        _quick_colors = {
            "🔄 Siparişe Dönüştür": ("#0369a1", "#ffffff", "#075985", "#075985"),
            "⚡ E-Fatura Gönder": ("#7c3aed", "#ffffff", "#6d28d9", "#6d28d9"),
        }
        for label in ("🔄 Siparişe Dönüştür", "📋 Belgeyi Kopyala", "⚡ E-Fatura Gönder"):
            b = _btn(label, *_quick_colors.get(label, ("#ffffff", "#1e293b", "#cbd5e1", "#f1f5f9")))
            b.clicked.connect(lambda _c=False, ll=label: self._stub(ll))
            sec_quick.add_widget(b)
        lyt.addWidget(sec_quick)

        # KDV DAĞILIMI
        self.sec_kdv = CollapsibleSection("KDV DAĞILIMI", is_expanded=True)
        self.kdv_grid = FilterableTableView(headers_dict=KDV_HEADERS, profile_key="belge_kdv_dagilim")
        self.kdv_grid.setMinimumHeight(130)
        # Dar sidebar'da salt-okunur/türetilmiş bir özet — kolon filtre satırına gerek yok.
        self.kdv_grid.filter_bar_container.setVisible(False)
        self.kdv_model = QStandardItemModel(self)
        self.kdv_model.setHorizontalHeaderLabels([KDV_HEADERS[c][0] for c in sorted(KDV_HEADERS)])
        self.kdv_grid.table_view.setModel(self.kdv_model)
        self.sec_kdv.add_widget(self.kdv_grid)
        lyt.addWidget(self.sec_kdv)

        # ÖZEL KODLAR & EK ALANLAR
        self.sec_ozel = CollapsibleSection("ÖZEL KODLAR & EK ALANLAR", is_expanded=False)
        form_w = QWidget()
        form = QFormLayout(form_w)
        form.setContentsMargins(2, 2, 2, 2)
        form.setSpacing(4)
        for key, label in OZEL_KOD_ALANLARI:
            le = QLineEdit()
            le.setStyleSheet("font-size:11px;padding:3px 6px;")
            self._ozel_kod_inputs[key] = le
            form.addRow(QLabel(label), le)
        self.sec_ozel.add_widget(form_w)
        lyt.addWidget(self.sec_ozel)

        self._right_sections_layout = lyt
        b_add_widget = _btn("➕ Widget Ekle…", "#eef2ff", "#4338ca", "#c7d2fe", "#e0e7ff")
        b_add_widget.clicked.connect(lambda: self._open_widget_catalog("right"))
        lyt.addWidget(b_add_widget)
        lyt.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        scroll.setWidget(frame)
        return scroll

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(6)

        self._lbl_footer_status = QLabel("")
        self._lbl_footer_status.setStyleSheet(
            "color:#16a34a;font-size:11px;font-weight:700;padding-left:4px;",
        )
        lyt.addWidget(self._lbl_footer_status)
        lyt.addStretch()

        # qt_material "QPushButton{height:36px}" global kuralını gerçekten ezmek için
        # burada da açıkça height veriyoruz (sadece padding küçültmek yetmiyor).
        _primary = (
            "QPushButton{{background:{bg};color:white;border:1px solid {bg};font-weight:700;"
            "font-size:11px;padding:0 14px;height:28px;border-radius:6px;}}"
            "QPushButton:hover{{background:{hv};}}"
        )
        _neutral = (
            "QPushButton{background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;font-size:11px;"
            "padding:0 14px;height:28px;border-radius:6px;}QPushButton:hover{background:#e2e8f0;}"
        )

        self.btn_cancel = QPushButton("❌ Vazgeç (Esc)")
        self.btn_cancel.setStyleSheet(_neutral)
        self.btn_cancel.clicked.connect(self.closed.emit)

        self.btn_preview = QPushButton("👁️ Önizle")
        self.btn_preview.setStyleSheet(_primary.format(bg="#0ea5e9", hv="#0284c7"))
        self.btn_preview.setToolTip("Kaydetmeden, ekrandaki veriyle baskı önizlemesi")
        self.btn_preview.clicked.connect(self._on_preview)

        # Bölünmüş buton (QToolButton): sol taraf = birincil eylem (Kaydet ve
        # Kapat / listeye dön), ok = varyantlar menüsü. Böylece buton sayısı
        # artmaz ama "listeye dön" tıklamayla erişilebilir olur.
        from PyQt6.QtWidgets import QToolButton
        self.btn_save = QToolButton()
        self.btn_save.setText("💾 Kaydet ve Kapat")
        self.btn_save.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_save.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_save.setToolTip("Kaydet ve teklif listesine dön (F2)")
        self.btn_save.setStyleSheet(
            "QToolButton{background:#2563eb;color:white;border:1px solid #1d4ed8;"
            "font-weight:700;font-size:11px;padding:0 10px 0 14px;height:28px;border-radius:6px;}"
            "QToolButton:hover{background:#1d4ed8;}"
            "QToolButton::menu-button{background:#1d4ed8;border:none;width:20px;"
            "border-top-right-radius:6px;border-bottom-right-radius:6px;}"
            "QToolButton::menu-button:hover{background:#1e40af;}",
        )
        self.btn_save.clicked.connect(self._on_save_close)

        self._save_menu = QMenu(self.btn_save)
        act_close = self._save_menu.addAction("💾 Kaydet ve Kapat (F2)")
        act_close.triggered.connect(self._on_save_close)
        act_cont = self._save_menu.addAction("💾 Kaydet ve Devam Et (Ctrl+S)")
        act_cont.triggered.connect(self._on_save)
        act_new = self._save_menu.addAction("➕ Kaydet ve Yeni (Ctrl+Enter)")
        act_new.triggered.connect(self._on_save_new)
        self._save_menu.addSeparator()
        act_print = self._save_menu.addAction("🖨️ Kaydet ve Yazdır (F9)")
        act_print.triggered.connect(self._on_save_print)
        self.btn_save.setMenu(self._save_menu)

        for b in (self.btn_cancel, self.btn_preview, self.btn_save):
            lyt.addWidget(b)

        # Yetki: yalnız görüntüleme yetkisi olan kullanıcı kaydedemez
        try:
            from src.desktop.security.gate import gate
            gate(self.btn_save, "teklif.edit")
            gate(self.btn_preview, "teklif.print")
        except Exception:  # noqa: BLE001
            pass
        return bar

    # ------------------------------------------------------------------
    def _open_widget_catalog(self, side: str):
        if not WIDGET_REGISTRY or create_widget_by_id is None:
            QMessageBox.information(self, "Katalog", "Widget kataloğu bulunamadı.")
            return
        dlg = WidgetCatalogDialog(side, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_id:
            return
        try:
            w = create_widget_by_id(dlg.selected_id, db_session=self.db)
        except TypeError:
            w = create_widget_by_id(dlg.selected_id)
        if w is None:
            return
        meta = WIDGET_REGISTRY.get(dlg.selected_id, {})
        sec = CollapsibleSection(meta.get("name", dlg.selected_id).upper(), is_expanded=True)
        sec.add_widget(w)
        layout = self._left_sections_layout if side == "left" else self._right_sections_layout
        layout.insertWidget(layout.count() - 2, sec)  # "+ Widget Ekle" ve stretch'ten önce
        (self._extra_left if side == "left" else self._extra_right).append(w)

    def _stub(self, name: str):
        logger.info("Aksiyon (henüz stub): %s", name)
        QMessageBox.information(self, name, f"'{name}' — sonraki adımda bağlanacak.")

    # ------------------------------------------------------------------
    def _load_products(self):
        if not self.db:
            return
        try:
            from sqlalchemy import select

            from src.core.models import Product
            rows = self.db.scalars(
                select(Product).where(Product.is_deleted == False),  # noqa: E712
            ).all()
            self.lines.set_products([
                {
                    "code": p.sku or "",
                    "barcode": p.barcode or "",
                    "name": p.name or "",
                    "unit": getattr(p, "unit", "Adet") or "Adet",
                    "price": float(p.base_price or p.price or 0),
                }
                for p in rows
            ])
        except Exception as e:
            logger.warning("Ürün kataloğu yüklenemedi: %s", e)

    def _wire(self):
        self.lines.totals_changed.connect(self._on_lines_totals)
        self.expenses.expenses_changed.connect(self._on_expenses_changed)
        self.finans.doviz_changed.connect(self._on_doviz_changed)
        self.cari.data_changed.connect(self._refresh_summary)
        self.cari.customer_selected.connect(lambda _d: self._refresh_summary())
        self.cari.balance_requested.connect(
            lambda code: logger.info("Bakiye istendi: %s", code),
        )
        self.notlar.notes_changed.connect(self._schedule_preview_refresh)

    # ------------------------------------------------------------------
    def _on_lines_totals(self, t: dict):
        self._last_line_totals = t
        self.expenses.set_base_amount(t.get("ara_toplam", 0.0))
        self._refresh_totals()

    def _on_expenses_changed(self, e: dict):
        self._expenses = e
        self._refresh_totals()

    def _on_doviz_changed(self, _kod: str, kur: float):
        self.lines.set_currency(self.finans.get_currency_symbol(), kur)

    def _refresh_totals(self):
        t = self._last_line_totals
        ekstra_indirim = self._expenses.get("indirim", 0.0)
        masraf = self._expenses.get("masraf", 0.0)
        ekstra_kdv = self._expenses.get("kdv", 0.0)
        matrah = t.get("kdv_matrahi", 0.0) - ekstra_indirim + masraf
        kdv = t.get("kdv_toplam", 0.0) + ekstra_kdv
        self.toplam.update_totals(
            ara_toplam=t.get("ara_toplam", 0.0),
            iskonto=t.get("iskonto", 0.0) + ekstra_indirim,
            masraflar=masraf,
            kdv_matrahi=matrah,
            kdv_toplam=kdv,
            genel_toplam=matrah + kdv,
            doviz_sembol=t.get("doviz_sembol", "₺"),
            doviz_kur=t.get("doviz_kur", 1.0),
        )
        self.expenses.set_grand_amount(matrah + kdv)
        self._refresh_kdv_table()
        self._refresh_summary()

    def _refresh_kdv_table(self):
        """Kalem KDV dağılımıyla masraf/indirim satırlarının KDV etkisini birleştirir."""
        merged: dict[float, dict[str, float]] = {}
        for src in (
            self._last_line_totals.get("kdv_dagilim", {}),
            self._expenses.get("kdv_dagilim", {}),
        ):
            for oran, d in src.items():
                m = merged.setdefault(float(oran), {"matrah": 0.0, "kdv": 0.0})
                m["matrah"] += d.get("matrah", 0.0)
                m["kdv"] += d.get("kdv", 0.0)
        self.kdv_model.removeRows(0, self.kdv_model.rowCount())
        for oran in sorted(merged):
            d = merged[oran]
            self.kdv_model.appendRow([
                QStandardItem(f"%{oran:g}"),
                QStandardItem(fmt_num(d["matrah"])),
                QStandardItem(fmt_num(d["kdv"])),
            ])

    def _refresh_summary(self):
        if not hasattr(self, "lbl_sum_cari"):
            return
        cari = self.cari.get_data().get("name", "") or "—"
        self.lbl_sum_cari.setText(f"👤 {cari}")
        self.lbl_sum_total.setText(f"💰 {fmt_num(self.toplam.get_grand_total())} ₺")
        self.lbl_sum_status.setText(f"Durum: {self.status_label()}")
        self._schedule_preview_refresh()

    # ------------------------------------------------------------------
    def _collect_payload(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.cmb_doc_type.currentText(),
            "doc_no": self.txt_doc_no.text().strip(),
            "cari": self.cari.get_data(),
            "belge_vade": self.belge_vade.get_data(),
            "finans": self.finans.get_data(),
            "lines": self.lines.get_lines(),
            "expenses": self.expenses.get_rows(),
            "toplam": self.toplam.get_data(),
            "notlar": self.notlar.get_notes(),
            "ozel_kodlar": {k: le.text().strip() for k, le in self._ozel_kod_inputs.items()},
            "status": self.status_label(),
        }

    def _load_document(self):
        payload = self.service.load_payload(self.doc_id)
        if not payload:
            return
        idx = self.cmb_doc_type.findText(payload.get("doc_type", ""))
        if idx >= 0:
            self.cmb_doc_type.setCurrentIndex(idx)
        self.txt_doc_no.setText(payload.get("doc_no", ""))
        try:
            self.cari.set_data(payload.get("cari", {}))
            self.belge_vade.set_data(payload.get("belge_vade", {}))
            self.finans.set_data(payload.get("finans", {}))
        except Exception as e:
            logger.warning("Widget doldurma hatası: %s", e)
        self.lines.load_lines(payload.get("lines", []))
        self.expenses.load_rows(payload.get("expenses", []))
        n1, n2 = (list(payload.get("notlar", ("", ""))) + ["", ""])[:2]
        self.notlar.set_notes(n1, n2)
        self.set_status_label(payload.get("status", "Taslak"))
        self._refresh_summary()

    def _persist(self, *, notify_empty: bool = True) -> bool:
        # Kayıt öncesi boş kalem satırlarını temizle (kullanıcıyı uyararak).
        n_empty = self.lines.empty_row_count()
        n_filled = self.lines.model.rowCount() - n_empty
        if n_empty:
            if notify_empty:
                QMessageBox.information(
                    self, "Boş Satırlar",
                    f"{n_empty} adet boş kalem satırı kayıt sırasında silinecek.",
                )
            self.lines.remove_empty_rows()

        # Hiç dolu kalem yoksa belge kaydedilemez.
        if n_filled <= 0:
            QMessageBox.warning(
                self, "Boş Belge",
                "Boş belge kaydedilemez.\nEn az bir kalem (stok kodu veya açıklama) girin.",
            )
            return False

        # Cari seçilmemişse uyar (kayda izin verilir).
        cari_d = self.cari.get_data()
        if not (cari_d.get("name") or (cari_d.get("customer") or {}).get("id")):
            if QMessageBox.question(
                self, "Cari Seçilmedi",
                "Bir cari seçilmedi. Belge cari olmadan kaydedilecektir.\n\nDevam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                return False

        payload = self._collect_payload()
        if not self.db:
            logger.info("DB yok — payload: %s satır", len(payload["lines"]))
            self.document_saved.emit(payload)
            return True
        result = self.service.save_payload(payload, doc_id=self.doc_id)
        if not result.success:
            QMessageBox.critical(self, "Hata", result.error or "Kayıt başarısız.")
            return False
        self.doc_id = result.quotation_id
        self.txt_doc_no.setText(result.quotation_number or "")
        payload["doc_id"] = result.quotation_id
        payload["quotation_number"] = result.quotation_number
        self.document_saved.emit(payload)
        return True

    def _confirm_save_before_output(self, title: str) -> bool:
        """
        Yazdırma / PDF öncesi: belge kaydedilmemişse veya boş satır varsa
        kullanıcıyı tek diyalogda uyarır. Devam ederse True.
        """
        notes: list[str] = []
        if self.doc_id is None:
            notes.append("• Belge henüz kaydedilmedi; devam edilirse otomatik kaydedilecek.")
        n_empty = self.lines.empty_row_count()
        if n_empty:
            notes.append(f"• {n_empty} adet boş kalem satırı kayıtta silinecek.")
        if not notes:
            return True
        return QMessageBox.question(
            self, title,
            "\n".join(notes) + "\n\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes

    def _on_save_close(self):
        """Birincil kaydet: kaydeder ve listeye döner (ekranı kapatır)."""
        if self._persist():
            self.closed.emit()

    def _on_save(self):
        """Kaydet ve ekranda kal (düzenlemeye devam)."""
        if self._persist():
            no = self.txt_doc_no.text().strip()
            self._flash_status(f"✓ Kaydedildi{(' · ' + no) if no else ''}")

    def _flash_status(self, msg: str):
        """Alt barda kısa bir onay mesajı gösterir (modal diyalog yerine)."""
        if not hasattr(self, "_lbl_footer_status"):
            return
        self._lbl_footer_status.setText(msg)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2500, lambda: self._lbl_footer_status.setText(""))

    def _on_save_new(self):
        if self._persist():
            self.doc_id = None
            self.txt_doc_no.clear()
            self.cari.clear()
            self.lines.clear_rows()
            self.lines.add_row()
            self.expenses.clear_rows()
            self.expenses.add_row()
            self.notlar.set_notes("", "")
            self.lines._emit_totals()
            self._flash_status("✓ Kaydedildi · yeni belge")

    def _on_save_print(self):
        """Önce belgeyi kaydeder (gerekirse uyararak), sonra baskı önizlemesini açar."""
        if not self._confirm_save_before_output("Kaydet ve Yazdır"):
            return
        if self._persist(notify_empty=False):
            self._open_print_preview()

    def _on_preview(self):
        """Kaydetmeden, ekrandaki canlı veriyle baskı önizlemesini açar."""
        self._open_print_preview()

    def _on_export_pdf(self):
        """Belgeyi (gerekirse kaydedip) doğrudan PDF dosyasına aktarır."""
        from PyQt6.QtWidgets import QFileDialog

        if not self._confirm_save_before_output("PDF'e Aktar"):
            return
        if (self.doc_id is None or self.lines.empty_row_count()) and not self._persist(
            notify_empty=False,
        ):
            return
        default_name = f"{self.txt_doc_no.text().strip() or 'belge'}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", default_name, "PDF (*.pdf)")
        if not path:
            return
        try:
            from src.desktop.designer.services.teklif_print_service import (
                TeklifPrintService,
            )
            tpl_path = self._tpl_selector.currentData() if self._tpl_selector.count() else None
            service = TeklifPrintService(db_session=self.db, template_path=tpl_path)
            if service.export_pdf_with_data(self._build_print_data(), path):
                QMessageBox.information(self, "PDF", f"PDF kaydedildi:\n{path}")
            else:
                QMessageBox.warning(self, "PDF", "PDF oluşturulamadı.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("PDF dışa aktarma hatası")
            QMessageBox.critical(self, "PDF Hatası", str(exc))

    # ---- Görünüm / sütun profili -------------------------------------
    def _reload_column_profiles(self):
        """Kalem gridinin kayıtlı sütun profillerini komboya doldurur."""
        if not hasattr(self, "cmb_profile"):
            return
        self.cmb_profile.blockSignals(True)
        self.cmb_profile.clear()
        try:
            names = self.lines.grid.load_column_profile_list()
        except Exception:  # noqa: BLE001
            names = []
        self.cmb_profile.addItems(names or ["Varsayılan"])
        self.cmb_profile.blockSignals(False)

    def _on_column_profile_changed(self, name: str):
        if not name:
            return
        try:
            self.lines.grid.load_profile(name)
        except Exception:  # noqa: BLE001
            logger.exception("Sütun profili yüklenemedi: %s", name)

    def _on_save_column_profile(self):
        from PyQt6.QtWidgets import QInputDialog
        cur = self.cmb_profile.currentText() if hasattr(self, "cmb_profile") else ""
        name, ok = QInputDialog.getText(
            self, "Profili Kaydet", "Profil adı:", text=cur or "Varsayılan",
        )
        if not ok or not name.strip():
            return
        try:
            self.lines.grid.save_column_profile(name.strip())
            self._reload_column_profiles()
            idx = self.cmb_profile.findText(name.strip())
            if idx >= 0:
                self.cmb_profile.setCurrentIndex(idx)
            QMessageBox.information(self, "Profil", f"'{name.strip()}' kaydedildi.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Sütun profili kaydedilemedi")
            QMessageBox.critical(self, "Profil Hatası", str(exc))

    # ---- Aktarım / Paylaşım (Excel · e-Posta · WhatsApp · Link) --------
    def _report_service(self):
        from src.desktop.reports.teklif_report_service import TeklifReportService
        return TeklifReportService(db_session=self.db, company_id=self.company_id)

    def _require_saved(self, action: str) -> int | None:
        """
        Kayıtlı belge isteyen aksiyonlar için: belge kaydedilmemişse (veya boş
        satır varsa) kullanıcıyı uyarıp kaydeder. Kayıtlı belge id'sini döndürür.
        """
        if self.doc_id is not None and self.lines.empty_row_count() == 0:
            return self.doc_id
        if not self._confirm_save_before_output(action):
            return None
        if not self._persist(notify_empty=False):
            return None
        return self.doc_id

    def _on_export_excel(self):
        tid = self._require_saved("Excel'e Aktar")
        if tid is None:
            return
        try:
            path = self._report_service().export_excel(tid)
            QMessageBox.information(self, "Excel", f"Excel hazırlandı:\n{path}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Excel aktarımı hatası")
            QMessageBox.critical(self, "Excel Hatası", str(exc))

    def _on_email(self):
        tid = self._require_saved("E-Posta Gönder")
        if tid is None:
            return
        try:
            ok, info = self._report_service().send_email(tid)
            fn = QMessageBox.information if ok else QMessageBox.warning
            fn(self, "E-Posta", info or ("Gönderildi." if ok else "Gönderilemedi."))
        except Exception as exc:  # noqa: BLE001
            logger.exception("E-posta hatası")
            QMessageBox.critical(self, "E-Posta Hatası", str(exc))

    def _on_whatsapp(self):
        tid = self._require_saved("WhatsApp ile Paylaş")
        if tid is None:
            return
        try:
            if not self._report_service().share_whatsapp(tid):
                QMessageBox.warning(self, "WhatsApp", "WhatsApp paylaşımı açılamadı.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("WhatsApp hatası")
            QMessageBox.critical(self, "WhatsApp Hatası", str(exc))

    def _on_copy_link(self):
        tid = self._require_saved("Linki Kopyala")
        if tid is None:
            return
        try:
            url = self._report_service().copy_share_link(tid)
            QMessageBox.information(self, "Bağlantı Kopyalandı", url)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Link kopyalama hatası")
            QMessageBox.critical(self, "Bağlantı Hatası", str(exc))

    def _on_share(self):
        """Gönder / Paylaş — paylaşım bağlantısı + hızlı seçenekler."""
        tid = self._require_saved("Gönder / Paylaş")
        if tid is None:
            return
        try:
            svc = self._report_service()
            d = svc.get_share_data(tid)
            url = d.get("public_url", "")
            box = QMessageBox(self)
            box.setWindowTitle("Gönder / Paylaş")
            box.setText(f"Paylaşım bağlantısı:\n{url}")
            b_copy = box.addButton("🔗 Kopyala", QMessageBox.ButtonRole.AcceptRole)
            b_wa = box.addButton("🟢 WhatsApp", QMessageBox.ButtonRole.AcceptRole)
            b_mail = box.addButton("✉️ E-Posta", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Kapat", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            c = box.clickedButton()
            if c is b_copy:
                svc.copy_share_link(tid)
            elif c is b_wa:
                svc.share_whatsapp(tid)
            elif c is b_mail:
                self._on_email()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Paylaşım hatası")
            QMessageBox.critical(self, "Paylaşım Hatası", str(exc))

    def _open_form_designer(self):
        """Seçili baskı formunu görsel tasarımcıda açar (ayrı, modeless pencere)."""
        try:
            from src.desktop.designer.ui.designer_window import ReportDesignerWindow
            tpl_path = self._tpl_selector.currentData() if self._tpl_selector.count() else None
            self._designer_win = ReportDesignerWindow(template_path=tpl_path, parent=self)
            self._designer_win.setWindowModality(Qt.WindowModality.NonModal)
            self._designer_win.destroyed.connect(self._populate_template_selector)
            self._designer_win.show()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Baskı formu tasarımcısı açılamadı")
            QMessageBox.critical(self, "Tasarımcı Hatası", str(exc))

    # ---- Baskı / Yazdırma ----------------------------------------------
    def _populate_template_selector(self):
        """Baskı formu kombosunu hazır şablonlarla doldurur (ilki = varsayılan)."""
        try:
            from src.desktop.designer.services.teklif_print_service import (
                TeklifPrintService,
            )
            templates = TeklifPrintService.available_templates()
        except Exception:
            logger.exception("Baskı şablonları listelenemedi")
            templates = []
        self._tpl_selector.clear()
        for title, path in templates:
            self._tpl_selector.addItem(title, str(path))
        if not templates:
            self._tpl_selector.addItem("Varsayılan A4", None)
        self._tpl_selector.setEnabled(self._tpl_selector.count() > 1)

    def _open_print_preview(self):
        """Seçili şablon + canlı belge verisiyle ReportPreviewDialog açar."""
        try:
            from src.desktop.designer.services.teklif_print_service import (
                TeklifPrintService,
            )
            tpl_path = self._tpl_selector.currentData() if self._tpl_selector.count() else None
            service = TeklifPrintService(db_session=self.db, template_path=tpl_path)
            service.preview_with_data(self._build_print_data(), parent=self)
        except Exception as exc:  # noqa: BLE001 - kullanıcıya anlamlı mesaj göster
            logger.exception("Baskı önizleme açılamadı")
            QMessageBox.critical(
                self, "Baskı Hatası",
                f"Baskı önizlemesi açılamadı:\n{exc}",
            )

    # ---- Canlı mini önizleme (sağ panel) ----------------------------
    def _on_mini_preview_toggled(self, expanded: bool):
        """Bölüm açıldığında ilk çizimi yap; kapalıyken boşuna render etme."""
        if expanded:
            self._refresh_mini_preview()

    def _schedule_preview_refresh(self):
        """Form değişince mini önizlemeyi gecikmeli (coalesced) tazele."""
        timer = getattr(self, "_preview_timer", None)
        sec = getattr(self, "sec_mini_preview", None)
        if timer is not None and sec is not None and sec.is_expanded:
            timer.start()

    def _refresh_mini_preview(self):
        """Seçili şablon + ekrandaki güncel veriyle mini önizlemeyi çizer."""
        sec = getattr(self, "sec_mini_preview", None)
        if sec is None or not sec.is_expanded:
            return
        try:
            from src.desktop.designer.services.teklif_print_service import (
                TeklifPrintService,
            )
            tpl_path = self._tpl_selector.currentData() if self._tpl_selector.count() else None
            service = TeklifPrintService(db_session=self.db, template_path=tpl_path)
            self.mini_preview.set_document(
                service.get_template(), data=self._build_print_data(),
            )
        except Exception:  # noqa: BLE001 - önizleme kritik değil, sessiz geç
            logger.exception("Mini baskı önizlemesi tazelenemedi")

    def _build_print_data(self) -> dict:
        """
        Ekrandaki canlı widget verisini şablon motorunun beklediği sözlüğe
        dönüştürür. Şema, kaydedilmiş belge yolundaki
        ``TeklifReportService._build_teklif_data`` ile birebir aynı tutulur —
        böylece görsel tasarımcıda hangi alan bağlanırsa bağlansın, hem canlı
        hem kayıtlı önizleme aynı veriyi çözer ve motor tarafında kod değişikliği
        gerekmez.
        """
        cari = self.cari.get_data()
        vade = self.belge_vade.get_data()
        finans = self.finans.get_data()
        toplam = self.toplam.get_data()
        note1, note2 = self.notlar.get_notes()

        kalemler: list[dict] = []
        for sira, ln in enumerate(self.lines.get_lines(), start=1):
            num = ln.get("_num", {})
            if not (ln.get("kod") or ln.get("aciklama")):
                continue  # boş satırları baskıya alma
            miktar = num.get("miktar", 0.0)
            bfiyat = num.get("birim_fiyat", 0.0)
            kalemler.append({
                "sira_no":     sira,
                "kod":         ln.get("kod", ""),
                "barkod":      ln.get("barkod", ""),
                "aciklama":    ln.get("aciklama", ""),
                "not2":        "",
                "tur":         ln.get("tur", ""),
                "miktar":      miktar,
                "birim":       ln.get("birim", ""),
                "birim_fiyat": bfiyat,
                "iskonto":     num.get("iskonto_yuzde", 0.0),
                "kdv":         num.get("kdv_yuzde", 0.0),
                "brut":        miktar * bfiyat,
                "tutar":       num.get("net_tutar", 0.0),
            })

        return {
            "firma":   self._firma_data(),
            "musteri": {
                "adi":         cari.get("name", ""),
                "adres":       cari.get("address", ""),
                "vergi_daire": cari.get("tax_office", ""),
                "vergi_no":    cari.get("tax_no", ""),
                "kod":         cari.get("code", ""),
                "tel":         (cari.get("customer") or {}).get("phone", ""),
                "email":       (cari.get("customer") or {}).get("email", ""),
            },
            "belge": {
                "teklif_no":   self.txt_doc_no.text().strip() or vade.get("belge_no", ""),
                "seri":        vade.get("seri", ""),
                "fis_no":      vade.get("fis_no", ""),
                "tarih":       _tr_date(vade.get("tarih", "")),
                "saat":        vade.get("saat", ""),
                "vade":        _tr_date(vade.get("vade", "")),
                "vade_gun":    vade.get("vade_gun", ""),
                "para_birimi": finans.get("doviz_kod", "TL"),
                "doviz_kur":   finans.get("doviz_kur", 1.0),
                "durum":       self.status_label(),
                "odeme_plani": vade.get("odeme_plani", ""),
                "aciklama":    self.cmb_doc_type.currentText(),
            },
            "kalemler": kalemler,
            "toplamlar": {
                "ara_toplam":   toplam.get("ara_toplam", 0.0),
                "iskonto":      toplam.get("iskonto", 0.0),
                "masraflar":    toplam.get("masraflar", 0.0),
                "ozel_vergi":   toplam.get("ozel_vergi", 0.0),
                "kdv_matrahi":  toplam.get("net_toplam", 0.0),
                "kdv_toplam":   toplam.get("kdv_toplam", 0.0),
                "kdv_tevkifat": toplam.get("kdv_tevkifat", 0.0),
                "genel_toplam": toplam.get("genel_toplam", 0.0),
            },
            "notlar": "\n".join(n for n in (note1, note2) if n),
            "ozel_kodlar": {
                k: le.text().strip() for k, le in self._ozel_kod_inputs.items()
            },
        }

    def _firma_data(self) -> dict:
        """Firma künyesini sistem ayarlarından okur (kayıtlı belge yoluyla aynı kaynak)."""
        try:
            from src.desktop.reports.teklif_report_service import TeklifReportService
            return TeklifReportService(
                db_session=self.db, company_id=self.company_id,
            )._get_firma_data()
        except Exception:  # noqa: BLE001 - firma bilgisi zorunlu değil
            return {}

    # ------------------------------------------------------------------
    @classmethod
    def open_as_dialog(cls, parent=None, **kwargs) -> QDialog:
        """Ekranı, bulunduğu monitöre tam oturan (maksimize) bir pencerede açar.

        QDialog varsayılan çerçevesi yalnız "kapat" düğmelidir ve yeniden
        boyutlandırılamaz; başlığından tutulup taşındığında Windows'un kenara /
        üste yapıştırma (Aero Snap) kuralları düzgün işlemez. Bu yüzden pencereye
        normal bir çerçeve (büyüt / küçült / kapat) verip açılışta maksimize
        ediyoruz — kullanıcı pencereyi başka bir monitöre taşırsa Windows onu
        o ekrana yeniden oturtur.
        """
        from PyQt6.QtWidgets import QApplication

        dlg = QDialog(parent)
        dlg.setWindowTitle("Belge Detayı")
        dlg.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint,
        )
        lyt = QVBoxLayout(dlg)
        lyt.setContentsMargins(0, 0, 0, 0)
        screen = cls(parent=dlg, **kwargs)
        lyt.addWidget(screen)
        screen.closed.connect(dlg.reject)
        screen.document_saved.connect(lambda _d: None)
        dlg.screen = screen

        # "Restore down" (küçültülmüş) boyutu ekranı aşmasın: önce bulunduğu
        # monitörün kullanılabilir alanına göre makul bir normal geometri ver.
        host = (parent.screen() if parent is not None else None) or QApplication.primaryScreen()
        if host is not None:
            a = host.availableGeometry()
            m_w, m_h = a.width() // 20, a.height() // 20
            dlg.setGeometry(a.adjusted(m_w, m_h, -m_w, -m_h))
        dlg.showMaximized()
        return dlg


if __name__ == "__main__":
    import sys

    from PyQt6.QtCore import Qt as _Qt
    from PyQt6.QtWidgets import QApplication
    from qt_material import apply_stylesheet

    # main.py'deki uygulama genelindeki temayla birebir aynı görünüm:
    # bu ekran TOYA_Belge_Detay_Yeni.bat ile tek başına (login/main_window'suz)
    # çalıştırıldığında da grid/buton/sidebar renkleri soluk kalmasın diye
    # qt_material teması burada da uygulanır.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        _Qt.HighDpiScaleFactorRoundingPolicy.PassThrough,
    )
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="light_teal.xml", extra={
        "font_family": "Segoe UI, -apple-system, sans-serif",
        "font_size": "13px",
    })
    scr = DocumentDetailScreen()
    scr.setWindowTitle("Belge Detay - DocumentDetailScreen (PoC)")
    scr.resize(1600, 880)  # "restore down" boyutu
    scr.document_saved.connect(lambda d: print("SAVED:", len(d.get("lines", [])), "satır"))
    scr.showMaximized()
    sys.exit(app.exec())
