"""
TOYA ERP - Bant Yönetimi Diyaloğu (BandManagerDialog)

Şablondaki bantların (Sayfa Üst Bilgisi, Detay Satırı, Sayfa Altı vb.) hangi
sırayla basılacağı bant tipine göre sabittir (baskı motoru bu sırayı bekler);
burada kullanıcının değiştirebildiği iki şey vardır: bandın baskıda hiç
kullanılıp kullanılmayacağı (Aktif) ve milimetrik yüksekliği. Değişiklikler
yalnızca "Tamam" ile onaylanınca şablona yazılır.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import ReportTemplate
from src.desktop.designer.ui.designer_band import DesignerBandWidget

_COL_ENABLED = 0
_COL_NAME = 1
_COL_ITEMS = 2
_COL_HEIGHT = 3


class BandManagerDialog(QDialog):
    """Bant listesi: aktif/kapalı + yükseklik (mm) düzenleme."""

    def __init__(self, template: ReportTemplate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.template = template
        self.setWindowTitle("🗂️ Bant Yönetimi")
        self.setMinimumSize(560, 420)
        self._checks: list[QCheckBox] = []
        self._spins: list[QDoubleSpinBox] = []
        self._init_ui()

    def _init_ui(self) -> None:
        lyt = QVBoxLayout(self)

        info = QLabel(
            "Bantların baskı sırası tipine göre sabittir (Sayfa Üst Bilgisi → ... → "
            "Sayfa Altı). Burada bir bandı baskıdan tamamen kapatabilir veya "
            "milimetrik yüksekliğini hassas biçimde girebilirsiniz.",
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748B; font-size:11px;")
        lyt.addWidget(info)

        self.table = QTableWidget(len(self.template.bands), 4, self)
        self.table.setHorizontalHeaderLabels(["Aktif", "Bant Adı", "Öğe", "Yükseklik (mm)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(_COL_NAME, QHeaderView.ResizeMode.Stretch)

        for row, band in enumerate(self.template.bands):
            chk = QCheckBox(self.table)
            chk.setChecked(band.enabled)
            self._checks.append(chk)
            chk_cell = QWidget(self.table)
            chk_lyt = QHBoxLayout(chk_cell)
            chk_lyt.addWidget(chk)
            chk_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_lyt.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, _COL_ENABLED, chk_cell)

            title = DesignerBandWidget.BAND_TITLES.get(band.type, band.type)
            self.table.setItem(row, _COL_NAME, QTableWidgetItem(title))

            self.table.setItem(
                row, _COL_ITEMS, QTableWidgetItem(str(len(band.items))),
            )

            spn = QDoubleSpinBox(self.table)
            spn.setRange(2.0, 300.0)
            spn.setDecimals(1)
            spn.setSingleStep(0.5)
            spn.setValue(band.height_mm)
            self._spins.append(spn)
            self.table.setCellWidget(row, _COL_HEIGHT, spn)

        lyt.addWidget(self.table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        lyt.addWidget(buttons)

    def _on_accept(self) -> None:
        for band, chk, spn in zip(self.template.bands, self._checks, self._spins):
            band.enabled = chk.isChecked()
            band.height_mm = round(spn.value(), 1)
        self.accept()
