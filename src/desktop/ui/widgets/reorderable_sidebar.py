"""
TOYA ERP - ReorderableSidebar

Sağ kenar paneli için: açılır/kapanır bölümleri (CollapsibleSection) taşıyan, kullanıcının bölüm başlığından
sürükleyip bırakarak sıralayabildiği ve sonucu kaydeden, ayrıca isme VE koda göre arama yapan bileşen.

  • Sürükle-bırak: bölüm başlığından tutup başka bir bölümün üstüne/altına bırakın (mavi çizgi hedefi gösterir).
  • Klavye/tık alternatifi: başlığa sağ tık → "Yukarı taşı / Aşağı taşı / Sıralamayı sıfırla".
  • Sıra `SidebarOrderStore` ile saklanır; eksik (yeni) bölümler sona eklenir.
  • Arama: bölüm başlığı, bölüm kodu, işlem adı ve işlem kodunda (Türkçe harf duyarsız) eşleşenleri gösterir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QFrame, QLineEdit, QMenu, QScrollArea, QVBoxLayout, QWidget

from src.desktop.services import settings_menu as sm
from src.desktop.ui.components.collapsible_section import CollapsibleSection

MIME = "application/x-toya-sidebar-section"


@dataclass
class _Entry:
    key: str
    section: CollapsibleSection
    code: str
    base_title: str
    items: list[tuple[QWidget, str, str]] = field(default_factory=list)   # (widget, metin, kod)
    owner_visible: bool = True
    filter_visible: bool = True


class _DropFrame(QFrame):
    dragged_over = pyqtSignal(int)      # y
    dropped = pyqtSignal(str, int)      # bölüm anahtarı, y
    left = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):  # noqa: N802
        if e.mimeData().hasFormat(MIME):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):  # noqa: N802
        if e.mimeData().hasFormat(MIME):
            e.acceptProposedAction()
            self.dragged_over.emit(int(e.position().y()))

    def dragLeaveEvent(self, e):  # noqa: N802
        self.left.emit()

    def dropEvent(self, e):  # noqa: N802
        if e.mimeData().hasFormat(MIME):
            key = bytes(e.mimeData().data(MIME)).decode("utf-8")
            e.acceptProposedAction()
            self.dropped.emit(key, int(e.position().y()))
        self.left.emit()


class ReorderableSidebar(QWidget):
    order_changed = pyqtSignal(list)

    def __init__(self, store: sm.SidebarOrderStore | None = None, parent=None, show_codes: bool = True,
                 placeholder: str = "🔍 Bölüm / işlem / kod ara…") -> None:
        super().__init__(parent)
        self.store = store
        self._show_codes = show_codes
        self._mode = "rozet" if show_codes else "ipucu"
        self._entries: dict[str, _Entry] = {}
        self._drag_start: QPoint | None = None
        self._drag_key: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText(placeholder)
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet("QLineEdit{border:1px solid #cbd5e1; border-radius:4px; padding:5px 8px; font-size:11px;"
                                  " background:white; color:#0f172a;}QLineEdit:focus{border-color:#3b82f6;}")
        self.search.textChanged.connect(self.filter)
        root.addWidget(self.search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none; background:transparent;}")
        self._frame = _DropFrame()
        self._frame.setStyleSheet("background:transparent; border:none;")
        self._lyt = QVBoxLayout(self._frame)
        self._lyt.setContentsMargins(4, 4, 4, 4)
        self._lyt.setSpacing(8)
        self._lyt.addStretch()
        scroll.setWidget(self._frame)
        root.addWidget(scroll, 1)
        self._indicator = QFrame(self._frame)
        self._indicator.setFixedHeight(3)
        self._indicator.setStyleSheet("background:#2563eb; border-radius:1px;")
        self._indicator.hide()
        self._frame.dragged_over.connect(self._show_indicator)
        self._frame.left.connect(self._indicator.hide)
        self._frame.dropped.connect(self._on_drop)

    # ------------------------------------------------------------------ bölümler
    def add_section(self, key: str, section: CollapsibleSection, code: str = "",
                    items: list[tuple[QWidget, str, str]] | None = None) -> None:
        e = _Entry(key, section, code, section.title_text, list(items or []))
        self._entries[key] = e
        section.header_btn.installEventFilter(self)
        section.header_btn.setProperty("sidebar_key", key)
        section.header_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        section.header_btn.customContextMenuRequested.connect(lambda pos, k=key: self._header_menu(k, pos))
        self._refresh_title(e)
        self._apply_saved_order()
        self._relayout()

    def set_items(self, key: str, items: list[tuple[QWidget, str, str]]) -> None:
        if key in self._entries:
            self._entries[key].items = list(items)
            for w, text, code in items:
                w.setToolTip(sm.tooltip(text, code, self._mode))
            self._apply_filter_to(self._entries[key], self.search.text())

    def set_section_visible(self, key: str, visible: bool) -> None:
        """Panele göre (ör. yalnız Döviz paneli açıkken) bölüm gizle/göster; sıra etkilenmez."""
        e = self._entries.get(key)
        if e:
            e.owner_visible = visible
            self._sync_visibility(e)

    def section(self, key: str) -> CollapsibleSection:
        return self._entries[key].section

    def keys(self) -> list[str]:
        return list(self._entries)

    def collapse_all(self, expanded: bool = False) -> None:
        for e in self._entries.values():
            e.section.set_expanded(expanded)

    def set_code_mode(self, mode: str) -> None:
        """ipucu: kod yalnız üzerine gelince; rozet: adın altında; gizli: hiç."""
        self._mode = mode
        self._show_codes = mode == "rozet"
        for e in self._entries.values():
            self._refresh_title(e)
            for w, text, code in e.items:
                if hasattr(w, "set_code_visible"):
                    w.set_code_visible(self._show_codes)
                w.setToolTip(sm.tooltip(text, code, mode))

    def _refresh_title(self, e: _Entry) -> None:
        e.section.set_code(e.code if self._show_codes else "")
        e.section.header_btn.setToolTip(sm.tooltip(e.base_title, e.code, self._mode,
                                                   "Sıralamak için başlığı sürükleyip bırakın (sağ tık: yukarı/aşağı taşı)"))

    # ------------------------------------------------------------------ sıra
    def order(self) -> list[str]:
        """Şu anki görsel sıra (gizli olanlar dahil)."""
        out = []
        for i in range(self._lyt.count()):
            w = self._lyt.itemAt(i).widget()
            for k, e in self._entries.items():
                if e.section is w:
                    out.append(k)
        return out

    def _relayout(self, order: list[str] | None = None) -> None:
        order = order or self._current_target_order
        for i in reversed(range(self._lyt.count())):
            it = self._lyt.itemAt(i)
            if it.widget() is not None:
                self._lyt.removeWidget(it.widget())
        for k in order:
            if k in self._entries:
                self._lyt.insertWidget(self._lyt.count() - 1 if self._lyt.count() else 0, self._entries[k].section)
        for e in self._entries.values():
            self._sync_visibility(e)

    @property
    def _current_target_order(self) -> list[str]:
        saved = self.store.load() if self.store else sm.DEFAULT_SIDEBAR_ORDER
        return sm.normalize_order(saved, [k for k in sm.DEFAULT_SIDEBAR_ORDER if k in self._entries] +
                                  [k for k in self._entries if k not in sm.DEFAULT_SIDEBAR_ORDER])

    def _apply_saved_order(self) -> None:
        pass  # add_section sonunda _relayout çağrılır

    def apply_order(self, order: list[str], persist: bool = True) -> None:
        avail = list(self._entries)
        order = sm.normalize_order(order, avail)
        self._relayout(order)
        if persist and self.store:
            self.store.save(order)
        self.order_changed.emit(order)

    def move(self, key: str, delta: int) -> None:
        cur = self.order()
        if key not in cur:
            return
        i = cur.index(key)
        j = max(0, min(len(cur) - 1, i + delta))
        if i != j:
            cur.insert(j, cur.pop(i))
            self.apply_order(cur)

    def reset_order(self) -> None:
        if self.store:
            self.store.reset()
        self._relayout([k for k in sm.DEFAULT_SIDEBAR_ORDER if k in self._entries] +
                       [k for k in self._entries if k not in sm.DEFAULT_SIDEBAR_ORDER])
        self.order_changed.emit(self.order())

    def _header_menu(self, key: str, pos) -> None:
        e = self._entries[key]
        m = QMenu(self)
        cur = self.order()
        up = m.addAction("⬆ Yukarı taşı", lambda: self.move(key, -1))
        up.setEnabled(cur.index(key) > 0)
        dn = m.addAction("⬇ Aşağı taşı", lambda: self.move(key, 1))
        dn.setEnabled(cur.index(key) < len(cur) - 1)
        m.addSeparator()
        m.addAction("↺ Sıralamayı varsayılana döndür", self.reset_order)
        m.addAction("📁 Tüm bölümleri kapat", lambda: self.collapse_all(False))
        m.addAction("📂 Tüm bölümleri aç", lambda: self.collapse_all(True))
        m.exec(e.section.header_btn.mapToGlobal(pos))

    # ------------------------------------------------------------------ sürükle-bırak
    def eventFilter(self, obj, ev):  # noqa: N802
        key = obj.property("sidebar_key") if hasattr(obj, "property") else None
        if key in self._entries:
            t = ev.type()
            if t == ev.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
                self._drag_start, self._drag_key = ev.position().toPoint(), key
            elif t == ev.Type.MouseMove and self._drag_start is not None and ev.buttons() & Qt.MouseButton.LeftButton:
                if (ev.position().toPoint() - self._drag_start).manhattanLength() >= 12:
                    self._start_drag(key, obj)
                    self._drag_start = None
                    return True
            elif t == ev.Type.MouseButtonRelease:
                self._drag_start = None
        return super().eventFilter(obj, ev)

    def _start_drag(self, key: str, header) -> None:
        drag = QDrag(header)
        mime = QMimeData()
        mime.setData(MIME, key.encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(header.grab())
        drag.exec(Qt.DropAction.MoveAction)
        self._indicator.hide()

    def _insertion_index(self, y: int, exclude: str | None = None) -> int:
        """`y` konumuna göre, görünür bölümler arasında hedef sıra numarası (order() listesinde)."""
        order = self.order()
        idx = 0
        for i, k in enumerate(order):
            if k == exclude:
                continue
            sec = self._entries[k].section
            if not sec.isVisibleTo(self._frame):
                continue
            mid = sec.y() + sec.height() / 2
            if y > mid:
                idx = i + 1
        return idx

    def _show_indicator(self, y: int) -> None:
        order = self.order()
        idx = self._insertion_index(y, self._drag_key)
        if idx >= len(order):
            vis = [self._entries[k].section for k in order if self._entries[k].section.isVisibleTo(self._frame)]
            ypos = (vis[-1].y() + vis[-1].height() + 2) if vis else 0
        else:
            ypos = self._entries[order[idx]].section.y() - 4
        self._indicator.setGeometry(4, max(0, ypos), max(10, self._frame.width() - 8), 3)
        self._indicator.show()
        self._indicator.raise_()

    def _on_drop(self, key: str, y: int) -> None:
        if key not in self._entries:
            return
        self.drop_at(key, y)

    def drop_at(self, key: str, y: int) -> None:
        """Bölümü `y` konumuna taşır (sürükle-bırak ve testler için)."""
        order = self.order()
        idx = self._insertion_index(y, key)
        old = order.index(key)
        order.remove(key)
        if idx > old:
            idx -= 1
        order.insert(max(0, min(len(order), idx)), key)
        self.apply_order(order)

    # ------------------------------------------------------------------ arama
    def _sync_visibility(self, e: _Entry) -> None:
        e.section.setVisible(e.owner_visible and e.filter_visible)

    def _apply_filter_to(self, e: _Entry, query: str) -> None:
        q = query.strip()
        if not q:
            for w, _t, _c in e.items:
                w.setVisible(True)
            e.filter_visible = True
            self._sync_visibility(e)
            return
        sec_hit = sm.matches(q, e.base_title, e.code)
        any_item = False
        for w, text, code in e.items:
            hit = sec_hit or sm.matches(q, text, code)
            w.setVisible(hit)
            any_item = any_item or hit
        e.filter_visible = sec_hit or any_item
        if e.filter_visible:
            e.section.set_expanded(True)
        self._sync_visibility(e)

    def filter(self, query: str) -> None:
        for e in self._entries.values():
            self._apply_filter_to(e, query)
        if not query.strip():
            self.collapse_all(False)
