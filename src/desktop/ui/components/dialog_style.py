"""Ortak açık-tema diyalog stili.

Uygulama genelinde bir palet tanımlı olmadığından, Windows koyu modundayken
`QDialog` siyah zemin + okunmaz yazıyla açılıyordu. Diyaloglar bu stili
uygulayarak programın açık renk şemasıyla (slate/mavi) uyumlu görünür.

Düğmeler kenar çubuğundaki düğmelerle aynıdır: alt kenarı kalın (derinlikli), üzerine gelince mavimsi, basınca
çöker. Varsayılan (birincil) düğme mavi zemin + beyaz yazıdır. İpuçları mavi zemin + beyaz yazıdır.
"""

from PyQt6.QtWidgets import QWidget

from src.desktop.ui.components.tooltip_style import with_tooltip

LIGHT_DIALOG_QSS = with_tooltip("""
QDialog, QMessageBox { background-color: #f8fafc; color: #1e293b; }
QLabel { color: #1e293b; background: transparent; }
QCheckBox, QRadioButton { color: #1e293b; background: transparent; }
QGroupBox { color: #1e293b; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #1e3a8a; font-weight: 700; }
QLineEdit, QComboBox, QListWidget, QTextEdit, QPlainTextEdit, QSpinBox, QDateEdit, QTimeEdit {
    background-color: #ffffff; color: #1e293b;
    border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px;
    selection-background-color: #bfdbfe; selection-color: #0f172a;
}
QListWidget::item { padding: 4px 6px; }
QListWidget::item:selected { background-color: #dbeafe; color: #1e3a8a; }
QComboBox { combobox-popup: 0; }
QComboBox QAbstractItemView {
    background-color: #ffffff; color: #1e293b; selection-background-color: #dbeafe; selection-color: #1e3a8a;
    outline: 0; padding: 0px; border: 1px solid #cbd5e1;
}
QComboBox QAbstractItemView::item { padding: 4px 8px; min-height: 20px; }
QTabWidget::pane { border: 1px solid #cbd5e1; background: #ffffff; border-radius: 4px; }
QTabBar::tab { background: #e2e8f0; color: #334155; padding: 6px 14px; border: 1px solid #cbd5e1; border-bottom: none;
               border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; font-weight: 600; }
QTabBar::tab:selected { background: #2563eb; color: #ffffff; border-color: #1d4ed8; }
QTabBar::tab:hover:!selected { background: #dbeafe; color: #1d4ed8; }
QPushButton {
    background-color: #ffffff; color: #1e293b;
    border: 1px solid #94a3b8; border-bottom: 3px solid #94a3b8; border-radius: 6px;
    padding: 5px 14px; font-weight: 600; min-height: 22px;
}
QPushButton:hover { background-color: #eff6ff; border-color: #60a5fa; border-bottom-color: #2563eb; color: #1d4ed8; }
QPushButton:pressed { border-bottom: 1px solid #94a3b8; padding-top: 7px; }
QPushButton:disabled { color: #94a3b8; background-color: #f1f5f9; border-color: #e2e8f0; }
QPushButton:default { background-color: #2563eb; color: #ffffff; border: 1px solid #1d4ed8; border-bottom: 3px solid #1e40af; }
QPushButton:default:hover { background-color: #1d4ed8; color: #ffffff; }
""")


def apply_light_dialog_style(dialog: QWidget) -> None:
    dialog.setStyleSheet(LIGHT_DIALOG_QSS)


# ---- Hazır (statik) diyalogların açık temalı karşılıkları -------------------------------------------------------
# Qt'nin statik `QInputDialog.getText` / `QMessageBox.question` diyalogları üst widget'ın stil sayfasını miras alır (ör. sol panelin
# `background-color: transparent`ı); miras alınan kural uygulama düzeyindeki kuralları ezdiğinden diyalog siyah/şeffaf açılıyordu.
# Bu yardımcılar diyalogu KENDİ stil sayfasıyla (miras kuralı ezer) kurar. Yeni kodda statik diyalog yerine bunları kullan.
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox  # noqa: E402


_TR_DUGME = {QMessageBox.StandardButton.Yes: "Evet", QMessageBox.StandardButton.No: "Hayır", QMessageBox.StandardButton.Ok: "Tamam",
             QMessageBox.StandardButton.Cancel: "Vazgeç", QMessageBox.StandardButton.Close: "Kapat", QMessageBox.StandardButton.Save: "Kaydet",
             QMessageBox.StandardButton.Discard: "Kaydetme", QMessageBox.StandardButton.YesToAll: "Tümüne Evet", QMessageBox.StandardButton.NoToAll: "Tümüne Hayır"}


def _kutu(parent, ikon, baslik: str, metin: str, butonlar) -> QMessageBox:
    kutu = QMessageBox(ikon, baslik, metin, butonlar, parent)
    apply_light_dialog_style(kutu)
    for dugme, ad in _TR_DUGME.items():
        b = kutu.button(dugme)
        if b is not None:
            b.setText(ad)
    return kutu


def bilgi(parent, baslik: str, metin: str) -> None:
    _kutu(parent, QMessageBox.Icon.Information, baslik, metin, QMessageBox.StandardButton.Ok).exec()


def uyari(parent, baslik: str, metin: str) -> None:
    _kutu(parent, QMessageBox.Icon.Warning, baslik, metin, QMessageBox.StandardButton.Ok).exec()


def onay(parent, baslik: str, metin: str) -> bool:
    """Evet / Hayır sorusu; Evet ise True."""
    yes, no = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
    kutu = _kutu(parent, QMessageBox.Icon.Question, baslik, metin, yes | no)
    kutu.setDefaultButton(no)
    return kutu.exec() == yes


def secenek_sor(parent, baslik: str, metin: str, secenekler: list[str]) -> int | None:
    """Düğme düğme çoklu seçenek sorusu (ör. 'Sadece cari' / 'Fatura kes' / 'İşleme') — `sec()`'ten farklı
    olarak bir açılır kutu değil, her seçenek kendi düğmesi olarak gösterilir. Tıklanan seçeneğin sırası
    (0-tabanlı) döner, pencere kapatılır/Vazgeç'e basılırsa None."""
    kutu = QMessageBox(QMessageBox.Icon.Question, baslik, metin, QMessageBox.StandardButton.NoButton, parent)
    apply_light_dialog_style(kutu)
    butonlar = [kutu.addButton(s, QMessageBox.ButtonRole.ActionRole) for s in secenekler]
    vazgec = kutu.addButton("Vazgeç", QMessageBox.ButtonRole.RejectRole)
    kutu.setDefaultButton(vazgec)
    kutu.exec()
    tiklanan = kutu.clickedButton()
    return None if tiklanan is vazgec or tiklanan is None else butonlar.index(tiklanan)


def ad_sor(parent, baslik: str, etiket: str, varsayilan: str = "") -> str | None:
    """Tek satır metin sorar; iptal ya da boşsa None."""
    d = QInputDialog(parent)
    d.setWindowTitle(baslik)
    d.setLabelText(etiket)
    d.setTextValue(varsayilan)
    d.setOkButtonText("Tamam")
    d.setCancelButtonText("Vazgeç")
    apply_light_dialog_style(d)
    if d.exec() and d.textValue().strip():
        return d.textValue().strip()
    return None


def sec(parent, baslik: str, etiket: str, secenekler: list[str], varsayilan: int = 0) -> int | None:
    """Listeden bir seçenek seçtirir; seçilen indeks, iptalde None."""
    d = QInputDialog(parent)
    d.setWindowTitle(baslik)
    d.setLabelText(etiket)
    d.setComboBoxItems(secenekler)
    d.setOkButtonText("Tamam")
    d.setCancelButtonText("Vazgeç")
    apply_light_dialog_style(d)
    if d.exec():
        return max(0, secenekler.index(d.textValue())) if d.textValue() in secenekler else varsayilan
    return None


# ---- Tüm statik çağrıları açık temaya alan kurulum -------------------------------------------------------------------
# Kod tabanında yüzlerce `QMessageBox.information/warning/critical/question` ve `QInputDialog.getText/getItem` çağrısı var. Hepsini tek tek
# değiştirmek yerine bu kurulum, aynı imzalı temalı karşılıklarını Qt sınıflarına bağlar (çağrı yerleri değişmez, yeni yazılan kod da kapsanır).
def _kutu_calistir(ikon, parent, baslik, metin, butonlar, varsayilan):
    kutu = _kutu(parent, ikon, baslik, metin, butonlar)
    if varsayilan != QMessageBox.StandardButton.NoButton:
        kutu.setDefaultButton(varsayilan)
    return QMessageBox.StandardButton(kutu.exec())


def _mesaj_fn(ikon, varsayilan_butonlar):
    def fn(parent, baslik, metin, buttons=varsayilan_butonlar, defaultButton=QMessageBox.StandardButton.NoButton):  # noqa: N803
        return _kutu_calistir(ikon, parent, baslik, metin, buttons, defaultButton)
    return staticmethod(fn)


def _get_text(parent, baslik, etiket, echo=QLineEdit.EchoMode.Normal, text="", flags=Qt.WindowType.Widget, inputMethodHints=Qt.InputMethodHint.ImhNone):  # noqa: N803
    d = QInputDialog(parent)
    d.setWindowTitle(baslik)
    d.setLabelText(etiket)
    d.setTextEchoMode(echo)
    d.setTextValue(text)
    d.setOkButtonText("Tamam")
    d.setCancelButtonText("Vazgeç")
    apply_light_dialog_style(d)
    ok = bool(d.exec())
    return (d.textValue() if ok else ""), ok


def _get_item(parent, baslik, etiket, items, current=0, editable=True, flags=Qt.WindowType.Widget, inputMethodHints=Qt.InputMethodHint.ImhNone):  # noqa: N803
    d = QInputDialog(parent)
    d.setWindowTitle(baslik)
    d.setLabelText(etiket)
    d.setComboBoxItems(list(items))
    d.setComboBoxEditable(editable)
    d.setTextValue(list(items)[current] if 0 <= current < len(items) else "")
    d.setOkButtonText("Tamam")
    d.setCancelButtonText("Vazgeç")
    apply_light_dialog_style(d)
    ok = bool(d.exec())
    return (d.textValue() if ok else ""), ok


def temali_statikleri_kur() -> None:
    """`QMessageBox`/`QInputDialog` statik çağrılarını temalı karşılıklarıyla değiştirir (uygulama başında bir kez)."""
    if getattr(QMessageBox, "_toya_temali", False):
        return
    ok, yn = QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    QMessageBox.information = _mesaj_fn(QMessageBox.Icon.Information, ok)
    QMessageBox.warning = _mesaj_fn(QMessageBox.Icon.Warning, ok)
    QMessageBox.critical = _mesaj_fn(QMessageBox.Icon.Critical, ok)
    QMessageBox.question = _mesaj_fn(QMessageBox.Icon.Question, yn)
    QInputDialog.getText = staticmethod(_get_text)
    QInputDialog.getItem = staticmethod(_get_item)
    QMessageBox._toya_temali = True
