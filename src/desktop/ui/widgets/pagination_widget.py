"""
ToyaUI — PaginationWidget
Tüm liste ve veri tabloları için bağımsız sayfalama (pagination) bileşeni.
"""

import math

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class PaginationWidget(QWidget):
    """Bağımsız ve yeniden kullanılabilir sayfalama (pagination) çubuğu bileşeni."""

    page_changed = pyqtSignal(int)        # Sayfa numarası değiştiğinde tetiklenir (1-indexed)
    page_size_changed = pyqtSignal(int)   # Sayfa başına kayıt adedi değiştiğinde tetiklenir

    def __init__(
        self,
        page_sizes: list[int] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self._page_sizes = page_sizes if page_sizes is not None else [25, 50, 100]
        self._current_page = 1
        self._current_page_size = self._page_sizes[0] if self._page_sizes else 25
        self._total_records = 0
        self._total_pages = 1

        self.init_ui()

    def init_ui(self):
        """Arayüz bileşenlerini ve buton stillerini oluşturur."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        btn_style = """
            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #ffffff;
                color: #334155;
                font-weight: bold;
                font-size: 11px;
                min-width: 28px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QPushButton:disabled {
                background-color: #f8fafc;
                color: #cbd5e1;
                border-color: #e2e8f0;
            }
        """

        combo_style = """
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 6px;
                background-color: white;
                color: #0f172a;
                font-size: 11px;
                min-height: 22px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #94a3b8;
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
        """

        # İlk sayfa butonu (⏮️)
        self.btn_first_page = QPushButton("⏮️")
        self.btn_first_page.setToolTip("İlk Sayfa")
        self.btn_first_page.setStyleSheet(btn_style)
        self.btn_first_page.clicked.connect(self.go_to_first_page)

        # Önceki sayfa butonu (⬅️)
        self.btn_prev_page = QPushButton("⬅️")
        self.btn_prev_page.setToolTip("Önceki Sayfa")
        self.btn_prev_page.setStyleSheet(btn_style)
        self.btn_prev_page.clicked.connect(self.go_to_prev_page)

        # Sayfa bilgisi etiketi
        self.lbl_page_info = QLabel("Sayfa 1 / 1 (Toplam: 0)")
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")

        # Sonraki sayfa butonu (➡️)
        self.btn_next_page = QPushButton("➡️")
        self.btn_next_page.setToolTip("Sonraki Sayfa")
        self.btn_next_page.setStyleSheet(btn_style)
        self.btn_next_page.clicked.connect(self.go_to_next_page)

        # Son sayfa butonu (⏭️)
        self.btn_last_page = QPushButton("⏭️")
        self.btn_last_page.setToolTip("Son Sayfa")
        self.btn_last_page.setStyleSheet(btn_style)
        self.btn_last_page.clicked.connect(self.go_to_last_page)

        # Sayfa boyutu seçim kutusu (Adet)
        self.lbl_size_title = QLabel("Adet:")
        self.lbl_size_title.setStyleSheet("color: #475569; font-size: 11px; font-weight: bold;")

        self.combo_page_size = QComboBox()
        self.combo_page_size.setStyleSheet(combo_style)
        for size in self._page_sizes:
            self.combo_page_size.addItem(f"{size} kayıt", size)
        self.combo_page_size.currentIndexChanged.connect(self._on_combo_size_changed)

        layout.addWidget(self.btn_first_page)
        layout.addWidget(self.btn_prev_page)
        layout.addWidget(self.lbl_page_info)
        layout.addWidget(self.btn_next_page)
        layout.addWidget(self.btn_last_page)
        layout.addStretch()
        layout.addWidget(self.lbl_size_title)
        layout.addWidget(self.combo_page_size)

        self._update_ui_state()

    def set_total(self, total_records: int):
        """Toplam kayıt sayısını belirler ve sayfa sayısını günceller."""
        self._total_records = max(0, total_records)
        self._total_pages = max(1, math.ceil(self._total_records / self._current_page_size)) if self._total_records > 0 else 1

        if self._current_page > self._total_pages:
            self._current_page = self._total_pages

        self._update_ui_state()

    def current_page(self) -> int:
        """Mevcut aktif sayfa numarasını döndürür (1-indexed)."""
        return self._current_page

    def current_page_size(self) -> int:
        """Mevcut seçili sayfa boyutu adedini döndürür."""
        return self._current_page_size

    def reset(self):
        """Sayfalama durumunu 1. sayfaya sıfırlar."""
        if self._current_page != 1:
            self._current_page = 1
            self._update_ui_state()
            self.page_changed.emit(self._current_page)
        else:
            self._update_ui_state()

    def set_current_page(self, page: int):
        """Belirtilen sayfaya geçiş yapar."""
        target_page = max(1, min(self._total_pages, page))
        if target_page != self._current_page:
            self._current_page = target_page
            self._update_ui_state()
            self.page_changed.emit(self._current_page)

    def go_to_first_page(self):
        """İlk sayfaya gider."""
        if self._current_page > 1:
            self._current_page = 1
            self._update_ui_state()
            self.page_changed.emit(self._current_page)

    def go_to_prev_page(self):
        """Bir önceki sayfaya gider."""
        if self._current_page > 1:
            self._current_page -= 1
            self._update_ui_state()
            self.page_changed.emit(self._current_page)

    def go_to_next_page(self):
        """Bir sonraki sayfaya gider."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._update_ui_state()
            self.page_changed.emit(self._current_page)

    def go_to_last_page(self):
        """Son sayfaya gider."""
        if self._current_page < self._total_pages:
            self._current_page = self._total_pages
            self._update_ui_state()
            self.page_changed.emit(self._current_page)

    def _on_combo_size_changed(self, index: int):
        """Sayfa boyutu değiştiğinde tetiklenir."""
        new_size = self.combo_page_size.itemData(index)
        if new_size and new_size != self._current_page_size:
            self._current_page_size = int(new_size)
            # Sayfa adedini yeniden hesapla
            self._total_pages = max(1, math.ceil(self._total_records / self._current_page_size)) if self._total_records > 0 else 1
            self._current_page = 1  # Sayfa boyutu değişince 1. sayfaya dön
            self._update_ui_state()
            self.page_size_changed.emit(self._current_page_size)
            self.page_changed.emit(self._current_page)

    def _update_ui_state(self):
        """Butonların aktiflik durumunu ve sayfa bilgi etiketini günceller."""
        self.lbl_page_info.setText(
            f"Sayfa {self._current_page} / {self._total_pages} (Toplam: {self._total_records})",
        )

        can_go_back = self._current_page > 1
        can_go_forward = self._current_page < self._total_pages

        self.btn_first_page.setEnabled(can_go_back)
        self.btn_prev_page.setEnabled(can_go_back)
        self.btn_next_page.setEnabled(can_go_forward)
        self.btn_last_page.setEnabled(can_go_forward)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = PaginationWidget(page_sizes=[10, 25, 50])
    widget.set_total(243)

    widget.page_changed.connect(lambda p: print(f"✅ Sayfa değişti: {p}"))
    widget.page_size_changed.connect(lambda s: print(f"✅ Sayfa boyutu değişti: {s}"))

    widget.show()
    print("Mevcut sayfa:", widget.current_page())
    print("Mevcut sayfa boyutu:", widget.current_page_size())
    widget.go_to_next_page()
    sys.exit(0)
