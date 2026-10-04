"""pos_mahsup_servisi.vadesi_gelenleri_tara(): POS→Banka parametrik otomatik mahsup
(04.09 — bkz. gelistirme/04_odeme_planlari/tasarim.md)."""

from datetime import date, timedelta

import pytest

from src.core.models import FinansFis, FinansHareket
from src.desktop.services.finans_fis_service import FinansFisService
from src.desktop.services.finans_hesap_service import FinansHesapService
from src.desktop.services.pos_mahsup_servisi import (
    bekleyen_bakiyeler,
    tek_hesabi_mahsup_et,
    vadesi_gelenleri_tara,
)


@pytest.fixture
def ortam(db_session):
    hs = FinansHesapService(db_session)
    banka = hs.kaydet({"tur": "banka", "ad": "Ziraat Vadesiz", "banka": "Ziraat"})
    pos = hs.kaydet({
        "tur": "pos", "ad": "Garanti POS", "valor_gun": 3,
        "pos_otomatik_mahsup": True, "pos_hedef_hesap_id": banka.id,
    })
    return db_session, FinansFisService(db_session), banka, pos


def _pos_tahsilat(db, fis_svc, pos, tutar, tarih):
    fis = fis_svc.fis_kaydet(
        {"grup": "banka", "tarih": tarih}, [{"tur": "havale_gelen", "hesap_id": pos.id, "tutar": tutar, "para_birimi": "TRY"}],
    )
    return db.query(FinansHareket).filter_by(fis_id=fis.id).one()


def test_valoru_gecen_pos_bakiyesi_otomatik_bankaya_aktarilir(ortam):
    db, fis_svc, banka, pos = ortam
    gecmis = date.today() - timedelta(days=5)   # valor_gun=3, 5 gün önce girmiş -> vadesi geçmiş
    h = _pos_tahsilat(db, fis_svc, pos, 1000.0, gecmis)

    sonuclar = vadesi_gelenleri_tara(db)

    assert len(sonuclar) == 1
    assert sonuclar[0].pos_hesap.id == pos.id
    assert sonuclar[0].tutar == 1000.0
    virman_fis = db.get(FinansFis, sonuclar[0].fis.id)
    assert virman_fis.grup == "banka"
    virman = db.query(FinansHareket).filter_by(fis_id=virman_fis.id).one()
    assert virman.hesap_id == pos.id
    assert virman.karsi_hesap_id == banka.id
    assert virman.tutar == 1000.0
    db.refresh(h)
    assert h.mahsup_virman_id == virman.id   # kaynak satır işaretlendi


def test_valoru_gelmemis_bakiye_tasinmaz(ortam):
    db, fis_svc, _banka, pos = ortam
    bugun = date.today()   # valor_gun=3, bugün girmiş -> vadesi henüz gelmedi
    _pos_tahsilat(db, fis_svc, pos, 500.0, bugun)

    assert vadesi_gelenleri_tara(db) == []


def test_otomatik_mahsup_kapaliysa_tasinmaz(ortam):
    db, fis_svc, banka, pos = ortam
    FinansHesapService(db).kaydet({"tur": "pos", "ad": pos.ad, "pos_otomatik_mahsup": False}, hesap_id=pos.id)
    gecmis = date.today() - timedelta(days=10)
    _pos_tahsilat(db, fis_svc, pos, 500.0, gecmis)

    assert vadesi_gelenleri_tara(db) == []


def test_tekrar_taraninca_ayni_satir_ikinci_kez_tasinmaz(ortam):
    db, fis_svc, _banka, pos = ortam
    gecmis = date.today() - timedelta(days=10)
    _pos_tahsilat(db, fis_svc, pos, 500.0, gecmis)

    ilk = vadesi_gelenleri_tara(db)
    ikinci = vadesi_gelenleri_tara(db)

    assert len(ilk) == 1
    assert ikinci == []   # zaten mahsup edilmiş, tekrar işlenmez


def test_birden_fazla_bekleyen_hareket_tek_fiste_toplanir(ortam):
    db, fis_svc, _banka, pos = ortam
    gecmis = date.today() - timedelta(days=10)
    _pos_tahsilat(db, fis_svc, pos, 300.0, gecmis)
    _pos_tahsilat(db, fis_svc, pos, 700.0, gecmis)

    sonuclar = vadesi_gelenleri_tara(db)

    assert len(sonuclar) == 1
    assert sonuclar[0].tutar == 1000.0


# ---------------------------------------------------------------- POS Mahsup Takip (2026-10-03)
def test_bekleyen_bakiyeler_vadesi_gelmis_ve_gelmemisi_ayirir(ortam):
    db, fis_svc, _banka, pos = ortam
    gecmis = date.today() - timedelta(days=10)
    bugun = date.today()
    _pos_tahsilat(db, fis_svc, pos, 300.0, gecmis)
    _pos_tahsilat(db, fis_svc, pos, 50.0, bugun)

    [b] = bekleyen_bakiyeler(db)

    assert b.pos_hesap.id == pos.id
    assert b.vadesi_gelmis == {"TRY": 300.0}
    assert b.vadesi_gelmemis == {"TRY": 50.0}
    assert b.en_eski_tarih == gecmis


def test_bekleyen_hareketi_olmayan_pos_hesabi_listede_gorunmez(ortam):
    db, _fis_svc, _banka, _pos = ortam
    assert bekleyen_bakiyeler(db) == []


def test_tek_hesabi_mahsup_et_otomatik_mahsup_kapali_hesapta_da_calisir(ortam):
    db, fis_svc, banka, pos = ortam
    FinansHesapService(db).kaydet({"tur": "pos", "ad": pos.ad, "pos_otomatik_mahsup": False}, hesap_id=pos.id)
    gecmis = date.today() - timedelta(days=10)
    _pos_tahsilat(db, fis_svc, pos, 500.0, gecmis)

    assert vadesi_gelenleri_tara(db) == []          # otomatik tarama bu hesabı atlar

    sonuclar = tek_hesabi_mahsup_et(db, pos.id)

    assert len(sonuclar) == 1
    assert sonuclar[0].tutar == 500.0
    assert sonuclar[0].pos_hesap.pos_hedef_hesap_id == banka.id
    assert bekleyen_bakiyeler(db) == []              # mahsup edildi, takip listesinde artık görünmez


def test_tek_hesabi_mahsup_et_vadesi_gelmemisse_bos_doner(ortam):
    db, fis_svc, _banka, pos = ortam
    _pos_tahsilat(db, fis_svc, pos, 500.0, date.today())

    assert tek_hesabi_mahsup_et(db, pos.id) == []
