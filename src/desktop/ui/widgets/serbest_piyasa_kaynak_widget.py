"""
TOYA ERP - Serbest Piyasa Kaynak Yönetimi

Döviz & Kur panelinde "Serbest Piyasa" kaynağı seçildiğinde kullanılacak,
adı + adresi (URL) olan kaynak tanımlarını Ekle/Düzenle/Test Et/Sil ile
yönetmeyi sağlar. Önceki sürümde bu alan yalnızca serbest metin adresleri
tutan genel `CatalogSearchField` idi; burada adlandırılmış, test edilebilir
kayıtlara geçilmiştir.

`SerbestPiyasaKaynakField`, `CatalogSearchField` ile aynı sözleşmeyi
(`text()` / `setText()` / `changed` sinyali) sağlar; böylece
`GeneralSettingsScreen` içindeki kaynak yükleme/kaydetme kodu değişmeden
kullanılabilir.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import currency_rate_service
from src.desktop.ui.components.dialog_style import apply_light_dialog_style


class _KaynakDuzenleDialog(QDialog):
    """Tek bir Serbest Piyasa kaynağı (ad + URL) için ekle/düzenle formu."""

    def __init__(self, parent=None, *, name: str = "", url: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Serbest Piyasa Kaynağı")
        self.setFixedSize(380, 150)
        apply_light_dialog_style(self)
        lyt = QVBoxLayout(self)
        form = QFormLayout()
        self.txt_ad = QLineEdit(name)
        self.txt_ad.setPlaceholderText("ör. Bankam XML")
        self.txt_url = QLineEdit(url)
        self.txt_url.setPlaceholderText("https://.../kurlar.xml")
        form.addRow("Ad:", self.txt_ad)
        form.addRow("Adres (URL):", self.txt_url)
        lyt.addLayout(form)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        lyt.addWidget(box)

    def _on_accept(self) -> None:
        if not self.txt_ad.text().strip() or not self.txt_url.text().strip():
            QMessageBox.warning(self, "Uyarı", "Ad ve adres alanları zorunludur.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {"name": self.txt_ad.text().strip(), "url": self.txt_url.text().strip()}


class SerbestPiyasaYonetimDialog(QDialog):
    """Kayıtlı Serbest Piyasa kaynaklarının tam listesi — Ekle/Düzenle/Test Et/Sil."""

    def __init__(self, parent=None, db=None) -> None:
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("🌐 Serbest Piyasa Kaynakları")
        self.resize(440, 380)
        apply_light_dialog_style(self)
        self._items: list[dict] = currency_rate_service.list_serbest_sources(db)

        lyt = QVBoxLayout(self)
        self.lst = QListWidget()
        self.lst.itemDoubleClicked.connect(lambda _it: self._duzenle())
        lyt.addWidget(self.lst, 1)

        row = QHBoxLayout()
        btn_ekle = QPushButton("➕ Ekle")
        btn_ekle.clicked.connect(self._ekle)
        btn_duzenle = QPushButton("✏️ Düzenle")
        btn_duzenle.clicked.connect(self._duzenle)
        btn_test = QPushButton("🔎 Test Et")
        btn_test.clicked.connect(self._test)
        btn_sil = QPushButton("🗑️ Sil")
        btn_sil.clicked.connect(self._sil)
        for b in (btn_ekle, btn_duzenle, btn_test, btn_sil):
            row.addWidget(b)
        lyt.addLayout(row)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.accept)
        lyt.addWidget(box)

        self._reload()

    def _reload(self) -> None:
        self.lst.clear()
        for it in self._items:
            li = QListWidgetItem(f"{it['name']}  —  {it['url']}")
            self.lst.addItem(li)

    def _persist(self) -> None:
        currency_rate_service.save_serbest_sources(self.db, self._items)

    def _ekle(self) -> None:
        dlg = _KaynakDuzenleDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._items.append(dlg.get_data())
        self._persist()
        self._reload()
        self.lst.setCurrentRow(self.lst.count() - 1)

    def _duzenle(self) -> None:
        row = self.lst.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlenecek kaynağı seçin.")
            return
        cur = self._items[row]
        dlg = _KaynakDuzenleDialog(self, name=cur["name"], url=cur["url"])
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._items[row] = dlg.get_data()
        self._persist()
        self._reload()
        self.lst.setCurrentRow(row)

    def _sil(self) -> None:
        row = self.lst.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silinecek kaynağı seçin.")
            return
        cur = self._items[row]
        reply = QMessageBox.question(
            self, "Sil", f"'{cur['name']}' kaynağı silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self._items[row]
        self._persist()
        self._reload()

    def _test(self) -> None:
        row = self.lst.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen test edilecek kaynağı seçin.")
            return
        cur = self._items[row]
        result = currency_rate_service.fetch_rates(
            currency_rate_service.SOURCE_SERBEST, cur["url"], for_date=date.today(),
        )
        if result.success:
            kodlar = ", ".join(sorted(result.rates.keys())[:12])
            fazla = " ..." if len(result.rates) > 12 else ""
            QMessageBox.information(
                self, "Test Başarılı",
                f"{len(result.rates)} döviz kuru bulundu.\n\n{kodlar}{fazla}",
            )
        else:
            QMessageBox.warning(self, "Test Başarısız", result.message)

    def items(self) -> list[dict]:
        return list(self._items)


class SerbestPiyasaKaynakField(QWidget):
    """Kayıtlı Serbest Piyasa kaynaklarından birini seçmeye yarayan kombo +
    yönetim penceresini açan ⚙ butonu. `CatalogSearchField` ile aynı
    sözleşmeyi (`text()`/`setText()`/`changed` sinyali) sağlar."""

    changed = pyqtSignal(str)

    def __init__(self, *, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self._db = db_session
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(3)
        self.cmb = QComboBox()
        self.cmb.setMinimumWidth(160)
        self.cmb.currentIndexChanged.connect(lambda _i: self.changed.emit(self.text()))
        btn = QPushButton("⚙")
        btn.setFixedWidth(28)
        btn.setToolTip("Serbest Piyasa kaynaklarını yönet (Ekle/Düzenle/Test Et/Sil)")
        btn.clicked.connect(self._manage)
        lyt.addWidget(self.cmb, 1)
        lyt.addWidget(btn)
        self._reload()

    def _reload(self) -> None:
        self.cmb.blockSignals(True)
        self.cmb.clear()
        for it in currency_rate_service.list_serbest_sources(self._db):
            self.cmb.addItem(it["name"], it["url"])
        self.cmb.blockSignals(False)

    def _manage(self) -> None:
        dlg = SerbestPiyasaYonetimDialog(self, db=self._db)
        dlg.exec()
        prev_url = self.text()
        self._reload()
        self.setText(prev_url)

    def text(self) -> str:
        return self.cmb.currentData() or ""

    def setText(self, value) -> None:  # noqa: N802
        value = value or ""
        idx = self.cmb.findData(value)
        if idx < 0 and value:
            # Eski/kayıtsız bir adres (ör. daha önceki sürümden kalan
            # tekil ayar) — listede yoksa geçici bir satır olarak gösterilir,
            # veri kaybı yaşanmaz.
            self.cmb.blockSignals(True)
            self.cmb.addItem(f"(kayıtsız) {value}", value)
            self.cmb.blockSignals(False)
            idx = self.cmb.count() - 1
        self.cmb.blockSignals(True)
        self.cmb.setCurrentIndex(idx if idx >= 0 else -1)
        self.cmb.blockSignals(False)
