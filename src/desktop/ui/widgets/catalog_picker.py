"""
TOYA ERP - Paylaşılan Değer Kataloğu (CatalogSearchField)

Stok kartı gibi ekranlarda "Ana Kategori", "Birim", "Özel Kod" gibi alanlara
her seferinde serbest metin yazmak yerine, önceden kaydedilmiş ortak bir
listeden seçim yapılmasını sağlar — aksi halde her stok kartı için aynı
değer farklı yazımlarla tekrar tekrar girilir ve raporlanamaz hale gelir.

Katalog verisi `SystemSetting` üzerinde `katalog:<catalog_key>` anahtarıyla
JSON liste olarak saklanır; bu nedenle tüm kartlar (Stok, Cari, Görev...)
aynı `catalog_key` ile aynı listeyi paylaşabilir.

Kullanım (DefinitionEditorScreen alan şeması içinde):
    {"key": "category", "type": "catalog_search",
     "catalog_key": "urun.kategori.ana", "db_session": db,
     "defaults": ["Elektronik", "Gıda", ...]}

Programatik kullanım:
    from src.desktop.ui.widgets.catalog_picker import open_catalog_picker
    value = open_catalog_picker(parent, db, "urun.birim", current_text="Adet")
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import settings_store

_SEARCH_BTN_QSS = (
    "QPushButton{background:#2563eb;color:#fff;border:none;border-radius:4px;font-size:11px;}"
    "QPushButton:hover{background:#1d4ed8;}QPushButton:pressed{background:#1e40af;}"
)


def _magnifier_icon(size: int = 14, color: str = "#ffffff") -> QIcon:
    """Emoji büyüteç yerine mavi buton üzerinde her zaman beyaz görünen,
    QPainter ile çizilmiş sade büyüteç ikonu döndürür."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    d = size * 0.58
    p.drawEllipse(QRectF(1.0, 1.0, d, d))
    p.drawLine(QPointF(d * 0.82, d * 0.82), QPointF(size - 1.4, size - 1.4))
    p.end()
    return QIcon(pm)


def make_search_button(*, width: int = 22, tooltip: str = "") -> QPushButton:
    """Katalog/arama alanlarında kullanılan standart mavi kutu + beyaz büyüteç
    butonu. Tüm 'listeden seç' alanlarında aynı görünümü paylaşmak için
    tek yerden üretilir."""
    btn = QPushButton()
    btn.setIcon(_magnifier_icon())
    btn.setIconSize(QSize(13, 13))
    btn.setFixedWidth(width)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(_SEARCH_BTN_QSS)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def _setting_key(catalog_key: str) -> str:
    return f"katalog:{catalog_key}"


def load_catalog(db, catalog_key: str, defaults: list[str] | None = None) -> list[str]:
    """Katalogdaki değerleri döndürür; ilk çağrıda `defaults` ile tohumlar."""
    if not db:
        return list(defaults or [])
    items = settings_store.get_json(db, _setting_key(catalog_key), None)
    if items is None:
        items = list(defaults or [])
        if items:
            save_catalog(db, catalog_key, items)
    return list(items or [])


def save_catalog(db, catalog_key: str, items: list[str]) -> None:
    if db:
        settings_store.set_setting(db, _setting_key(catalog_key), json.dumps(items, ensure_ascii=False))


def open_catalog_picker(
    parent, db, catalog_key: str, current_text: str = "", *,
    defaults: list[str] | None = None, title: str = "Kayıtlı Değerler",
) -> str | None:
    """Katalog seçim/yönetim penceresini açar. Seçilen/eklenen değeri döndürür,
    iptal edilirse `None` döner."""
    items = load_catalog(db, catalog_key, defaults)

    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(340, 380)
    lyt = QVBoxLayout(dlg)

    lst = QListWidget()
    lst.addItems(items)
    if current_text:
        matches = lst.findItems(current_text, Qt.MatchFlag.MatchExactly)
        if matches:
            lst.setCurrentItem(matches[0])
    lyt.addWidget(lst, 1)

    add_row = QHBoxLayout()
    txt_new = QLineEdit(current_text)
    txt_new.setPlaceholderText("Yeni değer…")
    btn_add = QPushButton("➕ Ekle")
    add_row.addWidget(txt_new, 1)
    add_row.addWidget(btn_add)
    lyt.addLayout(add_row)

    btn_del = QPushButton("🗑 Seçileni Sil")
    lyt.addWidget(btn_del)

    def add_item():
        t = txt_new.text().strip()
        if not t:
            return
        if t not in items:
            items.append(t)
            lst.addItem(t)
            save_catalog(db, catalog_key, items)
        matches = lst.findItems(t, Qt.MatchFlag.MatchExactly)
        if matches:
            lst.setCurrentItem(matches[0])

    def del_item():
        row = lst.currentRow()
        if row < 0:
            return
        val = lst.item(row).text()
        items.remove(val)
        lst.takeItem(row)
        save_catalog(db, catalog_key, items)

    btn_add.clicked.connect(add_item)
    btn_del.clicked.connect(del_item)
    lst.itemDoubleClicked.connect(lambda _it: dlg.accept())

    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    lyt.addWidget(box)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    cur = lst.currentItem()
    if cur:
        return cur.text()
    return txt_new.text().strip() or None


class CatalogSearchField(QWidget):
    """QLineEdit + mavi 🔍 butonu; buton paylaşılan katalog seçim/yönetim
    penceresini açar (bkz. `open_catalog_picker`)."""

    #: Metin elle yazılıp yazım bitirildiğinde ya da katalogdan bir değer
    #: seçildiğinde yayınlanır — dinleyiciler `.text()` yerine bu sinyali
    #: kullanarak hem klavye hem katalog seçimini tek yerden yakalayabilir.
    changed = pyqtSignal(str)

    def __init__(self, *, catalog_key: str, db_session=None, defaults: list[str] | None = None,
                 placeholder: str = "", title: str = "Kayıtlı Değerler", parent=None):
        super().__init__(parent)
        self._catalog_key = catalog_key
        self._db = db_session
        self._defaults = defaults
        self._title = title
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(3)
        self.edit = QLineEdit()
        if placeholder:
            self.edit.setPlaceholderText(placeholder)
        self.edit.editingFinished.connect(lambda: self.changed.emit(self.edit.text()))
        btn = make_search_button(tooltip="Kayıtlı değerlerden seç")
        btn.clicked.connect(self._open_picker)
        lyt.addWidget(self.edit, 1)
        lyt.addWidget(btn)

    def _open_picker(self) -> None:
        chosen = open_catalog_picker(
            self, self._db, self._catalog_key, self.edit.text().strip(),
            defaults=self._defaults, title=self._title,
        )
        if chosen is not None:
            self.edit.setText(chosen)
            self.changed.emit(chosen)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, value) -> None:  # noqa: N802
        self.edit.setText("" if value is None else str(value))
