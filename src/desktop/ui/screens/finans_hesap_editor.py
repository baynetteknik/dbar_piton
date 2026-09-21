"""TOYA ERP - Kasa / Banka & POS kartı editörü (`DefinitionEditorScreen`, Stok/Cari Kartı kalıbı).

İki grup tek pencerede yönetilir:
- ``kasa``: Kasa Kartı (kod, ad, varsayılan döviz, isteğe bağlı döviz kısıtı, sorumlu). Açılış bakiyesi kartta girilmez; hareket (açılış fişi) olarak girilir.
- ``banka``: Banka & POS Kartı (Banka Hesabı, Kredi Kartı, POS: banka, şube, hesap no / IBAN, üye işyeri, komisyon, valör).

Veri `FinansHesap` tablosuna yazılır; cari fişlerindeki "Araç / Hesap" seçici aynı tabloyu okur. Kasa/banka hareketlerine
bağlantı sonraki aşamadır. Pencere ekranı kaplayarak açılır; Kaydet / Kaydet ve Yeni / Vazgeç alt çubuktadır."""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QDialog, QVBoxLayout

from src.core.models import FinansHesap
from src.desktop.services.currency_catalog import CURRENCY_CODES
from src.desktop.services.finans_hesap_service import HESAP_TURLERI, FinansHesapError, FinansHesapService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

logger = logging.getLogger(__name__)

BANKA_TURLERI = ("banka", "kredi_karti", "pos")
_TUR_ETIKET = {"banka": "Banka Hesabı", "kredi_karti": "Kredi Kartı", "pos": "POS"}
_ETIKET_TUR = {v: k for k, v in _TUR_ETIKET.items()}


def _para_birimleri(db) -> list[str]:
    try:
        from sqlalchemy import select

        from src.core.models import Currency
        kodlar = list(db.scalars(select(Currency.code).where(Currency.is_deleted == False, Currency.is_active == True)  # noqa: E712
                                 .order_by(Currency.code)))
        return ["TRY"] + [k for k in kodlar if k != "TRY"] if kodlar else ["TRY"] + [c for c in CURRENCY_CODES if c != "TRY"]
    except Exception:  # noqa: BLE001
        return ["TRY"]


def kart_sekmeleri(db, grup: str) -> list[dict]:
    """Gruba göre kart bölümleri. Açılış bakiyesi ortak para alanıdır (`tutar` tipi)."""
    para = {"key": "para_birimi", "label": "Varsayılan Döviz", "type": "combo", "options_provider": lambda: _para_birimleri(db)}
    kisit = {"key": "doviz_kisitli", "label": "Döviz Kısıtı", "type": "bool",
             "text": "Yalnızca bu dövizle işlem yapılabilsin (kapalıysa her dövizle çalışır)"}
    if grup == "kasa":
        return [{"title": "Kimlik", "bands": [{"sections": [
            {"title": "1. Kasa Kimliği", "columns": 2, "stretch": 6, "fields": [
                {"key": "kod", "label": "Kasa Kodu", "type": "text", "placeholder": "boş bırakılırsa otomatik (KSA001)", "lock_on_edit": True},
                {"key": "ad", "label": "Kasa Adı", "type": "text", "required": True, "placeholder": "örn. Merkez TL Kasası"},
                para,
                {"key": "sorumlu", "label": "Sorumlu", "type": "text"},
                kisit,
                {"key": "aciklama", "label": "Açıklama", "type": "multiline", "span": 2, "height": 50},
            ]},
        ]}]}]
    return [{"title": "Kimlik", "bands": [{"sections": [
        {"title": "1. Hesap Kimliği", "columns": 2, "stretch": 6, "fields": [
            {"key": "kod", "label": "Hesap Kodu", "type": "text", "placeholder": "boş bırakılırsa otomatik (BNK001)", "lock_on_edit": True},
            {"key": "ad", "label": "Hesap Adı", "type": "text", "required": True, "placeholder": "örn. Ziraat TL Vadesiz"},
            {"key": "tur_etiket", "label": "Hesap Türü", "type": "combo", "options": list(_TUR_ETIKET.values())},
            {"key": "banka", "label": "Banka Adı", "type": "text"},
            para,
            kisit,
            {"key": "aciklama", "label": "Açıklama", "type": "multiline", "span": 2, "height": 50},
        ]},
        {"title": "2. Şube & Hesap Bilgileri", "columns": 2, "stretch": 6, "fields": [
            {"key": "sube_adi", "label": "Şube Adı", "type": "text"},
            {"key": "sube_kodu", "label": "Şube Kodu", "type": "text"},
            {"key": "hesap_no", "label": "Hesap No", "type": "text"},
            {"key": "iban", "label": "IBAN", "type": "text", "placeholder": "TR.."},
        ]},
    ]}, {"sections": [
        {"title": "3. POS / Kart Bilgileri", "columns": 2, "stretch": 6, "fields": [
            {"key": "uye_isyeri_no", "label": "Üye İşyeri / Terminal No", "type": "text"},
            {"key": "komisyon_orani", "label": "Komisyon Oranı (%)", "type": "tutar", "decimals": 2},
            {"key": "valor_gun", "label": "Valör (gün)", "type": "int", "min": 0, "max": 365},
        ]},
    ]}]}]


def bos_kart(grup: str, tur: str | None = None) -> dict:
    d = {"kod": "", "ad": "", "para_birimi": "TRY", "aktif": True, "sorumlu": "", "aciklama": "", "doviz_kisitli": False,
         "banka": "", "sube_adi": "", "sube_kodu": "", "hesap_no": "", "iban": "", "uye_isyeri_no": "",
         "komisyon_orani": 0.0, "valor_gun": 0}
    if grup == "banka":
        d["tur_etiket"] = _TUR_ETIKET.get(tur or "banka", "Banka Hesabı")
    return d


class FinansHesapEditorDialog(QDialog):
    """`grup`: "kasa" | "banka". `hesap_id` verilirse düzenleme, yoksa yeni kart (`tur`: banka grubunda başlangıç türü)."""

    def __init__(self, db, grup: str = "kasa", hesap_id: int | None = None, tur: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.db, self.grup = db, grup
        self.svc = FinansHesapService(db)
        self.hesap_id = hesap_id
        self.saved_id: int | None = None
        baslik = "Kasa Kartı" if grup == "kasa" else "Banka & POS Kartı"
        self.setWindowTitle(baslik)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.editor = DefinitionEditorScreen(
            title=baslik, tabs=kart_sekmeleri(db, grup), code_field="kod", title_field="ad",
            header_extra_field="para_birimi", status_field="aktif", nav_sidebar=False, show_section_nav=False,
            enable_save_and_new=True, summary_provider=lambda d: " · ".join(x for x in (d.get("kod"), d.get("ad"), d.get("para_birimi")) if x),
            parent=self)
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(lambda d: self._kaydet(d, yeni=False))
        self.editor.saved_and_new.connect(lambda d: self._kaydet(d, yeni=True))
        self._yukle(tur)
        self.showMaximized()

    def _yukle(self, tur: str | None = None) -> None:
        if self.hesap_id:
            h = self.db.get(FinansHesap, self.hesap_id)
            d = self.svc.sozluk(h)
            if self.grup == "banka":
                d["tur_etiket"] = _TUR_ETIKET.get(h.tur, "Banka Hesabı")
            self.editor.set_data(d, is_edit=True)
        else:
            self.editor.set_data(bos_kart(self.grup, tur), is_edit=False)

    def _yukle_bos(self) -> None:
        self.hesap_id = None
        self.editor.set_data(bos_kart(self.grup), is_edit=False)

    def _kaydet(self, data: dict, yeni: bool) -> None:
        payload = dict(data)
        payload["tur"] = "kasa" if self.grup == "kasa" else _ETIKET_TUR.get(payload.pop("tur_etiket", ""), "banka")
        try:
            h = self.svc.kaydet(payload, hesap_id=self.hesap_id)
        except (FinansHesapError, ValueError) as e:
            self.svc.db.rollback()
            self.editor.lbl_status.setText(str(e))
            return
        self.saved_id = h.id
        if yeni:
            self._yukle_bos()
            self.editor.lbl_status.setText(f"✔ {h.kod} kaydedildi.")
        else:
            self.accept()
