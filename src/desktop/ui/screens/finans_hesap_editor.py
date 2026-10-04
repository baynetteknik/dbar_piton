"""TOYA ERP - Kasa / Banka & POS kartı editörü (`DefinitionEditorScreen`, Stok/Cari Kartı kalıbı).

İki grup tek pencerede yönetilir:
- ``kasa``: Kasa Kartı (kod, ad, varsayılan döviz, isteğe bağlı döviz kısıtı, sorumlu). Açılış bakiyesi kartta girilmez; hareket (açılış fişi) olarak girilir.
- ``banka``: Banka & POS Kartı (Banka Hesabı, Kredi Kartı, POS: banka, şube, hesap no / IBAN, üye işyeri, komisyon, valör).

Veri `FinansHesap` tablosuna yazılır; cari fişlerindeki "Araç / Hesap" seçici aynı tabloyu okur. Kasa/banka hareketlerine
bağlantı sonraki aşamadır. Pencere ekranı kaplayarak açılır; Kaydet / Kaydet ve Yeni / Vazgeç alt çubuktadır."""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QDialog, QVBoxLayout
from sqlalchemy import select

from src.core.models import FinansHesap
from src.desktop.services.currency_catalog import CURRENCY_CODES
from src.desktop.services.finans_hesap_service import (
    FinansHesapError,
    FinansHesapService,
)
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

logger = logging.getLogger(__name__)

BANKA_TURLERI = ("banka", "kredi_karti", "pos")
_TUR_ETIKET = {"banka": "Banka Hesabı", "kredi_karti": "Kredi Kartı", "pos": "POS"}
_ETIKET_TUR = {v: k for k, v in _TUR_ETIKET.items()}


def _banka_hesap_secenekleri(db, haric_id: int | None = None) -> list[str]:
    """POS'un otomatik mahsup hedefi olabilecek banka hesapları ("KOD — Ad"); kendisi hariç tutulur."""
    try:
        from sqlalchemy import select

        hesaplar = db.scalars(
            select(FinansHesap).where(
                FinansHesap.tur == "banka", FinansHesap.is_deleted == False, FinansHesap.aktif == True,  # noqa: E712
            ).order_by(FinansHesap.kod),
        ).all()
        return ["(Seçilmedi)"] + [f"{h.kod} — {h.ad}" for h in hesaplar if h.id != haric_id]
    except Exception:  # noqa: BLE001
        return ["(Seçilmedi)"]


def _banka_odeme_plani_secenekleri(db) -> list[str]:
    """Kredi Kartı/POS kartının kendi varsayılan Banka Ödeme Planı'nı seçmesi için ("KOD — Açıklama")."""
    try:
        from src.core.models import BankaOdemePlani
        planlar = db.scalars(
            select(BankaOdemePlani).where(
                BankaOdemePlani.is_deleted == False, BankaOdemePlani.is_active == True,  # noqa: E712
            ).order_by(BankaOdemePlani.kod),
        ).all()
        return ["(Seçilmedi)"] + [f"{p.kod} — {p.aciklama or ''}".rstrip(" —") for p in planlar]
    except Exception:  # noqa: BLE001
        return ["(Seçilmedi)"]


def _para_birimleri(db) -> list[str]:
    try:
        from sqlalchemy import select

        from src.core.models import Currency
        kodlar = list(db.scalars(select(Currency.code).where(Currency.is_deleted == False, Currency.is_active == True)  # noqa: E712
                                 .order_by(Currency.code)))
        from src.desktop.services import money_service
        yerel = money_service.yerel_para(db)
        return [yerel] + [k for k in kodlar if k != yerel] if kodlar else [yerel] + [c for c in CURRENCY_CODES if c != yerel]
    except Exception:  # noqa: BLE001
        return ["TRY"]


def kart_sekmeleri(db, grup: str, hesap_id: int | None = None) -> list[dict]:
    """Gruba göre kart bölümleri. Açılış bakiyesi ortak para alanıdır (`tutar` tipi)."""
    para = {"key": "para_birimi", "label": "Para Birimi", "type": "combo", "options_provider": lambda: _para_birimleri(db)}
    kisit = {"key": "doviz_kisitli", "label": "Döviz Kısıtı", "type": "bool",
             "text": "Yalnızca bu para birimiyle işlem yapılabilsin",
             "tooltip": "Önerilen: para birimi başına ayrı kasa/hesap. Kapalıysa bu hesap çok dövizli çalışır."}
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
            {"key": "pos_otomatik_mahsup", "label": "Otomatik Mahsup", "type": "bool",
             "text": "Valör günü geçen bakiye hedef hesaba otomatik aktarılsın",
             "tooltip": "Kasa/Banka Hareketleri ekranı her açıldığında kontrol edilir. Kapalıysa "
                        "\"POS Mahsup Takip\" ekranından elle (onay sorularak) aktarılabilir."},
            {"key": "pos_hedef_hesap_etiket", "label": "Hedef Banka Hesabı",
             "type": "combo", "options_provider": lambda: _banka_hesap_secenekleri(db, hesap_id),
             "tooltip": "Otomatik Mahsup açıksa, valörü geçen POS bakiyesi bu banka hesabına virmanla aktarılır."},
            {"key": "varsayilan_banka_odeme_plani_etiket", "label": "Varsayılan Banka Ödeme Planı",
             "type": "combo", "options_provider": lambda: _banka_odeme_plani_secenekleri(db),
             "tooltip": "Kredi Kartı / POS hesabının kendi varsayılan komisyon-BSMV-hizmet bedeli planı "
                        "(Genel Ayarlar → Banka Ödeme Planları'nda tanımlanır)."},
        ]},
        {"title": "4. Kredi Kartı Bilgileri", "columns": 2, "stretch": 6, "fields": [
            {"key": "kk_kart_no", "label": "Kart Numarası", "type": "text", "placeholder": "**** **** **** 1234 (güvenlik için maskeli girin)"},
            {"key": "kk_hesap_kesim_gunu", "label": "Hesap Kesim Günü", "type": "int", "min": 0, "max": 31},
            {"key": "kk_son_odeme_gunu", "label": "Son Ödeme Günü", "type": "int", "min": 0, "max": 31},
            {"key": "kk_faiz_orani", "label": "Aylık Gecikme Faiz Oranı (%)", "type": "tutar", "decimals": 2},
        ]},
    ]}]}]


def bos_kart(grup: str, tur: str | None = None, yerel: str = "TRY") -> dict:
    """Yeni kart: para birimi şirketin yerel parası, döviz kısıtı AÇIK (para birimi başına ayrı kasa/hesap; çok dövizli kasa isteğe bağlı)."""
    d = {"kod": "", "ad": "", "para_birimi": yerel, "aktif": True, "sorumlu": "", "aciklama": "", "doviz_kisitli": True,
         "banka": "", "sube_adi": "", "sube_kodu": "", "hesap_no": "", "iban": "", "uye_isyeri_no": "",
         "komisyon_orani": 0.0, "valor_gun": 0, "pos_otomatik_mahsup": False, "pos_hedef_hesap_etiket": "(Seçilmedi)",
         "varsayilan_banka_odeme_plani_etiket": "(Seçilmedi)", "kk_kart_no": "", "kk_hesap_kesim_gunu": 0,
         "kk_son_odeme_gunu": 0, "kk_faiz_orani": 0.0}
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
        self.has_saved: bool = False
        baslik = "Kasa Kartı" if grup == "kasa" else "Banka & POS Kartı"
        self.setWindowTitle(baslik)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.editor = DefinitionEditorScreen(
            title=baslik, tabs=kart_sekmeleri(db, grup, hesap_id), code_field="kod", title_field="ad",
            header_extra_field="para_birimi", status_field="aktif", nav_sidebar=False, show_section_nav=False,
            right_panel=False, enable_save_and_new=True,
            parent=self)
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self._on_close_requested)
        self.editor.saved.connect(lambda d: self._kaydet(d, yeni=False))
        self.editor.saved_and_new.connect(lambda d: self._kaydet(d, yeni=True))
        self._yukle(tur)
        self.showMaximized()
        from src.desktop.ui.components.window_fit_helper import zorla_ilk_yerlesim
        zorla_ilk_yerlesim(self)

    def _yukle(self, tur: str | None = None) -> None:
        if self.hesap_id:
            h = self.db.get(FinansHesap, self.hesap_id)
            d = self.svc.sozluk(h)
            if self.grup == "banka":
                d["tur_etiket"] = _TUR_ETIKET.get(h.tur, "Banka Hesabı")
            self.editor.set_data(d, is_edit=True)
        else:
            self.editor.set_data(bos_kart(self.grup, tur, self._yerel()), is_edit=False)

    def _yerel(self) -> str:
        from src.desktop.services import money_service
        return money_service.yerel_para(self.db)

    def _yukle_bos(self) -> None:
        self.hesap_id = None
        self.editor.set_data(bos_kart(self.grup, yerel=self._yerel()), is_edit=False)

    def _on_close_requested(self):
        if self.has_saved:
            self.accept()
        else:
            self.reject()

    def closeEvent(self, event):  # noqa: N802
        if self.has_saved:
            self.setResult(QDialog.DialogCode.Accepted)
        super().closeEvent(event)

    def _kaydet(self, data: dict, yeni: bool) -> None:
        payload = dict(data)
        payload["tur"] = "kasa" if self.grup == "kasa" else _ETIKET_TUR.get(payload.pop("tur_etiket", ""), "banka")
        etiket = (payload.pop("pos_hedef_hesap_etiket", "") or "").strip()
        hedef_kod = etiket.split(" — ", 1)[0].strip() if " — " in etiket else ""
        hedef = self.db.scalar(
            select(FinansHesap).where(FinansHesap.kod == hedef_kod, FinansHesap.is_deleted == False),  # noqa: E712
        ) if hedef_kod else None
        payload["pos_hedef_hesap_id"] = hedef.id if hedef else None
        plan_etiket = (payload.pop("varsayilan_banka_odeme_plani_etiket", "") or "").strip()
        plan_kod = plan_etiket.split(" — ", 1)[0].strip() if " — " in plan_etiket else ""
        if not plan_kod and plan_etiket and plan_etiket != "(Seçilmedi)":
            plan_kod = plan_etiket
        plan = None
        if plan_kod:
            from src.core.models import BankaOdemePlani
            plan = self.db.scalar(
                select(BankaOdemePlani).where(BankaOdemePlani.kod == plan_kod, BankaOdemePlani.is_deleted == False),  # noqa: E712
            )
        payload["varsayilan_banka_odeme_plani_id"] = plan.id if plan else None
        try:
            h = self.svc.kaydet(payload, hesap_id=self.hesap_id)
        except (FinansHesapError, ValueError) as e:
            self.svc.db.rollback()
            self.editor.lbl_status.setText(str(e))
            return
        self.saved_id = h.id
        self.has_saved = True
        if yeni:
            self._yukle_bos()
            self.editor.lbl_status.setText(f"✔ {h.kod} kaydedildi.")
        else:
            self.accept()
