"""
TOYA ERP - AppGrid Sınıfı
Kurumsal ERP mimarisinin DEĞİŞMEZ temel liste/tablo bileşenidir.
Doğrudan QTableWidget kullanmak yasaktır; tüm tablolar AppGrid'den türetilir.
Merkezi ThemeManager'a bağlıdır ve isteğe bağlı ekran bazlı özel başlık yüksekliği (custom_header_height)
ve veri satır yüksekliği (custom_row_height) ayarlarını destekler.
"""

from typing import Any

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemDelegate,
    QApplication,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from src.desktop.core.grid_presets import get_preset
from src.desktop.managers.theme_manager import ThemeManager


class AppGrid(QTableWidget):
    # Sinyaller
    row_double_clicked = pyqtSignal(int, dict)  # row_index, row_dict
    row_append_requested = pyqtSignal()          # klavye gezinmesi son satırı aştığında (yeni satır iste)

    def __init__(
        self, 
        preset: str, 
        custom_row_height: int | None = None, 
        custom_header_height: int | None = None,
        parent=None,
        editable: bool = False,
    ):
        super().__init__(parent)
        #: Sağ tık menüsünün en üstüne eklenecek (metin, geri çağrı) çiftlerini döndüren sağlayıcı.
        #: Ayarlar ekranlarında sağ paneldeki işlemlerin aynısını tabloda da sunmak için kullanılır.
        self.context_actions_provider = None
        self._editable = editable
        
        self.preset_id = preset
        self.preset_config = get_preset(preset)
        self.theme = ThemeManager()
        self.custom_row_height = custom_row_height
        self.custom_header_height = custom_header_height
        self._raw_data: list[list[Any]] = []
        # Kalıcı sütun yerleşimi (bkz. enable_layout_persistence)
        self._layout_db = None
        self._layout_key = ""
        self._layout_has_widths = False
        self._applying_layout = False
        self._header_pressed = False
        self._enter_nav = False
        self.nav_skip_columns: set[int] = set()
        self._nav_suspended = False
        self._nav_deferred = None
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(400)
        self._layout_timer.timeout.connect(self._save_layout)

        self._setup_table_properties()
        self._apply_preset_headers()
        self._connect_theme_signals()
        self._setup_context_menu()

    @property
    def effective_row_height(self) -> int:
        """Ekran özel veri satır yüksekliği tanımlıysa onu, değilse merkezi ThemeManager değerini kullanır."""
        return self.custom_row_height if self.custom_row_height is not None else self.theme.row_height

    @property
    def effective_header_height(self) -> int:
        """Ekran özel başlık yüksekliği tanımlıysa onu, değilse merkezi ThemeManager değerini kullanır."""
        return self.custom_header_height if self.custom_header_height is not None else self.theme.header_height

    def set_custom_row_height(self, height: int | None):
        """Ekran bazlı özel veri satır yüksekliğini ayarlar veya None ile merkezi temaya geri döner."""
        self.custom_row_height = height
        eff_height = self.effective_row_height
        self.verticalHeader().setDefaultSectionSize(eff_height)
        for r in range(self.rowCount()):
            self.setRowHeight(r, eff_height)
        self.viewport().update()

    def set_custom_header_height(self, height: int | None):
        """Ekran bazlı özel başlık satır yüksekliğini ayarlar veya None ile merkezi temaya geri döner."""
        self.custom_header_height = height
        eff_h_height = self.effective_header_height
        self.horizontalHeader().setFixedHeight(eff_h_height)
        self.viewport().update()

    def _setup_table_properties(self):
        """Temel ERP tablo standartlarını ayarlar."""
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        if self._editable:   # tanım tabloları (hücre içi düzenleme)
            self.setEditTriggers(
                QTableWidget.EditTrigger.DoubleClicked
                | QTableWidget.EditTrigger.EditKeyPressed
                | QTableWidget.EditTrigger.AnyKeyPressed,
            )
        else:
            self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWordWrap(False)
        
        # Dikey başlık ve satır yüksekliği
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.effective_row_height)
        
        # Yatay başlık davranışı ve başlık satır yüksekliği
        h_header = self.horizontalHeader()
        h_header.setHighlightSections(False)
        h_header.setStretchLastSection(True)
        h_header.setFixedHeight(self.effective_header_height)
        h_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h_header.customContextMenuRequested.connect(self._show_header_context_menu)
        
        # Tema stilini uygula
        self.setStyleSheet(self.theme.get_table_stylesheet())
        
        # Çift tıklama olayı
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _apply_preset_headers(self):
        """Preset içerisindeki sütun başlıklarını uygular."""
        cols = self.preset_config["columns"]
        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels(cols)

    def _connect_theme_signals(self):
        """ThemeManager canlı güncellemelerine bağlanır."""
        self.theme.theme_changed.connect(self._on_theme_changed)
        self.theme.row_height_changed.connect(self._on_row_height_changed)
        self.theme.header_height_changed.connect(self._on_header_height_changed)

    def _on_theme_changed(self):
        self.setStyleSheet(self.theme.get_table_stylesheet())

    def _on_row_height_changed(self, height: int):
        """Merkezi tema satır yüksekliği değiştiğinde anında tepki verir (özel yükseklik yoksa)."""
        if self.custom_row_height is None:
            self.verticalHeader().setDefaultSectionSize(height)
            for r in range(self.rowCount()):
                self.setRowHeight(r, height)
            self.viewport().update()

    def _on_header_height_changed(self, height: int):
        """Merkezi tema başlık yüksekliği değiştiğinde anında tepki verir (özel başlık yüksekliği yoksa)."""
        if self.custom_header_height is None:
            self.horizontalHeader().setFixedHeight(height)
            self.viewport().update()

    def resizeEvent(self, event):  # noqa: N802
        """Pencere boyutu değiştiğinde sütunları preset oranlarına göre akıllıca dağıtır."""
        super().resizeEvent(event)
        self._apply_column_width_ratios()

    def _apply_column_width_ratios(self):
        """width_ratios listesine göre sütun genişliklerini hesaplar."""
        available_width = self.viewport().width()
        if available_width <= 0:
            return

        if self._layout_has_widths:      # kullanıcı genişlik belirlediyse oranlar ezmesin
            return
        ratios = self.preset_config.get("width_ratios", [])
        num_cols = self.columnCount()

        self._applying_layout = True
        try:
            for col_idx in range(min(len(ratios), num_cols)):
                ratio = ratios[col_idx]
                col_width = int(available_width * ratio)
                self.setColumnWidth(col_idx, max(col_width, 40))
        finally:
            self._applying_layout = False

    # ─────────────────────────────────────────────
    # KALICI SÜTUN YERLEŞİMİ (sıra / görünürlük / genişlik)
    # ─────────────────────────────────────────────
    def enable_layout_persistence(self, db, key: str | None = None) -> None:
        """Sütunlar sürükle-bırak ile taşınabilir olur; sıra, görünürlük ve genişlikler `db`'deki ayar deposuna
        (anahtar `grid.layout.<key>`) otomatik kaydedilir ve bir sonraki açılışta geri yüklenir."""
        self._layout_db = db
        self._layout_key = f"grid.layout.{key or self.preset_id}"
        header = self.horizontalHeader()
        header.setSectionsMovable(True)
        header.sectionMoved.connect(lambda *_a: self._schedule_layout_save())
        header.sectionResized.connect(self._on_section_resized)
        header.viewport().installEventFilter(self)   # fare basılıyken olan yeniden boyutlar kullanıcıya aittir
        self._load_layout()

    def _on_section_resized(self, *_a) -> None:
        if self._layout_db is None or self._applying_layout or not self._header_pressed:
            return
        self._layout_has_widths = True
        self._schedule_layout_save()

    def eventFilter(self, obj, event):  # noqa: N802
        if self._layout_db is not None and obj is self.horizontalHeader().viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                self._header_pressed = True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._header_pressed = False
                self._schedule_layout_save()
        return super().eventFilter(obj, event)

    # ─────────────────────────────────────────────
    # KLAVYE GEZİNMESİ (Enter / Tab ile sağa, satır sonunda yeni satıra)
    # ─────────────────────────────────────────────
    def enable_enter_navigation(self, skip_columns=()) -> None:
        """Enter/Tab: düzenlemeyi kaydedip sağdaki sonraki düzenlenebilir hücreye geçer, satır sonunda alt satırın başına
        iner; son satırın sonunda `row_append_requested` ile yeni satır ister. Shift+Tab geri gider. `skip_columns`
        klavye akışında atlanan (yine de tıklayarak düzenlenebilen) sütunlardır. Ctrl+Tab grid'den çıkar."""
        from src.desktop.ui.components.grid_delegates import NavDelegate
        self._enter_nav = True
        self.nav_skip_columns = set(skip_columns)
        self.setItemDelegate(NavDelegate(self))       # özel editörü olmayan (metin) hücrelerde de Enter/Tab akışı

    def _nav_editable(self, r: int, c: int) -> bool:
        it = self.item(r, c)
        return bool(it and it.flags() & Qt.ItemFlag.ItemIsEditable and not self.isColumnHidden(c)
                    and c not in self.nav_skip_columns)

    def commit_editor(self) -> None:
        """Açık hücre editörü varsa değeri hücreye yazıp kapatır (Kaydet gibi düğmelerden önce çağrılır)."""
        ed = self.indexWidget(self.currentIndex())
        if ed is not None and self.state() == QTableWidget.State.EditingState:
            onayla = getattr(ed, "commit_expression", None)
            if onayla is not None:
                onayla()
            self.commitData(ed)
            self.closeEditor(ed, QAbstractItemDelegate.EndEditHint.NoHint)

    def suspend_navigation(self) -> None:
        """Bir açılır pencere (örn. hesap seçimi) açılacakken klavye akışını bekletir; `resume_navigation` sürdürür."""
        self._nav_suspended = True
        self._nav_deferred = None

    def resume_navigation(self) -> None:
        self._nav_suspended = False
        step, self._nav_deferred = self._nav_deferred, None
        if step:
            self.navigate(step)

    def focusInEvent(self, event):  # noqa: N802
        """Tab ile grid'e girildiğinde ilk düzenlenebilir hücre düzenlemeye açılır (başlıktan kalemlere geçiş)."""
        super().focusInEvent(event)
        if self._enter_nav and event.reason() == Qt.FocusReason.TabFocusReason and self.state() != QTableWidget.State.EditingState:
            QTimer.singleShot(0, self.focus_first_cell)

    def focus_first_cell(self) -> None:
        header = self.horizontalHeader()
        for r in range(self.rowCount()):
            for v in range(self.columnCount()):
                c = header.logicalIndex(v)
                if self._nav_editable(r, c):
                    self.setCurrentCell(r, c)
                    self.editItem(self.item(r, c))
                    return

    def navigate(self, step: int = 1) -> None:
        """Bir sonraki (step=1) ya da önceki (step=-1) düzenlenebilir hücreye geçip düzenlemeyi başlatır (görsel sütun sırasına göre)."""
        if self._nav_suspended:
            self._nav_deferred = step
            return
        header = self.horizontalHeader()
        order = [header.logicalIndex(v) for v in range(self.columnCount())]
        order = [c for c in order if not self.isColumnHidden(c)]
        r, c = self.currentRow(), self.currentColumn()
        if not order or r < 0 or c not in order:
            return
        pos = order.index(c)
        for _guard in range(self.rowCount() * len(order) + len(order) + 2):
            pos += step
            if pos >= len(order):
                pos, r = 0, r + 1
                if r >= self.rowCount():
                    self.row_append_requested.emit()
                    if r >= self.rowCount():
                        return
            elif pos < 0:
                pos, r = len(order) - 1, r - 1
                if r < 0:
                    return
            if self._nav_editable(r, order[pos]):
                self.setCurrentCell(r, order[pos])
                self.editItem(self.item(r, order[pos]))
                return

    def keyPressEvent(self, event):  # noqa: N802
        if self._enter_nav and self.state() != QTableWidget.State.EditingState:
            key, mods = event.key(), event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                it = self.currentItem()
                if it is not None and self._nav_editable(self.currentRow(), self.currentColumn()):
                    self.editItem(it)
                else:
                    self.navigate(1)
                return
            if key == Qt.Key.Key_Tab and not mods & Qt.KeyboardModifier.ControlModifier:
                self.navigate(1)
                return
            if key == Qt.Key.Key_Backtab and not mods & Qt.KeyboardModifier.ControlModifier:
                self.navigate(-1)
                return
        super().keyPressEvent(event)

    def hideEvent(self, event):  # noqa: N802
        """Pencere kapanırken bekleyen sütun yerleşimi kaydı (400 ms gecikmeli) kaybolmasın."""
        if self._layout_timer.isActive():
            self._layout_timer.stop()
            self._save_layout()
        super().hideEvent(event)

    def _schedule_layout_save(self) -> None:
        if self._layout_db is not None and not self._applying_layout:
            self._layout_timer.start()

    def layout_state(self) -> dict:
        header = self.horizontalHeader()
        n = self.columnCount()
        return {
            "order": [header.logicalIndex(v) for v in range(n)],
            "hidden": [c for c in range(n) if self.isColumnHidden(c)],
            "widths": {str(c): self.columnWidth(c) for c in range(n)} if self._layout_has_widths else {},
        }

    def _save_layout(self) -> None:
        if self._layout_db is None:
            return
        import json

        from src.desktop.services import settings_store
        try:
            settings_store.set_setting(self._layout_db, self._layout_key, json.dumps(self.layout_state()))
        except Exception:  # noqa: BLE001 — yerleşim kaydı ekranı bozmamalı
            pass

    def _load_layout(self) -> None:
        from src.desktop.services import settings_store
        state = settings_store.get_json(self._layout_db, self._layout_key, None)
        if not isinstance(state, dict):
            return
        n = self.columnCount()
        header = self.horizontalHeader()
        self._applying_layout = True
        try:
            order = [c for c in state.get("order", []) if isinstance(c, int) and 0 <= c < n]
            if sorted(order) == list(range(n)):
                for visual, logical in enumerate(order):
                    header.moveSection(header.visualIndex(logical), visual)
            for c in range(n):
                self.setColumnHidden(c, c in state.get("hidden", []))
            widths = state.get("widths") or {}
            for c, w in widths.items():
                if str(c).isdigit() and int(c) < n:
                    self.setColumnWidth(int(c), max(int(w), 30))
            self._layout_has_widths = bool(widths)
        finally:
            self._applying_layout = False

    def reset_layout(self) -> None:
        """Sütun sırası, görünürlüğü ve genişliklerini preset varsayılanına döndürür (kayıt da sıfırlanır)."""
        header = self.horizontalHeader()
        self._applying_layout = True
        try:
            for logical in range(self.columnCount()):
                header.moveSection(header.visualIndex(logical), logical)
                self.setColumnHidden(logical, False)
            self._layout_has_widths = False
        finally:
            self._applying_layout = False
        self._apply_column_width_ratios()
        if self._layout_db is not None:
            self._layout_timer.stop()
            from src.desktop.services import settings_store
            settings_store.set_setting(self._layout_db, self._layout_key, "")

    def setData(self, rows_data: list[list[Any]]):  # noqa: N802
        """
        Verileri tabloya yükler ve preset'e göre otomatik hizalama & tip formatlaması yapar.
        Performans için render döngüsü optimize edilmiştir.
        """
        self.setUpdatesEnabled(False)
        self._raw_data = rows_data
        self.setRowCount(len(rows_data))
        
        eff_height = self.effective_row_height
        align_map = {
            "L": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "R": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "C": Qt.AlignmentFlag.AlignCenter,
        }
        
        alignments = self.preset_config.get("alignments", ["L"] * self.columnCount())
        types = self.preset_config.get("types", ["text"] * self.columnCount())

        for row_idx, row in enumerate(rows_data):
            self.setRowHeight(row_idx, eff_height)
            for col_idx in range(self.columnCount()):
                val = row[col_idx] if col_idx < len(row) else ""
                formatted_text = self._format_cell_value(val, types[col_idx])
                
                item = QTableWidgetItem(formatted_text)
                align_key = alignments[col_idx] if col_idx < len(alignments) else "L"
                item.setTextAlignment(align_map.get(align_key, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
                
                self.setItem(row_idx, col_idx, item)

        self.setUpdatesEnabled(True)

    def _format_cell_value(self, val: Any, col_type: str) -> str:
        """ERP veri tiplerine göre otomatik formatlama yapar."""
        if val is None:
            return ""
        
        if col_type == "currency":
            try:
                num = float(val)
                # Standart 1.250,50 TL formatı
                return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except (ValueError, TypeError):
                return str(val)
        elif col_type == "percent":
            try:
                num = float(val)
                return f"%{num:g}"
            except (ValueError, TypeError):
                return str(val)
        return str(val)

    def _on_cell_double_clicked(self, row: int, column: int):
        """Satır çift tıklandığında veri sözlüğü ile sinyal yayar."""
        if 0 <= row < len(self._raw_data):
            cols = self.preset_config["columns"]
            row_vals = self._raw_data[row]
            row_dict = {cols[i]: row_vals[i] for i in range(min(len(cols), len(row_vals)))}
            self.row_double_clicked.emit(row, row_dict)

    def _setup_context_menu(self):
        """Standart ERP sağ tık menüsü (Kopyala, Excel, Kolon Göster/Gizle, Kolon Oranla)."""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_header_context_menu(self, pos):
        """Başlığa sağ tık: iki sütunlu, aramalı sütun görünürlüğü (standart `FilterableTableView` menüsüyle aynı düzen)."""
        menu = QMenu(self)
        menu.setStyleSheet(self.theme.get_context_menu_stylesheet())
        menu.addAction(self._build_column_menu_action(menu))
        menu.exec(self.horizontalHeader().mapToGlobal(pos))

    def _build_column_menu_action(self, parent_menu) -> QWidgetAction:
        box = QWidget()
        box.setMinimumWidth(320)
        box.setStyleSheet("QWidget { background:#f8fafc; color:#334155; font-size:11px; }"
                          " QLineEdit { border:1px solid #cbd5e1; border-radius:4px; padding:4px 8px; background:white; color:#0f172a; }"
                          " QCheckBox::indicator { width:14px; height:14px; }")
        lyt = QVBoxLayout(box)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)
        title = QLabel("📊 SÜTUN GÖRÜNÜRLÜĞÜ")
        title.setStyleSheet("font-weight:800; font-size:10px; color:#1e3a8a;")
        search = QLineEdit()
        search.setPlaceholderText("Sütun ara...")
        lyt.addWidget(title)
        lyt.addWidget(search)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)
        boxes: list[tuple[QCheckBox, str]] = []
        for i, name in enumerate(self.preset_config.get("columns", [])):
            hi = self.horizontalHeaderItem(i)
            name = (hi.toolTip() if hi is not None and hi.toolTip() else name)      # kısaltılmış başlıkta tam ad
            cb = QCheckBox(name)
            cb.setChecked(not self.isColumnHidden(i))
            cb.toggled.connect(lambda checked, idx=i: self.toggle_column_visibility(idx, checked))
            grid.addWidget(cb, i // 2, i % 2)
            boxes.append((cb, name))
        lyt.addWidget(grid_host)

        def _filter(text: str) -> None:
            t = text.strip().lower()
            for cb, name in boxes:
                cb.setVisible(not t or t in name.lower())

        search.textChanged.connect(_filter)
        btns = QHBoxLayout()
        b_all = QPushButton("➕ Tümünü Göster")
        b_reset = QPushButton("↺ Varsayılan Düzen")
        for b in (b_all, b_reset):
            b.setStyleSheet("QPushButton { background:#eff6ff; border:1px solid #bfdbfe; border-radius:4px; padding:3px 8px; }"
                            " QPushButton:hover { background:#bfdbfe; }")
            btns.addWidget(b)
        b_all.clicked.connect(lambda: (self.show_all_columns(), [cb.setChecked(True) for cb, _n in boxes]))
        b_reset.clicked.connect(lambda: (self.reset_layout(), parent_menu.close()))
        lyt.addLayout(btns)
        if self._layout_db is not None:
            note = QLabel("Sütunları başlıktan sürükleyerek yer değiştirebilirsiniz; düzen otomatik kaydedilir.")
            note.setWordWrap(True)
            note.setStyleSheet("color:#64748b; font-size:10px;")
            lyt.addWidget(note)
        act = QWidgetAction(parent_menu)
        act.setDefaultWidget(box)
        return act

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(self.theme.get_context_menu_stylesheet())

        extra = self.context_actions_provider() if callable(self.context_actions_provider) else []
        menu.setToolTipsVisible(True)
        for item in extra:                       # (etiket, geri çağrı) ya da (etiket, geri çağrı, ipucu)
            label, callback = item[0], item[1]
            act = QAction(label, menu)
            if len(item) > 2 and item[2]:
                act.setToolTip(item[2])
            act.triggered.connect(lambda _=False, cb=callback: cb())
            menu.addAction(act)
        if extra:
            menu.addSeparator()

        copy_action = QAction("📋 Seçili Hücreleri Kopyala", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self._copy_selected_cells)
        menu.addAction(copy_action)
        
        menu.addSeparator()
        
        excel_action = QAction("📊 Excel'e Aktar (.xlsx)", self)
        excel_action.triggered.connect(lambda: print(f"[{self.preset_id}] Excel aktarımı tetiklendi."))
        menu.addAction(excel_action)

        col_menu = menu.addMenu("👁️ Sütunları Göster / Gizle")
        col_menu.setStyleSheet(self.theme.get_context_menu_stylesheet())
        col_menu.addAction(self._build_column_menu_action(col_menu))

        menu.exec(self.viewport().mapToGlobal(pos))

    def toggle_column_visibility(self, col_idx: int, visible: bool):
        """Belirtilen sütunun görünürlüğünü ayarlar."""
        self.setColumnHidden(col_idx, not visible)
        self._schedule_layout_save()

    def show_all_columns(self):
        """Tüm sütunları görünür yapar."""
        for col_idx in range(self.columnCount()):
            self.setColumnHidden(col_idx, False)
        self._schedule_layout_save()

    def _copy_selected_cells(self):
        """Seçili hücreleri panoya kopyalar."""
        selected_ranges = self.selectedRanges()
        if not selected_ranges:
            return
        
        clipboard_text = ""
        for r_range in selected_ranges:
            for r in range(r_range.topRow(), r_range.bottomRow() + 1):
                row_items = []
                for c in range(r_range.leftColumn(), r_range.rightColumn() + 1):
                    item = self.item(r, c)
                    row_items.append(item.text() if item else "")
                clipboard_text += "\t".join(row_items) + "\n"
                
        QApplication.clipboard().setText(clipboard_text.strip())
