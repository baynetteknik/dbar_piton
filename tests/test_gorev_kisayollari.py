"""Ana paneldeki "Bugünün Görevleri", cari/stok listelerinde "Görev Ekle" kısayolu ve ilişkili görevler penceresi."""

from datetime import datetime, timedelta

import pytest

from src.core.models import Customer, Product
from src.desktop.services.gorev_service import GorevFiltre, GorevService

BUGUN = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)


class _Sahte:
    """GorevDialog yerine geçer: oluşturma parametrelerini kaydeder, isteğe göre görev kaydeder."""
    acilan: list = []
    kaydet_baslik: str | None = None

    def __init__(self, db, gorev_id=None, varsayilan=None, kullanici="", parent=None):
        self.db, self.v, self.gorev_id = db, varsayilan or {}, gorev_id
        _Sahte.acilan.append({"gorev_id": gorev_id, "varsayilan": self.v, "kullanici": kullanici})

    def exec(self):
        if _Sahte.kaydet_baslik:
            GorevService(self.db).kaydet(dict(self.v, baslik=_Sahte.kaydet_baslik))
            return 1
        return 0


@pytest.fixture(autouse=True)
def _sifirla():
    _Sahte.acilan, _Sahte.kaydet_baslik = [], None


# ---------------------------------------------------------------- servis
def test_bugun_ozeti_gecikmis_bugun_yinelenen_kullanici_ve_tamamlananlar(db_session):
    s = GorevService(db_session)
    simdi = datetime(2026, 6, 10, 12, 0)
    s.kaydet({"baslik": "Dünden kalan", "bitis": datetime(2026, 6, 8, 17, 0), "atanan": "ayse"})
    s.kaydet({"baslik": "Bugün akşam", "bitis": datetime(2026, 6, 10, 18, 0), "atanan": "ayse"})
    s.kaydet({"baslik": "Bugün sabah geçti", "bitis": datetime(2026, 6, 10, 9, 0)})
    s.kaydet({"baslik": "Günlük kontrol", "baslangic": datetime(2026, 6, 1, 8, 30), "tekrar": "gunluk"})
    s.kaydet({"baslik": "Veli'nin", "bitis": datetime(2026, 6, 10, 15, 0), "atanan": "veli"})
    s.kaydet({"baslik": "Bitti", "bitis": datetime(2026, 6, 10, 15, 0), "durum": "tamam"})
    s.kaydet({"baslik": "Yarın", "bitis": datetime(2026, 6, 11, 10, 0)})
    o = s.bugun_ozeti("ayse", simdi)
    assert [g.baslik for g in o["gecikmis"]] == ["Dünden kalan"]
    assert sorted(x.gorev.baslik for x in o["bugun"]) == ["Bugün akşam", "Bugün sabah geçti", "Günlük kontrol"]      # atanmamış olanlar dahil, veli'nin değil
    assert [x.gorev.baslik for x in o["bugun"]][0] == "Günlük kontrol"                                            # saate göre sıralı
    assert "Veli'nin" in [x.gorev.baslik for x in s.bugun_ozeti("ayse", simdi, tumu=True)["bugun"]]
    assert len(s.bugun_ozeti(None, simdi)["bugun"]) == 4                                                          # kullanıcı yoksa herkesin


# ---------------------------------------------------------------- ana panel kartı
def test_bugun_gorevleri_karti_listeler_tamamlar_ve_yeni_gorev_acar(qapp, db_session, monkeypatch):
    import src.desktop.ui.widgets.bugun_gorevleri_widget as m
    from src.desktop.ui.widgets.bugun_gorevleri_widget import BugunGorevleriWidget
    monkeypatch.setattr(m, "GorevDialog", _Sahte)
    s = GorevService(db_session)
    s.kaydet({"baslik": "Gecikmiş fatura", "bitis": datetime.now() - timedelta(days=2), "atanan": "ayse"})
    s.kaydet({"baslik": "Bugünkü ziyaret", "tur": "randevu", "baslangic": datetime.now().replace(hour=23, minute=0), "atanan": "ayse", "oncelik": 3})
    s.kaydet({"baslik": "Veli işi", "bitis": datetime.now().replace(hour=23, minute=30), "atanan": "veli"})
    w = BugunGorevleriWidget(db_session, "ayse", otomatik_yenile=False)
    metinler = [w.liste.item(i).text() for i in range(w.liste.count())]
    assert w.lbl_ozet.text() == "⚠ Gecikmiş: 1    📆 Bugün: 1" and metinler[0].startswith("⚠") and any("23:00 Bugünkü ziyaret" in t for t in metinler)
    assert not any("Veli işi" in t for t in metinler)
    w.chk_herkes.setChecked(True)
    assert w.liste.count() == 3
    w.chk_herkes.setChecked(False)
    assert not w.btn_tamam.isEnabled()
    w.liste.setCurrentRow(0)
    assert w.btn_tamam.isEnabled()
    degisti = []
    w.degisti.connect(lambda: degisti.append(1))
    w.tamamla()
    assert w.lbl_ozet.text().startswith("⚠ Gecikmiş: 0") and w.liste.count() == 1 and degisti
    w.liste.itemDoubleClicked.emit(w.liste.item(0))
    assert _Sahte.acilan[-1]["gorev_id"] is not None
    tumu = []
    w.tumu_istendi.connect(lambda: tumu.append(1))
    w.btn_tumu.click()
    w.btn_yeni.click()
    assert tumu and _Sahte.acilan[-1]["varsayilan"] == {"atanan": "ayse"}
    for g in GorevService(db_session).hepsi(GorevFiltre()):
        GorevService(db_session).durum_degistir(g.id, "tamam")
    w.yenile()
    assert "açık görev yok" in w.liste.item(0).text()
    w.close()
    w.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------- kısayol bölümü
def test_gorev_kisayol_bolumu_kayda_bagli_gorev_ekler_ve_sayiyi_gosterir(qapp, db_session, monkeypatch):
    import src.desktop.ui.widgets.gorev_kisayol_bolumu as m
    from src.desktop.ui.widgets.gorev_kisayol_bolumu import GorevKisayolBolumu
    from PyQt6.QtWidgets import QWidget
    monkeypatch.setattr(m, "GorevDialog", _Sahte)
    ust = QWidget()
    b = GorevKisayolBolumu(db_session, "cari", ust)
    assert not b.btn_ekle.isEnabled()
    b.gorev_ekle()                                                                        # kayıt seçili değil: bir şey açılmaz
    assert _Sahte.acilan == []
    b.kayit_sec(7, "C1 — ACME")
    assert b.btn_ekle.isEnabled() and b.btn_liste.text() == "📋 Görevleri"
    _Sahte.kaydet_baslik = "ACME'yi ara"
    b.gorev_ekle()
    v = _Sahte.acilan[0]["varsayilan"]
    assert (v["ilgili_tur"], v["ilgili_id"], v["ilgili_ad"]) == ("cari", 7, "C1 — ACME")
    assert b.btn_liste.text() == "📋 Görevleri (1)"
    b.kayit_sec(8, "C2")                                                                  # başka kayıtta sayı yok
    assert b.btn_liste.text() == "📋 Görevleri"
    ust.close()
    b.deleteLater()
    ust.deleteLater()
    qapp.processEvents()


def test_ilgili_gorevler_penceresi_yalniz_o_kaydin_gorevlerini_gosterir(qapp, db_session):
    from src.desktop.ui.widgets.gorev_kisayol_bolumu import IlgiliGorevlerDialog
    s = GorevService(db_session)
    s.iliskili_olustur("stok", 5, "SKU5 — Vida", "Sayım yap")
    s.iliskili_olustur("stok", 6, "SKU6", "Başka")
    d = IlgiliGorevlerDialog(db_session, ("stok", 5, "SKU5 — Vida"), "ayse")
    assert d.ekran.table_model.rowCount() == 1 and d.ekran.table_model.item(0, 1).text() == "Sayım yap" and "SKU5" in d.windowTitle()
    d.close()
    d.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------- cari / stok listeleri
def test_cari_listesinde_gorev_ekle_secili_cariye_baglanir(qapp, db_session, monkeypatch):
    import src.desktop.ui.widgets.gorev_kisayol_bolumu as m
    from src.desktop.ui.cari_list_screen import CariListScreen
    monkeypatch.setattr(m, "GorevDialog", _Sahte)
    c = Customer(fullname="ACME Ltd.", marketplace="local", customer_code="C1")
    db_session.add(c)
    db_session.commit()
    sc = CariListScreen(db_session=db_session)
    assert not sc.gorev_bolumu.btn_ekle.isEnabled()
    sc.table_view.selectRow(0)
    assert sc.gorev_bolumu.btn_ekle.isEnabled()
    sc.gorev_bolumu.btn_ekle.click()
    v = _Sahte.acilan[-1]["varsayilan"]
    assert (v["ilgili_tur"], v["ilgili_id"], v["ilgili_ad"]) == ("cari", c.id, "C1 — ACME Ltd.")
    sc.close()


def test_stok_listesinde_gorev_ekle_secili_urune_baglanir(qapp, db_session, monkeypatch):
    import src.desktop.ui.widgets.gorev_kisayol_bolumu as m
    from src.desktop.ui.stok_list_screen import StokListScreen
    monkeypatch.setattr(m, "GorevDialog", _Sahte)
    p = Product(sku="SKU1", name="Vida", price=1.0)
    db_session.add(p)
    db_session.commit()
    sc = StokListScreen(db_session=db_session)
    sc.table_view.selectRow(0)
    assert sc.gorev_bolumu.btn_ekle.isEnabled()
    sc.gorev_bolumu.btn_ekle.click()
    v = _Sahte.acilan[-1]["varsayilan"]
    assert (v["ilgili_tur"], v["ilgili_id"], v["ilgili_ad"]) == ("stok", p.id, "SKU1 — Vida")
    sc.close()
