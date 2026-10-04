"""
TOYA ERP - Atomik Dışa Aktarım ve Yazdırma Widget'ı (ExportActionsWidget)
Excel (.xlsx), PDF, CSV aktarımı ve Yazıcı (Baskı) işlemlerini yöneten bağımsız bileşen.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QPushButton, QVBoxLayout, QWidget

from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.ui.components.button_style import btn_style


class ExportActionsWidget(QWidget):
    """Excel, PDF, CSV ve Yazdırma işlemlerini barındıran modüler aktarım paneli."""

    excel_requested = pyqtSignal()
    pdf_requested = pyqtSignal()
    csv_requested = pyqtSignal()
    print_requested = pyqtSignal()

    def __init__(self, title: str = "DIŞA AKTARIM & BASKI", parent=None):
        super().__init__(parent)
        self.theme = ThemeManager()
        self.title = title
        self._init_ui()

    def _btn_style(self, bg="#ffffff", text="#1e293b", border="#cbd5e1"):
        return btn_style(bg, text)

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(0, 0, 0, 0)
        main_lyt.setSpacing(6)

        self.grp_box = QGroupBox(self.title)
        self.grp_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #1e3a8a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 4px;
                background-color: transparent;
            }
        """)
        grp_lyt = QVBoxLayout(self.grp_box)
        grp_lyt.setSpacing(6)
        grp_lyt.setContentsMargins(6, 8, 6, 8)

        # 1. Excel Aktarımı
        self.btn_excel = QPushButton("📊 Excel'e Aktar (F9)")
        self.btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_excel.setStyleSheet(self._btn_style(bg="#f0fdf4", text="#15803d", border="#bbf7d0"))
        self.btn_excel.clicked.connect(self.excel_requested.emit)
        grp_lyt.addWidget(self.btn_excel)

        # 2. PDF Aktarımı
        self.btn_pdf = QPushButton("📑 PDF Rapor Oluştur")
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.setStyleSheet(self._btn_style(bg="#fef2f2", text="#b91c1c", border="#fecaca"))
        self.btn_pdf.clicked.connect(self.pdf_requested.emit)
        grp_lyt.addWidget(self.btn_pdf)

        # 3. CSV / Düz Metin
        self.btn_csv = QPushButton("📄 CSV / Metin Formatı")
        self.btn_csv.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_csv.setStyleSheet(self._btn_style())
        self.btn_csv.clicked.connect(self.csv_requested.emit)
        grp_lyt.addWidget(self.btn_csv)

        # 4. Yazdır (Print)
        self.btn_print = QPushButton("🖨️ Yazdır / Baskı Önizle")
        self.btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_print.setStyleSheet(self._btn_style())
        self.btn_print.clicked.connect(self.print_requested.emit)
        grp_lyt.addWidget(self.btn_print)

        main_lyt.addWidget(self.grp_box)
