"""TOYA ERP - GoogleDriveFolderDialog: Google Drive klasörlerini Windows Gezgini gibi gezip hedef klasör seçme penceresi.

Klasöre çift tıklayınca içine girilir, "Yukarı" bir üst klasöre çıkar, "Drive'ım" ve "Benimle Paylaşılanlar" kökleri arasında
geçilir, "Yeni Klasör" geçerli klasörün içine klasör açar. Seçilen klasör `secilen` sözlüğünde ({"id", "name", "path"}) kalır.

`provider`: `list_folders(parent_id)`, `create_folder(name, parent_id)` sağlayan nesne (`GoogleDriveProvider`). Ağ çağrıları
arka plan iş parçacığında yapılır (pencere donmaz); `senkron=True` testler içindir."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services.backup.providers import ProviderError
from src.desktop.services.backup.remote_providers import ROOT, SHARED
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.entry_table_view import standart_grid
from src.desktop.ui.widgets.backup_runner import TaskThread

PRESET_ID = "dbgrid_gdrive_klasor"
_KOK_AD = {ROOT: "Drive'ım", SHARED: "Benimle Paylaşılanlar"}


class GoogleDriveFolderDialog(QDialog):
    def __init__(self, provider, parent=None, senkron: bool = False) -> None:
        super().__init__(parent)
        self.provider = provider
        self.senkron = senkron
        self.secilen: dict | None = None
        self._yigin: list[tuple[str, str]] = [(ROOT, _KOK_AD[ROOT])]      # geçerli yol: [(klasör id, ad), ...]
        self._klasorler: list[dict] = []
        self._thread: TaskThread | None = None
        self._kapaniyor = False
        self.setWindowTitle("☁ Google Drive — Klasör Seç")
        self.setMinimumSize(620, 460)
        apply_light_dialog_style(self)

        lyt = QVBoxLayout(self)
        nav = QHBoxLayout()
        self.btn_yukari = QPushButton("⬆ Yukarı")
        self.btn_drive = QPushButton("🏠 Drive'ım")
        self.btn_paylasilan = QPushButton("👥 Benimle Paylaşılanlar")
        self.btn_yenile = QPushButton("🔄 Yenile")
        self.btn_yeni = QPushButton("➕ Yeni Klasör")
        for b in (self.btn_yukari, self.btn_drive, self.btn_paylasilan, self.btn_yenile, self.btn_yeni):
            nav.addWidget(b)
        nav.addStretch()
        lyt.addLayout(nav)
        self.lbl_yol = QLabel()
        self.lbl_yol.setStyleSheet("font-weight:700; color:#1e3a8a; padding:4px 6px; background:#eff6ff; border:1px solid #bfdbfe;"
                                   " border-radius:4px;")
        lyt.addWidget(self.lbl_yol)
        self.entry = standart_grid(PRESET_ID, [("name", "KLASÖR ADI")])
        self.grid = self.entry.table_view
        self.grid.cellDoubleClicked.connect(lambda r, _c: self._gir(r))
        self.grid.selectionModel().selectionChanged.connect(lambda *_args: self._secim_metni())
        lyt.addWidget(self.entry, 1)
        self.lbl_durum = QLabel("")
        self.lbl_durum.setWordWrap(True)
        lyt.addWidget(self.lbl_durum)
        alt = QHBoxLayout()
        alt.addStretch()
        self.btn_sec = QPushButton()
        self.btn_sec.setDefault(True)
        b_iptal = QPushButton("Vazgeç")
        alt.addWidget(self.btn_sec)
        alt.addWidget(b_iptal)
        lyt.addLayout(alt)

        self.btn_yukari.clicked.connect(self.yukari)
        self.btn_drive.clicked.connect(lambda: self.kok(ROOT))
        self.btn_paylasilan.clicked.connect(lambda: self.kok(SHARED))
        self.btn_yenile.clicked.connect(self.yenile)
        self.btn_yeni.clicked.connect(self.yeni_klasor)
        self.btn_sec.clicked.connect(self.sec)
        b_iptal.clicked.connect(self.reject)
        self.yenile()

    # ---- durum -----------------------------------------------------------------------
    @property
    def gecerli(self) -> tuple[str, str]:
        return self._yigin[-1]

    def yol(self) -> str:
        return " / ".join(ad for _i, ad in self._yigin)

    def _yolu_goster(self) -> None:
        self.lbl_yol.setText("  ›  ".join(ad for _i, ad in self._yigin))
        self.btn_yukari.setEnabled(len(self._yigin) > 1)
        self._secim_metni()

    def _secim_metni(self) -> None:
        r = self.grid.currentRow() if self.grid.selectedIndexes() else -1
        if 0 <= r < len(self._klasorler):
            self.btn_sec.setText(f"✔ Seç: {self._klasorler[r]['name']}")
            self.btn_sec.setEnabled(True)
        else:
            self.btn_sec.setText(f"✔ Bu klasörü seç: {self.gecerli[1]}")
            self.btn_sec.setEnabled(self.gecerli[0] != SHARED)         # "Benimle Paylaşılanlar" bir klasör değildir

    def _durum(self, metin: str, hata: bool = False) -> None:
        self.lbl_durum.setStyleSheet(f"color:{'#b91c1c' if hata else '#475569'};")
        self.lbl_durum.setText(metin)

    # ---- yükleme ---------------------------------------------------------------------
    def _calistir(self, fn, sonra) -> None:
        """`fn()` arka planda çalışır; sonucu / hatayı `sonra(sonuc, hata)` ile ana iş parçacığında teslim eder."""
        if self.senkron:
            try:
                sonra(fn(), None)
            except (ProviderError, Exception) as e:  # noqa: BLE001
                sonra(None, e)
            return
        self._thread = TaskThread(fn, self)

        def bitti(r):
            if self._kapaniyor:
                return
            sonra(None, r) if isinstance(r, Exception) else sonra(r, None)

        self._thread.done.connect(bitti)
        self._thread.start()

    def yenile(self) -> None:
        pid = self.gecerli[0]
        self._durum("Klasörler yükleniyor…")
        self.grid.setEnabled(False)

        def sonra(klasorler, hata):
            self.grid.setEnabled(True)
            if hata is not None:
                self._klasorler = []
                self.grid.setRowCount(0)
                self._durum(str(hata) if isinstance(hata, ProviderError) else f"Klasörler alınamadı: {hata}", True)
            else:
                self._doldur(klasorler)
                self._durum(f"{len(klasorler)} klasör." if klasorler else "Bu klasörde alt klasör yok.")
            self._yolu_goster()

        self._calistir(lambda: self.provider.list_folders(pid), sonra)

    def _doldur(self, klasorler: list[dict]) -> None:
        self._klasorler = list(klasorler)
        g = self.grid
        g.setRowCount(0)
        for k in self._klasorler:
            r = g.rowCount()
            g.insertRow(r)
            g.setRowHeight(r, g.effective_row_height)
            it = QStandardItem("📁  " + k["name"])
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            g.setItem(r, 0, it)

    # ---- gezinme ---------------------------------------------------------------------
    def _gir(self, r: int) -> None:
        if 0 <= r < len(self._klasorler):
            k = self._klasorler[r]
            self._yigin.append((k["id"], k["name"]))
            self.yenile()

    def yukari(self) -> None:
        if len(self._yigin) > 1:
            self._yigin.pop()
            self.yenile()

    def kok(self, kok: str) -> None:
        self._yigin = [(kok, _KOK_AD[kok])]
        self.yenile()

    def yeni_klasor(self) -> None:
        if self.gecerli[0] == SHARED:
            self._durum("Yeni klasör için önce bir klasörün içine girin.", True)
            return
        ad, ok = QInputDialog.getText(self, "Yeni Klasör", f"'{self.gecerli[1]}' içinde oluşturulacak klasörün adı:")
        if not ok or not ad.strip():
            return
        pid = self.gecerli[0]
        self._durum("Klasör oluşturuluyor…")

        def sonra(yeni, hata):
            if hata is not None:
                self._durum(str(hata) if isinstance(hata, ProviderError) else f"Klasör oluşturulamadı: {hata}", True)
                return
            self._yigin.append((yeni["id"], yeni["name"]))        # Gezgin'de olduğu gibi yeni klasörün içine girilir
            self.yenile()

        self._calistir(lambda: self.provider.create_folder(ad.strip(), pid), sonra)

    # ---- seçim -----------------------------------------------------------------------
    def sec(self) -> None:
        r = self.grid.currentRow() if self.grid.selectedIndexes() else -1
        if 0 <= r < len(self._klasorler):
            k = self._klasorler[r]
            self.secilen = {"id": k["id"], "name": k["name"], "path": self.yol() + " / " + k["name"]}
        elif self.gecerli[0] != SHARED:
            self.secilen = {"id": self.gecerli[0], "name": self.gecerli[1], "path": self.yol()}
        else:
            return
        self.accept()

    def done(self, sonuc: int) -> None:  # noqa: D401 — pencere kapanırken arka plan görevini bekle
        self._kapaniyor = True
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(3000)
        super().done(sonuc)
