from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.models import Site, Product, Order, SyncLog


class DashboardWidget(QWidget):
    """Genel istatistikleri ve son senkronizasyon günlüklerini gösteren Kontrol Paneli ekranı."""

    refresh_requested = pyqtSignal()

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Başlık ve Yenileme Butonu
        header_layout = QHBoxLayout()
        title_label = QLabel("Kontrol Paneli")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")
        
        self.refresh_btn = QPushButton("Verileri Yenile")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        header_layout.addWidget(self.refresh_btn)
        header_layout.addStretch()
        header_layout.addWidget(title_label)
        layout.addLayout(header_layout)

        # İstatistik Kartları (Sitesi, Ürünler, Siparişler)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)

        self.site_card = self.create_stat_card("Aktif Siteler", "0", "#2ecc71")
        self.product_card = self.create_stat_card("Eşleşen Ürünler", "0", "#3498db")
        self.order_card = self.create_stat_card("Eşleşen Siparişler", "0", "#e74c3c")

        cards_layout.addWidget(self.site_card)
        cards_layout.addWidget(self.product_card)
        cards_layout.addWidget(self.order_card)
        layout.addLayout(cards_layout)

        # Son Senkronizasyon Aktiviteleri Başlığı
        recent_title = QLabel("Son Senkronizasyon Günlükleri")
        recent_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        recent_title.setStyleSheet("color: #34495e; margin-top: 10px;")
        layout.addWidget(recent_title)

        # Son Aktiviteler Listesi
        self.log_list = QListWidget()
        self.log_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                background-color: white;
                padding: 5px;
            }
        """)
        layout.addWidget(self.log_list)

        # İlk veri yükleme
        self.refresh_data()

    def create_stat_card(self, title: str, value: str, color_hex: str) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #dcdde1;
                border-left: 5px solid {color_hex};
                border-radius: 6px;
                padding: 15px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(5)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 10))
        title_lbl.setStyleSheet("color: #7f8c8d; border: none;")

        value_lbl = QLabel(value)
        value_lbl.setObjectName("value_label")
        value_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        value_lbl.setStyleSheet("color: #2c3e50; border: none;")

        card_layout.addWidget(title_lbl)
        card_layout.addWidget(value_lbl)
        return card

    def refresh_data(self):
        """Veritabanından güncel verileri çekip arayüzü günceller."""
        try:
            # 1. Sayımları Güncelle
            site_count = self.db.query(Site).filter(Site.is_active == True).count()
            product_count = self.db.query(Product).filter(Product.is_deleted == False).count()
            order_count = self.db.query(Order).filter(Order.is_deleted == False).count()

            # Kart değerlerini bulup set et
            self.site_card.findChild(QLabel, "value_label").setText(str(site_count))
            self.product_card.findChild(QLabel, "value_label").setText(str(product_count))
            self.order_card.findChild(QLabel, "value_label").setText(str(order_count))

            # 2. Son Senkronizasyon Loglarını Çek (son 10 kayıt)
            self.log_list.clear()
            logs = self.db.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(10).all()

            for log in logs:
                site_name = log.site.name if log.site else f"Site #{log.site_id}"
                time_str = log.started_at.strftime("%d.%m.%Y %H:%M:%S")
                status_emoji = "✔" if log.status == "success" else "❌" if log.status == "failed" else "⏳"
                
                log_text = f"[{time_str}] {status_emoji} {site_name} | Tip: {log.sync_type.upper()} | Durum: {log.status.upper()}\n  └ Detay: {log.details or 'Detay yok.'}"
                
                item = QListWidgetItem(log_text)
                # Duruma göre hafif renk tonu ekleyebiliriz
                if log.status == "failed":
                    item.setForeground(Qt.GlobalColor.red)
                elif log.status == "success":
                    item.setForeground(Qt.GlobalColor.darkGreen)
                    
                self.log_list.addItem(item)
                
            self.refresh_requested.emit()
        except Exception as e:
            self.log_list.clear()
            self.log_list.addItem(f"Veri yüklenirken hata oluştu: {str(e)}")
