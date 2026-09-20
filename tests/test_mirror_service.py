"""Kaynak-bağımsız ayna senkronu ve raporları — sahte bağlayıcılar + gerçek Wolvox örnek veritabanı."""

from __future__ import annotations

import os
from datetime import datetime

import pytest

from src.core.models import MirrorCari, MirrorCariHareket, MirrorFatura
from src.desktop.connectors import registry
from src.desktop.connectors.base import SourceConnector
from src.desktop.connectors.wolvox_connector import WolvoxConnector, WolvoxError
from src.desktop.services import mirror_service as svc


def _cari(ext_id, kod, unvan):
    return {"ext_id": ext_id, "cari_kodu": kod, "unvan": unvan, "email": "", "telefon": "", "vergi_no": "",
            "aktif": True, "silindi": False}


def _h(ext_id, cari, tarih, evrak, tur, borc, alacak, ilgili=None):
    return {"ext_id": ext_id, "cari_ext_id": cari, "tarihi": tarih, "vadesi": None, "evrak_no": evrak,
            "kaynak_tur": tur, "borc": borc, "alacak": alacak, "aciklama": "", "ilgili_ext_id": ilgili,
            "silindi": False}


def _f(ext_id, no, cari, yon, toplam, iptal=False):
    return {"ext_id": ext_id, "fatura_no": no, "tarihi": datetime(2026, 1, 5), "vadesi": None,
            "cari_ext_id": cari, "yon": yon, "kaynak_durum": "", "iptal": iptal, "ara_toplam": toplam,
            "iskonto": 0.0, "kdv": 0.0, "genel_toplam": toplam, "doviz": "", "ek_bilgi": "",
            "aciklama": "", "silindi": False}


class FakeConnector:
    capabilities = frozenset({"read"})

    def __init__(self, source_name="fake"):
        self.source_name = source_name
        self.cariler = [_cari("1", "A", "Alfa"), _cari("2", "B", "Beta")]
        self.hareketler = [
            _h("10", "1", datetime(2026, 1, 5), "FTR-1", "9", 1000.0, 0.0, ilgili="100"),
            _h("11", "1", datetime(2026, 2, 5), "TAH-1", "3", 0.0, 400.0),
            _h("12", "2", datetime(2026, 2, 6), "AF-1", "9", 0.0, 250.0),
        ]
        self.faturalar = [
            _f("100", "SF00001", "1", "satis", 1000.0),
            _f("101", "SF00001", "1", "satis", 500.0),  # aynı numara, farklı kimlik
            _f("102", "AF00001", "2", "alis", 250.0),
            _f("103", "SF00002", "1", "satis", 999.0, iptal=True),
            _f("104", "XX1", "1", None, 10.0),  # yönü bilinmeyen
        ]
        self.kalemler = [
            {"ext_id": "1000", "fatura_ext_id": "100", "stok_kodu": "S1", "stok_adi": "Ürün", "birim": "ADET",
             "miktar": 2.0, "fiyat": 500.0, "kdv_orani": 18.0, "tutar": 1000.0, "kdvli_tutar": 1180.0,
             "sira_no": 1, "silindi": False},
        ]
        self.stoklar = [
            {"ext_id": "7", "stok_kodu": "S1", "stok_adi": "Ürün", "birim": "ADET", "kdv_orani": 18.0,
             "aktif": True, "silindi": False, "satis_fiyati": 500.0, "miktar": 12.0},
        ]

    def test_connection(self): return "ok"
    def fetch_cariler(self): return self.cariler
    def fetch_cari_hareketleri(self): return self.hareketler
    def fetch_faturalar(self): return self.faturalar
    def fetch_fatura_kalemleri(self): return self.kalemler
    def fetch_stoklar(self): return self.stoklar


# ---- sözleşme ve kayıt defteri ------------------------------------------------
def test_connectors_satisfy_the_source_contract():
    assert isinstance(FakeConnector(), SourceConnector)
    w = WolvoxConnector(database="x.fdb", connect=lambda **k: None)
    assert isinstance(w, SourceConnector)
    assert w.source_name == "wolvox" and w.capabilities == frozenset({"read"})  # yazma yok


def test_registry_lists_wolvox_and_accepts_new_sources(db_session):
    assert "wolvox" in registry.available()
    registry.register("fake", "Sahte Sistem", lambda db: FakeConnector())
    try:
        assert registry.available()["fake"] == "Sahte Sistem"
        assert registry.get_connector(db_session, "fake").source_name == "fake"
    finally:
        registry._REGISTRY.pop("fake", None)
    with pytest.raises(KeyError):
        registry.get_connector(db_session, "yok")


# ---- senkron --------------------------------------------------------------------
def test_first_sync_adds_everything_and_records_time(db_session):
    r = svc.sync_all(db_session, FakeConnector())
    assert r.success is True
    assert r.counts["cari"]["added"] == 2 and r.counts["fatura"]["added"] == 5
    assert svc.last_sync(db_session, "fake")


def test_second_identical_sync_changes_nothing(db_session):
    fc = FakeConnector()
    svc.sync_all(db_session, fc)
    r = svc.sync_all(db_session, fc)
    assert all(c["added"] == c["updated"] == c["vanished"] == 0 for c in r.counts.values())


def test_changes_are_updated_and_vanished_records_flagged(db_session):
    fc = FakeConnector()
    svc.sync_all(db_session, fc)
    fc.cariler[0]["unvan"] = "Alfa Yeni"
    fc.hareketler = fc.hareketler[:2]
    r = svc.sync_all(db_session, fc)
    assert r.counts["cari"]["updated"] == 1 and r.counts["cari_hareket"]["vanished"] == 1
    assert db_session.query(MirrorCari).filter_by(ext_id="1").one().unvan == "Alfa Yeni"
    assert db_session.query(MirrorCariHareket).filter_by(ext_id="12").one().source_deleted is True


def test_source_deleted_flag_is_mirrored(db_session):
    fc = FakeConnector()
    fc.faturalar[0]["silindi"] = True
    svc.sync_all(db_session, fc)
    assert db_session.query(MirrorFatura).filter_by(ext_id="100").one().source_deleted is True


def test_connector_failure_leaves_mirror_untouched(db_session):
    fc = FakeConnector()
    svc.sync_all(db_session, fc)

    class Broken(FakeConnector):
        def fetch_stoklar(self):
            raise WolvoxError("bağlantı koptu")

    b = Broken()
    b.cariler = []
    r = svc.sync_all(db_session, b)
    assert r.success is False and "koptu" in r.message
    assert db_session.query(MirrorCari).filter_by(source_deleted=True).count() == 0


def test_two_sources_live_side_by_side_without_interference(db_session):
    a, b = FakeConnector("kaynak_a"), FakeConnector("kaynak_b")
    b.cariler = [_cari("1", "Z", "Zeta")]  # aynı ext_id, farklı kaynak
    b.hareketler = []
    svc.sync_all(db_session, a)
    svc.sync_all(db_session, b)
    assert db_session.query(MirrorCari).count() == 3
    assert svc.sources(db_session) == ["kaynak_a", "kaynak_b"]
    assert db_session.query(MirrorCari).filter_by(source="kaynak_a", ext_id="1").one().unvan == "Alfa"
    # b'nin aynası a'nın kayıtlarını "kayboldu" işaretlememeli
    assert db_session.query(MirrorCari).filter_by(source="kaynak_a", source_deleted=True).count() == 0
    assert svc.cari_bakiyeleri(db_session, "kaynak_b")[0]["bakiye"] == 0.0


def test_duplicate_invoice_numbers_are_kept_separate(db_session):
    svc.sync_all(db_session, FakeConnector())
    assert [f.fatura_no for f in db_session.query(MirrorFatura).all()].count("SF00001") == 2


# ---- raporlar --------------------------------------------------------------------
def test_cari_bakiyeleri_and_firma_ozeti(db_session):
    svc.sync_all(db_session, FakeConnector())
    bak = {b["cari_kodu"]: b for b in svc.cari_bakiyeleri(db_session, "fake")}
    assert bak["A"]["bakiye"] == 600.0 and bak["B"]["bakiye"] == -250.0
    o = svc.firma_ozeti(db_session, "fake")
    assert o["toplam_borc"] == 600.0 and o["toplam_alacak"] == 250.0
    assert o["fatura_adedi"] == 4  # iptal edilen dışlanır
    assert o["satis_fatura_adedi"] == 2 and o["satis_fatura_toplami"] == 1500.0
    assert o["alis_fatura_adedi"] == 1 and o["alis_fatura_toplami"] == 250.0
    assert o["yonu_bilinmeyen_fatura_adedi"] == 1


def test_cari_ekstre_running_balance_and_opening(db_session):
    svc.sync_all(db_session, FakeConnector())
    tam = svc.cari_ekstre(db_session, "fake", "1")
    assert [s["bakiye"] for s in tam["satirlar"]] == [1000.0, 600.0] and tam["devir"] == 0.0
    assert tam["satirlar"][0]["ilgili_ext_id"] == "100"
    donem = svc.cari_ekstre(db_session, "fake", "1", date_from=datetime(2026, 2, 1))
    assert donem["devir"] == 1000.0
    assert [s["evrak_no"] for s in donem["satirlar"]] == ["TAH-1"] and donem["bakiye"] == 600.0


def test_faturalar_lists_items_and_filters(db_session):
    svc.sync_all(db_session, FakeConnector())
    fs = svc.faturalar(db_session, "fake")
    assert len(fs) == 4
    f100 = next(f for f in fs if f["ext_id"] == "100")
    assert f100["cari_unvan"] == "Alfa" and f100["kalemler"][0]["stok_adi"] == "Ürün"
    assert len(svc.faturalar(db_session, "fake", cari_ext_id="2")) == 1


# ---- gerçek Wolvox örnek veritabanı ------------------------------------------------
_FDB = r"C:\AKINSOFT\Wolvox9\Database_FB\WOLVOX.FDB"


@pytest.mark.skipif(not os.path.exists(_FDB), reason="Wolvox örnek veritabanı bu makinede yok")
def test_real_wolvox_mirror_matches_known_values(db_session):
    c = WolvoxConnector(database=_FDB)
    try:
        c.test_connection()
    except WolvoxError:
        pytest.skip("Firebird sunucusuna ulaşılamıyor")
    r = svc.sync_all(db_session, c)
    assert r.success, r.message
    assert r.counts["fatura"]["total"] == 25 and r.counts["fatura_kalem"]["total"] == 37
    bak = {b["cari_kodu"]: b["bakiye"] for b in svc.cari_bakiyeleri(db_session, "wolvox")}
    assert bak["KONYA2"] == 4997106.49 and bak["MERAM1"] == -73.75
    ozet = svc.firma_ozeti(db_session, "wolvox")
    assert ozet["fatura_adedi"] > 0 and ozet["yonu_bilinmeyen_fatura_adedi"] == 0
    # Wolvox'un fatura-hareket bağı: bazı cari hareketler bir faturaya (FTO_<id>) bağlanmış olmalı
    assert db_session.query(MirrorCariHareket).filter(MirrorCariHareket.ilgili_ext_id.isnot(None)).count() > 0
    r2 = svc.sync_all(db_session, c)
    assert sum(x["added"] + x["updated"] + x["vanished"] for x in r2.counts.values()) == 0
