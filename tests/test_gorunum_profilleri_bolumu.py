"""Sol panel "GÖRÜNÜM PROFİLLERİ" bölümü: yeni, düzenle (yeniden adlandır), sil, kaydet; açık temalı diyaloglar."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QFrame

from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.ui.components import dialog_style
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.widgets.gorunum_profilleri_bolumu import GorunumProfilleriBolumu

ANAHTAR = "test_gorunum_bolumu"


@pytest.fixture
def bolum(qapp):
    t = FilterableTableView(headers_dict={0: ("A", "a"), 1: ("B", "b")}, profile_key=ANAHTAR)
    b = GorunumProfilleriBolumu(t)
    yield b
    pm = ProfileManager(profile_key=ANAHTAR)
    for ad in list(pm.load_profiles()):
        if ad != "Varsayılan":
            pm.delete_profile(ad)
    pm.set_active_profile_name("Varsayılan")


def _adlar(b):
    return [b.combo.itemText(i) for i in range(b.combo.count())]


def test_yeni_profil_listede_hemen_gorunur_ve_aktif_olur(bolum, monkeypatch):
    monkeypatch.setattr(dialog_style, "ad_sor", lambda *a, **k: "Profil 1")
    assert not bolum.btn_duzenle.isEnabled() and not bolum.btn_sil.isEnabled()          # Varsayılan: düzenle/sil pasif
    bolum.yeni()
    assert "Profil 1" in _adlar(bolum) and bolum.combo.currentText() == "Profil 1"
    assert bolum.btn_duzenle.isEnabled() and bolum.btn_sil.isEnabled()


def test_yeni_varsayilan_adini_reddeder_ve_iptalde_bir_sey_yapmaz(bolum, monkeypatch):
    uyarilar = []
    monkeypatch.setattr(dialog_style, "uyari", lambda *a, **k: uyarilar.append(a))
    monkeypatch.setattr(dialog_style, "ad_sor", lambda *a, **k: "Varsayılan")
    bolum.yeni()
    assert uyarilar and _adlar(bolum) == ["Varsayılan"]
    monkeypatch.setattr(dialog_style, "ad_sor", lambda *a, **k: None)
    bolum.yeni()
    assert _adlar(bolum) == ["Varsayılan"]


def test_duzenle_yeniden_adlandirir_ve_sil_varsayilana_doner(bolum, monkeypatch):
    monkeypatch.setattr(dialog_style, "ad_sor", lambda *a, **k: "Eski Ad")
    bolum.yeni()
    monkeypatch.setattr(dialog_style, "ad_sor", lambda *a, **k: "Yeni Ad")
    bolum.duzenle()
    assert "Yeni Ad" in _adlar(bolum) and "Eski Ad" not in _adlar(bolum) and bolum.combo.currentText() == "Yeni Ad"
    monkeypatch.setattr(dialog_style, "onay", lambda *a, **k: False)
    bolum.sil()                                                                          # onay verilmedi: silinmez
    assert "Yeni Ad" in _adlar(bolum)
    monkeypatch.setattr(dialog_style, "onay", lambda *a, **k: True)
    bolum.sil()
    assert "Yeni Ad" not in _adlar(bolum) and bolum.combo.currentText() == "Varsayılan"


def test_baska_yerden_kaydedilen_profil_bolume_yansir(bolum):
    bolum.tablo.save_column_profile("Menüden")                                           # sütun menüsündeki kaydetme yolu
    assert "Menüden" in _adlar(bolum) and bolum.combo.currentText() == "Menüden"


def test_kaydet_varsayilanda_yeni_profil_sorar(bolum, monkeypatch):
    monkeypatch.setattr(dialog_style, "ad_sor", lambda *a, **k: "Kaydet Yeni")
    bolum.kaydet()
    assert "Kaydet Yeni" in _adlar(bolum)


def test_dialog_yardimcilari_dusman_ust_stile_ragmen_kendi_acik_stilini_tasir(qapp):
    from PyQt6.QtWidgets import QMessageBox
    host = QFrame()
    host.setStyleSheet("background-color: transparent; border: none;")
    kutu = dialog_style._kutu(host, QMessageBox.Icon.Information, "B", "M", QMessageBox.StandardButton.Ok)
    assert "#f8fafc" in kutu.styleSheet()
