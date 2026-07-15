from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from src.core.models import Customer


class CustomerDialog(QDialog):
    """Yeni müşteri kartı ekleme dialogu."""
    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.setWindowTitle(self.tr("Yeni Müşteri Ekle"))
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.fullname_input = QLineEdit()
        self.tax_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.address_input = QLineEdit()
        
        for widget in [self.fullname_input, self.tax_input, self.phone_input, self.email_input, self.address_input]:
            widget.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 6px 10px;
                    background-color: white;
                    color: #0f172a;
                }
            """)
            
        form.addRow(self.tr("Ad / Cari Ünvan:"), self.fullname_input)
        form.addRow(self.tr("Vergi No / TCKN:"), self.tax_input)
        form.addRow(self.tr("Telefon:"), self.phone_input)
        form.addRow(self.tr("E-Posta:"), self.email_input)
        form.addRow(self.tr("Adres:"), self.address_input)
        
        layout.addLayout(form)
        
        btn_lyt = QHBoxLayout()
        btn_save = QPushButton(self.tr("Kaydet"))
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
        """)
        btn_save.clicked.connect(self.save_customer)
        
        btn_cancel = QPushButton(self.tr("İptal"))
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_lyt.addStretch()
        btn_lyt.addWidget(btn_cancel)
        btn_lyt.addWidget(btn_save)
        layout.addLayout(btn_lyt)

    def save_customer(self):
        name = self.fullname_input.text().strip()
        if not name:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Ad / Cari Ünvan zorunludur."))
            return
            
        try:
            cust = Customer(
                fullname=name,
                tax_number=self.tax_input.text().strip(),
                phone=self.phone_input.text().strip(),
                email=self.email_input.text().strip(),
                address=self.address_input.text().strip(),
                marketplace="local"
            )
            self.db.add(cust)
            self.db.commit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), f"Müşteri kaydedilemedi: {e}")


class MusteriYonetimiWidget(QWidget):
    """Veritabanı bağlantılı, arama ve filtreleme yapabilen modern Cari/Müşteri Yönetim paneli."""

    toast_requested = pyqtSignal(str, str) # message, type

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        header_lbl = QLabel(self.tr("👥 Müşteri & Cari Kart Yönetimi"))
        header_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #0f172a; font-family: 'Segoe UI';")
        layout.addWidget(header_lbl)
        
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(self.tr("🔍 Müşteri veya Vergi No ara..."))
        self.search_box.setMinimumWidth(260)
        self.search_box.textChanged.connect(self.refresh_customers)
        self.search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: white;
                color: #0f172a;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
        """)
        action_layout.addWidget(self.search_box)
        action_layout.addStretch()
        
        btn_new = QPushButton(self.tr("➕ Yeni Müşteri"))
        btn_new.setStyleSheet(self.btn_style("#10b981"))
        btn_new.clicked.connect(self.open_new_customer_dialog)
        
        btn_import = QPushButton(self.tr("📥 İçe Aktar"))
        btn_import.setStyleSheet(self.btn_style("#3b82f6"))
        btn_import.clicked.connect(lambda: self.toast_requested.emit(self.tr("Excel dosyasından veri aktarımı başlatıldı."), "info"))
        
        btn_export = QPushButton(self.tr("📤 Dışa Aktar"))
        btn_export.setStyleSheet(self.btn_style("#64748b"))
        btn_export.clicked.connect(lambda: self.toast_requested.emit(self.tr("Müşteri listesi dışa aktarılıyor..."), "info"))
        
        action_layout.addWidget(btn_new)
        action_layout.addWidget(btn_import)
        action_layout.addWidget(btn_export)
        layout.addLayout(action_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            self.tr("ID"), self.tr("Ad / Cari Ünvan"), self.tr("Vergi No / TCKN"), 
            self.tr("Telefon"), self.tr("E-Posta Adresi"), self.tr("Mecra / Kaynak")
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                background-color: white;
                border-radius: 8px;
                font-family: 'Segoe UI';
                font-size: 13px;
                color: #334155;
            }
            QTableWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:hover {
                background-color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 10px 12px;
                font-weight: 700;
                font-family: 'Segoe UI';
                color: #475569;
                text-align: left;
            }
        """)
        
        self.table.setMinimumHeight(280)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 10))
        shadow.setOffset(0, 2)
        self.table.setGraphicsEffect(shadow)
        
        layout.addWidget(self.table)
        layout.addStretch()
        
        self.refresh_customers()

    def open_new_customer_dialog(self):
        dlg = CustomerDialog(self.db, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.toast_requested.emit(self.tr("Yeni müşteri kartı başarıyla oluşturuldu."), "success")
            self.refresh_customers()

    def refresh_customers(self):
        try:
            query = self.db.query(Customer).filter(Customer.is_deleted == False)
            search_text = self.search_box.text().strip()
            if search_text:
                query = query.filter(
                    Customer.fullname.like(f"%{search_text}%") | 
                    Customer.tax_number.like(f"%{search_text}%") |
                    Customer.email.like(f"%{search_text}%")
                )
            customers = query.all()
            
            self.table.setRowCount(len(customers))
            for row, cust in enumerate(customers):
                id_item = QTableWidgetItem(str(cust.id))
                id_item.setForeground(QColor("#64748b"))
                id_item.setFlags(id_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, id_item)
                
                name_item = QTableWidgetItem(cust.fullname)
                name_item.setFlags(name_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 1, name_item)
                
                tax_item = QTableWidgetItem(cust.tax_number or "")
                tax_item.setFlags(tax_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 2, tax_item)
                
                phone_item = QTableWidgetItem(cust.phone or "")
                phone_item.setFlags(phone_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 3, phone_item)
                
                email_item = QTableWidgetItem(cust.email or "")
                email_item.setFlags(email_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 4, email_item)
                
                mp_item = QTableWidgetItem(cust.marketplace.upper() if cust.marketplace else "LOCAL")
                mp_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                mp_item.setForeground(QColor("#2563eb"))
                mp_item.setFlags(mp_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 5, mp_item)
                
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), f"Müşteriler listelenemedi: {e}")

    def btn_style(self, bg_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """
