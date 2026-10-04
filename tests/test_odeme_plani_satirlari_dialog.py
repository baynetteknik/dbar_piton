"""OdemePlaniSatirlariDialog: bir Ödeme Planı'nın çok türlü bölüştürme satırlarını düzenleme popup'ı
(04.11 — bkz. gelistirme/04_odeme_planlari/tasarim.md)."""

import pytest
from PyQt6.QtWidgets import QTableWidgetItem

from src.core.models import PaymentPlan, PaymentPlanLine
from src.desktop.services.finans_hesap_service import FinansHesapService
from src.desktop.ui.widgets.odeme_plani_satirlari_dialog import (
    OdemePlaniSatirlariDialog,
)

_TIPLER = ["Nakit", "Havale/EFT", "Kredi Kartı", "POS", "Açık Hesap", "Çek", "Senet"]


@pytest.fixture
def ortam(db_session):
    hs = FinansHesapService(db_session)
    kasa = hs.kaydet({"tur": "kasa", "ad": "Merkez Kasa"})
    kk = hs.kaydet({"tur": "kredi_karti", "ad": "Garanti Sanal POS"})
    plan = PaymentPlan(code="KARMA", description="Yarı Nakit Yarı KK")
    db_session.add(plan)
    db_session.commit()
    return db_session, plan, kasa, kk


def _hesap_etiket(h) -> str:
    return f"{h.kod} — {h.ad}"


def test_bos_planda_tek_bos_satirla_baslar(qapp, ortam):
    db, plan, kasa, kk = ortam
    dlg = OdemePlaniSatirlariDialog(
        db, plan.id, plan.code, _TIPLER, [_hesap_etiket(kasa), _hesap_etiket(kk)], ["(Seçilmedi)"],
    )
    assert dlg.tbl.rowCount() == 1
    dlg.close()


def test_satir_ekle_doldur_kaydet_db_ye_yazar(qapp, ortam):
    db, plan, kasa, kk = ortam
    dlg = OdemePlaniSatirlariDialog(
        db, plan.id, plan.code, _TIPLER, [_hesap_etiket(kasa), _hesap_etiket(kk)], ["(Seçilmedi)"],
    )
    # ilk (boş) satırı Nakit/yarı olarak doldur
    dlg.tbl.setItem(0, 1, QTableWidgetItem("Nakit"))
    dlg.tbl.setItem(0, 2, QTableWidgetItem("TUTAR/2"))
    dlg.tbl.setItem(0, 4, QTableWidgetItem(_hesap_etiket(kasa)))
    # ikinci satırı ekle: Kredi Kartı/kalan
    dlg._satir_ekle()
    dlg.tbl.setItem(1, 1, QTableWidgetItem("Kredi Kartı"))
    dlg.tbl.setItem(1, 2, QTableWidgetItem("KALAN"))
    dlg.tbl.setItem(1, 4, QTableWidgetItem(_hesap_etiket(kk)))

    dlg._kaydet()

    satirlar = db.query(PaymentPlanLine).filter_by(payment_plan_id=plan.id, is_deleted=False).order_by(PaymentPlanLine.sira_no).all()
    assert len(satirlar) == 2
    assert satirlar[0].odeme_tipi == "Nakit"
    assert satirlar[0].tutar_formulu == "TUTAR/2"
    assert satirlar[0].hedef_finans_hesap_id == kasa.id
    assert satirlar[1].odeme_tipi == "Kredi Kartı"
    assert satirlar[1].tutar_formulu == "KALAN"
    assert satirlar[1].hedef_finans_hesap_id == kk.id


def test_var_olan_satirlar_yuklenir_ve_duzenlenince_guncellenir_yeni_satir_acilmaz(qapp, ortam):
    db, plan, kasa, kk = ortam
    db.add(PaymentPlanLine(payment_plan_id=plan.id, sira_no=1, odeme_tipi="Nakit", tutar_formulu="TUTAR", hedef_finans_hesap_id=kasa.id))
    db.commit()

    dlg = OdemePlaniSatirlariDialog(
        db, plan.id, plan.code, _TIPLER, [_hesap_etiket(kasa), _hesap_etiket(kk)], ["(Seçilmedi)"],
    )
    assert dlg.tbl.rowCount() == 1
    assert dlg.tbl.item(0, 1).text() == "Nakit"
    assert dlg.tbl.item(0, 2).text() == "TUTAR"

    dlg.tbl.item(0, 2).setText("TUTAR*0.8")
    dlg._kaydet()

    satirlar = db.query(PaymentPlanLine).filter_by(payment_plan_id=plan.id, is_deleted=False).all()
    assert len(satirlar) == 1   # yeni satır açılmadı, güncellendi
    assert satirlar[0].tutar_formulu == "TUTAR*0.8"


def test_satir_silinince_db_den_de_gizlenir(qapp, ortam):
    db, plan, kasa, kk = ortam
    db.add_all([
        PaymentPlanLine(payment_plan_id=plan.id, sira_no=1, odeme_tipi="Nakit", hedef_finans_hesap_id=kasa.id),
        PaymentPlanLine(payment_plan_id=plan.id, sira_no=2, odeme_tipi="Kredi Kartı", hedef_finans_hesap_id=kk.id),
    ])
    db.commit()

    dlg = OdemePlaniSatirlariDialog(
        db, plan.id, plan.code, _TIPLER, [_hesap_etiket(kasa), _hesap_etiket(kk)], ["(Seçilmedi)"],
    )
    assert dlg.tbl.rowCount() == 2
    dlg.tbl.setCurrentCell(1, 0)
    dlg._satir_sil()
    dlg._kaydet()

    satirlar = db.query(PaymentPlanLine).filter_by(payment_plan_id=plan.id, is_deleted=False).all()
    assert len(satirlar) == 1
    assert satirlar[0].odeme_tipi == "Nakit"


def test_odeme_tipi_bos_satir_kaydedilmez(qapp, ortam):
    db, plan, kasa, kk = ortam
    dlg = OdemePlaniSatirlariDialog(
        db, plan.id, plan.code, _TIPLER, [_hesap_etiket(kasa), _hesap_etiket(kk)], ["(Seçilmedi)"],
    )
    dlg._kaydet()   # hiçbir satır doldurulmadı (varsayılan boş satır)
    assert db.query(PaymentPlanLine).filter_by(payment_plan_id=plan.id).count() == 0
