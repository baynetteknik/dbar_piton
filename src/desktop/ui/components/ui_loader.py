"""
TOYA ERP - Qt Designer (.ui) Dinamik Yükleyici ve Köprü Modülü (UILoader)
Qt6 Designer ile tasarlanan herhangi bir .ui dosyasını çalışma anında (runtime)
doğrudan Python widget'ına dönüştürür ve merkezi ThemeManager & AppGrid ile otomatik bağlar.
"""

import os
from pathlib import Path
from PyQt6 import uic
from PyQt6.QtWidgets import QWidget, QTableWidget, QTableView
from src.desktop.managers.theme_manager import ThemeManager


class DynamicUIScreen(QWidget):
    """
    Qt Designer ile oluşturulmuş .ui dosyalarını dinamik yükleyen
    ve kurumsal ERP tema standartlarını otomatik uygulayan ana sınıf.
    """

    def __init__(self, ui_file_path: str, parent=None):
        super().__init__(parent)
        self.theme = ThemeManager()
        self.ui_file_path = ui_file_path
        
        # .ui Dosyasını Yükle
        if os.path.exists(ui_file_path):
            uic.loadUi(ui_file_path, self)
            self._apply_corporate_styles()
        else:
            raise FileNotFoundError(f"UI dosyası bulunamadı: {ui_file_path}")

    def _apply_corporate_styles(self):
        """Yüklenen ekrandaki tüm grid ve tablolara kurumsal stilleri enjekte eder."""
        # Ekrandaki tüm tabloları bul ve merkezi temayı uygula
        tables = self.findChildren((QTableWidget, QTableView))
        table_qss = self.theme.get_table_stylesheet()
        for tbl in tables:
            tbl.setStyleSheet(table_qss)
            if hasattr(tbl, "verticalHeader"):
                tbl.verticalHeader().setDefaultSectionSize(self.theme.row_height)
            if hasattr(tbl, "horizontalHeader"):
                tbl.horizontalHeader().setFixedHeight(self.theme.header_height)
