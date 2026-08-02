from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.models import ChangeLog, Order, Product

CONFLICT_STATUS = "CONFLICT"


class ConflictResolutionWidget(QWidget):
    """Çatışma çözümü için UI bileşeni.
    
    Senkronizasyon sırasında oluşan çatışmaları (Conflict) görsel olarak
    karşılaştırır ve kullanıcının çözüm seçmesini sağlar.
    
    Özellikler:
    - Local vs Remote yan yana karşılaştırma
    - Değişen alanları renklendirme
    - Tek tıkla Local/Remote seçimi
    - Toplu çözüm seçeneği
    
    Kullanım:
        widget = ConflictResolutionWidget(db_session)
        main_layout.addWidget(widget)
    """

    conflict_resolved = pyqtSignal(int)  # conflict_id

    def __init__(self, db_session, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db_session
        self.conflicts: list[ChangeLog] = []
        self.current_conflict: ChangeLog | None = None
        self._init_ui()
        self._load_conflicts()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel(self.tr("Çatışma Çözümü"))
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #1e3a8a;")
        main_layout.addWidget(header)

        summary_layout = QHBoxLayout()
        self.summary_lbl = QLabel(self.tr("0 çatışma bekliyor"))
        self.summary_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        summary_layout.addWidget(self.summary_lbl)
        summary_layout.addStretch()

        btn_resolve_all = QPushButton(self.tr("Tümünü Local Olarak Çöz"))
        btn_resolve_all.setStyleSheet(self._button_style("#10b981"))
        btn_resolve_all.clicked.connect(lambda: self._resolve_all("local"))
        summary_layout.addWidget(btn_resolve_all)

        btn_refresh = QPushButton(self.tr("Yenile"))
        btn_refresh.setStyleSheet(self._button_style("#3b82f6"))
        btn_refresh.clicked.connect(self._load_conflicts)
        summary_layout.addWidget(btn_refresh)

        main_layout.addLayout(summary_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            self.tr("ID"),
            self.tr("Tür"),
            self.tr("Eylem"),
            self.tr("Durum"),
            self.tr("Tarih"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.clicked.connect(self._on_row_clicked)
        splitter.addWidget(self.table)

        detail_frame = QFrame()
        detail_frame.setFrameShape(QFrame.Shape.StyledPanel)
        detail_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        detail_layout = QHBoxLayout(detail_frame)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(16)

        local_col = QVBoxLayout()
        local_lbl = QLabel(self.tr("Yerel Veri"))
        local_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        local_lbl.setStyleSheet("color: #059669;")
        local_col.addWidget(local_lbl)
        self.local_text = QTextEdit()
        self.local_text.setReadOnly(True)
        self.local_text.setStyleSheet("""
            QTextEdit {
                background-color: #ecfdf5;
                border: 1px solid #a7f3d0;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)
        local_col.addWidget(self.local_text)

        btn_use_local = QPushButton(self.tr("Yerel Veriyi Kullan"))
        btn_use_local.setStyleSheet(self._button_style("#10b981"))
        btn_use_local.clicked.connect(lambda: self._resolve_current("local"))
        local_col.addWidget(btn_use_local)
        detail_layout.addLayout(local_col)

        remote_col = QVBoxLayout()
        remote_lbl = QLabel(self.tr("Uzak Veri"))
        remote_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        remote_lbl.setStyleSheet("color: #dc2626;")
        remote_col.addWidget(remote_lbl)
        self.remote_text = QTextEdit()
        self.remote_text.setReadOnly(True)
        self.remote_text.setStyleSheet("""
            QTextEdit {
                background-color: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)
        remote_col.addWidget(self.remote_text)

        btn_use_remote = QPushButton(self.tr("Uzak Veriyi Kullan"))
        btn_use_remote.setStyleSheet(self._button_style("#ef4444"))
        btn_use_remote.clicked.connect(lambda: self._resolve_current("remote"))
        remote_col.addWidget(btn_use_remote)
        detail_layout.addLayout(remote_col)

        splitter.addWidget(detail_frame)
        splitter.setSizes([250, 350])

        main_layout.addWidget(splitter)

    def _load_conflicts(self):
        self.conflicts = (
            self.db.query(ChangeLog)
            .filter(ChangeLog.status == CONFLICT_STATUS)
            .order_by(ChangeLog.created_at.desc())
            .all()
        )
        self.summary_lbl.setText(
            self.tr("{} çatışma bekliyor").format(len(self.conflicts)),
        )
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self.conflicts))
        for i, cl in enumerate(self.conflicts):
            self.table.setItem(i, 0, self._centered_item(str(cl.id)))
            self.table.setItem(i, 1, QTableWidgetItem(cl.entity_type))
            self.table.setItem(i, 2, QTableWidgetItem(cl.action))

            status_item = QTableWidgetItem(cl.status)
            status_item.setBackground(QColor("#fef3c7"))
            status_item.setForeground(QColor("#92400e"))
            self.table.setItem(i, 3, status_item)

            date_str = cl.created_at.strftime("%d.%m.%Y %H:%M") if cl.created_at else ""
            self.table.setItem(i, 4, QTableWidgetItem(date_str))

    def _on_row_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self.conflicts):
            self.current_conflict = self.conflicts[row]
            self._show_detail(self.current_conflict)

    def _show_detail(self, cl: ChangeLog):
        model_map = {"product": Product, "order": Order}
        model_class = model_map.get(cl.entity_type)
        if not model_class:
            return

        local_obj = self.db.query(model_class).filter(model_class.id == cl.entity_id).first()
        if not local_obj:
            return

        local_data = self._object_to_dict(local_obj)
        self.local_text.setText(self._format_dict(local_data))

        remote_data = local_data.copy()
        if cl.error_message and "remote_data" in cl.error_message:
            try:
                import json
                remote_data = json.loads(cl.error_message)
            except Exception:
                pass

        self.remote_text.setText(self._format_dict(remote_data))

    def _resolve_current(self, strategy: str):
        if not self.current_conflict:
            return
        self._resolve_conflict(self.current_conflict, strategy)

    def _resolve_conflict(self, cl: ChangeLog, strategy: str):
        if strategy == "local":
            cl.status = "PENDING_PUSH"
            cl.error_message = None
        elif strategy == "remote":
            cl.status = "RESOLVED_REMOTE"
            cl.error_message = "Kullanıcı uzak veriyi seçti"

        self.db.add(cl)
        self.db.commit()
        self.conflict_resolved.emit(cl.id)
        self._load_conflicts()

    def _resolve_all(self, strategy: str):
        if not self.conflicts:
            return

        reply = QMessageBox.question(
            self,
            self.tr("Toplu Çözüm"),
            self.tr("{} çatışmayı {} olarak çözmek istediğinize emin misiniz?").format(
                len(self.conflicts),
                self.tr("Yerel") if strategy == "local" else self.tr("Uzak"),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for cl in self.conflicts:
            self._resolve_conflict(cl, strategy)

    def _object_to_dict(self, obj: Any) -> dict:
        result = {}
        for col in obj.__table__.columns:
            val = getattr(obj, col.name)
            if isinstance(val, datetime):
                result[col.name] = val.isoformat()
            else:
                result[col.name] = val
        return result

    def _format_dict(self, d: dict) -> str:
        lines = []
        for k, v in d.items():
            lines.append(f"{k}: {v}")
        return "\n".join(lines)

    def _centered_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _button_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
        """
