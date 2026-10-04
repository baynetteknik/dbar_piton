"""TOYA ERP - GorevKisayolBolumu: kart listelerinin (cari, stok, ileride servis…) yan paneline konan "GÖREVLER" bölümü.

Seçili kayıt için "✅ Görev Ekle" (kayda bağlı görev penceresi) ve "📋 Görevleri (N)" (yalnız o kaydın görevleri) düğmeleri verir.
Kayıt seçimini ekran bildirir (`kayit_sec(id, ad)`); bölüm açık görev sayısını düğmede gösterir. Kullanıcı adı ana pencereden alınır.

    self.gorev_bolumu = GorevKisayolBolumu(self.db, "cari", self)
    self.action_bar.add_custom_section(self.gorev_bolumu)
    ... seçim değişince:  self.gorev_bolumu.kayit_sec(cid, "C001 — ACME")
    ... sağ tık menüsü:   menu.addAction("✅ Görev Ekle", self.gorev_bolumu.gorev_ekle)
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from src.desktop.services.gorev_service import GorevService
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.window_fit_helper import ekrana_sigdir
from src.desktop.ui.widgets.gorev_dialog import GorevDialog


def kullanici_adi(widget: QWidget | None) -> str:
    """Widget'ın bağlı olduğu ana pencereden giriş yapan kullanıcının adı (yoksa boş)."""
    w = widget.window() if widget is not None else None
    f = getattr(w, "_kullanici_adi", None)
    try:
        return f() if callable(f) else ""
    except Exception:  # noqa: BLE001
        return ""


class IlgiliGorevlerDialog(QDialog):
    """Bir kayda bağlı görevler (Liste/Pano/Takvim görünümlü Görevler ekranı, o kayda filtreli)."""

    def __init__(self, db, ilgili: tuple[str, int, str], kullanici: str = "", parent=None) -> None:
        super().__init__(parent)
        from src.desktop.ui.gorevler_screen import GorevlerScreen
        self.setWindowTitle(f"Görevler — {ilgili[2]}")
        ekrana_sigdir(self, 1200, 700)   # 1366x768 gibi düşük çözünürlüklerde taşmasın
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(6, 6, 6, 6)
        self.ekran = GorevlerScreen(db_session=db, parent=self, embedded=True, kullanici=kullanici, ilgili=ilgili)
        lyt.addWidget(self.ekran, 1)
        alt = QHBoxLayout()
        alt.addStretch()
        b = QPushButton("Kapat")
        b.clicked.connect(self.accept)
        alt.addWidget(b)
        lyt.addLayout(alt)


class GorevKisayolBolumu(CollapsibleSection):
    def __init__(self, db, ilgili_tur: str, ust: QWidget, baslik: str = "GÖREVLER") -> None:
        super().__init__(baslik, is_expanded=True)
        self.db, self.ilgili_tur, self.ust = db, ilgili_tur, ust
        self._id: int | None = None
        self._ad = ""
        self.btn_ekle = QPushButton("✅ Görev Ekle")
        self.btn_liste = QPushButton("📋 Görevleri")
        for b in (self.btn_ekle, self.btn_liste):
            b.setStyleSheet(btn_style())
            self.add_widget(b)
        self.btn_ekle.clicked.connect(self.gorev_ekle)
        self.btn_liste.clicked.connect(self.gorevleri_goster)
        try:
            from src.desktop.security.gate import gate
            gate(self.btn_ekle, "gorev.create", hide=True)
            gate(self.btn_liste, "gorev.view", hide=True)
        except Exception:  # noqa: BLE001 - yetki altyapısı yoksa düğmeler açık kalır
            pass
        for b in (self.btn_ekle, self.btn_liste):            # yetki uygulandıktan sonra: kayıt seçilene dek kapalı
            b.setEnabled(False)

    def kayit_sec(self, kayit_id: int | None, ad: str = "") -> None:
        self._id, self._ad = kayit_id, ad
        self.btn_ekle.setEnabled(kayit_id is not None)
        self.btn_liste.setEnabled(kayit_id is not None)
        self.btn_liste.setText("📋 Görevleri")
        if kayit_id is not None and self.db is not None:
            try:
                n = len(GorevService(self.db).ilgili_gorevler(self.ilgili_tur, kayit_id))
            except Exception:  # noqa: BLE001
                n = 0
            self.btn_liste.setText(f"📋 Görevleri ({n})" if n else "📋 Görevleri")

    def gorev_ekle(self) -> None:
        if self._id is None:
            return
        kul = kullanici_adi(self.ust)
        v = {"ilgili_tur": self.ilgili_tur, "ilgili_id": self._id, "ilgili_ad": self._ad, "atanan": kul, "baslik": ""}
        if GorevDialog(self.db, varsayilan=v, kullanici=kul, parent=self.ust).exec():
            self.kayit_sec(self._id, self._ad)

    def gorevleri_goster(self) -> None:
        if self._id is None:
            return
        IlgiliGorevlerDialog(self.db, (self.ilgili_tur, self._id, self._ad), kullanici_adi(self.ust), parent=self.ust).exec()
        self.kayit_sec(self._id, self._ad)
