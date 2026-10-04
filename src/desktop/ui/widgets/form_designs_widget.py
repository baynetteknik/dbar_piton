"""
TOYA ERP - Form Tasarımları yardımcıları

"Form Tasarımları" (Genel Ayarlar > Sistem > Görünüm), diğer tüm tanım tabloları gibi
`settings.py`'deki standart dbgrid + sağ tık/İŞLEMLER kalıbını kullanır (bkz.
`GeneralSettingsScreen.build_form_tasarimlari_panel`). Bu dosyada yalnızca o panelin
UI'dan bağımsız kalabilecek parçaları var: yeni form diyaloğu ve boş şablon dosyası
üretimi. Şablonların modül etiketi (`ReportTemplate.module`) ve modüle göre alan ağacı
(bkz. `data_tree_widget.MODULE_FIELD_SCHEMAS`) için asıl mekanizma `designer/models.py`
ve `designer/ui/data_tree_widget.py`'dedir.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from src.core.belge_turleri import BELGE_TURLERI
from src.desktop.designer.models import blank_template
from src.desktop.designer.services import teklif_print_service

PAGE_SIZES = ["A4", "A5"]
_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slugify(text: str) -> str:
    text = (text or "").strip().translate(_TR_MAP).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or uuid.uuid4().hex[:8]


def create_blank_form(ad: str, modul: str, boyut: str) -> Path:
    """Verilen ad/modül/sayfa boyutuyla boş bir form şablonu JSON'ı yazar, yolunu döner."""
    slug = slugify(ad)
    template_id = f"tpl_{slug}_{boyut.lower()}"
    tpl_dir = teklif_print_service.templates_dir()
    path = tpl_dir / f"{template_id}.json"
    if path.exists():
        template_id = f"{template_id}_{uuid.uuid4().hex[:4]}"
        path = tpl_dir / f"{template_id}.json"
    tpl = blank_template(template_id=template_id, title=ad, module=modul, page_size=boyut)
    path.write_text(json.dumps(tpl.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


_COMBO_STYLE = """
    QComboBox {
        combobox-popup: 0;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 4px 6px;
        background-color: white;
        color: #0f172a;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #cbd5e1;
        background-color: #ffffff;
        color: #0f172a;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
"""


class YeniFormDialog(QDialog):
    """Yeni form kaydı: ad + hangi modül için + sayfa boyutu."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni Form Tasarımı")
        self.setMinimumWidth(360)
        lyt = QVBoxLayout(self)

        form = QFormLayout()
        self.txt_ad = QLineEdit()
        self.txt_ad.setPlaceholderText("ör. Kurumsal Fatura (Yedek)")
        form.addRow("Form Adı", self.txt_ad)

        self.cmb_modul = QComboBox()
        self.cmb_modul.setStyleSheet(_COMBO_STYLE)
        for key, label in BELGE_TURLERI.items():
            self.cmb_modul.addItem(label, key)
        form.addRow("Modül", self.cmb_modul)

        self.cmb_boyut = QComboBox()
        self.cmb_boyut.setStyleSheet(_COMBO_STYLE)
        self.cmb_boyut.addItems(PAGE_SIZES)
        form.addRow("Sayfa Boyutu", self.cmb_boyut)
        lyt.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        lyt.addWidget(bb)

    def _on_accept(self) -> None:
        if not self.txt_ad.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Form adını girin.")
            return
        self.accept()

    def values(self) -> tuple[str, str, str]:
        return self.txt_ad.text().strip(), self.cmb_modul.currentData(), self.cmb_boyut.currentText()
