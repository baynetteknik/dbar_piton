"""PosMahsupTakipDialog: bekleyen POS bakiyelerini listeleyen, manuel "Tahsil Et" aksiyonu
sunan takip ekranı (2026-10-03 — bkz. gelistirme/04_odeme_planlari/tasarim.md)."""

from datetime import date, timedelta

import pytest
from PyQt6.QtWidgets import QMessageBox, QPushButton

from src.core.models import FinansHareket
from src.desktop.services.finans_fis_service import FinansFisService
from src.desktop.services.finans_hesap_service import FinansHesapService
from src.desktop.ui.widgets.pos_mahsup_takip_dialog import PosMahsupTakipDialog


@pytest.fixture
def ortam(db_session):
    hs = FinansHesapService(db_session)
    banka = hs.kaydet({"tur": "banka", "ad": "Ziraat Vadesiz", "banka": "Ziraat"})
    pos = hs.kaydet({"tur": "pos", "ad": "Garanti POS", "valor_gun": 3, "pos_hedef_hesap_id": banka.id})
    return db_session, FinansFisService(db_session), banka, pos


def _pos_tahsilat(db, fis_svc, pos, tutar, tarih):
    fis_svc.fis_kaydet(
        {"grup": "banka", "tarih": tarih}, [{"tur": "havale_gelen", "hesap_id": pos.id, "tutar": tutar, "para_birimi": "TRY"}],
    )


def test_bos_bekleyen_yokken_bos_mesaj_gosterir(qapp, ortam):
    db, _fis_svc, _banka, _pos = ortam
    dlg = PosMahsupTakipDialog(db)
    assert dlg.tbl.rowCount() == 0
    assert "yok" in dlg.lbl_durum.text()
    dlg.close()


def test_vadesi_gelmis_satir_listelenir_ve_tahsil_et_calisir(qapp, ortam, monkeypatch):
    db, fis_svc, banka, pos = ortam
    gecmis = date.today() - timedelta(days=10)
    _pos_tahsilat(db, fis_svc, pos, 500.0, gecmis)

    dlg = PosMahsupTakipDialog(db)
    assert dlg.tbl.rowCount() == 1
    assert dlg.tbl.item(0, 0).text() == f"{pos.kod} — {pos.ad}"
    assert "500,00 TRY" in dlg.tbl.item(0, 3).text()
    btn = dlg.tbl.cellWidget(0, 6)
    assert isinstance(btn, QPushButton)
    assert btn.isEnabled()

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    btn.click()

    assert "aktarıldı" in dlg.lbl_durum.text()
    assert dlg.tbl.rowCount() == 0   # mahsup edildi, liste yenilendi
    virman = db.query(FinansHareket).filter_by(hesap_id=pos.id, karsi_hesap_id=banka.id).one()
    assert virman.tutar == 500.0
    dlg.close()


def test_tahsil_et_onay_verilmezse_islem_yapilmaz(qapp, ortam, monkeypatch):
    db, fis_svc, _banka, pos = ortam
    _pos_tahsilat(db, fis_svc, pos, 500.0, date.today() - timedelta(days=10))

    dlg = PosMahsupTakipDialog(db)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    dlg.tbl.cellWidget(0, 6).click()

    assert dlg.tbl.rowCount() == 1   # hiçbir şey değişmedi
    dlg.close()


def test_hedef_hesap_secilmemisse_tahsil_et_pasif(qapp, ortam):
    db, fis_svc, _banka, pos = ortam
    FinansHesapService(db).kaydet({"tur": "pos", "ad": pos.ad, "pos_hedef_hesap_id": None}, hesap_id=pos.id)
    _pos_tahsilat(db, fis_svc, pos, 500.0, date.today() - timedelta(days=10))

    dlg = PosMahsupTakipDialog(db)
    assert not dlg.tbl.cellWidget(0, 6).isEnabled()
    dlg.close()
