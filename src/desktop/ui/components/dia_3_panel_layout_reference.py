"""DIA Stili 3-Panelli Düzen (Edge-Triggered Panel & Dinamik Grid Mimarisi) Referans Kodu.

Bu dosya, Multi-CMS Manager uygulamasında kullanılan DIA stili 3-panelli ekran
mimarisinin tüm bileşenlerini ve kullanım örneğini tek bir çalıştırılabilir dosya
olarak sunar.

Bileşenler:
1. EdgeTriggeredPanel: Sol ve sağ tarafta açılıp kapanabilen, iğnelenebilen (pinned/unpinned) yan paneller.
2. DIAThreePanelWidget: Sol Filtre Paneli + Orta Tablo/İçerik + Sağ İşlem Paneli düzenini oluşturan ana kapsayıcı.
"""

import sys
from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)


class EdgeTriggeredPanel(QWidget):
    """Chrome Remote Desktop tarzı Edge-Triggered (Overlay/Dock) Yan Panel."""

    pinned_changed = pyqtSignal(bool)
    opened_changed = pyqtSignal(bool)

    def __init__(self, side="left", parent=None):
        super().__init__(parent)
        self.side = side  # "left" veya "right"
        self.is_pinned = False
        self.is_open = False
        self.panel_width = 230
        self.content_widget = None

        self.setObjectName(f"EdgePanel_{self.side}")
        self.init_ui()

        if parent:
            parent.installEventFilter(self)

    def init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Tetikleme Şeridi (Trigger Strip)
        self.trigger_strip = QPushButton()
        self.trigger_strip.setObjectName(f"TriggerStrip_{self.side}")
        self.trigger_strip.setFixedWidth(14)
        self.trigger_strip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_trigger_strip_icon()

        strip_style = """
            QPushButton {
                background-color: #e2e8f0;
                border: 1px solid #cbd5e1;
                color: #475569;
                font-weight: bold;
                font-size: 9px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #cbd5e1;
            }
        """
        self.trigger_strip.setStyleSheet(strip_style)
        self.trigger_strip.clicked.connect(self.toggle_panel)

        # 2. İçerik Kutusu (Panel Frame)
        self.panel_frame = QFrame()
        self.panel_frame.setObjectName(f"PanelFrame_{self.side}")
        self.panel_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
            }
        """)
        self.panel_frame.setFixedWidth(self.panel_width)

        self.panel_layout = QVBoxLayout(self.panel_frame)
        self.panel_layout.setContentsMargins(6, 6, 6, 6)
        self.panel_layout.setSpacing(6)

        # Header (Raptiye & Kapat Butonları)
        self.header_widget = QWidget()
        header_lyt = QHBoxLayout(self.header_widget)
        header_lyt.setContentsMargins(2, 2, 2, 2)
        header_lyt.setSpacing(4)

        self.pin_btn = QPushButton("📌 Sabitle")
        self.pin_btn.setObjectName(f"PinBtn_{self.side}")
        self.pin_btn.setFixedHeight(24)
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.setToolTip("Paneli Sabitle")
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                color: #475569;
                padding: 2px 6px;
            }
            QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }
        """)
        self.pin_btn.clicked.connect(self.toggle_pin)

        self.close_btn = QPushButton("❌ Gizle")
        self.close_btn.setObjectName(f"CloseBtn_{self.side}")
        self.close_btn.setFixedHeight(24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Paneli Kapat")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                color: #475569;
                padding: 2px 6px;
            }
            QPushButton:hover { background-color: #fee2e2; color: #ef4444; }
        """)
        self.close_btn.clicked.connect(self.close_panel)

        header_lyt.addWidget(self.pin_btn)
        header_lyt.addStretch()
        header_lyt.addWidget(self.close_btn)
        self.panel_layout.addWidget(self.header_widget)

        # Başlangıç Durumu
        self.panel_frame.hide()

        # Layout Yerleşimi
        if self.side == "left":
            self.main_layout.addWidget(self.panel_frame)
            self.main_layout.addWidget(self.trigger_strip)
        else:
            self.main_layout.addWidget(self.trigger_strip)
            self.main_layout.addWidget(self.panel_frame)

    def set_content(self, widget):
        """Panelin içine verilecek olan içerik widget'ını tanımlar."""
        if self.content_widget:
            self.panel_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

        self.content_widget = widget
        self.panel_layout.addWidget(self.content_widget, 1)

    def update_trigger_strip_icon(self):
        if self.side == "left":
            self.trigger_strip.setText("▶" if not self.is_open else "◀")
        else:
            self.trigger_strip.setText("◀" if not self.is_open else "▶")

    def toggle_panel(self):
        if self.is_open:
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self):
        self.is_open = True
        self.panel_frame.show()
        self.update_trigger_strip_icon()
        self.update_position()
        self.opened_changed.emit(True)

    def close_panel(self):
        self.is_open = False
        self.panel_frame.hide()
        self.update_trigger_strip_icon()
        self.update_position()
        self.opened_changed.emit(False)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.pin_btn.setText("📍 Serbest")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    border: 1px solid #1d4ed8;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                    color: white;
                    padding: 2px 6px;
                }
                QPushButton:hover { background-color: #2563eb; }
            """)
        else:
            self.pin_btn.setText("📌 Sabitle")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                    color: #475569;
                    padding: 2px 6px;
                }
                QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }
            """)
        self.pinned_changed.emit(self.is_pinned)
        self.update_position()

    def update_position(self):
        parent = self.parentWidget()
        if not parent or self.is_pinned:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setGeometry(self.geometry())
            return

        parent_height = parent.height()
        parent_width = parent.width()
        w = self.panel_width + 14 if self.is_open else 14

        self.raise_()
        if self.side == "left":
            self.setGeometry(0, 0, w, parent_height)
        else:
            self.setGeometry(parent_width - w, 0, w, parent_height)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj == self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.update_position()
        return super().eventFilter(obj, event)


class DIAThreePanelWidget(QWidget):
    """Sol Filtre Paneli + Orta Tablo/İçerik + Sağ İşlem Paneli mimarisine sahip örnek ekran."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def toolbar_btn_style(self, bg_color="#ffffff", text_color="#1e293b"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }}
        """

    def init_ui(self):
        # 1. Ana Yatay Layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # ==========================================
        # SOL PANEL (EdgeTriggeredPanel - Filtreler)
        # ==========================================
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

        filter_content = QWidget()
        filter_layout = QVBoxLayout(filter_content)
        filter_layout.setContentsMargins(4, 4, 4, 4)
        filter_layout.setSpacing(10)

        lbl_filter_title = QLabel("🔍 Filtre & Arama")
        lbl_filter_title.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 13px;")
        filter_layout.addWidget(lbl_filter_title)

        # Hızlı Arama
        lbl_search = QLabel("Arama Metni:")
        lbl_search.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Kod, Ünvan veya İsim...")
        self.txt_search.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
            }
        """)
        filter_layout.addWidget(lbl_search)
        filter_layout.addWidget(self.txt_search)

        # Kategori Seçimi
        lbl_cat = QLabel("Kategori / Durum:")
        lbl_cat.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(["Tümü", "Aktif Kayıtlar", "Pasif Kayıtlar", "Taslaklar"])
        self.cmb_cat.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
            }
        """)
        filter_layout.addWidget(lbl_cat)
        filter_layout.addWidget(self.cmb_cat)
        filter_layout.addStretch()

        self.left_panel.set_content(filter_content)
        main_layout.addWidget(self.left_panel)

        # ==========================================
        # ORTA PANEL (İçerik / Tablo & Sayfalama)
        # ==========================================
        self.center_container = QWidget()
        center_layout = QVBoxLayout(self.center_container)
        center_layout.setContentsMargins(4, 0, 4, 0)
        center_layout.setSpacing(8)

        # Tablo
        self.table_view = QTableView()
        self.model = QStandardItemModel(10, 4)
        self.model.setHorizontalHeaderLabels(["ID", "Kod / Ad", "Açıklama", "Durum"])
        for r in range(10):
            self.model.setItem(r, 0, QStandardItem(str(1001 + r)))
            self.model.setItem(r, 1, QStandardItem(f"Örnek Kayıt #{r+1}"))
            self.model.setItem(r, 2, QStandardItem(f"DIA stili 3-panelli düzen test verisi {r+1}"))
            self.model.setItem(r, 3, QStandardItem("Aktif" if r % 2 == 0 else "Pasif"))
        self.table_view.setModel(self.model)
        self.table_view.setStyleSheet("""
            QTableView {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                padding: 6px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: bold;
            }
        """)
        center_layout.addWidget(self.table_view, 1)

        # Alt Sayfalama (Pagination Bar)
        pagination_layout = QHBoxLayout()
        btn_prev = QPushButton("⬅️ Önceki")
        lbl_page = QLabel("Sayfa 1 / 5")
        lbl_page.setStyleSheet("font-weight: bold; color: #475569;")
        btn_next = QPushButton("Sonraki ➡️")

        pg_btn_style = """
            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                padding: 4px 10px;
                color: #475569;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """
        btn_prev.setStyleSheet(pg_btn_style)
        btn_next.setStyleSheet(pg_btn_style)

        pagination_layout.addWidget(btn_prev)
        pagination_layout.addWidget(lbl_page)
        pagination_layout.addWidget(btn_next)
        pagination_layout.addStretch()
        center_layout.addLayout(pagination_layout)

        main_layout.addWidget(self.center_container, 1)

        # ==========================================
        # SAĞ PANEL (EdgeTriggeredPanel - İşlem Butonları)
        # ==========================================
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(8)

        # 1. Grup: Veri İşlemleri
        grp_data = QFrame()
        grp_data.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_data_lyt = QVBoxLayout(grp_data)
        grp_data_lyt.setContentsMargins(6, 8, 6, 8)
        grp_data_lyt.setSpacing(6)

        lbl_grp1 = QLabel("İŞLEMLER")
        lbl_grp1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp1.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_data_lyt.addWidget(lbl_grp1)

        btn_new = QPushButton("➕ Yeni Ekle")
        btn_new.setStyleSheet(self.toolbar_btn_style("#10b981", "#ffffff"))
        btn_edit = QPushButton("✏️ Düzenle")
        btn_edit.setStyleSheet(self.toolbar_btn_style())
        btn_delete = QPushButton("🗑️ Sil")
        btn_delete.setStyleSheet(self.toolbar_btn_style("#ef4444", "#ffffff"))

        grp_data_lyt.addWidget(btn_new)
        grp_data_lyt.addWidget(btn_edit)
        grp_data_lyt.addWidget(btn_delete)
        right_layout.addWidget(grp_data)

        # 2. Grup: Görünüm & Kolonlar
        grp_view = QFrame()
        grp_view.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_view_lyt = QVBoxLayout(grp_view)
        grp_view_lyt.setContentsMargins(6, 8, 6, 8)
        grp_view_lyt.setSpacing(6)

        lbl_grp2 = QLabel("GÖRÜNÜM")
        lbl_grp2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp2.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_view_lyt.addWidget(lbl_grp2)

        btn_columns = QPushButton("⚙️ Kolonları Yönet")
        btn_columns.setStyleSheet(self.toolbar_btn_style())
        btn_profile = QPushButton("🎨 Görünüm Profili")
        btn_profile.setStyleSheet(self.toolbar_btn_style())

        grp_view_lyt.addWidget(btn_columns)
        grp_view_lyt.addWidget(btn_profile)
        right_layout.addWidget(grp_view)
        right_layout.addStretch()

        right_scroll.setWidget(right_content)
        self.right_panel.set_content(right_scroll)
        main_layout.addWidget(self.right_panel)


class MainWindow(QMainWindow):
    """Referans gösterim için ana pencere."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DIA Stili 3-Panelli Düzen Referans Uygulaması")
        self.resize(1050, 650)
        self.widget = DIAThreePanelWidget(self)
        self.setCentralWidget(self.widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
