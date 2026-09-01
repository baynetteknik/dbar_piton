"""
ToyaUI — ExportWidget
Sağ panel dosya dışa/içe aktarım ve raporlama butonları widget'ı.
Tüm liste ekranlarında kullanılabilir.
"""


from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.collapsible_section import CollapsibleSection


class ExportWidget(QWidget):
    """Excel, PDF, İçe Aktarma, Yazdırma ve Raporlama işlemlerini yöneten akordiyon widget'ı."""

    export_excel_clicked = pyqtSignal()
    export_pdf_clicked = pyqtSignal()
    import_excel_clicked = pyqtSignal()
    print_clicked = pyqtSignal()
    report_clicked = pyqtSignal()

    def __init__(
        self,
        group_title: str = "DOSYA & AKTARIM",
        show_buttons: list[str] | None = None,
        hide_buttons: list[str] | None = None,
        initial_open: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.group_title = group_title
        self.show_buttons = show_buttons
        self.hide_buttons = hide_buttons if hide_buttons is not None else []
        self.initial_open = initial_open

        self.init_ui()

    def _btn_style(self) -> str:
        """Standart dışa aktarım butonu stili."""
        return """
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
                font-family: 'Segoe UI';
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background-color: #f8fafc;
                border-color: #e2e8f0;
            }
        """

    def init_ui(self):
        """Bileşenleri ve butonları oluşturur."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Akordiyon bölümü
        self.section = CollapsibleSection(self.group_title, is_expanded=self.initial_open)
        self.section.setObjectName("cmp.export.001")

        self.buttons_dict = {}

        # 1. 📤 Dışa Aktar (Excel)
        self.btn_export_excel = QPushButton("📤 Dışa Aktar (Excel)")
        self.btn_export_excel.setObjectName("act.exp_xls.001")
        self.btn_export_excel.setToolTip("Verileri Excel (.xlsx) dosyası olarak dışa aktar")
        self.btn_export_excel.setStyleSheet(self._btn_style())
        self.btn_export_excel.clicked.connect(self.export_excel_clicked.emit)
        self.buttons_dict["export_excel"] = self.btn_export_excel

        # 2. 📄 PDF Olarak Kaydet
        self.btn_export_pdf = QPushButton("📄 PDF Olarak Kaydet")
        self.btn_export_pdf.setObjectName("act.exp_pdf.001")
        self.btn_export_pdf.setToolTip("Listeyi veya belgeyi PDF olarak kaydet")
        self.btn_export_pdf.setStyleSheet(self._btn_style())
        self.btn_export_pdf.clicked.connect(self.export_pdf_clicked.emit)
        self.buttons_dict["export_pdf"] = self.btn_export_pdf

        # 3. 📥 Excel'den İçe Aktar
        self.btn_import_excel = QPushButton("📥 Excel'den İçe Aktar")
        self.btn_import_excel.setObjectName("act.imp_xls.001")
        self.btn_import_excel.setToolTip("Excel dosyasından toplu veri aktarımı yap")
        self.btn_import_excel.setStyleSheet(self._btn_style())
        self.btn_import_excel.clicked.connect(self.import_excel_clicked.emit)
        self.buttons_dict["import_excel"] = self.btn_import_excel

        # 4. 🖨️ Yazdır
        self.btn_print = QPushButton("🖨️ Yazdır")
        self.btn_print.setObjectName("act.prn.001")
        self.btn_print.setToolTip("Doğrudan yazıcıya gönder veya önizle")
        self.btn_print.setStyleSheet(self._btn_style())
        self.btn_print.clicked.connect(self.print_clicked.emit)
        self.buttons_dict["print"] = self.btn_print

        # 5. 📊 Detaylı Rapor
        self.btn_report = QPushButton("📊 Detaylı Rapor")
        self.btn_report.setObjectName("act.rep.001")
        self.btn_report.setToolTip("Detaylı icmal ve durum raporu üret")
        self.btn_report.setStyleSheet(self._btn_style())
        self.btn_report.clicked.connect(self.report_clicked.emit)
        self.buttons_dict["report"] = self.btn_report

        button_order = ["export_excel", "export_pdf", "import_excel", "print", "report"]

        for key in button_order:
            btn = self.buttons_dict[key]
            if self.show_buttons is not None and key not in self.show_buttons:
                btn.hide()
                continue
            if key in self.hide_buttons:
                btn.hide()
                continue
            self.section.add_widget(btn)

        main_layout.addWidget(self.section)

    def set_expanded(self, expanded: bool):
        """Akordiyonun açık/kapalı durumunu ayarlar."""
        if self.section.is_expanded != expanded:
            self.section.toggle()


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = ExportWidget(
        hide_buttons=["import_excel"],
        initial_open=True,
    )
    widget.export_excel_clicked.connect(lambda: print("✅ Excel Dışa Aktar tıklandı"))
    widget.export_pdf_clicked.connect(lambda: print("✅ PDF Kaydet tıklandı"))
    widget.report_clicked.connect(lambda: print("✅ Detaylı Rapor tıklandı"))

    widget.show()
    print("ExportWidget başarıyla oluşturuldu.")
    sys.exit(0)
