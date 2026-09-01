"""
TOYA ERP - Hareket Kalemleri Satır Tablosu Widget'ı (HareketKalemleriDbGridWidget)
AppGrid tabanlı, dinamik satır ekleme/çıkarma, canlı iskonto ve KDV hesaplama
yeteneklerine sahip modüler evrak satırları bileşeni.
"""

from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from src.desktop.managers.theme_manager import ThemeManager


class HareketKalemleriDbGridWidget(QWidget):
    """Teklif, Fatura, Sipariş ve İrsaliye satırları dinamik tablosu."""

    totals_changed = pyqtSignal(float, float, float, float)  # subtotal, discount, vat, grand_total
    row_count_changed = pyqtSignal(int)

    def __init__(self, title: str = "BELGE SATIRLARI / HAREKET KALEMLERİ", parent=None):
        super().__init__(parent)
        self.theme = ThemeManager()
        self.title = title
        self.columns = [
            "SIRA", "KOD", "AÇIKLAMA / STOK ADI", 
            "MİKTAR", "BİRİM", "BİRİM FİYAT", "İSK. (%)", "KDV (%)", "TUTAR"
        ]
        self._init_ui()

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
                border-radius: 8px;
                background-color: #ffffff;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                background-color: white;
            }
        """)
        grp_lyt = QVBoxLayout(self.grp_box)
        grp_lyt.setSpacing(6)
        grp_lyt.setContentsMargins(8, 8, 8, 8)

        # Üst Araç Çubuğu (Satır Ekle / Sil)
        tool_bar = QHBoxLayout()
        tool_bar.setSpacing(6)

        btn_style = """
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """

        self.btn_add_row = QPushButton("➕ Satır Ekle (Ins)")
        self.btn_add_row.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_row.setStyleSheet(btn_style)
        self.btn_add_row.clicked.connect(self.add_empty_row)
        tool_bar.addWidget(self.btn_add_row)

        self.btn_del_row = QPushButton("🗑️ Satır Sil (Del)")
        self.btn_del_row.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_row.setStyleSheet(btn_style)
        self.btn_del_row.clicked.connect(self.delete_selected_row)
        tool_bar.addWidget(self.btn_del_row)

        tool_bar.addStretch()
        self.lbl_row_count = QLabel("Toplam: 0 Satır")
        self.lbl_row_count.setStyleSheet("font-weight: bold; color: #64748b; font-size: 11px;")
        tool_bar.addWidget(self.lbl_row_count)

        grp_lyt.addLayout(tool_bar)

        # QTableWidget Grid
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setStyleSheet(self.theme.get_table_stylesheet())
        self.table.horizontalHeader().setFixedHeight(self.theme.header_height)
        self.table.verticalHeader().setDefaultSectionSize(self.theme.row_height)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        # Sütun Genişlikleri
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Sıra
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)      # Kod
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)          # Açıklama
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)      # Miktar
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)      # Birim
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)      # Birim Fiyat
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)      # İsk %
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)      # KDV %
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Interactive)      # Tutar

        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 75)
        self.table.setColumnWidth(7, 75)
        self.table.setColumnWidth(8, 120)

        self.table.cellChanged.connect(self._on_cell_changed)
        grp_lyt.addWidget(self.table, 1)

        main_lyt.addWidget(self.grp_box)

    def add_empty_row(self):
        """Tabloya yeni boş satır ekler."""
        row = self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(row)

        item_seq = QTableWidgetItem(str(row + 1))
        item_seq.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_seq.setFlags(item_seq.flags() & ~Qt.ItemFlag.ItemIsEditable)

        item_code = QTableWidgetItem("")
        item_desc = QTableWidgetItem("Yeni Kalem / Hizmet")
        item_qty = QTableWidgetItem("1,00")
        item_qty.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_unit = QTableWidgetItem("Adet")
        item_price = QTableWidgetItem("0,00")
        item_price.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_disc = QTableWidgetItem("0")
        item_disc.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_vat = QTableWidgetItem("20")
        item_vat.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_total = QTableWidgetItem("0,00 ₺")
        item_total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item_total.setFlags(item_total.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.table.setItem(row, 0, item_seq)
        self.table.setItem(row, 1, item_code)
        self.table.setItem(row, 2, item_desc)
        self.table.setItem(row, 3, item_qty)
        self.table.setItem(row, 4, item_unit)
        self.table.setItem(row, 5, item_price)
        self.table.setItem(row, 6, item_disc)
        self.table.setItem(row, 7, item_vat)
        self.table.setItem(row, 8, item_total)

        self.table.blockSignals(False)
        self._recalculate_totals()

    def delete_selected_row(self):
        """Seçili satırı tablodan siler."""
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            # Sıra numaralarını yeniden düzenle
            self.table.blockSignals(True)
            for r in range(self.table.rowCount()):
                it = self.table.item(r, 0)
                if it: it.setText(str(r + 1))
            self.table.blockSignals(False)
            self._recalculate_totals()

    def _on_cell_changed(self, row: int, column: int):
        if column in (3, 5, 6, 7):  # Miktar, Fiyat, İskonto, KDV
            self._recalculate_row(row)
            self._recalculate_totals()

    def _recalculate_row(self, row: int):
        try:
            qty_text = self.table.item(row, 3).text().replace(".", "").replace(",", ".") if self.table.item(row, 3) else "0"
            price_text = self.table.item(row, 5).text().replace(".", "").replace(",", ".") if self.table.item(row, 5) else "0"
            disc_text = self.table.item(row, 6).text().replace(".", "").replace(",", ".") if self.table.item(row, 6) else "0"
            
            qty = float(qty_text)
            price = float(price_text)
            disc = float(disc_text)

            row_gross = qty * price
            row_disc = row_gross * (disc / 100.0)
            row_net = row_gross - row_disc

            self.table.blockSignals(True)
            item_total = self.table.item(row, 8)
            if item_total:
                item_total.setText(f"{row_net:,.2f} ₺")
            self.table.blockSignals(False)
        except Exception:
            pass

    def _recalculate_totals(self):
        subtotal = 0.0
        discount_total = 0.0
        vat_total = 0.0

        for r in range(self.table.rowCount()):
            try:
                qty_text = self.table.item(r, 3).text().replace(".", "").replace(",", ".") if self.table.item(r, 3) else "0"
                price_text = self.table.item(r, 5).text().replace(".", "").replace(",", ".") if self.table.item(r, 5) else "0"
                disc_text = self.table.item(r, 6).text().replace(".", "").replace(",", ".") if self.table.item(r, 6) else "0"
                vat_text = self.table.item(r, 7).text().replace(".", "").replace(",", ".") if self.table.item(r, 7) else "20"

                qty = float(qty_text)
                price = float(price_text)
                disc = float(disc_text)
                vat_rate = float(vat_text)

                gross = qty * price
                disc_val = gross * (disc / 100.0)
                net = gross - disc_val
                vat_val = net * (vat_rate / 100.0)

                subtotal += gross
                discount_total += disc_val
                vat_total += vat_val
            except Exception:
                pass

        grand_total = (subtotal - discount_total) + vat_total
        self.lbl_row_count.setText(f"Toplam: {self.table.rowCount()} Satır")
        self.totals_changed.emit(subtotal, discount_total, vat_total, grand_total)
        self.row_count_changed.emit(self.table.rowCount())
