"""
TOYA ERP - Görsel Tasarımcı Araç Kutusu (ToolboxWidget)
Sol paneldeki görsel nesne ekleme paleti.
"""

from __future__ import annotations

import uuid
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import ItemConfig


class ToolboxWidget(QWidget):
    """Görsel eleman ekleme paleti."""

    item_requested = pyqtSignal(object)  # ItemConfig

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        grp = QGroupBox("🧰 Araç Kutusu (Bileşenler)", self)
        grp.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; color: #1E293B; }")
        grp_layout = QGridLayout(grp)
        grp_layout.setContentsMargins(6, 12, 6, 6)
        grp_layout.setSpacing(6)

        tools = [
            ("🔤 Sabit Metin", "text", self._create_text_item),
            ("📊 Veri Alanı", "data_field", self._create_field_item),
            ("🖼️ Resim / Logo", "image", self._create_image_item),
            ("➖ Çizgi / Ayırıcı", "line", self._create_line_item),
            ("⬛ Kutu / Çerçeve", "box", self._create_box_item),
            ("📱 Barkod & QR", "barcode", self._create_barcode_item),
            ("📄 Sayfa No", "system_var", self._create_system_item),
        ]

        btn_style = """
            QPushButton {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 6px;
                text-align: left;
                font-size: 11px;
                color: #0F172A;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                border-color: #94A3B8;
            }
            QPushButton:pressed {
                background-color: #CBD5E1;
            }
        """

        row = 0
        for label, code, factory in tools:
            btn = QPushButton(label, grp)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(factory)
            grp_layout.addWidget(btn, row, 0)
            row += 1

        layout.addWidget(grp)
        layout.addStretch()

    def _generate_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:6]}"

    def _create_text_item(self):
        cfg = ItemConfig(
            id=self._generate_id("txt"),
            type="text",
            text="Sabit Başlık Metni",
            x_mm=10.0,
            y_mm=2.0,
            w_mm=40.0,
            h_mm=6.0,
            font_size=9,
            font_bold=True,
        )
        self.item_requested.emit(cfg)

    def _create_field_item(self):
        cfg = ItemConfig(
            id=self._generate_id("fld"),
            type="data_field",
            field="belge.teklif_no",
            x_mm=10.0,
            y_mm=2.0,
            w_mm=35.0,
            h_mm=6.0,
            font_size=8,
        )
        self.item_requested.emit(cfg)

    def _create_image_item(self):
        cfg = ItemConfig(
            id=self._generate_id("img"),
            type="image",
            field="sirket.logo",
            x_mm=5.0,
            y_mm=2.0,
            w_mm=35.0,
            h_mm=15.0,
        )
        self.item_requested.emit(cfg)

    def _create_line_item(self):
        cfg = ItemConfig(
            id=self._generate_id("line"),
            type="line",
            x_mm=0.0,
            y_mm=5.0,
            w_mm=190.0,
            h_mm=0.0,
            border_color="#CBD5E1",
            border_width=0.5,
        )
        self.item_requested.emit(cfg)

    def _create_box_item(self):
        cfg = ItemConfig(
            id=self._generate_id("box"),
            type="box",
            x_mm=5.0,
            y_mm=2.0,
            w_mm=50.0,
            h_mm=15.0,
            bg_color="#F8FAFC",
            border_color="#E2E8F0",
            border_width=0.5,
            corner_radius=2.0,
        )
        self.item_requested.emit(cfg)

    def _create_barcode_item(self):
        cfg = ItemConfig(
            id=self._generate_id("qr"),
            type="barcode",
            field="belge.gib_karekod_data",
            barcode_format="qrcode",
            x_mm=160.0,
            y_mm=2.0,
            w_mm=20.0,
            h_mm=20.0,
        )
        self.item_requested.emit(cfg)

    def _create_system_item(self):
        cfg = ItemConfig(
            id=self._generate_id("sys"),
            type="system_var",
            field="sistem.sayfa_no",
            x_mm=70.0,
            y_mm=2.0,
            w_mm=40.0,
            h_mm=5.0,
            font_size=8,
            align="center",
            text_color="#94A3B8",
        )
        self.item_requested.emit(cfg)
