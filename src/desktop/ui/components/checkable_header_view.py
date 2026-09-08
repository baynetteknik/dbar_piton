"""
TOYA ERP - CheckableHeaderView

Bir tabloda tek bir "seçim" kolonunun başlığına üç durumlu (boş / kısmi / dolu)
bir onay kutusu çizen QHeaderView alt sınıfı. O kolonda başlık tıklaması
sıralama tetiklemez; sadece "tümünü seç / tümünü bırak" davranışı üretir.

Tamamen opt-in: yalnızca FilterableTableView'e select_column verildiğinde takılır,
verilmeyen ekranlar için hiçbir davranış değişmez.
"""

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import QHeaderView, QStyle, QStyleOptionButton


class CheckableHeaderView(QHeaderView):
    """Seçim kolonunun başlığında üç durumlu onay kutusu gösteren yatay başlık."""

    #: Kullanıcı başlıktaki kutuya tıkladığında yayılır. True = hepsini seç.
    select_all_toggled = pyqtSignal(bool)

    def __init__(self, orientation, select_column: int = 0, parent=None):
        super().__init__(orientation, parent)
        self.select_column = select_column
        self._check_state = Qt.CheckState.Unchecked
        self.setSectionsClickable(True)
        self.setHighlightSections(False)

    # ------------------------------------------------------------------
    # Dış API
    # ------------------------------------------------------------------
    def set_check_state(self, state: Qt.CheckState) -> None:
        """Başlık kutusunun görünümünü günceller (sinyal yaymaz)."""
        if self._check_state != state:
            self._check_state = state
            self.updateSection(self.select_column)

    def check_state(self) -> Qt.CheckState:
        return self._check_state

    # ------------------------------------------------------------------
    # Çizim
    # ------------------------------------------------------------------
    def paintSection(self, painter, rect, logical_index):  # noqa: N802
        painter.save()
        super().paintSection(painter, rect, logical_index)
        painter.restore()

        if logical_index != self.select_column:
            return

        opt = QStyleOptionButton()
        size = 15
        cx = rect.x() + (rect.width() - size) // 2
        cy = rect.y() + (rect.height() - size) // 2
        opt.rect = QRect(cx, cy, size, size)
        opt.state = QStyle.StateFlag.State_Enabled
        if self._check_state == Qt.CheckState.Checked:
            opt.state |= QStyle.StateFlag.State_On
        elif self._check_state == Qt.CheckState.PartiallyChecked:
            opt.state |= QStyle.StateFlag.State_NoChange
        else:
            opt.state |= QStyle.StateFlag.State_Off

        self.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorCheckBox, opt, painter, self,
        )

    # ------------------------------------------------------------------
    # Fare - seçim kolonunda sıralamayı yut, kutuyu çevir
    # ------------------------------------------------------------------
    def _is_select_section(self, pos) -> bool:
        return self.logicalIndexAt(pos) == self.select_column

    def mousePressEvent(self, event):  # noqa: N802
        if self._is_select_section(event.pos()):
            want_checked = self._check_state != Qt.CheckState.Checked
            self.set_check_state(
                Qt.CheckState.Checked if want_checked else Qt.CheckState.Unchecked,
            )
            self.select_all_toggled.emit(want_checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        # Sıralama mouse-release üzerinde tetiklenir; seçim kolonunda engelle.
        if self._is_select_section(event.pos()):
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if self._is_select_section(event.pos()):
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
