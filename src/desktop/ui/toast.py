from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel


class ToastNotification(QFrame):
    """DIAApp3 benzeri animasyonlu bildirim sistemi.
    
    Bildirim türleri:
    - success: Yeşil arka plan
    - warning: Sarı arka plan
    - error: Kırmızı arka plan
    - info: Mavi arka plan
    """

    # Bildirim renkleri
    BG_COLORS = {
        "success": "#10b981",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "info": "#3b82f6",
    }

    # Bildirim ikonları
    ICONS = {
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "info": "ℹ️",
    }

    def __init__(self, parent, message: str, notification_type: str = "info"):
        super().__init__(parent)
        self.parent_widget = parent
        self.message = message
        self.notification_type = notification_type

        # Stil ayarları
        bg_color = self.BG_COLORS.get(notification_type, "#1e293b")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                color: white;
                border-radius: 8px;
                padding: 12px 20px;
            }}
        """)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # İkon
        icon_emoji = self.ICONS.get(notification_type, "ℹ️")
        icon_lbl = QLabel(icon_emoji)
        icon_lbl.setFont(QFont("Segoe UI", 12))
        layout.addWidget(icon_lbl)

        # Mesaj
        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        # Gölge efekti
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        # Animasyon ayarları
        self.adjustSize()

        # Slide-in animasyonu
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Otomatik kaybolma zamanlayıcısı
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)

    def show_toast(self, duration_ms: int = 3000):
        """Toast bildirimini gösterir.
        
        Args:
            duration_ms: Gösterim süresi (milisaniye). Varsayılan: 3000ms
        """
        # Ebeveyn widget'ın boyutlarını al
        parent_rect = self.parent_widget.rect()

        # Başlangıç pozisyonu (sağ alt köşe)
        start_x = parent_rect.width() - self.width() - 24
        start_y = parent_rect.height()

        # Bitiş pozisyonu (sağ üst köşe, biraz yukarıda)
        end_y = parent_rect.height() - self.height() - 40

        # Pozisyon ayarla ve göster
        self.move(start_x, start_y)
        self.show()

        # Animasyonu başlat
        self.anim.setStartValue(QPoint(start_x, start_y))
        self.anim.setEndValue(QPoint(start_x, end_y))
        self.anim.start()

        # Zamanlayıcıyı başlat
        self.timer.start(duration_ms)

    def fade_out(self):
        """Toast bildirimini kaybolma animasyonuyla gizler."""
        parent_rect = self.parent_widget.rect()
        dest_x = self.x()
        dest_y = parent_rect.height()

        # Kaybolma animasyonu
        self.anim.setStartValue(QPoint(self.x(), self.y()))
        self.anim.setEndValue(QPoint(dest_x, dest_y))
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()

    def set_message(self, message: str, notification_type: str = None):
        """Toast mesajını ve türünü günceller."""
        self.message = message
        if notification_type:
            self.notification_type = notification_type
            bg_color = self.BG_COLORS.get(notification_type, "#1e293b")
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    color: white;
                    border-radius: 8px;
                    padding: 12px 20px;
                }}
            """)

        # Mesaj ve ikon güncelle
        for child in self.findChildren(QLabel):
            if child.font().pointSize() == 12:
                child.setText(self.ICONS.get(self.notification_type, "ℹ️"))
            else:
                child.setText(message)

        self.adjustSize()
