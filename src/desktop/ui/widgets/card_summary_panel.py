"""
TOYA ERP - CardSummaryPanel

Tanım/kart ekranlarının sağ "Özet Bilgi" paneli: büyük bir KPI sayısı,
etiket/değer satırları ve gömülü resim yükleme alanı.

`DefinitionEditorScreen(summary_widget=CardSummaryPanel(...))` ile kullanılır;
editör her alan değişiminde `update_from(form_data)` çağırır (varsa `updater`).

Kullanım:
    panel = CardSummaryPanel(title="Özet Bilgi", image_key="image_path")
    panel.set_updater(lambda d: panel.set_kpi("Toplam Stok Miktarı", d.get("stock", 0)))
    editor = DefinitionEditorScreen(..., summary_widget=panel)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from src.desktop.ui.screens.definition_editor_screen import _ImageField


class CardSummaryPanel(QWidget):
    def __init__(self, title: str = "Özet Bilgi", *, image_key: str | None = None,
                 image_size: tuple[int, int] = (120, 64), image_title: str = "🖼 Görsel",
                 parent=None) -> None:
        super().__init__(parent)
        self.image_key = image_key
        self._image_size = image_size
        self._image_title = image_title
        self._updater = None
        self._build_ui(title)

    def _build_ui(self, title: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        box = QFrame()
        box.setObjectName("SummaryBox")
        box.setStyleSheet(
            "#SummaryBox{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;}",
        )
        inner = QVBoxLayout(box)
        inner.setContentsMargins(0, 0, 12, 12)
        inner.setSpacing(8)

        hdr = QLabel("▾ " + title)
        hdr.setStyleSheet(
            "background:#2563eb;color:#fff;font-size:11px;font-weight:800;padding:5px 10px;"
            "border-top-left-radius:8px;border-top-right-radius:8px;",
        )
        inner.addWidget(hdr)

        self.lbl_kpi_label = QLabel("")
        self.lbl_kpi_label.setStyleSheet("color:#475569;font-size:11px;padding:0 12px;")
        self.lbl_kpi_value = QLabel("—")
        self.lbl_kpi_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_kpi_value.setStyleSheet("color:#0f172a;font-size:30px;font-weight:800;")
        inner.addWidget(self.lbl_kpi_label)
        inner.addWidget(self.lbl_kpi_value)

        self._rows_host = QWidget()
        self._rows_grid = QGridLayout(self._rows_host)
        self._rows_grid.setContentsMargins(12, 4, 4, 4)
        self._rows_grid.setHorizontalSpacing(8)
        self._rows_grid.setVerticalSpacing(4)
        inner.addWidget(self._rows_host)

        # Görsel + ekstra bilgiler (ör. "E-ticarette yayında"), tek başlıklı kutuda.
        img_box = QFrame()
        img_box.setStyleSheet(
            "QFrame{border:1px solid #bfdbfe;border-radius:8px;background:#f8fafc;}",
        )
        img_box_lyt = QVBoxLayout(img_box)
        img_box_lyt.setContentsMargins(0, 0, 0, 10)
        img_box_lyt.setSpacing(8)

        img_hdr = QLabel(self._image_title)
        img_hdr.setStyleSheet(
            "background:#2563eb;color:#fff;font-size:11px;font-weight:800;padding:5px 10px;"
            "border-top-left-radius:8px;border-top-right-radius:8px;",
        )
        img_box_lyt.addWidget(img_hdr)

        self._extra_host = QWidget()
        self._extra_lyt = QVBoxLayout(self._extra_host)
        self._extra_lyt.setContentsMargins(10, 0, 10, 0)
        self._extra_lyt.setSpacing(6)
        img_box_lyt.addWidget(self._extra_host)

        if self.image_key is not None:
            img_inner = QWidget()
            img_lyt = QVBoxLayout(img_inner)
            img_lyt.setContentsMargins(10, 0, 10, 0)
            self.image_field = _ImageField(preview_size=self._image_size, buttons_below=True)
            img_lyt.addWidget(self.image_field)
            img_box_lyt.addWidget(img_inner)
        else:
            self.image_field = None

        inner.addSpacing(4)
        inner.addWidget(img_box)

        root.addWidget(box)
        root.addStretch()

    # ------------------------------------------------------------------
    def set_kpi(self, label: str, value) -> None:
        self.lbl_kpi_label.setText(label)
        self.lbl_kpi_value.setText(str(value))

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        while self._rows_grid.count():
            item = self._rows_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, (k, v) in enumerate(rows):
            lk = QLabel(str(k))
            lk.setStyleSheet("color:#64748b;font-size:11px;")
            lv = QLabel(str(v))
            lv.setStyleSheet("color:#1e293b;font-size:11px;font-weight:700;")
            lv.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._rows_grid.addWidget(lk, i, 0)
            self._rows_grid.addWidget(lv, i, 1)

    def add_extra_widget(self, widget: QWidget) -> None:
        """Özet paneline, görselden önce ekstra bir alan (ör. Diğer Bilgiler) ekler."""
        self._extra_lyt.addWidget(widget)

    def image_value(self):
        return self.image_field.value() if self.image_field else None

    def set_image_value(self, val) -> None:
        if self.image_field:
            self.image_field.set_value(val)

    # ------------------------------------------------------------------
    def set_updater(self, fn) -> None:
        """fn(form_data: dict) -> None — editör alan değişiminde çağırır."""
        self._updater = fn

    def update_from(self, data: dict) -> None:
        if callable(self._updater):
            self._updater(data)
