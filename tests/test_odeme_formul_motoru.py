"""odeme_formul_motoru: TOYA'ya özgü Ödeme Planı tutar formülü sözlüğü, mevcut `FormulaService` (Görünüm
Profilleri kural motoru) üzerine ince bir katman (04.11 — bkz. gelistirme/04_odeme_planlari/tasarim.md)."""

import pytest

from src.desktop.services.odeme_formul_motoru import (
    OdemeFormulHatasi,
    baglam_olustur,
    degerlendir,
)


@pytest.fixture
def baglam():
    return baglam_olustur(tutar=1000.0, aratoplam=833.33, kdv=166.67, kalan=400.0)


def test_bos_formul_kalani_doner(baglam):
    assert degerlendir("", baglam) == 400.0
    assert degerlendir(None, baglam) == 400.0
    assert degerlendir("   ", baglam) == 400.0


def test_degiskenler_okunur(baglam):
    assert degerlendir("TUTAR", baglam) == 1000.0
    assert degerlendir("ARATOPLAM", baglam) == 833.33
    assert degerlendir("KDV", baglam) == 166.67
    assert degerlendir("KALAN", baglam) == 400.0


def test_dort_islem_ve_parantez(baglam):
    assert degerlendir("TUTAR/2", baglam) == 500.0
    assert degerlendir("TUTAR*0.3", baglam) == pytest.approx(300.0)
    assert degerlendir("TUTAR-KDV", baglam) == pytest.approx(833.33)
    assert degerlendir("(TUTAR+KDV)/2", baglam) == pytest.approx(583.335)


def test_round_fonksiyonu_formula_service_uzerinden_calisir(baglam):
    """Fonksiyon adları `FormulaService`'inkiyle aynı (round/abs/min/max/sum) — ayrı bir Türkçe takma ad
    (YUVARLA vb.) eklenmedi, DRY gereği mevcut motor doğrudan kullanılıyor."""
    assert degerlendir("round(TUTAR/3,2)", baglam) == round(1000.0 / 3, 2)
    assert degerlendir("min(TUTAR,KDV)", baglam) == 166.67
    assert degerlendir("max(TUTAR,KDV)", baglam) == 1000.0


def test_sifira_bolme_sessizce_sifir_doner(baglam):
    """`FormulaService` "fail-soft" tasarımı: bölme hatası exception değil, 0 döner — otomasyon servisi
    zaten tutar<=0 olan satırları atlıyor, bu yüzden zincirleme güvenli."""
    assert degerlendir("TUTAR/0", baglam) == 0.0


def test_bilinmeyen_degisken_reddedilir(baglam):
    """`FormulaService` tanımadığı bir adı sessizce 0 sayar (görünüm kuralları için uygundur) — ödeme
    planı formüllerinde bu bir yazım hatasını gizleyeceği için burada AÇIKÇA reddedilir."""
    with pytest.raises(OdemeFormulHatasi, match="Bilinmeyen değişken"):
        degerlendir("GENEL_FIS_TUTARI", baglam)


def test_fonksiyon_cagrisindaki_ad_degisken_sayilmaz(baglam):
    """`round(TUTAR,2)` içindeki `round` bir değişken değil, fonksiyon adıdır — "bilinmeyen değişken"
    olarak reddedilmemeli."""
    assert degerlendir("round(TUTAR,2)", baglam) == 1000.0


def test_bilinmeyen_fonksiyon_reddedilir(baglam):
    with pytest.raises(OdemeFormulHatasi, match="desteklenmeyen"):
        degerlendir("MIN(TUTAR,KDV)", baglam)   # büyük harfli DIA tarzı değil — FormulaService küçük harf bekler


def test_gecersiz_sozdizimi_reddedilir(baglam):
    with pytest.raises(OdemeFormulHatasi, match="ayrıştırılamadı"):
        degerlendir("TUTAR +* 2", baglam)


def test_tehlikeli_ifadeler_reddedilir(baglam):
    """eval() kullanılmıyor — import/attribute erişimi/keyfi fonksiyon çağrısı güvenlik sınırının
    dışında kalmalı (yalnız admin'in girdiği formüller olsa da, kısıtlı değerlendirici ilkesi)."""
    for tehlikeli in ['__import__("os")', "TUTAR.__class__", "()", "[1,2,3]"]:
        with pytest.raises(OdemeFormulHatasi):
            degerlendir(tehlikeli, baglam)
