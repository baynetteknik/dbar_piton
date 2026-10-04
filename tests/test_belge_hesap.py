"""belge_hesap: satır / belge / dip toplam hesabının tek sahibi (arayüzden bağımsız, düz sayılarla)."""

from __future__ import annotations

import pytest

from src.desktop.services import belge_hesap as h


def test_satir_net_iskonto_kdv_ve_try_kur_bir_alinir():
    s = h.satir(2, 100, 10, 20)                                   # 200 brüt, %10 iskonto
    assert (s.brut, s.iskonto, s.net, s.kdv, s.net_para) == pytest.approx((200.0, 20.0, 180.0, 36.0, 180.0))
    assert h.satir(1, 50, 0, 20, kur=0).net == pytest.approx(50.0)   # kur boş/0 = 1


def test_doviz_satiri_toplamlar_tl_karsiligi_net_para_kendi_dovizinde():
    s = h.satir(2, 10, 0, 20, kur=40.0)                            # 2 × 10 USD, kur 40
    assert s.net_para == pytest.approx(20.0) and s.net == pytest.approx(800.0) and s.kdv == pytest.approx(160.0)


def test_belge_toplami_ve_kdv_dagilimi_oran_bazinda():
    t = h.belge_toplami([h.satir(2, 1500, 10, 20), h.satir(6, 250, 0, 20), h.satir(1, 600, 0, 10)])
    assert t.ara_toplam == pytest.approx(5100.0) and t.iskonto == pytest.approx(300.0)
    assert t.kdv_matrahi == pytest.approx(4800.0) and t.kdv_toplam == pytest.approx(900.0) and t.genel_toplam == pytest.approx(5700.0)
    assert t.kdv_dagilim[20]["matrah"] == pytest.approx(4200.0) and t.kdv_dagilim[10]["kdv"] == pytest.approx(60.0)
    assert t.satir_sayisi == 3


def test_dip_toplam_ek_indirim_masraf_ve_ek_kdv():
    t = h.belge_toplami([h.satir(1, 1000, 0, 20)])                 # matrah 1000, KDV 200
    d = h.dip_toplam(t, ek_indirim=100, masraf=50, ek_kdv=10)
    assert d["kdv_matrahi"] == pytest.approx(950.0) and d["kdv_toplam"] == pytest.approx(210.0) and d["genel_toplam"] == pytest.approx(1160.0)
    assert d["iskonto"] == pytest.approx(100.0) and d["masraflar"] == 50
    kalem = {"kdv_matrahi": 1000.0, "kdv_toplam": 200.0, "ara_toplam": 1000.0, "iskonto": 0.0}       # sözlük girdisi de kabul
    assert h.dip_toplam(kalem)["genel_toplam"] == pytest.approx(1200.0)


def test_kdv_dagilimi_birlestir_ve_netten_satir_yuvarlama():
    m = h.kdv_dagilimi_birlestir({20: {"matrah": 100, "kdv": 20}}, {20.0: {"matrah": 10, "kdv": 2}, 10: {"matrah": 5, "kdv": 0.5}})
    assert m[20.0] == {"matrah": 110.0, "kdv": 22.0} and m[10.0]["kdv"] == 0.5
    s = h.satir_netten(33.333, 20, kur=3.0, kdv_yuvarla=2)          # net = 99.999 TL, KDV 19.9998 → 20.00
    assert s.net == pytest.approx(99.999) and s.kdv == 20.0


def test_eski_diyalog_satir_toplami_kademeli_iskonto_ve_kdv_dahil():
    from src.desktop.services import belge_hesap
    assert belge_hesap.eski_diyalog_satir_toplami({"qty": 2, "price": 100, "disc1": 10, "disc2": 10, "vat": 20}) == 194.4     # 200 × .9 × .9 × 1,2
    assert belge_hesap.eski_diyalog_satir_toplami({}) == 0.0                                                                    # boş: 1 × 0 × 1,2
    assert belge_hesap.eski_diyalog_satir_toplami({"qty": "x"}) == 0.0
