"""TOYA ERP - Genel Ayarlar İkonlu Karşılama Paneli (SettingsHubWidget).

Tüm ayar modüllerine ana ekrandaki gibi büyük, estetik ve kategorize edilmiş
kartlarla tek tıkla geçiş sağlar. Kullanıcının sağladığı 3D ikonları ve
akıllı arama süzgecini barındırır.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons" / "settings"

#: Ayar paneli ID'si → İkon dosya adı
SETTINGS_ICONS_MAP: dict[str, str] = {
    "firma_bilgileri": "sirket_tanimlari.png",
    "doviz_kur": "finans_tanimlari.png",
    "adres_tanimlari": "adres_tanimlari.png",
    "vergi_daireleri": "vergi_daireleri.png",
    "banka_tanimlari": "finans_tanimlari.png",
    "kullanicilar": "kullanici_tanimlari.png",
    "roller": "kullanici_tanimlari.png",
    "yetkiler": "yetkilendirme.png",
    "odeme_planlari": "finans_tanimlari.png",
    "banka_odeme_planlari": "finans_tanimlari.png",
    "fiyat_listeleri": "finans_tanimlari.png",
    "stok_kategoriler": "stok_tanimlari.png",
    "stok_markalar": "stok_tanimlari.png",
    "birim_tanimlari": "stok_tanimlari.png",
    "stok_ozel_alanlar": "stok_tanimlari.png",
    "cari_gruplari": "cari_tanimlari.png",
    "cari_ozel_alanlar": "cari_tanimlari.png",
    "yedek_merkezi": "yedekleme.png",
    "portal_yedek": "yedekleme.png",
    "guvenlik": "guvenlik.png",
    "numara_serileri": "genel_ayarlar.png",
    "gorunum_profilleri": "gorunum.png",
    "ekran_grid": "ekran_tasarim.png",
    "form_tasarimlari": "genel_gorunum.png",
    "cms_baglantilari": "surum_ayar.png",
    "portal_yayin": "surum_ayar.png",
    "online_portal": "surum_ayar.png",
    "eposta_smtp": "bildirimler.png",
    "kdv_oranlari": "finans_tanimlari.png",
    "sayi_bicimi": "genel_ayarlar.png",
    "surum_git": "surum.png",
    "yardim": "genel_ayarlar.png",
}

SETTINGS_FALLBACK_EMOJI: dict[str, str] = {
    "firma_bilgileri": "🏢",
    "doviz_kur": "💱",
    "adres_tanimlari": "🌍",
    "vergi_daireleri": "🏛️",
    "banka_tanimlari": "🏦",
    "kullanicilar": "👤",
    "roller": "👥",
    "yetkiler": "🔐",
    "odeme_planlari": "💳",
    "banka_odeme_planlari": "🧾",
    "fiyat_listeleri": "🏷️",
    "stok_kategoriler": "📑",
    "stok_markalar": "🏷️",
    "birim_tanimlari": "⚖️",
    "stok_ozel_alanlar": "📝",
    "cari_gruplari": "👥",
    "cari_ozel_alanlar": "📝",
    "yedek_merkezi": "💾",
    "portal_yedek": "☁️",
    "guvenlik": "🛡️",
    "numara_serileri": "🔢",
    "gorunum_profilleri": "🎨",
    "ekran_grid": "📐",
    "form_tasarimlari": "🖨️",
    "cms_baglantilari": "🔌",
    "portal_yayin": "🚀",
    "online_portal": "🌐",
    "eposta_smtp": "✉️",
    "kdv_oranlari": "🧾",
    "sayi_bicimi": "🔢",
    "surum_git": "🛠️",
    "yardim": "📖",
}


class SettingsTileButton(QPushButton):
    """Büyük, 3D ikonlu ayar kart butonu."""

    def __init__(self, title: str, panel_id: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.panel_id = panel_id
        self.subtitle = subtitle
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(112, 104)

        self.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-bottom: 3px solid #94a3b8;
                border-radius: 12px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #eff6ff;
                border-color: #3b82f6;
                border-bottom-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #dbeafe;
                border-bottom: 1px solid #2563eb;
                padding-top: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 5, 4, 5)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # İkon / Görsel
        icon_file = SETTINGS_ICONS_MAP.get(panel_id)
        icon_path = ICONS_DIR / icon_file if icon_file else None

        self.lbl_icon = QLabel()
        if icon_path and icon_path.is_file():
            pm = QPixmap(str(icon_path))
            if not pm.isNull():
                self.lbl_icon.setPixmap(pm.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.lbl_icon.setFixedSize(42, 42)
                self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            emoji = SETTINGS_FALLBACK_EMOJI.get(panel_id, "⚙️")
            self.lbl_icon.setText(emoji)
            self.lbl_icon.setFont(QFont("Segoe UI Emoji", 24))
            self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.lbl_icon, 0, Qt.AlignmentFlag.AlignCenter)

        # Başlık
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #1e3a8a; font-family: 'Segoe UI';")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.lbl_title)

        # Alt Başlık / Kod
        if subtitle:
            self.lbl_sub = QLabel(subtitle)
            self.lbl_sub.setStyleSheet("font-size: 8px; color: #64748b; font-family: 'Segoe UI';")
            self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_sub.setWordWrap(True)
            self.lbl_sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(self.lbl_sub)

        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(8)
        sh.setColor(QColor(0, 0, 0, 20))
        sh.setOffset(0, 2)
        self.setGraphicsEffect(sh)


class SettingsHubWidget(QWidget):
    """Genel Ayarlar Ana Karşılama Ekranı."""

    navigate_requested = pyqtSignal(str)  # panel_id

    #: Kategori kartları yan yana kaç sütun olsun (dar ekranlarda daha az dikey kaydırma).
    CARD_COLUMNS = 3
    #: Her kartın İÇİNDEKİ ikon kutuları kaç sütun olsun (kart dar olduğu için satır taşmaz).
    TILE_COLUMNS = 3

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsHubWidget")
        self._buttons: list[SettingsTileButton] = []
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 10, 16, 16)
        main_layout.setSpacing(10)

        # Arama Çubuğu — üst başlık (breadcrumb'da zaten var) tekrar edilmiyor; ince,
        # dar bir satır olarak ekranın asıl yerini kartlara bırakıyor.
        top_lyt = QHBoxLayout()
        top_lyt.setContentsMargins(0, 0, 0, 0)
        top_lyt.setSpacing(8)
        top_lyt.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Ayar / Tanım Ara...")
        self.txt_search.setFixedWidth(240)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                color: #0f172a;
            }
            QLineEdit:focus {
                background-color: #ffffff;
                border-color: #2563eb;
            }
        """)
        self.txt_search.textChanged.connect(self._on_search)
        top_lyt.addWidget(self.txt_search)

        main_layout.addLayout(top_lyt)

        # Kaydırılabilir Alan
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setContentsMargins(0, 4, 8, 4)
        self.grid_layout.setSpacing(14)
        for col in range(self.CARD_COLUMNS):
            self.grid_layout.setColumnStretch(col, 1)

        # Gruplar & Kartlar
        self._build_sections()

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def _build_sections(self) -> None:
        sections = [
            ("🏢 ŞİRKET TANIMLARI", "#1e40af", [
                ("Firma Bilgileri", "firma_bilgileri", "Firma & İletişim"),
                ("Belge & Seri No", "numara_serileri", "e-Fatura / Şablonlar"),
            ]),
            ("🌍 ADRES & VERGİ TANIMLARI", "#047857", [
                ("Adres Tanımları", "adres_tanimlari", "Ülke, İl, İlçe, Semt"),
                ("Vergi Daireleri", "vergi_daireleri", "Vergi Dairesi Kodları"),
            ]),
            ("🏦 BANKA & FİNANS TANIMLARI", "#b45309", [
                ("Döviz & Kur", "doviz_kur", "Döviz Kurları & MB"),
                ("Banka Tanımları", "banka_tanimlari", "Bankalar & Şubeler"),
                ("Ödeme Planları", "odeme_planlari", "Vade & Taksit"),
                ("Banka Ödeme Planları", "banka_odeme_planlari", "Komisyon/BSMV"),
                ("Fiyat Listeleri", "fiyat_listeleri", "Fiyat Kartları"),
            ]),
            ("📦 STOK & ÜRÜN TANIMLARI", "#0369a1", [
                ("Kategoriler", "stok_kategoriler", "Ürün Ağacı"),
                ("Markalar", "stok_markalar", "Ürün Markaları"),
                ("Birim Tanımları", "birim_tanimlari", "Adet, Kg, Metre"),
                ("Özel Alanlar", "stok_ozel_alanlar", "Stok Ek Alanları"),
            ]),
            ("👥 CARİ TANIMLARI", "#6d28d9", [
                ("Cari Grupları", "cari_gruplari", "Müşteri/Tedarikçi"),
                ("Özel Alanlar", "cari_ozel_alanlar", "Cari Ek Alanları"),
            ]),
            ("👤 KULLANICI & YETKİ", "#475569", [
                ("Kullanıcılar", "kullanicilar", "ERP Kullanıcıları"),
                ("Rol Tanımları", "roller", "Kullanıcı Rolleri"),
                ("Yetki Matrisi", "yetkiler", "Erişim İzinleri"),
            ]),
            ("💾 YEDEKLEME & GÜVENLİK", "#b91c1c", [
                ("Yedekleme Merkezi", "yedek_merkezi", "Otomatik / Bulut Yedek"),
                ("Portal Yedeği", "portal_yedek", "cPanel İndirme"),
                ("Giriş & Güvenlik", "guvenlik", "Kilit & Parola"),
            ]),
            ("🎨 GÖRÜNÜM & ŞABLONLAR", "#c026d3", [
                ("Görünüm Profilleri", "gorunum_profilleri", "Tablo Görünümleri"),
                ("Ekran Gridleri", "ekran_grid", "Grid Standartları"),
                ("Form Tasarımları", "form_tasarimlari", "Baskı Şablonları"),
            ]),
            ("🔌 ENTEGRASYON & SİSTEM", "#0f766e", [
                ("CMS / ERP", "cms_baglantilari", "WooCommerce/Presta"),
                ("Portal Yayın", "portal_yayin", "FTP Dağıtımı"),
                ("Online Portal", "online_portal", "Müşteri Teklif Portalı"),
                ("E-Posta (SMTP)", "eposta_smtp", "Mail Sunucusu"),
                ("KDV Oranları", "kdv_oranlari", "Vergi Oranları"),
                ("Kuruş Hanesi", "sayi_bicimi", "Ondalık Hassasiyeti"),
                ("Sürüm & Git", "surum_git", "Sürüm Takip Merkezi"),
                ("Yardım", "yardim", "Kullanım Kılavuzu"),
            ]),
        ]

        for idx, (sec_title, color, items) in enumerate(sections):
            sec_card = QFrame()
            sec_card.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                    padding: 8px;
                }
            """)
            sec_vbox = QVBoxLayout(sec_card)
            sec_vbox.setContentsMargins(10, 8, 10, 10)
            sec_vbox.setSpacing(8)

            lbl_header = QLabel(sec_title)
            lbl_header.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {color}; border-bottom: 2px solid {color}; padding-bottom: 3px;")
            sec_vbox.addWidget(lbl_header)

            # Kart dar olduğu için (3 sütunlu dış grid) ikonlar tek satırda taşmasın diye
            # kendi içinde de TILE_COLUMNS'a göre satır satır sarılır.
            tile_grid = QGridLayout()
            tile_grid.setSpacing(8)

            for i, (title, panel_id, sub) in enumerate(items):
                btn = SettingsTileButton(title, panel_id, sub)
                btn.clicked.connect(lambda _=False, pid=panel_id: self.navigate_requested.emit(pid))
                tile_grid.addWidget(btn, i // self.TILE_COLUMNS, i % self.TILE_COLUMNS)
                self._buttons.append(btn)

            sec_vbox.addLayout(tile_grid)
            sec_vbox.addStretch()
            row, col = divmod(idx, self.CARD_COLUMNS)
            self.grid_layout.addWidget(sec_card, row, col, Qt.AlignmentFlag.AlignTop)

    def _on_search(self, text: str) -> None:
        q = text.strip().lower()
        for btn in self._buttons:
            match = (not q) or (q in btn.title.lower()) or (q in btn.subtitle.lower()) or (q in btn.panel_id.lower())
            btn.setVisible(match)
