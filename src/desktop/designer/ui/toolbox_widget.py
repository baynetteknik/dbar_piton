"""
TOYA ERP - Görsel Tasarımcı Araç Kutusu (ToolboxWidget)
Sol paneldeki görsel nesne ekleme paleti.

Her buton hem tıklanarak (seçili nesnenin bandına varsayılan konumda) hem de
sürükle-bırak ile tuval üzerindeki istenen banda, istenen konuma bırakılabilir.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import Callable

from PyQt6.QtCore import QMimeData, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import MIME_ITEM_CONFIG, ItemConfig


class _ToolboxButton(QPushButton):
    """Tıklanabilir VE sürüklenebilir araç kutusu butonu.

    Basit bir tık, eskisi gibi seçili nesnenin bandına varsayılan konumda ekler
    (``clicked`` sinyali dışarıdan bağlanır). Fare basılıyken sürükleme
    mesafesi aşılırsa bunun yerine bir QDrag başlatılır; tuval üzerine
    bırakıldığında eleman tam bırakılan konuma yerleşir.
    """

    def __init__(self, label: str, factory: Callable[[], ItemConfig], parent=None):
        super().__init__(label, parent)
        self.factory = factory
        self._press_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._press_pos is not None
            and bool(event.buttons() & Qt.MouseButton.LeftButton)
            and (event.pos() - self._press_pos).manhattanLength()
            > QApplication.startDragDistance()
        ):
            self._press_pos = None
            self._start_drag()
            return
        super().mouseMoveEvent(event)

    def _start_drag(self):
        cfg = self.factory()
        mime = QMimeData()
        mime.setData(
            MIME_ITEM_CONFIG,
            json.dumps(dataclasses.asdict(cfg)).encode("utf-8"),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


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
            ("🔤 Sabit Metin", self._make_text_item),
            ("📊 Veri Alanı", self._make_field_item),
            ("🖼️ Resim / Logo", self._make_image_item),
            ("➖ Çizgi / Ayırıcı", self._make_line_item),
            ("⬛ Kutu / Çerçeve", self._make_box_item),
            ("📱 Barkod & QR", self._make_barcode_item),
            ("📄 Sayfa No", self._make_system_item),
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
        for label, factory in tools:
            btn = _ToolboxButton(label, factory, grp)
            btn.setStyleSheet(btn_style)
            btn.setToolTip("Tıklayarak ekleyin veya tuval üzerine sürükleyip bırakın.")
            btn.clicked.connect(lambda _c=False, f=factory: self.item_requested.emit(f()))
            grp_layout.addWidget(btn, row, 0)
            row += 1

        layout.addWidget(grp)
        layout.addStretch()

    def _generate_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:6]}"

    def _make_text_item(self) -> ItemConfig:
        return ItemConfig(
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

    def _make_field_item(self) -> ItemConfig:
        return ItemConfig(
            id=self._generate_id("fld"),
            type="data_field",
            field="belge.teklif_no",
            x_mm=10.0,
            y_mm=2.0,
            w_mm=35.0,
            h_mm=6.0,
            font_size=8,
        )

    def _make_image_item(self) -> ItemConfig:
        return ItemConfig(
            id=self._generate_id("img"),
            type="image",
            field="firma.logo_base64",
            x_mm=5.0,
            y_mm=2.0,
            w_mm=35.0,
            h_mm=15.0,
        )

    def _make_line_item(self) -> ItemConfig:
        return ItemConfig(
            id=self._generate_id("line"),
            type="line",
            x_mm=0.0,
            y_mm=5.0,
            w_mm=190.0,
            h_mm=0.0,
            border_color="#CBD5E1",
            border_width=0.5,
        )

    def _make_box_item(self) -> ItemConfig:
        return ItemConfig(
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

    def _make_barcode_item(self) -> ItemConfig:
        return ItemConfig(
            id=self._generate_id("qr"),
            type="barcode",
            field="belge.gib_karekod_data",
            barcode_format="qrcode",
            x_mm=160.0,
            y_mm=2.0,
            w_mm=20.0,
            h_mm=20.0,
        )

    def _make_system_item(self) -> ItemConfig:
        return ItemConfig(
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
