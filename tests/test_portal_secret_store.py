"""Portal API/güncelleme anahtarı kimlik deposunda tutulur; eski düz metin ayar bir kereye mahsus taşınır ve silinir."""

import pytest

from src.desktop.services import portal_secret_store as st
from src.desktop.services.settings_store import get_setting, set_setting


def test_eski_duz_metin_deger_kimlik_deposuna_tasinir_ve_ayardan_silinir(db_session):
    set_setting(db_session, "portal.api_key", "eski-anahtar")
    assert st.al(db_session, "portal.api_key") == "eski-anahtar"
    assert not get_setting(db_session, "portal.api_key")                     # düz metin artık yok
    assert st.al(db_session, "portal.api_key") == "eski-anahtar"             # kimlik deposundan gelir


def test_yaz_kimlik_deposuna_yazar_ve_duz_metin_birakmaz(db_session):
    st.yaz(db_session, "portal.update_secret", " yeni ")
    assert st.al(db_session, "portal.update_secret") == "yeni" and not get_setting(db_session, "portal.update_secret")
    st.yaz(db_session, "portal.update_secret", "")
    assert st.al(db_session, "portal.update_secret") == ""


def test_kimlik_deposu_yoksa_yazma_duz_metne_dusmez(db_session, monkeypatch):
    import keyring

    def boom(*a):
        raise RuntimeError("depo yok")
    monkeypatch.setattr(keyring, "set_password", boom)
    with pytest.raises(st.SecretStoreError):
        st.yaz(db_session, "portal.api_key", "x")
    assert not get_setting(db_session, "portal.api_key")
    set_setting(db_session, "portal.api_key", "eski")                        # taşınamazsa okuma eski değerle çalışır
    assert st.al(db_session, "portal.api_key") == "eski"
