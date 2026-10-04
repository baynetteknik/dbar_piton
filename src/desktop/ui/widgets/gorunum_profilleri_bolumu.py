"""TOYA ERP - Sol panel "GÖRÜNÜM PROFİLLERİ" bölümü: liste ekranlarında profili seçme, yeni oluşturma, kaydetme, yeniden adlandırma,
silme ve sütunları yönetme.

Tek ortak bileşen (önceden Teklif, Cari ve başka ekranlarda kopya kod olarak yazılmıştı; kopyaların bir kısmı var olmayan metotları çağırıyordu).
`FilterableTableView`'in profil API'sini kullanır (`load_column_profile_list`, `load_profile`, `save_column_profile`, `delete_column_profile`,
`open_column_manager_dialog`); profil başka yerden (sütun menüsü, profil yöneticisi) değişince `profiles_changed` sinyaliyle kendini günceller.
Sorular/bildirimler açık temalı diyalog yardımcılarıyla (`dialog_style`) gösterilir; siyah/şeffaf diyalog çıkmaz."""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton

from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.ui.components import dialog_style
from src.desktop.ui.components.button_style import DANGER_BG, DANGER_FG, btn_style
from src.desktop.ui.components.collapsible_section import CollapsibleSection

_COMBO = ("QComboBox { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; color: #0f172a; font-size: 12px; combobox-popup: 0; }"
          " QComboBox QAbstractItemView { border: 1px solid #94a3b8; background-color: #ffffff; color: #0f172a; outline: none; padding: 0px; }"
          " QComboBox QAbstractItemView::item { padding: 3px 6px; min-height: 20px; }")
VARSAYILAN = "Varsayılan"


class GorunumProfilleriBolumu(CollapsibleSection):
    def __init__(self, tablo, parent=None) -> None:
        super().__init__("GÖRÜNÜM PROFİLLERİ", is_expanded=True)
        self.tablo = tablo
        self._guncelleniyor = False
        lbl = QLabel("Aktif Profil:")
        lbl.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.combo = QComboBox()
        self.combo.setStyleSheet(_COMBO)
        self.combo.currentTextChanged.connect(self._secildi)
        self.btn_yeni = QPushButton("➕ Yeni")
        self.btn_duzenle = QPushButton("✏️ Düzenle")
        self.btn_sil = QPushButton("🗑️ Sil")
        self.btn_kaydet = QPushButton("💾 Kaydet")
        self.btn_sutunlar = QPushButton("⚙️ Sütunlar")
        for b, stil in ((self.btn_yeni, btn_style()), (self.btn_duzenle, btn_style()), (self.btn_sil, btn_style(DANGER_BG, DANGER_FG)),
                        (self.btn_kaydet, btn_style()), (self.btn_sutunlar, btn_style())):
            b.setStyleSheet(stil)
        self.btn_yeni.setToolTip("Mevcut görünümü yeni bir profil olarak kaydeder")
        self.btn_duzenle.setToolTip("Seçili profili yeniden adlandırır")
        self.btn_sil.setToolTip("Seçili profili siler (Varsayılan silinmez)")
        self.btn_kaydet.setToolTip("Mevcut görünümü seçili profile kaydeder")
        self.btn_yeni.clicked.connect(self.yeni)
        self.btn_duzenle.clicked.connect(self.duzenle)
        self.btn_sil.clicked.connect(self.sil)
        self.btn_kaydet.clicked.connect(self.kaydet)
        self.btn_sutunlar.clicked.connect(self.tablo.open_column_manager_dialog)
        s1, s2 = QHBoxLayout(), QHBoxLayout()
        for s, dugmeler in ((s1, (self.btn_yeni, self.btn_duzenle, self.btn_sil)), (s2, (self.btn_kaydet, self.btn_sutunlar))):
            s.setSpacing(4)
            for b in dugmeler:
                s.addWidget(b)
        self.add_widget(lbl)
        self.add_widget(self.combo)
        self.add_layout(s1)
        self.add_layout(s2)
        self.tablo.profiles_changed.connect(self.yenile)
        self.yenile()

    # ---- durum -------------------------------------------------------------------------
    def _yonetici(self) -> ProfileManager:
        return ProfileManager(profile_key=self.tablo.profile_key)

    def aktif(self) -> str:
        return self.combo.currentText() or VARSAYILAN

    def yenile(self) -> None:
        """Listeyi ve aktif profili güncel duruma getirir (sinyal döngüsü olmadan); Varsayılan seçiliyken Düzenle/Sil pasif olur."""
        self._guncelleniyor = True
        try:
            self.combo.clear()
            for ad in self.tablo.load_column_profile_list():
                self.combo.addItem(ad)
            i = self.combo.findText(self._yonetici().get_active_profile_name())
            if i >= 0:
                self.combo.setCurrentIndex(i)
        finally:
            self._guncelleniyor = False
        ozel = self.aktif() != VARSAYILAN
        self.btn_duzenle.setEnabled(ozel)
        self.btn_sil.setEnabled(ozel)

    def _secildi(self, ad: str) -> None:
        if ad and not self._guncelleniyor:
            self.tablo.load_profile(ad)

    # ---- eylemler ----------------------------------------------------------------------
    def _yeni_ad(self, baslik: str, varsayilan: str = "") -> str | None:
        ad = dialog_style.ad_sor(self.window(), baslik, "Profil adı:", varsayilan)
        if not ad:
            return None
        if ad == VARSAYILAN:
            dialog_style.uyari(self.window(), baslik, "'Varsayılan' adı sistem profiline aittir; başka bir ad girin.")
            return None
        return ad

    def yeni(self) -> None:
        """Mevcut görünümü yeni bir profil olarak kaydeder ve etkinleştirir."""
        ad = self._yeni_ad("Yeni Profil")
        if ad is None:
            return
        if ad in self.tablo.load_column_profile_list() and not dialog_style.onay(
                self.window(), "Profil Güncellensin mi?", f"'{ad}' adlı profil zaten var. Üzerine kaydedilsin mi?"):
            return
        self.tablo.save_column_profile(ad)

    def kaydet(self) -> None:
        """Mevcut görünümü seçili profile kaydeder; seçili profil "Varsayılan" ise yeni profil sorar (Varsayılan üzerine yazılmaz)."""
        ad = self.aktif()
        if ad == VARSAYILAN:
            self.yeni()
            return
        self.tablo.save_column_profile(ad)
        dialog_style.bilgi(self.window(), "Profil Kaydedildi", f"'{ad}' görünüm profili kaydedildi.")

    def duzenle(self) -> None:
        """Seçili profili yeniden adlandırır (görünümü ve kimliği korunur)."""
        eski = self.aktif()
        if eski == VARSAYILAN:
            return
        yeni = self._yeni_ad("Profili Yeniden Adlandır", eski)
        if yeni is None or yeni == eski:
            return
        pm = self._yonetici()
        profiller = pm.load_profiles()
        if yeni in profiller:
            dialog_style.uyari(self.window(), "Yeniden Adlandır", f"'{yeni}' adlı bir profil zaten var.")
            return
        p = profiller.get(eski)
        if p is None:
            return
        p.profile.name = yeni
        pm.save_profile(p)
        pm.delete_profile(eski)
        pm.set_active_profile_name(yeni)
        self.tablo.profiles_changed.emit()

    def sil(self) -> None:
        """Seçili profili siler ve Varsayılan görünüme döner."""
        ad = self.aktif()
        if ad == VARSAYILAN:
            return
        if not dialog_style.onay(self.window(), "Profili Sil", f"'{ad}' görünüm profili silinsin mi?"):
            return
        self.tablo.delete_column_profile(ad)
        self.tablo.load_profile(VARSAYILAN)
