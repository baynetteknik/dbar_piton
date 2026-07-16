import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QLabel
)
from PyQt6.QtCore import Qt


class ColumnManagerDialog(QDialog):
    """DIA stiline uygun, arama filtrelemeli ve toplu seçim destekli gelişmiş Sütun/Kolon Yönetim Ekranı."""
    
    def __init__(self, headers_dict, hidden_columns, settings_file_name, parent=None):
        super().__init__(parent)
        self.headers_dict = headers_dict # {col_idx: (display_name, field_name)}
        self.hidden_columns = set(hidden_columns)
        self.settings_path = Path("data") / f"{settings_file_name}.json"
        
        self.setWindowTitle(self.tr("Sütun / Kolon Yapılandırması (DIA)"))
        self.setMinimumSize(400, 500)
        self.init_ui()
        self.load_columns()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Üst Bilgilendirme
        info_lbl = QLabel(self.tr("Tabloda gösterilmesini istediğiniz sütunları işaretleyin:"))
        info_lbl.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(info_lbl)
        
        # Arama Kutusu (Hızlı Kolon Arama)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(self.tr("🔍 Sütun adı ara..."))
        self.search_box.textChanged.connect(self.filter_columns)
        self.search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
            }
        """)
        layout.addWidget(self.search_box)
        
        # ListWidget (Checkable Items)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f1f5f9;
            }
        """)
        layout.addWidget(self.list_widget)
        
        # Toplu Seçim Butonları
        select_layout = QHBoxLayout()
        btn_all = QPushButton(self.tr("Tümünü Seç"))
        btn_all.setStyleSheet(self.action_btn_style("#3b82f6"))
        btn_all.clicked.connect(self.select_all)
        
        btn_none = QPushButton(self.tr("Tümünü Kaldır"))
        btn_none.setStyleSheet(self.action_btn_style("#64748b"))
        btn_none.clicked.connect(self.clear_all)
        
        select_layout.addWidget(btn_all)
        select_layout.addWidget(btn_none)
        layout.addLayout(select_layout)
        
        # Alt Kaydet/İptal Butonları
        btn_layout = QHBoxLayout()
        btn_save = QPushButton(self.tr("Tasarımı Kaydet"))
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_save.clicked.connect(self.save_settings)
        
        btn_cancel = QPushButton(self.tr("İptal"))
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def action_btn_style(self, bg):
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """

    def load_columns(self):
        """Sütun tanımlarını listeye yükler."""
        self.list_widget.clear()
        for col_idx, (display_name, _) in self.headers_dict.items():
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, col_idx)
            # Eğer sütun gizli değilse check'li yap
            is_visible = col_idx not in self.hidden_columns
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if is_visible else Qt.CheckState.Unchecked)
            self.list_widget.addItem(item)

    def filter_columns(self, query):
        """Arama metnine göre sütunları filtreler."""
        query = query.strip().lower()
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if query in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def select_all(self):
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)

    def clear_all(self):
        # En az bir sütun görünür kalmalı, ancak arayüz esnekliği için hepsini kaldırabilir
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Unchecked)

    def save_settings(self):
        """Seçilen sütun görünürlük ayarlarını kaydeder."""
        new_hidden = set()
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            col_idx = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Unchecked:
                new_hidden.add(col_idx)
                
        self.hidden_columns = new_hidden
        
        # Ayarları JSON olarak kaydet
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(list(self.hidden_columns), f)
        except Exception:
            pass
            
        self.accept()

    def get_hidden_columns(self):
        return self.hidden_columns
