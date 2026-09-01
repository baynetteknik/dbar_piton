"""
ToyaUI — FilterWidget
Sağ EdgeTriggeredPanel filtreleme widget'ı.
Tüm liste ekranlarında kullanılabilir.
"""

from typing import Any

from PyQt6.QtCore import QDate, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel


class FilterWidget(QWidget):
    """Sağ açılır/kapanır EdgePanel içinde filtreleme alanlarını ve ek bölümleri yöneten bileşen."""

    filter_changed = pyqtSignal(dict)  # Aktif filtre sözlüğü (örn: {"search": "abc", "status": "Aktif"})
    filters_cleared = pyqtSignal()      # Tüm filtreler sıfırlandığında tetiklenir

    def __init__(
        self,
        group_title: str = "FİLTRELER",
        show_filters: list[str] | None = None,
        status_options: list[str] | None = None,
        group_options: list[str] | None = None,
        initial_open: bool = False,
        panel_width: int = 240,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.group_title = group_title
        self.show_filters = show_filters
        self.status_options = status_options or [
            "Tümü",
            "Taslak (Draft)",
            "Gönderildi (Sent)",
            "Onaylandı (Accepted)",
            "Reddedildi (Rejected)",
            "Dönüştürüldü (Converted)",
        ]
        self.group_options = group_options or ["Tümü", "Genel", "Özel", "VIP", "Toptan", "Perakende"]
        self.initial_open = initial_open
        self.panel_width_val = panel_width

        self._min_dummy_date = QDate(1900, 1, 1)

        self.init_ui()

    def _input_style(self) -> str:
        """Giriş kutuları ve açılır kutuların ortak stili."""
        return """
            QLineEdit, QComboBox, QDateEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                background-color: white;
                color: #0f172a;
                font-size: 11px;
                font-family: 'Segoe UI';
                min-height: 22px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border-color: #3b82f6;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #94a3b8;
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
        """

    def _label_style(self) -> str:
        """Filtre başlık etiketlerinin stili."""
        return "font-weight: bold; color: #0f172a; font-size: 11px; font-family: 'Segoe UI';"

    def init_ui(self):
        """EdgeTriggeredPanel ve filtre bileşenlerini oluşturur."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sağ Kenar Paneli
        self.edge_panel = EdgeTriggeredPanel(side="right", default_width=self.panel_width_val, parent=self)
        if hasattr(self.edge_panel, "set_panel_width"):
            self.edge_panel.set_panel_width(self.panel_width_val)

        # Scroll Alanı
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content_frame = QFrame()
        content_frame.setStyleSheet("background-color: transparent; border: none;")
        self.content_layout = QVBoxLayout(content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        # Akordiyon bölümü
        self.sec_filters = CollapsibleSection(self.group_title, is_expanded=True)
        self.sec_filters.setObjectName("cmp.filter.001")

        # Filtre Sayacı Etiketi
        self.lbl_counter = QLabel("")
        self.lbl_counter.setStyleSheet("""
            QLabel {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 10px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }
        """)
        self.lbl_counter.hide()
        self.sec_filters.add_widget(self.lbl_counter)

        self.filter_widgets = {}

        # 1. Ünvan / Kod Arama (search)
        self.lbl_search = QLabel("Ünvan / Fiş No / Kod:")
        self.lbl_search.setStyleSheet(self._label_style())
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Hızlı ara...")
        self.search_box.setStyleSheet(self._input_style())
        self.search_box.textChanged.connect(self._on_control_changed)
        self.filter_widgets["search"] = (self.lbl_search, self.search_box)

        # 2. Durum Filtresi (status)
        self.lbl_status = QLabel("Durum:")
        self.lbl_status.setStyleSheet(self._label_style())
        self.cmb_status = QComboBox()
        self.cmb_status.setStyleSheet(self._input_style())
        self.cmb_status.addItems(self.status_options)
        self.cmb_status.currentTextChanged.connect(self._on_control_changed)
        self.filter_widgets["status"] = (self.lbl_status, self.cmb_status)

        # 3. Grup Filtresi (group)
        self.lbl_group = QLabel("Grup / Kategori:")
        self.lbl_group.setStyleSheet(self._label_style())
        self.cmb_group = QComboBox()
        self.cmb_group.setStyleSheet(self._input_style())
        self.cmb_group.addItems(self.group_options)
        self.cmb_group.currentTextChanged.connect(self._on_control_changed)
        self.filter_widgets["group"] = (self.lbl_group, self.cmb_group)

        # 4. Tarih Başlangıç (date_from)
        self.lbl_date_from = QLabel("Başlangıç Tarihi:")
        self.lbl_date_from.setStyleSheet(self._label_style())
        self.date_from = QDateEdit()
        self.date_from.setStyleSheet(self._input_style())
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setMinimumDate(self._min_dummy_date)
        self.date_from.setSpecialValueText("Tarih Seçilmedi")
        self.date_from.setDate(self._min_dummy_date)
        self.date_from.dateChanged.connect(self._on_control_changed)
        self.filter_widgets["date_from"] = (self.lbl_date_from, self.date_from)

        # 5. Tarih Bitiş (date_to)
        self.lbl_date_to = QLabel("Bitiş Tarihi:")
        self.lbl_date_to.setStyleSheet(self._label_style())
        self.date_to = QDateEdit()
        self.date_to.setStyleSheet(self._input_style())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setMinimumDate(self._min_dummy_date)
        self.date_to.setSpecialValueText("Tarih Seçilmedi")
        self.date_to.setDate(self._min_dummy_date)
        self.date_to.dateChanged.connect(self._on_control_changed)
        self.filter_widgets["date_to"] = (self.lbl_date_to, self.date_to)

        # Filtreleri Sırayla Akordiyona Ekle
        filter_order = ["search", "status", "group", "date_from", "date_to"]
        for key in filter_order:
            lbl, widget = self.filter_widgets[key]
            if self.show_filters is not None and key not in self.show_filters:
                lbl.hide()
                widget.hide()
                continue

            self.sec_filters.add_widget(lbl)
            self.sec_filters.add_widget(widget)

        # Filtreleri Temizle Butonu
        self.btn_clear = QPushButton("🗑️ Filtreleri Temizle")
        self.btn_clear.setObjectName("act.clr.001")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                color: #334155;
                padding: 6px 10px;
                border-radius: 4px;
                font-weight: 600;
                font-size: 11px;
                font-family: 'Segoe UI';
                text-align: center;
                margin-top: 4px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_filters)
        self.sec_filters.add_widget(self.btn_clear)

        self.content_layout.addWidget(self.sec_filters)
        self.content_layout.addStretch()

        scroll_area.setWidget(content_frame)
        self.edge_panel.set_content(scroll_area)
        main_layout.addWidget(self.edge_panel)

        # Başlangıç durumu
        if self.initial_open:
            self.edge_panel.open_panel()
        else:
            self.edge_panel.close_panel()

        self._update_counter_and_emit(emit_signal=False)

    def open_panel(self):
        """Paneli açar."""
        self.edge_panel.open_panel()

    def close_panel(self):
        """Paneli kapatır."""
        self.edge_panel.close_panel()

    def toggle_panel(self):
        """Paneli açıp kapatır."""
        self.edge_panel.toggle_panel()

    def is_open(self) -> bool:
        """Panelin açık olup olmadığını döndürür."""
        return self.edge_panel.is_open

    def add_custom_section(self, section: QWidget):
        """Sağ sidebar içerisine ek bir akordiyon veya widget (örn: ExportWidget) ekler."""
        idx = self.content_layout.count() - 1
        if idx >= 0:
            self.content_layout.insertWidget(idx, section)
        else:
            self.content_layout.addWidget(section)

    def get_filters(self) -> dict[str, Any]:
        """Aktif filtreleri sözlük olarak döndürür."""
        filters = {}

        # Arama
        search_val = self.search_box.text().strip()
        if search_val:
            filters["search"] = search_val

        # Durum
        status_val = self.cmb_status.currentText()
        if status_val and status_val != "Tümü":
            filters["status"] = status_val

        # Grup
        group_val = self.cmb_group.currentText()
        if group_val and group_val != "Tümü":
            filters["group"] = group_val

        # Tarih Başlangıç
        if self.date_from.date() > self._min_dummy_date:
            filters["date_from"] = self.date_from.date().toString("yyyy-MM-dd")

        # Tarih Bitiş
        if self.date_to.date() > self._min_dummy_date:
            filters["date_to"] = self.date_to.date().toString("yyyy-MM-dd")

        return filters

    def _on_control_changed(self):
        """Herhangi bir filtre değiştiğinde sayacı günceller ve sinyal gönderir."""
        self._update_counter_and_emit(emit_signal=True)

    def _update_counter_and_emit(self, emit_signal: bool = True):
        """Aktif filtre sayısını hesaplar, sayacı günceller ve `filter_changed` sinyali üretir."""
        active_filters = self.get_filters()
        count = len(active_filters)

        if count > 0:
            self.lbl_counter.setText(f"🔍 {count} Filtre Aktif")
            self.lbl_counter.show()
        else:
            self.lbl_counter.hide()

        if emit_signal:
            self.filter_changed.emit(active_filters)

    def clear_filters(self):
        """Tüm filtre girişlerini sıfırlar."""
        self.blockSignals(True)
        self.search_box.blockSignals(True)
        self.cmb_status.blockSignals(True)
        self.cmb_group.blockSignals(True)
        self.date_from.blockSignals(True)
        self.date_to.blockSignals(True)

        self.search_box.clear()
        self.cmb_status.setCurrentIndex(0)
        self.cmb_group.setCurrentIndex(0)
        self.date_from.setDate(self._min_dummy_date)
        self.date_to.setDate(self._min_dummy_date)

        self.search_box.blockSignals(False)
        self.cmb_status.blockSignals(False)
        self.cmb_group.blockSignals(False)
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(False)
        self.blockSignals(False)

        self.lbl_counter.hide()
        self.filters_cleared.emit()
        self.filter_changed.emit({})

    def set_filter(self, key: str, value: Any):
        """Belirtilen filtreyi programatik olarak ayarlar."""
        if key == "search" and hasattr(self, "search_box"):
            self.search_box.setText(str(value))
        elif key == "status" and hasattr(self, "cmb_status"):
            idx = self.cmb_status.findText(str(value))
            if idx >= 0:
                self.cmb_status.setCurrentIndex(idx)
        elif key == "group" and hasattr(self, "cmb_group"):
            idx = self.cmb_group.findText(str(value))
            if idx >= 0:
                self.cmb_group.setCurrentIndex(idx)
        elif key == "date_from" and hasattr(self, "date_from"):
            qdate = QDate.fromString(str(value), "yyyy-MM-dd") if isinstance(value, str) else value
            if qdate.isValid():
                self.date_from.setDate(qdate)
        elif key == "date_to" and hasattr(self, "date_to"):
            qdate = QDate.fromString(str(value), "yyyy-MM-dd") if isinstance(value, str) else value
            if qdate.isValid():
                self.date_to.setDate(qdate)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = FilterWidget(
        status_options=["Tümü", "Açık", "Kapalı", "Beklemede"],
        initial_open=True,
    )
    widget.filter_changed.connect(lambda f: print(f"✅ Filtre değişti: {f}"))
    widget.filters_cleared.connect(lambda: print("✅ Filtreler temizlendi"))

    widget.show()
    widget.search_box.setText("Toya ERP")
    widget.cmb_status.setCurrentText("Açık")
    print("Mevcut filtreler:", widget.get_filters())
    sys.exit(0)
