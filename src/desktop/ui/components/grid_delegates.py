"""TOYA ERP - AppGrid hücre editörleri: klavye gezinmeli temel sınıf, tarih seçici ve takvim stili.

`NavDelegate` editörde Enter / Tab / Shift+Tab tuşlarını yakalar, hücreyi kaydeder ve `AppGrid.navigate()` ile bir sonraki
düzenlenebilir hücreye geçer (bkz. `AppGrid.enable_enter_navigation`). Tarih hücreleri `DateDelegate` ile takvimli
tarih seçiciyle düzenlenir; takvim açılır penceresi açık renk (okunaklı) stillidir.
"""

from __future__ import annotations

from PyQt6.QtCore import QDate, QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import (
    QAbstractItemDelegate,
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QLineEdit,
    QStyledItemDelegate,
)

#: Takvim açılır penceresi: uygulama teması koyu/turkuaz olsa da beyaz zemin, koyu yazı, mavi gezinme çubuğu.
CALENDAR_QSS = """
QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #1e3a8a; }
QCalendarWidget QToolButton { color: #ffffff; background-color: transparent; border: none; border-radius: 4px;
                              padding: 3px 8px; font-weight: 700; icon-size: 16px; }
QCalendarWidget QToolButton:hover { background-color: #2563eb; }
QCalendarWidget QToolButton::menu-indicator { image: none; }
QCalendarWidget QMenu { background-color: #ffffff; color: #1e293b; }
QCalendarWidget QMenu::item:selected { background-color: #dbeafe; color: #1e3a8a; }
QCalendarWidget QSpinBox { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1;
                           selection-background-color: #2563eb; selection-color: #ffffff; }
QCalendarWidget QAbstractItemView:enabled { background-color: #ffffff; color: #1e293b; outline: 0;
                                            selection-background-color: #2563eb; selection-color: #ffffff; }
QCalendarWidget QAbstractItemView:disabled { color: #94a3b8; }
QCalendarWidget QAbstractItemView { font-size: 12px; }
QCalendarWidget QAbstractItemView::item { padding: 0px; }
QCalendarWidget QHeaderView::section { padding: 0px; background-color: #f1f5f9; color: #334155; border: none; font-weight: 600; }
"""


def apply_calendar_style(date_edit: QDateEdit) -> None:
    """QDateEdit'i takvim açılır pencereli yapar ve takvimi okunaklı açık renklere boyar."""
    date_edit.setCalendarPopup(True)
    cal = date_edit.calendarWidget()
    if cal is not None:
        cal.setStyleSheet(CALENDAR_QSS)
        cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        cal.setMinimumSize(250, 200)                     # gün adları kırpılmasın
        for gun in (Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday, Qt.DayOfWeek.Wednesday, Qt.DayOfWeek.Thursday, Qt.DayOfWeek.Friday):
            cal.setWeekdayTextFormat(gun, _gun_bicimi("#1e293b"))
        for gun in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            cal.setWeekdayTextFormat(gun, _gun_bicimi("#dc2626"))    # hafta sonu okunaklı kırmızı


def _gun_bicimi(renk: str) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(renk))
    return f


class NavDelegate(QStyledItemDelegate):
    """Editörde Enter/Tab/Shift+Tab ile kaydedip sıradaki düzenlenebilir hücreye geçen temel delegate."""

    def _grid(self):
        return self.parent()

    def eventFilter(self, editor, event):  # noqa: N802
        grid = self._grid()
        if getattr(grid, "_enter_nav", False) and event.type() == QEvent.Type.KeyPress \
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            comp = editor.completer() if isinstance(editor, QLineEdit) else None
            if comp is not None and comp.popup() is not None and comp.popup().isVisible():
                return super().eventFilter(editor, event)        # açık öneri listesinde Enter, öneriyi seçer
            step = -1 if event.key() == Qt.Key.Key_Backtab else 1
            onayla = getattr(editor, "commit_expression", None)
            if onayla is not None and not onayla():          # para alanı: geçersiz işlem varsa hücreden çıkma
                return True
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)
            QTimer.singleShot(0, lambda: grid.navigate(step))
            return True
        return super().eventFilter(editor, event)


class ComboDelegate(NavDelegate):
    """Hücreyi açılır liste ile düzenletir; liste öğeleri sola dayalı, boşluksuzdur (`combobox-popup: 0` standardı)."""

    _QSS = ("QComboBox { combobox-popup: 0; padding: 0px 4px; }"
            " QComboBox QAbstractItemView { padding: 0px; }"
            " QComboBox QAbstractItemView::item { padding: 2px 4px; margin: 0px; min-height: 20px; }")

    _VIEW_QSS = ("QListView { background-color: #ffffff; color: #1e293b; outline: 0; padding: 0px; }"
                 " QListView::item { padding: 3px 4px; min-height: 20px; }"
                 " QListView::item:selected { background-color: #dbeafe; color: #1e3a8a; }")

    def __init__(self, options, parent=None) -> None:
        super().__init__(parent)
        self._options = options       # çağrılabilir: seçenek metinlerini döner

    def createEditor(self, parent, _option, _index):  # noqa: N802
        cmb = QComboBox(parent)
        cmb.setStyleSheet(self._QSS)
        cmb.setItemDelegate(QStyledItemDelegate(cmb))      # tema/Qt'nin öğe başına ayırdığı sol boşluğu kaldırır
        cmb.view().setStyleSheet(self._VIEW_QSS)
        cmb.addItems(self._options())
        return cmb

    def setEditorData(self, editor, index):  # noqa: N802
        editor.setCurrentIndex(max(editor.findText(index.data() or ""), 0))

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, editor.currentText())

    def sizeHint(self, option, index):  # noqa: N802
        s = super().sizeHint(option, index)
        return QSize(s.width(), max(s.height(), 24))


class MoneyDelegate(NavDelegate):
    """Parasal hücre: `MoneyEdit` ile düzenlenir (yazarken binlik nokta, virgülle kuruş, + - * / hesap makinesi;
    Enter sonucu hücreye aktarır)."""

    _QSS = ("QLineEdit { background: #ffffff; color: #0f172a; border: 1px solid #2563eb; padding: 0px 4px;"
            " selection-background-color: #bfdbfe; selection-color: #0f172a; }")

    def __init__(self, decimals: int = 2, allow_empty: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.decimals, self.allow_empty = decimals, allow_empty

    def createEditor(self, parent, _option, _index):  # noqa: N802
        from src.desktop.ui.widgets.money_edit import MoneyEdit
        ed = MoneyEdit(decimals=self.decimals, allow_empty=self.allow_empty, parent=parent)
        ed.setStyleSheet(self._QSS)
        return ed

    def setEditorData(self, editor, index):  # noqa: N802
        editor.setText(index.data() or "")
        editor.selectAll()

    def setModelData(self, editor, model, index):  # noqa: N802
        if editor.commit_expression():
            model.setData(index, editor.text())


class DateDelegate(NavDelegate):
    """Tarih hücresini takvimli tarih seçici ile düzenletir; metin `gg.aa.yyyy` biçimindedir."""

    FORMAT = "dd.MM.yyyy"

    def createEditor(self, parent, _option, _index):  # noqa: N802
        ed = QDateEdit(parent)
        ed.setDisplayFormat(self.FORMAT)
        apply_calendar_style(ed)
        return ed

    def setEditorData(self, editor, index):  # noqa: N802
        d = QDate.fromString((index.data() or "").strip(), self.FORMAT)
        editor.setDate(d if d.isValid() else QDate.currentDate())

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, editor.date().toString(self.FORMAT))
