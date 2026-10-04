import datetime
import logging
import os
from pathlib import Path

from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Site
from src.desktop.services.dev_tracker_store import gelistirme_acik
from src.desktop.ui.backup import BackupWidget
from src.desktop.ui.cari_list_screen import CariListScreen
from src.desktop.ui.components.text_selection_helper import init_global_text_selection
from src.desktop.ui.settings import SettingsWidget
from src.desktop.ui.stok_list_screen import StokListScreen
from src.desktop.ui.toast import ToastNotification
from src.desktop.ui.widgets.favorite_actions_widget import FavoriteActionsWidget
from src.desktop.ui.widgets.menu_grid_widget import MenuGridWidget
from src.desktop.ui.widgets.quick_tiles_bar_widget import QuickTilesBarWidget

logger = logging.getLogger(__name__)

#: Uygulama logosu (dizayn/logo3d.jpg'den kırpıldı) — pencere ikonu ve üst bar rozeti.
LOGO_PATH = str(Path(__file__).resolve().parent / "assets" / "logo" / "toya_logo.png")


class QtLogHandler(logging.Handler):
    """Standart Python loglarını PyQt sinyallerine yönlendiren özel log işleyici."""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signal.emit(msg)
        except Exception:
            self.handleError(record)


# ==========================================
# MENÜ VE SAĞ KLİK AÇILIR PENCERE STİLİ
# Kural: Zemin Mavi (#1e3a8a), Yazılar Beyaz (#ffffff)
# ==========================================
MENU_STYLESHEET = """
    QMenu {
        background-color: #1e3a8a;
        color: #ffffff;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 6px;
        font-size: 12px;
        font-weight: 600;
        font-family: 'Segoe UI';
    }
    QMenu::item {
        background-color: transparent;
        color: #ffffff;
        padding: 8px 22px 8px 12px;
        border-radius: 4px;
        margin: 2px 0px;
    }
    QMenu::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QMenu::separator {
        height: 1px;
        background-color: #3b82f6;
        margin: 4px 0px;
    }
"""


# ==========================================
# HOVER İLE YUKARI/AŞAĞI AÇILAN POPUP MENÜ
# Zemin Mavi (#1e3a8a), Yazılar Beyaz (#ffffff)
# ==========================================
class MenuPopup(QFrame):
    def __init__(self, parent, category_name, items, on_item_click):
        super().__init__(parent)
        self.parent_widget = parent
        self.on_item_click = on_item_click

        self.setStyleSheet("""
            QFrame {
                background-color: #1e3a8a;
                border: 1px solid #3b82f6;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, -4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        cat_lbl = QLabel(category_name)
        cat_lbl.setStyleSheet("""
            color: #93c5fd;
            font-size: 11px;
            font-weight: 800;
            font-family: 'Segoe UI';
            padding: 4px 10px;
            letter-spacing: 1px;
            border-bottom: 1px solid #2563eb;
        """)
        layout.addWidget(cat_lbl)

        implemented = getattr(self.parent_widget, "IMPLEMENTED_MODULES", None)
        muaf = getattr(self.parent_widget, "MODUL_FIRMA_MUAF", frozenset())
        firma_var = getattr(self.parent_widget, "_aktif_firma_var_mi", lambda: True)()
        for item in items:
            is_built = implemented is None or item in implemented
            # Firma gerektiren ama tanımlı/aktif firma olmayan modüller (2026-09-30): buton TIKLANABİLİR
            # kalır (tıklanınca open_module_in_tab firma tanımlamaya yönlendirir) ama pasif GÖRÜNÜR.
            firma_gerekli = is_built and item not in muaf and not firma_var
            etiket = item
            if not is_built:
                etiket = f"{item} (Yakında)"
            elif firma_gerekli:
                etiket = f"🔒 {item}"
            btn = QPushButton(etiket)
            btn.setCursor(
                Qt.CursorShape.PointingHandCursor if is_built
                else Qt.CursorShape.ForbiddenCursor,
            )
            btn.setEnabled(is_built)
            if firma_gerekli:
                btn.setToolTip("Bu modülü kullanmak için önce bir firma tanımlamanız/seçmeniz gerekiyor.")
            btn.setStyleSheet(("""
                QPushButton {
                    text-align: left;
                    padding: 8px 14px;
                    color: #ffffff;
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    font-family: 'Segoe UI';
                }
                QPushButton:hover {
                    background-color: #2563eb;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #1d4ed8;
                }
                QPushButton:disabled {
                    color: #93a5c9;
                }
            """) + ("QPushButton{color:#93a5c9;}" if firma_gerekli else ""))
            if is_built:
                btn.clicked.connect(lambda checked, i=item: self.item_clicked(i))
            layout.addWidget(btn)

        self.adjustSize()
        self.hide()

    def item_clicked(self, item_name):
        self.on_item_click(item_name)
        self.hide()

    def leaveEvent(self, event):  # noqa: N802
        self.hide()
        super().leaveEvent(event)


# ==========================================
# FOOTER BÜYÜK MENÜ BUTONU (TEK İKONLU & YUKARI AÇILIR)
# Zemin Mavi (#1e3a8a), Yazılar Beyaz (#ffffff)
# ==========================================
class FooterMenuButton(QPushButton):
    def __init__(self, emoji, category_name, items, parent_window):
        # Eğer category_name içinde önceden emoji varsa temizle (çift ikon önleme)
        clean_name = category_name
        for e in ["📊", "👥", "📦", "📄", "🔄", "⚙️", "🏢", "🏷️", "💾", "🤝", "💵", "📝", "🛒"]:
            clean_name = clean_name.replace(e, "").strip()
        super().__init__(f"{emoji}  {clean_name}")
        self.emoji = emoji
        self.category_name = clean_name
        self.items = items
        self.main_window = parent_window
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)

        self.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                font-weight: 700;
                color: #ffffff;
                font-family: 'Segoe UI';
                background-color: #1e3a8a;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #2563eb;
                color: #ffffff;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)

    def enterEvent(self, event):  # noqa: N802
        self.trigger_popup()
        super().enterEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        self.trigger_popup()
        super().mousePressEvent(event)

    def trigger_popup(self):
        global_pos = self.parentWidget().mapTo(self.main_window, self.pos())
        x = global_pos.x()
        y_bottom = global_pos.y()
        self.main_window.show_popup(self.category_name, self.items, x, y_bottom, open_upwards=True)


# Geriye dönük uyumluluk referansı
HoverMenuButton = FooterMenuButton


# ==========================================
# ANA SAYFA BÜYÜK MODÜL BUTONU (SAĞ VE SOL KLİK DESTEKLİ)
# Kural: Zemin Beyaz Kart İçinde Butonların İçi Mavi (#2563eb), Yazıları Beyaz (#ffffff)
# ==========================================
class GridModuleButton(QPushButton):
    def __init__(self, mod_name, mod_emoji, target_menu, parent_window):
        super().__init__()
        self.mod_name = mod_name
        self.mod_emoji = mod_emoji
        self.target_menu = target_menu
        self.main_window = parent_window
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(115, 96)

        self.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
                border-color: #1e3a8a;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)

        btn_lyt = QVBoxLayout(self)
        btn_lyt.setContentsMargins(8, 8, 8, 8)
        btn_lyt.setSpacing(4)
        btn_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.emoji_lbl = QLabel(mod_emoji)
        self.emoji_lbl.setFont(QFont("Segoe UI", 24))
        self.emoji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emoji_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        btn_lyt.addWidget(self.emoji_lbl)

        self.name_lbl = QLabel(mod_name)
        self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #ffffff; font-family: 'Segoe UI';")
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_lbl.setWordWrap(True)
        self.name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        btn_lyt.addWidget(self.name_lbl)

        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(8)
        sh.setColor(QColor(0, 0, 0, 30))
        sh.setOffset(0, 2)
        self.setGraphicsEffect(sh)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            self.main_window.show_grid_module_context_menu(event.pos(), self.target_menu, self)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_window.alt_menu_tiklandi(self.target_menu)
            super().mouseReleaseEvent(event)


# Placeholder Widgets for future tabs
class PlaceholderWidget(QWidget):
    def __init__(self, title_text, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(title_text)
        lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(lbl)

        desc = QLabel(self.tr("Bu modül Faz planına göre bir sonraki aşamada aktif edilecektir."))
        desc.setFont(QFont("Segoe UI", 11))
        desc.setStyleSheet("color: #95a5a6;")
        layout.addWidget(desc)


class MainWindow(QMainWindow):
    """3 Dikey Bölümlü Ana Panel (Sol: Favori İşlemler, Orta: Favori Raporlar, Sağ: Ana İkonlar)

    ve Mavi/Beyaz Tasarım Kararlı Modern Kurumsal ERP Ana Penceresi.
    """

    log_signal = pyqtSignal(str)

    def __init__(self, db_session, user_config: dict | None = None):
        super().__init__()
        self.db = db_session
        self.user_config = user_config or {}
        self.current_user = self._resolve_current_user()
        self.company_id = None
        self.active_popup = None
        self.favoriler = [self.tr("Ürün Yönetimi"), self.tr("Görevler"), self.tr("Teklif Yönetimi"), self.tr("Müşteriler & Cariler")]
        init_global_text_selection()

        # Şu an gerçekten açılan (placeholder'a düşmeyen) modüller — ana menüde ve
        # hızlı kısayollarda sadece bunların linki tıklanabilir olsun (madde 12).
        self.IMPLEMENTED_MODULES = frozenset({
            self.tr("Ana Panel"),
            self.tr("Görevler"),
            self.tr("Takvim"),
            self.tr("Geliştirme"),
            self.tr("Ürün Yönetimi"),
            self.tr("Stok Yönetimi"),
            self.tr("Hizmet Tanımları"),
            self.tr("Masraf Tanımları"),
            self.tr("Genel Ayarlar"),
            self.tr("Ekran & Grid Tanımları"),
            self.tr("Cari Listesi (AppGrid)"),
            self.tr("Müşteriler & Cariler"),
            self.tr("Cari Hareketleri"),
            self.tr("Stok Hareketleri"),
            self.tr("Kasa Kartları"),
            self.tr("Banka & POS Kartları"),
            self.tr("Kasa Hareketleri"),
            self.tr("Banka Hareketleri"),
            self.tr("Teklif Yönetimi"),
            self.tr("Sipariş Yönetimi"),
            self.tr("İrsaliyeler"),
            self.tr("Faturalar"),
            self.tr("Yeni Cari Kartı"),
            self.tr("Yeni Teklif Hazırla"),
        })

        self.menu_structure = {
            self.tr("GÖSTERGE"): ([self.tr("Ana Panel"), self.tr("Bildirimler")], "📊"),
            self.tr("CARİ"): ([self.tr("Müşteriler & Cariler"), self.tr("Cari Hareketleri"), self.tr("Cari Analiz")], "👥"),
            self.tr("STOK"): ([self.tr("Ürün Yönetimi"), self.tr("Hizmet Tanımları"), self.tr("Masraf Tanımları"), self.tr("Stok Hareketleri"), self.tr("Fiyat Politikaları")], "📦"),
            self.tr("KASA & BANKA"): ([self.tr("Kasa Kartları"), self.tr("Banka & POS Kartları"), self.tr("Kasa Hareketleri"), self.tr("Banka Hareketleri")], "💰"),
            self.tr("TEKLİF & SİPARİŞ"): ([self.tr("Teklif Yönetimi"), self.tr("Sipariş Yönetimi")], "📄"),
            self.tr("İRSALİYE & FATURA"): ([self.tr("İrsaliyeler"), self.tr("Faturalar")], "🧾"),
            self.tr("GÖREVLER"): ([self.tr("Görevler"), self.tr("Takvim")] + ([self.tr("Geliştirme")] if gelistirme_acik() else []), "✅"),
            self.tr("SİSTEM"): ([self.tr("Genel Ayarlar"), self.tr("İşlem Günlükleri")], "⚙️"),
        }

        self.init_ui()
        self._schedule_currency_autofetch()
        self._schedule_portal_pull()
        self._schedule_gorev_reminders()
        self._ilk_gosterim_yapildi = False

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._ilk_gosterim_yapildi:
            self._ilk_gosterim_yapildi = True
            QTimer.singleShot(0, self._ilk_yerlesimi_zorla)

    def _ilk_yerlesimi_zorla(self) -> None:
        """İlk gösterimden bir olay döngüsü turu sonra çağrılır: pencere gerçek (maksimize) boyutuna henüz
        oturmadan iç içe QSplitter/QTabWidget ağacı yerleşirse gösterge paneli dar kalabiliyordu (kullanıcı
        pencereyi elle büyütüp küçültene kadar). Bölücüyü kendi güncel boyutuna göre yeniden dağıtmak bunu düzeltir."""
        if hasattr(self, "dash_splitter"):
            self.dash_splitter.setSizes(self.dash_splitter.sizes())

    def _schedule_backups(self) -> None:
        """Zamanlanmış yedek işlerini (dakikada bir) ve takılan harici diskleri (5 sn) izler; işler arka plan
        iş parçacığında çalışır. pytest altında atlanır (bkz. `_schedule_currency_autofetch`)."""
        import os

        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        try:
            from src.desktop.ui.widgets.backup_runner import BackupRunner
            self.backup_runner = BackupRunner(self.db, self)
            self.backup_runner.job_finished.connect(
                lambda name, status, msg: self.show_toast(
                    f"Yedek — {name}: {msg}", "success" if status in ("ok", "nochange") else ("warning" if status == "warning" else "error")))
            self.backup_runner.start()
            self._setup_backup_popup()
        except Exception as exc:  # noqa: BLE001 - yedek zamanlayıcısı açılışı engellememeli
            logger.warning("Yedek zamanlayıcısı başlatılamadı: %s", exc)

    def _setup_backup_popup(self) -> None:
        """Yedek sürerken köşede aşama/ilerleme penceresi; kullanıcı işlem yaparsa uyarı. Ayrıca bu oturumun 'bağlıyım' işaretini
        30 sn'de bir yazar (yedek, başka kullanıcı bağlıyken başlamaz)."""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication

        from src.desktop.services.backup import presence
        from src.desktop.ui.widgets.backup_status_popup import (
            ActivityFilter,
            BackupStatusPopup,
        )

        r = self.backup_runner
        self.backup_popup = BackupStatusPopup(self)
        r.job_started.connect(self.backup_popup.on_started)
        r.line.connect(self.backup_popup.on_line)
        r.progress.connect(self.backup_popup.on_progress)
        r.job_finished.connect(self.backup_popup.on_finished)
        r.job_waiting.connect(self.backup_popup.on_waiting)
        self._activity_filter = ActivityFilter(self.backup_popup)
        QApplication.instance().installEventFilter(self._activity_filter)

        def beat() -> None:
            u = self.current_user
            try:
                presence.beat(self.db, (u.username if u is not None else (self.user_config or {}).get("username", "")) or "")
            except Exception:  # noqa: BLE001 - varlık işareti yazılamazsa uygulama etkilenmesin
                logger.debug("Oturum işareti yazılamadı", exc_info=True)

        self._presence_timer = QTimer(self)
        self._presence_timer.timeout.connect(beat)
        self._presence_timer.start(30_000)
        beat()

    def _gorev_paneli_sarmala(self, icerik: QWidget) -> QWidget:
        """Ana panelin orta sütunu (Görevler & Bildirimler) için açılır/kapanır sarmalayıcı.
        Kullanıcı isteği: bu sütun Favoriler ile Menü Gridi'nin tam ortasında durup dikkat
        dağıtıyordu; artık ince bir ok tuşuyla kapatılabiliyor, kapanınca boşalan genişlik Menü
        Gridi'ne geçiyor. Son durum `QSettings`'te kalıcı — bir sonraki açılışta hatırlanır."""
        self._gorev_panel_icerik = icerik
        self._gorev_panel_son_genislik = 340
        wrapper = QWidget()
        lyt = QHBoxLayout(wrapper)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(2)
        self._gorev_panel_toggle_btn = btn = QPushButton()
        btn.setFixedWidth(16)
        btn.setToolTip("Görevler & Bildirimler panelini aç/kapat")
        btn.setStyleSheet(
            "QPushButton{background:#e2e8f0;color:#475569;border:none;border-radius:4px;"
            "font-weight:700;font-size:11px;}QPushButton:hover{background:#cbd5e1;}",
        )
        btn.clicked.connect(lambda: self._gorev_paneli_ac_kapa(not icerik.isVisible()))
        lyt.addWidget(icerik, 1)
        lyt.addWidget(btn)
        acik = self.dash_settings.value("dashboard/gorevler_acik", True, type=bool)
        icerik.setVisible(acik)
        btn.setText("‹" if acik else "›")
        return wrapper

    def _gorev_paneli_ac_kapa(self, acik: bool) -> None:
        """`_gorev_paneli_sarmala`'nın aç/kapa mantığı — splitter genişliğini de Menü Gridi
        lehine/aleyhine ayarlar, hem anlık tıklamadan hem başlangıç tercihinden çağrılır."""
        self._gorev_panel_icerik.setVisible(acik)
        self._gorev_panel_toggle_btn.setText("‹" if acik else "›")
        self.dash_settings.setValue("dashboard/gorevler_acik", acik)
        sizes = self.dash_splitter.sizes()
        if len(sizes) != 3:
            return
        if acik:
            hedef = max(self._gorev_panel_son_genislik, 260)
            fark = hedef - sizes[1]
            self.dash_splitter.setSizes([sizes[0], hedef, max(sizes[2] - fark, 200)])
        else:
            if sizes[1] > 24:
                self._gorev_panel_son_genislik = sizes[1]
            self.dash_splitter.setSizes([sizes[0], 20, sizes[2] + sizes[1] - 20])
        self.dash_settings.setValue("dashboard/splitter_sizes", self.dash_splitter.sizes())

    def _bildirim_rozeti_guncelle(self) -> None:
        """Zil düğmesindeki okunmamış bildirim sayısını günceller."""
        try:
            from src.desktop.services.bildirim_service import BildirimService
            n = BildirimService(self.db).okunmamis_sayisi()
        except Exception:  # noqa: BLE001 - üst çubuk bildirim hatasıyla bozulmasın
            return
        self.btn_bildirim.setText(f"🔔 {n}" if n else "🔔")
        self.btn_bildirim.setStyleSheet(
            "QPushButton{background-color:%s; border:none; border-radius:18px; font-size:13px; font-weight:700; color:white; padding:0 10px;}"
            "QPushButton:hover{background-color:#2563eb;}" % ("#f59e0b" if n else "#1a2744"))

    def _bildirimleri_ac(self) -> None:
        from PyQt6.QtWidgets import QDialog, QVBoxLayout

        from src.desktop.ui.widgets.bildirimler_widget import BildirimlerWidget
        dlg = QDialog(self)
        dlg.setWindowTitle("Bildirimler")
        dlg.resize(520, 560)
        lay = QVBoxLayout(dlg)
        w = BildirimlerWidget(self.db, dlg, limit=100)
        w.degisti.connect(self._bildirim_rozeti_guncelle)
        w.kontrol_istendi.connect(lambda: self.portal_kontrol_et(elle=True))
        w.ac_istendi.connect(lambda tur, no: (dlg.accept(), self._bildirimden_ac(tur, no)))
        self.portal_kontrol_et()
        lay.addWidget(w)
        dlg.exec()
        self._bildirim_rozeti_guncelle()

    def _bildirimden_ac(self, tur: str, no: str) -> None:
        """Bildirimdeki belgeyi (teklif) açar."""
        if tur != "teklif" or not no:
            return
        from sqlalchemy import select

        from src.core.models import Quotation
        from src.desktop.ui.screens.document_detail_screen import DocumentDetailScreen
        q = self.db.scalar(select(Quotation).where(Quotation.quotation_number == no))
        if q is None:
            self.show_toast(f"{no} numaralı teklif bulunamadı.", "warning")
            return
        dlg = DocumentDetailScreen.open_as_dialog(parent=self, db_session=self.db, doc_id=q.id, initial_type_idx=0, company_id=q.company_id)
        dlg.exec()

    def _portal_kararlarini_bildir(self, applied: list[dict]) -> None:
        """Portaldan çekilen müşteri kararlarını ekranda bildirir (en fazla 3 ayrı uyarı, kalanı özet)."""
        from src.desktop.services.bildirim_service import TURLER
        haberler = [a for a in applied if a.get("baslik")]
        for a in haberler[:3]:
            simge, tip = TURLER.get(a.get("tur", ""), ("🔔", "info"))
            self.show_toast(f"{simge} {a['baslik']} — {a['quotation_number']}", tip)
        if len(haberler) > 3:
            self.show_toast(f"🔔 {len(haberler) - 3} bildirim daha var (zil düğmesine bakın).", "info")
        self._bildirim_rozeti_guncelle()

    def _schedule_portal_pull(self) -> None:
        """Online teklif portalındaki müşteri kararlarını (kabul/ret/karşı teklif/süre dolumu) açılıştan 5 sn sonra ve her dakika
        arka planda çeker. Portal tanımlı değilse hiçbir şey yapmaz; pytest altında atlanır (bkz. `_schedule_currency_autofetch`)."""
        import os

        from PyQt6.QtCore import QTimer

        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        self._portal_timer = QTimer(self)
        self._portal_timer.timeout.connect(self.portal_kontrol_et)
        self._portal_timer.start(60 * 1000)
        QTimer.singleShot(5000, self.portal_kontrol_et)

    def portal_kontrol_et(self, elle: bool = False) -> None:
        """Portalı şimdi kontrol eder (ağ arka planda). `elle=True` ise sonuç (yeni karar yok / hata) da bildirilir."""
        from src.desktop.services import portal_sync_service
        from src.desktop.ui.widgets.portal_pull_worker import PortalPullWorker

        w = getattr(self, "_portal_worker", None)
        if w is not None and w.isRunning():
            return
        try:
            req = portal_sync_service.decisions_request(self.db)
        except Exception as exc:  # noqa: BLE001 - arka plan görevi hiçbir zaman engellememeli
            logger.warning("Portal ayarları okunamadı: %s", exc)
            return
        if req is None:
            if elle:
                self.show_toast("Portal adresi / API anahtarı tanımlı değil (Ayarlar › Sistem › Online Portal).", "warning")
            return
        self._portal_worker = PortalPullWorker(req, 8 if elle else 5, self)
        self._portal_worker.bitti.connect(lambda body, err, c=req[2]: self._portal_cekildi(c, body, err, elle))
        self._portal_worker.start()

    def _portal_cekildi(self, cursor: int, body, err: str, elle: bool) -> None:
        from src.desktop.services import portal_sync_service
        if body is None:
            logger.warning("Portal kararları alınamadı: %s", err)
            if elle:
                self.show_toast(err, "warning")
            return
        try:
            r = portal_sync_service.apply_decisions(self.db, cursor, body)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Portal kararları uygulanamadı: %s", exc)
            self.db.rollback()
            return
        if r.applied:
            self._portal_kararlarini_bildir(r.applied)
        elif elle:
            self.show_toast("Portal kontrol edildi: yeni karar yok.", "info")

    def _schedule_currency_autofetch(self) -> None:
        """Program açıldığında, ayarlarda seçilen döviz kuru kaynağından
        (manuel değilse) bugün için henüz çekilmemişse BİR KEZ otomatik kur
        çeker. Pencere ilk çizimini engellemesin diye kısa bir gecikmeyle
        (ve tamamen best-effort: ağ hatası girişi hiçbir şekilde etkilemez).

        Test ortamında (pytest) atlanır — aksi halde testler arasında
        Qt olay döngüsü işletildikçe (`processEvents`/`qWait`) bu zamanlayıcı
        beklenmedik anda ateşlenip gerçek bir ağ isteği başlatabilir; bu da
        internet erişimi olmayan CI/test ortamlarında tüm test paketini
        yavaşlatır/kilitler. Servisin kendisi (`currency_rate_service`) ve bu
        zamanlayıcının kurulumu ayrı ayrı test edilir (bkz. test_main_window.py)."""
        import os

        from PyQt6.QtCore import QTimer

        if os.environ.get("PYTEST_CURRENT_TEST"):
            return

        def _run():
            try:
                from src.desktop.services import currency_rate_service
                currency_rate_service.startup_autofetch(self.db)
            except Exception as exc:  # noqa: BLE001 - açılışı asla engellemesin
                logger.warning("Açılışta otomatik döviz kuru çekimi başarısız: %s", exc)

        QTimer.singleShot(800, _run)

    def _resolve_current_user(self):
        """Login'de gelen kullanıcı adına göre DB'den User nesnesini çeker."""
        uname = (self.user_config or {}).get("username")
        if not uname:
            return None
        try:
            from src.core.models import User
            return self.db.query(User).filter(User.username == uname).first()
        except Exception:  # noqa: BLE001
            return None

    def _kullanici_adi(self) -> str:
        u = self.current_user
        return (u.username if u is not None else (self.user_config or {}).get("username", "")) or ""

    def _schedule_gorev_reminders(self) -> None:
        """Zamanı gelen görev/randevu hatırlatmalarını dakikada bir kontrol edip bildirim (toast) gösterir. pytest altında atlanır."""
        import os

        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        from PyQt6.QtCore import QTimer

        from src.desktop.services.gorev_service import GorevService

        def kontrol() -> None:
            try:
                for g in GorevService(self.db).hatirlatmalar(kullanici=self._kullanici_adi()):
                    self.show_toast(f"🔔 {g.baslik}" + (f" — {g.bitis:%d.%m %H:%M}" if g.bitis else ""), "info")
            except Exception:  # noqa: BLE001 - hatırlatma hatası uygulamayı etkilemesin
                logger.debug("Görev hatırlatması kontrol edilemedi", exc_info=True)

        self._gorev_timer = QTimer(self)
        self._gorev_timer.timeout.connect(kontrol)
        self._gorev_timer.start(60_000)
        QTimer.singleShot(5000, kontrol)

    def _current_user_label(self) -> str:
        u = self.current_user
        if u is not None:
            name = u.full_name or u.username
            role = getattr(getattr(u, "role_ref", None), "name", None)
            if not role:
                role = "Yönetici" if getattr(u, "role", "") == "admin" else "Kullanıcı"
            return f"👤 {name} · {role}"
        uname = (self.user_config or {}).get("username") or "misafir"
        return f"👤 {uname}"

    def init_ui(self):
        self.setWindowTitle(self.tr("Toya ERP"))
        self.resize(1366, 768)  # 1366x768 ekranlarda normal/restore boyutu bile taşmasın
        self.setStyleSheet("background-color: #f0f4f8;")
        if Path(LOGO_PATH).is_file():
            self.setWindowIcon(QIcon(LOGO_PATH))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ==========================================
        # 1. ÜST BAR (HEADER BAR)
        # ==========================================
        header_bar = QWidget()
        header_bar.setFixedHeight(56)
        header_bar.setStyleSheet("background-color: #0b1120;")

        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(18)

        self.logo_icon = QLabel()
        if Path(LOGO_PATH).is_file():
            pix = QPixmap(LOGO_PATH).scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo_icon.setPixmap(pix)
            self.logo_icon.setFixedSize(42, 42)
            self.logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.logo_icon.setStyleSheet("background-color:#ffffff; border-radius:8px;")
            header_layout.addWidget(self.logo_icon)

        self.logo = QLabel(self.tr("TOYA ERP"))
        self.logo.setObjectName("pan.nav.logo")
        self.logo.setToolTip("[pan.nav.logo] Toya ERP Kurumsal Yönetim Platformu")
        self.logo.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff; font-family: 'Segoe UI';")
        header_layout.addWidget(self.logo)

        header_layout.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setObjectName("cmp.top.search")
        self.search_box.setToolTip("[cmp.top.search] Global Modül ve Kayıt Hızlı Arama (Ctrl+K)")
        self.search_box.setPlaceholderText(self.tr("🔍 Arama yap... (Ctrl+K)"))
        self.search_box.setMinimumWidth(280)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #1a2744;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 12px;
                color: white;
                font-size: 13px;
                font-family: 'Segoe UI';
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
        """)
        header_layout.addWidget(self.search_box)

        self.user_lbl = QLabel(self._current_user_label())
        self.user_lbl.setObjectName("sys.usr.001")
        self.user_lbl.setToolTip("[sys.usr.001] Oturum açan kullanıcı ve rolü")
        self.user_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; font-family: 'Segoe UI';")
        header_layout.addWidget(self.user_lbl)

        self.btn_switch_user = QPushButton("🔄 Değiştir")
        self.btn_switch_user.setToolTip("Kullanıcı Değiştir (şirket sabit kalır)")
        self.btn_switch_user.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_user.setStyleSheet(
            "QPushButton{background:#1a2744;color:#cbd5e1;border:1px solid #334155;"
            "border-radius:6px;padding:5px 10px;font-size:11px;font-weight:600;}"
            "QPushButton:hover{background:#243356;color:#fff;}",
        )
        self.btn_switch_user.clicked.connect(self.switch_user)
        header_layout.addWidget(self.btn_switch_user)

        self.company_combo = QComboBox()
        self.company_combo.setObjectName("tan.cmp.001")
        self.company_combo.setToolTip("[tan.cmp.001] Aktif Şirket / Şube Seçimi")
        self.company_combo.setMinimumWidth(160)
        self.company_combo.setStyleSheet("""
            QComboBox {
                background-color: #1a2744;
                color: white;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI';
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        header_layout.addWidget(self.company_combo)

        # Mimari Kodları Göster / Gizle Parametre Butonu
        self.btn_toggle_hints = QPushButton("🏷️ Kodlar: AÇIK")
        self.btn_toggle_hints.setObjectName("sys.cfg.hints")
        self.btn_toggle_hints.setCheckable(True)
        self.btn_toggle_hints.setChecked(True)
        self.btn_toggle_hints.setToolTip("[sys.cfg.hints] Standart Mimari Ekran ve Buton Kodlarını (act.* / cmp.*) Aç / Kapat")
        self.btn_toggle_hints.setStyleSheet("""
            QPushButton {
                background-color: #047857;
                color: #a7f3d0;
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #059669;
                color: #ffffff;
            }
        """)
        self.btn_toggle_hints.clicked.connect(self.toggle_architecture_hints)
        header_layout.addWidget(self.btn_toggle_hints)

        btn_theme_settings = QPushButton("📐 " + self.tr("Grid & Tema"))
        btn_theme_settings.setObjectName("cmp.top.theme")
        btn_theme_settings.setToolTip("[cmp.top.theme] AppGrid Tema, Renk ve Satır Yüksekliği Ayarları")
        btn_theme_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_theme_settings.setStyleSheet("""
            QPushButton {
                background-color: #1e3a8a;
                color: #bfdbfe;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        btn_theme_settings.clicked.connect(self._open_theme_settings_dialog)
        header_layout.addWidget(btn_theme_settings)

        self.btn_bildirim = QPushButton("🔔")
        self.btn_bildirim.setObjectName("cmp.top.bildirim")
        self.btn_bildirim.setToolTip("Bildirimler (online portal müşteri kararları)")
        self.btn_bildirim.setMinimumSize(36, 36)
        self.btn_bildirim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bildirim.clicked.connect(self._bildirimleri_ac)
        header_layout.addWidget(self.btn_bildirim)

        help_btn = QPushButton("❓")
        help_btn.setObjectName("cmp.top.help")
        help_btn.setToolTip("[cmp.top.help] Kullanıcı Kılavuzu & Yardım Dokümantasyonu")
        help_btn.setFixedSize(36, 36)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a2744;
                border: none;
                border-radius: 18px;
                font-size: 14px;
                color: white;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        help_btn.clicked.connect(lambda: self.show_toast(self.tr("Kullanıcı kılavuzu ve yardım paneli yükleniyor..."), "info"))
        header_layout.addWidget(help_btn)

        main_layout.addWidget(header_bar)

        # ==========================================
        # 2. DİNAMİK SEKMELİ EKRAN ALANI & ESNEK FLEXBOX / SPLITTER ANA PANEL
        # ==========================================
        self.dashboard_container = QWidget()
        dash_main_vlyt = QVBoxLayout(self.dashboard_container)
        dash_main_vlyt.setContentsMargins(16, 16, 16, 16)
        dash_main_vlyt.setSpacing(12)

        self.dash_settings = QSettings("ToyaERP", "DashboardSettings")

        # QSplitter ile serbestçe boyutlandırılabilen Flexbox Gövde (Resim 1 & 2)
        self.dash_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.dash_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cbd5e1;
                width: 6px;
                margin: 4px 2px;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background-color: #2563eb;
            }
        """)

        # 1. Sol: Favori İşlemler Widget'ı
        self.fav_widget = FavoriteActionsWidget(favorites=self.favoriler, parent=self)
        self.fav_widget.module_selected.connect(self.alt_menu_tiklandi)
        self.fav_widget.quick_action_triggered.connect(self.alt_menu_tiklandi)
        self.dash_splitter.addWidget(self.fav_widget)

        # 1b. Orta: Bugünün görevleri (gecikmiş + bugün; çift tıkla aç, tamamla)
        from src.desktop.ui.widgets.bugun_gorevleri_widget import BugunGorevleriWidget
        self.bugun_gorevleri = BugunGorevleriWidget(self.db, self._kullanici_adi(), parent=self, otomatik_yenile=not os.environ.get("PYTEST_CURRENT_TEST"))
        self.bugun_gorevleri.tumu_istendi.connect(lambda: self.alt_menu_tiklandi(self.tr("Görevler")))
        from src.desktop.ui.widgets.bildirimler_widget import BildirimlerWidget
        self.bildirimler_karti = BildirimlerWidget(self.db, parent=self, limit=15, otomatik_yenile=not os.environ.get("PYTEST_CURRENT_TEST"))
        self.bildirimler_karti.ac_istendi.connect(self._bildirimden_ac)
        self.bildirimler_karti.degisti.connect(self._bildirim_rozeti_guncelle)
        self.bildirimler_karti.kontrol_istendi.connect(lambda: self.portal_kontrol_et(elle=True))
        orta = QWidget()
        orta_l = QVBoxLayout(orta)
        orta_l.setContentsMargins(0, 0, 0, 0)
        orta_l.setSpacing(8)
        orta_l.addWidget(self.bugun_gorevleri, 3)
        orta_l.addWidget(self.bildirimler_karti, 2)
        self.dash_splitter.addWidget(self._gorev_paneli_sarmala(orta))
        self._bildirim_rozeti_guncelle()
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            from src.desktop.services import veri_bus
            veri_bus.kur()
            veri_bus.veri_bus().degisti.connect(lambda k: QTimer.singleShot(150, self._bildirim_rozeti_guncelle) if k == "bildirim" else None)

        # 2. Sağ: Ana Menüler Modül Gridi Widget'ı
        self.menu_grid_widget = MenuGridWidget(parent=self)
        self.menu_grid_widget.set_implemented(self.IMPLEMENTED_MODULES)
        self.menu_grid_widget.module_selected.connect(self.alt_menu_tiklandi)
        self.menu_grid_widget.module_right_clicked.connect(
            lambda mod, pos: self.show_grid_module_context_menu(pos, mod, self),
        )
        self.menu_grid_widget.log_action_requested.connect(
            lambda: self.open_module_in_tab(self.tr("İşlem Günlükleri")),
        )
        self.dash_splitter.addWidget(self.menu_grid_widget)

        # Splitter Genişlik Oranlarını QSettings'ten Yükle / Kaydet
        saved_sizes = self.dash_settings.value("dashboard/splitter_sizes", None)
        if saved_sizes:
            try:
                boyutlar = [int(s) for s in saved_sizes]
                self.dash_splitter.setSizes(boyutlar if len(boyutlar) == self.dash_splitter.count() else [380, 340, 800])
            except Exception:
                self.dash_splitter.setSizes([380, 340, 800])
        else:
            self.dash_splitter.setSizes([380, 340, 800])

        self.dash_splitter.splitterMoved.connect(
            lambda: self.dash_settings.setValue("dashboard/splitter_sizes", self.dash_splitter.sizes()),
        )

        dash_main_vlyt.addWidget(self.dash_splitter, 1)

        # Geriye dönük uyumluluk için referanslar
        self.fav_screens_list = self.fav_widget.list_widget
        self.fav_count_badge = self.fav_widget.badge_count

        # ----------------------------------------------------
        # QTabWidget Ana Kapsayıcı
        # ----------------------------------------------------
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.tab_changed)

        # Tab 0: Sabit ve Kapatılamaz Dashboard
        self.tab_widget.addTab(self.dashboard_container, "🏠 " + self.tr("Ana Panel"))
        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)

        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #f0f4f8;
            }
            QTabBar::tab {
                background-color: #e2e8f0;
                color: #475569;
                font-weight: 600;
                font-family: 'Segoe UI';
                font-size: 11px;
                padding: 6px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
                min-height: 22px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2563eb;
                border-bottom: 2px solid #2563eb;
                font-weight: 700;
            }
            QTabBar::tab:hover:!selected {
                background-color: #cbd5e1;
                color: #1e293b;
            }
        """)
        main_layout.addWidget(self.tab_widget, 1)

        # ==========================================
        # 2.5. FOOTER ÜSTÜ AÇILIR/KAPANIR HIZLI ERİŞİM BANDI (QuickTilesBarWidget - Resim 2)
        # ==========================================
        self.quick_tiles_bar = QuickTilesBarWidget(parent=self)
        self.quick_tiles_bar.tile_clicked.connect(self.alt_menu_tiklandi)
        main_layout.addWidget(self.quick_tiles_bar)

        # ==========================================
        # 3. BÜYÜK MODÜL MENÜLERİ VE DURUM ÇUBUĞU (FOOTER BAR)
        # ==========================================
        self.footer_bar = QFrame()
        self.footer_bar.setObjectName("pan.nav.footer")
        self.footer_bar.setFixedHeight(56)
        self.footer_bar.setStyleSheet("""
            QFrame#pan.nav.footer, QFrame {
                background-color: #0b1120;
                color: #94a3b8;
                border-top: 1px solid #1e293b;
            }
        """)
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(10)

        # Footer Menü Butonları (Büyük, Tek İkonlu ve Belirgin) — 8 buton tek satırda ~1955px
        # tutuyor (1366x768'de taşıyordu); yatay kaydırmalı bir şeride sarıldı: geniş ekranda
        # kaydırma çubuğu hiç görünmez, dar ekranda pencere minimum genişliği butonlara göre
        # şişmek yerine şerit kaydırılabilir olur.
        btn_strip = QWidget()
        btn_row = QHBoxLayout(btn_strip)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(10)
        self.menu_buttons = []
        for category_name, (sub_items, emoji) in self.menu_structure.items():
            btn = FooterMenuButton(emoji, category_name, sub_items, self)
            btn_row.addWidget(btn)
            self.menu_buttons.append(btn)
        btn_row.addStretch()

        btn_scroll = QScrollArea()
        btn_scroll.setWidgetResizable(True)
        btn_scroll.setWidget(btn_strip)
        btn_scroll.setFrameShape(QFrame.Shape.NoFrame)
        btn_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        btn_scroll.setStyleSheet("background: transparent; QScrollArea{background:transparent;}")
        footer_layout.addWidget(btn_scroll, 1)

        # Geriye dönük uyumluluk referansı
        self.menu_bar = self.footer_bar

        # Sistem Durum Rozeti
        status_badge = QLabel("🟢 " + self.tr("Sistem Aktif"))
        status_badge.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 700; font-family: 'Segoe UI'; padding-right: 12px;")
        footer_layout.addWidget(status_badge)

        # Canlı Saat & Tarih
        self.live_time_label = QLabel()
        self.live_time_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #38bdf8; font-family: 'Segoe UI';")
        footer_layout.addWidget(self.live_time_label)

        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_live_time)
        self.time_timer.start(1000)
        self.update_live_time()

        main_layout.addWidget(self.footer_bar)

        self.update_favorites_ui()

        self.ctrl_k = QShortcut(QKeySequence("Ctrl+K"), self)
        self.ctrl_k.activated.connect(self.focus_search)

        # Şirketleri yükle ve dinle
        self.load_companies()

        # Log Altyapısı
        self.setup_live_logs()

    def setup_live_logs(self):
        self.qt_log_handler = QtLogHandler(self.log_signal)
        self.qt_log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(self.qt_log_handler)
        self.log_signal.connect(self.append_log)

    def closeEvent(self, event):  # noqa: N802
        runner = getattr(self, "backup_runner", None)
        if runner is not None and runner.is_busy():
            from PyQt6.QtWidgets import QMessageBox
            if QMessageBox.question(
                    self, "Yedek çalışıyor", "Şu anda bir yedek işi çalışıyor. Şimdi çıkarsanız yarım kalır (yarım yedek geçerli sayılmaz, "
                    "sonraki denemede yeniden alınır).\n\nYine de çıkılsın mı?",
                    defaultButton=QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if runner is not None:
            runner.stop()
            try:
                from src.desktop.services.backup import presence
                presence.leave(self.db)
            except Exception:  # noqa: BLE001
                pass
        if hasattr(self, "time_timer") and self.time_timer.isActive():
            self.time_timer.stop()
        if hasattr(self, "qt_log_handler"):
            try:
                logging.getLogger().removeHandler(self.qt_log_handler)
            except Exception:
                pass
        super().closeEvent(event)

    def append_log(self, message):
        pass

    def show_popup(self, category_name, items, x, y_bottom, open_upwards=True):
        if self.active_popup:
            self.active_popup.close()
        self.active_popup = MenuPopup(self, category_name, items, self.alt_menu_tiklandi)
        self.active_popup.adjustSize()
        popup_height = self.active_popup.sizeHint().height()

        if open_upwards:
            # Footer'ın hemen üzerinde açılır
            y = max(10, y_bottom - popup_height - 6)
        else:
            y = y_bottom

        self.active_popup.move(x, y)
        self.active_popup.show()
        self.active_popup.raise_()

    def show_toast(self, message, notification_type="info"):
        toast = ToastNotification(self, message, notification_type)
        toast.show_toast()

    def focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def toggle_architecture_hints(self, checked):
        if checked:
            self.btn_toggle_hints.setText("🏷️ Kodlar: AÇIK")
            self.btn_toggle_hints.setStyleSheet("""
                QPushButton {
                    background-color: #047857;
                    color: #a7f3d0;
                    border: 1px solid #10b981;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.show_toast(self.tr("🏷️ Standart mimari kod ve ipucu gösterimi AÇILDI."), "success")
        else:
            self.btn_toggle_hints.setText("🏷️ Kodlar: KAPALI")
            self.btn_toggle_hints.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    border: 1px solid #475569;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.show_toast(self.tr("🏷️ Mimari kod gösterimi KAPATILDI (Kullanıcı Modu)."), "warning")

    def _open_theme_settings_dialog(self):
        self.open_module_in_tab(self.tr("Ekran & Grid Tanımları"))

    def update_live_time(self):
        self.live_time_label.setText(datetime.datetime.now().strftime("🕒 %d.%m.%Y %H:%M:%S"))

    def alt_menu_tiklandi(self, menu_name):
        self.open_module_in_tab(menu_name)

    #: Aktif firma tanımlanmadan da açılabilecek modüller (2026-09-30) — kurulum/başlangıç akışı için
    #: gerekli olanlar (Firma Bilgileri'ne ulaşmak için Genel Ayarlar açılabilmeli) + kişisel/sistem
    #: araçları (şirket verisiyle ilgisi olmayan Görevler, Geliştirme vb.). Diğer TÜM modüller (Cari,
    #: Stok, Kasa/Banka, Teklif/Sipariş, İrsaliye/Fatura...) aktif firma gerektirir.
    MODUL_FIRMA_MUAF = frozenset({
        "Ana Panel", "Bildirimler", "Genel Ayarlar", "Görevler", "Takvim", "Geliştirme", "İşlem Günlükleri",
    })

    def _aktif_firma_var_mi(self) -> bool:
        if not self.db:
            return True
        from src.desktop.services.company_service import CompanyService
        return CompanyService(self.db).aktif_firma() is not None

    def _firma_tanimlamaya_yonlendir(self) -> None:
        """Aktif firma yokken bir modül açılmaya çalışılınca çağrılır. Hiç firma yoksa yeni kayıt formunu
        açar ve kaydedilince otomatik aktif yapar. Firma(lar) var ama hiçbiri aktif değilse (nadir durum:
        kullanıcı birden fazla firma tanımlamış ama birini seçmemiş) ilkini aktif yapar — ayrı bir "firma
        seç" ekranı bu aşamada kapsam dışı bırakıldı, bkz. gelistirme/13_sirket_tanimlari/tasarim.md."""
        from src.desktop.services.company_service import CompanyService
        svc = CompanyService(self.db)
        firmalar = svc.list_companies()
        if firmalar:
            svc.aktif_firma_sec(firmalar[0].id)
            self.show_toast(f"'{firmalar[0].short_name}' aktif firma olarak seçildi.", "info")
        else:
            from src.desktop.ui.dialogs.firma_sihirbazi_dialog import FirmaSihirbaziDialog
            dlg = FirmaSihirbaziDialog(db_session=self.db, parent=self)
            dlg.exec()
            self.load_companies()
        if hasattr(self, "menu_grid_widget"):
            self.menu_grid_widget.set_implemented(self.IMPLEMENTED_MODULES)

    def open_module_in_tab(self, menu_name):
        # --- Yetki kontrolü ---
        from src.desktop.security.gate import can, module_permission
        perm = module_permission(menu_name)
        if perm and not can(perm):
            self.show_toast(f"'{menu_name}' için yetkiniz yok.", "error")
            return

        # --- Firma tanımlı mı kontrolü (2026-09-30) ---
        if menu_name not in self.MODUL_FIRMA_MUAF and not self._aktif_firma_var_mi():
            self.show_toast("Önce bir firma tanımlamanız/seçmeniz gerekiyor.", "warning")
            self._firma_tanimlamaya_yonlendir()
            return

        SCREEN_CODES = {
            self.tr("Teklif Yönetimi"): "📄 [isl.quo.001] " + self.tr("Teklif Yönetimi"),
            self.tr("Teklifler"): "📄 [isl.quo.001] " + self.tr("Teklif Yönetimi"),
            self.tr("Sipariş Yönetimi"): "🛒 [isl.ord.001] " + self.tr("Sipariş Yönetimi"),
            self.tr("Siparişler"): "🛒 [isl.ord.001] " + self.tr("Sipariş Yönetimi"),
            self.tr("İrsaliyeler"): "🚚 [isl.wbl.001] " + self.tr("İrsaliye Yönetimi"),
            self.tr("Faturalar"): "🧾 [isl.inv.001] " + self.tr("Fatura Yönetimi"),
            self.tr("Hızlı Fatura"): "🧾 [isl.inv.001] " + self.tr("Fatura Yönetimi"),
            self.tr("Bugün Ciro"): "🧾 [isl.inv.001] " + self.tr("Fatura Yönetimi"),
            self.tr("Müşteriler & Cariler"): "👥 [tan.car.001] " + self.tr("Müşteriler & Cariler"),
            self.tr("Cari Listesi (AppGrid)"): "📐 [app.grd.001] " + self.tr("Cari Listesi (AppGrid)"),
            self.tr("Ekran & Grid Tanımları"): "📐 [sys.grd.001] " + self.tr("Ekran & Grid Tanımları"),
            self.tr("Ürün Yönetimi"): "🏷️ [tan.stk.001] " + self.tr("Ürün & Stok Yönetimi"),
            self.tr("Hizmet Tanımları"): "🧰 [tan.hzm.001] " + self.tr("Hizmet Tanımları"),
            self.tr("Masraf Tanımları"): "💸 [tan.msr.001] " + self.tr("Masraf Tanımları"),
            self.tr("Görevler"): "✅ [isl.tsk.001] " + self.tr("Görevler"),
            self.tr("Takvim"): "📅 [isl.tak.001] " + self.tr("Takvim"),
            self.tr("Geliştirme"): "🛠️ [dev.trk.001] " + self.tr("Geliştirme"),
            self.tr("Genel Ayarlar"): "⚙️ [sys.set.001] " + self.tr("Genel Ayarlar"),
            self.tr("İşlem Günlükleri"): "📝 [sys.log.001] " + self.tr("İşlem Günlükleri"),
            self.tr("Cari Analiz"): "📊 [rpt.car.001] " + self.tr("Cari Analiz"),
            self.tr("Cari Hareketleri"): "💱 [isl.car.001] " + self.tr("Cari Hareketleri"),
            self.tr("Fiyat Politikaları"): "💵 [tan.prc.001] " + self.tr("Fiyat Politikaları"),
            self.tr("Stok Hareketleri"): "📦 [isl.stk.001] " + self.tr("Stok Hareketleri"),
            self.tr("Kasa Kartları"): "💰 [tan.ksa.001] " + self.tr("Kasa Kartları"),
            self.tr("Banka & POS Kartları"): "🏦 [tan.bnk.001] " + self.tr("Banka & POS Kartları"),
            self.tr("Kasa Hareketleri"): "💰 [isl.ksa.001] " + self.tr("Kasa Hareketleri"),
            self.tr("Banka Hareketleri"): "🏦 [isl.bnk.001] " + self.tr("Banka Hareketleri"),
            self.tr("Pazaryeri Bağlantıları"): "🤝 [int.mkt.001] " + self.tr("Pazaryeri Bağlantıları"),
        }
        # Hızlı Kısayollar ("Yeni Cari Kartı Aç" / "Yeni Teklif Hazırla") gerçek
        # liste ekranını açar ve ardından o ekranın "yeni kayıt" işlemini tetikler.
        QUICK_NEW_TARGETS = {
            self.tr("Yeni Cari Kartı"): (self.tr("Müşteriler & Cariler"), "on_new_clicked"),
            self.tr("Yeni Teklif Hazırla"): (self.tr("Teklif Yönetimi"), "on_new_clicked"),
        }
        quick_new_action = None
        if menu_name in QUICK_NEW_TARGETS:
            menu_name, quick_new_action = QUICK_NEW_TARGETS[menu_name]

        tab_title = SCREEN_CODES.get(menu_name, f"📌 {menu_name}")

        # Eğer sekme zaten açıksa ona odaklan
        for idx in range(1, self.tab_widget.count()):
            t_text = self.tab_widget.tabText(idx)
            if menu_name in t_text or tab_title == t_text:
                self.tab_widget.setCurrentIndex(idx)
                if quick_new_action:
                    existing = self.tab_widget.widget(idx)
                    action = getattr(existing, quick_new_action, None)
                    if callable(action):
                        action()
                return

        # Yeni sekme için widget oluştur
        new_widget = None
        company_id = self.company_combo.currentData()

        if menu_name in (self.tr("Görevler"), self.tr("Takvim")):
            from src.desktop.ui.gorevler_screen import GorevlerScreen
            new_widget = GorevlerScreen(db_session=self.db, parent=self, kullanici=self._kullanici_adi())
            if menu_name == self.tr("Takvim"):
                new_widget.set_gorunum("takvim")
        elif menu_name == self.tr("Geliştirme") and gelistirme_acik():
            from src.desktop.ui.dev_tracker_screen import DevTrackerScreen
            new_widget = DevTrackerScreen(parent=self, kullanici=self._kullanici_adi())
        elif menu_name in (self.tr("Aktif Görevler"), self.tr("Yedekleme")):
            new_widget = BackupWidget(self.db)
        elif menu_name in (
            "Stok", "Stok Kartları", "Stok Yönetimi", "Ürün Yönetimi", "Stok Uyarısı",
            self.tr("Stok"), self.tr("Stok Kartları"), self.tr("Stok Yönetimi"),
            self.tr("Ürün Yönetimi"), self.tr("Stok Uyarısı"),
        ):
            new_widget = StokListScreen(
                db_session=self.db,
                company_id=company_id,
                kart_modu="stok",
                parent=self,
            )
            new_widget.toast_requested.connect(self.show_toast)
        elif menu_name in ("Hizmet Tanımları", self.tr("Hizmet Tanımları")):
            new_widget = StokListScreen(
                db_session=self.db,
                company_id=company_id,
                kart_modu="hizmet",
                parent=self,
            )
            new_widget.toast_requested.connect(self.show_toast)
        elif menu_name in ("Masraf Tanımları", self.tr("Masraf Tanımları")):
            new_widget = StokListScreen(
                db_session=self.db,
                company_id=company_id,
                kart_modu="masraf",
                parent=self,
            )
            new_widget.toast_requested.connect(self.show_toast)
        elif menu_name in (self.tr("Genel Ayarlar"), self.tr("Sistem Ayarları")):
            new_widget = SettingsWidget(self.db)
            if hasattr(new_widget, "companies_updated"):
                new_widget.companies_updated.connect(self._refresh_header_from_settings)
            # Ayarlarda firma/kullanıcı değişince üst bar tazelensin
            new_widget.destroyed.connect(self._refresh_header_from_settings)
        elif menu_name == self.tr("Ekran & Grid Tanımları"):
            from src.desktop.ui.screen_definitions_manager import (
                ScreenDefinitionsManagerWidget,
            )
            new_widget = ScreenDefinitionsManagerWidget(self)
        elif menu_name in (self.tr("Cari Listesi (AppGrid)"), self.tr("AppGrid Demo")):
            from src.desktop.ui.demo_appgrid_screen import AppGridCariDemoScreen
            new_widget = AppGridCariDemoScreen(self)
        elif menu_name in (
            "Cari", "Müşteriler & Cariler", "Cari Bakiye", "Müşteriler",
            self.tr("Cari"), self.tr("Müşteriler & Cariler"), self.tr("Cari Bakiye"), self.tr("Müşteriler"),
        ):
            new_widget = CariListScreen(
                db_session=self.db,
                company_id=company_id,
                parent=self,
            )
            new_widget.toast_requested.connect(self.show_toast)
        elif menu_name in (self.tr("Kasa Kartları"), self.tr("Banka & POS Kartları")):
            from src.desktop.ui.finans_hesap_list_screen import FinansHesapListScreen
            new_widget = FinansHesapListScreen(db_session=self.db, grup="kasa" if menu_name == self.tr("Kasa Kartları") else "banka", parent=self)
        elif menu_name in (self.tr("Kasa Hareketleri"), self.tr("Banka Hareketleri")):
            from src.desktop.ui.finans_hareket_screen import FinansHareketScreen
            new_widget = FinansHareketScreen(db_session=self.db, grup="kasa" if menu_name == self.tr("Kasa Hareketleri") else "banka", parent=self)
        elif menu_name == self.tr("Stok Hareketleri"):
            from src.desktop.ui.stok_hareket_screen import StokHareketScreen
            new_widget = StokHareketScreen(db_session=self.db, parent=self)
        elif menu_name == self.tr("Cari Hareketleri"):
            from src.desktop.ui.cari_hareket_screen import CariHareketScreen
            new_widget = CariHareketScreen(db_session=self.db, parent=self)
        elif menu_name in (self.tr("Teklif Yönetimi"), self.tr("Teklifler"), self.tr("Açık Teklifler"), self.tr("Yeni Teklif Hazırla")):
            from src.desktop.ui.quotations import QuotationsWidget
            new_widget = QuotationsWidget(self.db)
        elif menu_name in (self.tr("Sipariş Yönetimi"), self.tr("Siparişler"), self.tr("Bekleyen Sipariş")):
            from src.desktop.ui.quotations import OrdersWidget
            new_widget = OrdersWidget(self.db)
        elif menu_name in (self.tr("İrsaliyeler"), self.tr("İrsaliye Yönetimi")):
            from src.desktop.ui.quotations import WaybillWidget
            new_widget = WaybillWidget(self.db)
        elif menu_name in (self.tr("Faturalar"), self.tr("Hızlı Fatura"), self.tr("Bugün Ciro")):
            from src.desktop.ui.quotations import InvoicesWidget
            new_widget = InvoicesWidget(self.db)
        else:
            new_widget = PlaceholderWidget(f"{menu_name} {self.tr('Modülü')}")

        if new_widget:
            new_idx = self.tab_widget.addTab(new_widget, tab_title)
            self.tab_widget.setCurrentIndex(new_idx)
            if quick_new_action:
                action = getattr(new_widget, quick_new_action, None)
                if callable(action):
                    action()

    def close_tab(self, index):
        if index <= 0:
            return  # Sabit Dashboard kapatılamaz
        self.tab_widget.removeTab(index)

    def tab_changed(self, index):
        if index <= 0:
            if hasattr(self, "bugun_gorevleri"):
                self.bugun_gorevleri.yenile()
            self.logo.setText(self.tr("TOYA ERP"))
            self.setWindowTitle(self.tr("Toya ERP"))
        else:
            tab_text = self.tab_widget.tabText(index)
            self.logo.setText(f"TOYA ERP | {tab_text}")
            self.setWindowTitle(f"Toya ERP | {tab_text}")

    # Favori Yönetimi
    def favoriye_ekle(self, menu_name):
        if menu_name not in self.favoriler:
            self.favoriler.append(menu_name)
            self.update_favorites_ui()
            self.show_toast(f"'{menu_name}' {self.tr('favorilere eklendi.')}", "success")

    def favoriden_cikar(self, menu_name):
        clean_name = menu_name.split("  ")[-1].strip() if "  " in menu_name else menu_name.strip()
        if clean_name in self.favoriler:
            self.favoriler.remove(clean_name)
            self.update_favorites_ui()
            self.show_toast(f"'{clean_name}' {self.tr('favorilerden çıkarıldı.')}", "warning")
        elif menu_name in self.favoriler:
            self.favoriler.remove(menu_name)
            self.update_favorites_ui()
            self.show_toast(f"'{menu_name}' {self.tr('favorilerden çıkarıldı.')}", "warning")

    def update_favorites_ui(self):
        self.fav_screens_list.clear()
        SCREEN_ICONS = {
            "Teklif Yönetimi": "📄",
            "Sipariş Yönetimi": "🛒",
            "Müşteriler & Cariler": "👥",
            "Ürün Yönetimi": "📦",
            "Görevler": "✅",
            "Takvim": "📅",
            "Geliştirme": "🛠️",
            "Genel Ayarlar": "⚙️",
            "İşlem Günlükleri": "📝",
            "Pazaryeri Bağlantıları": "🤝",
            "Fiyat Politikaları": "💵",
            "Cari Analiz": "📊",
            "Cari Hareketleri": "💱",
            "Stok Hareketleri": "📦",
            "Kasa Kartları": "💰",
            "Banka & POS Kartları": "🏦",
        }
        from src.desktop.security.gate import can, module_permission
        shown = 0
        for fav in self.favoriler:
            perm = module_permission(fav)
            if perm and not can(perm):
                continue  # yetkisi olmayan favoriyi listeleme
            icon = SCREEN_ICONS.get(fav, "⭐")
            item = QListWidgetItem(f"{icon}  {fav}")
            item.setData(Qt.ItemDataRole.UserRole, fav)
            self.fav_screens_list.addItem(item)
            shown += 1

        if hasattr(self, "fav_count_badge"):
            self.fav_count_badge.setText(str(shown))

    def create_styled_menu(self):
        """Kurala uygun mavi zeminli, beyaz yazılı sağ tık menüsü üretir."""
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLESHEET)
        return menu

    def show_grid_module_context_menu(self, pos, target_menu, sender_btn):
        menu = self.create_styled_menu()
        is_fav = target_menu in self.favoriler
        if not is_fav:
            add_action = QAction(self.tr("⭐ Favorilere Ekle"), self)
            add_action.triggered.connect(lambda: self.favoriye_ekle(target_menu))
            menu.addAction(add_action)
        else:
            remove_action = QAction(self.tr("❌ Favorilerden Çıkar"), self)
            remove_action.triggered.connect(lambda: self.favoriden_cikar(target_menu))
            menu.addAction(remove_action)
        menu.exec(sender_btn.mapToGlobal(pos))

    def show_favorites_context_menu(self, pos):
        item = self.fav_screens_list.itemAt(pos)
        if item:
            menu = self.create_styled_menu()
            target_text = item.data(Qt.ItemDataRole.UserRole) or item.text()
            remove_action = QAction(self.tr("❌ Favorilerden Çıkar"), self)
            remove_action.triggered.connect(lambda: self.favoriden_cikar(target_text))
            menu.addAction(remove_action)
            menu.exec(QCursor.pos())

    def load_companies(self):
        """Üst bardaki şirket kutusunu 'Firma Tanımları' (Company) verisinden doldurur."""
        self.company_combo.blockSignals(True)
        self.company_combo.clear()
        try:
            from src.desktop.services.company_service import CompanyService
            companies = CompanyService(self.db).list_companies()
            if companies:
                for c in companies:
                    label = f"{c.code} · {c.short_name}" if c.code else c.short_name
                    self.company_combo.addItem(label, c.id)
            else:
                self.company_combo.addItem("— Firma tanımlanmadı —", None)
        except Exception:  # noqa: BLE001
            # Company tablosu yoksa eski Site listesine düş
            try:
                for comp in self.db.query(Site).filter(Site.is_active == True).all():
                    self.company_combo.addItem(comp.name, comp.id)
            except Exception:  # noqa: BLE001
                pass
        self.company_combo.blockSignals(False)
        self.company_id = self.company_combo.currentData()
        try:
            self.company_combo.currentIndexChanged.disconnect(self.on_company_changed)
        except (TypeError, RuntimeError):
            pass
        self.company_combo.currentIndexChanged.connect(self.on_company_changed)

    def switch_user(self):
        """Şirket sabit kalır; oturum açan kullanıcıyı değiştirir."""
        from src.desktop.ui.dialogs.switch_user_dialog import SwitchUserDialog
        dlg = SwitchUserDialog(self.db, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_user:
            return
        user = dlg.selected_user
        self.current_user = user
        self.user_config = {**(self.user_config or {}), "username": user.username}
        try:
            from src.desktop.managers.permission_manager import PermissionManager
            pm = PermissionManager()
            pm.load_from_db(self.db)
            pm.set_current_user(user)
        except Exception:  # noqa: BLE001
            pass
        self.user_lbl.setText(self._current_user_label())
        # Açık modül sekmelerini kapat (yeni yetkilerle yeniden açılsın)
        while self.tab_widget.count() > 1:
            self.tab_widget.removeTab(1)
        self.tab_widget.setCurrentIndex(0)
        self.show_toast(f"Kullanıcı değişti: {user.full_name or user.username}", "success")

    def _refresh_header_from_settings(self, *_):
        """Genel Ayarlar sekmesi kapanınca üst bardaki firma/kullanıcı bilgisini yeniler."""
        try:
            cur = self.company_combo.currentData()
            self.load_companies()
            idx = self.company_combo.findData(cur)
            if idx >= 0:
                self.company_combo.setCurrentIndex(idx)
            self.current_user = self._resolve_current_user()
            self.user_lbl.setText(self._current_user_label())
        except Exception:  # noqa: BLE001
            pass

    def on_company_changed(self):
        self.company_id = self.company_combo.currentData()
        # Şirket değiştiğinde tüm açık modül sekmelerini temizle
        while self.tab_widget.count() > 1:
            self.tab_widget.removeTab(1)
        self.tab_widget.setCurrentIndex(0)
