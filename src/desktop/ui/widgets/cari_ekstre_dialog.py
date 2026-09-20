"""
TOYA ERP - CariEkstreDialog

`CariEkstreWidget`'i saran ince modal kabuk. Cari kartından, cari listesinden
ve teklif ekranındaki "💳 BAKİYE" düğmesinden açılır.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout

from src.desktop.ui.widgets.cari_ekstre_widget import CariEkstreWidget


class CariEkstreDialog(QDialog):
    def __init__(self, db_session=None, customer_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cari Ekstresi / Hareketler")
        self.setModal(True)
        self.resize(760, 520)

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.widget = CariEkstreWidget(db_session=db_session)
        lyt.addWidget(self.widget)
        self.widget.set_customer(customer_id)
