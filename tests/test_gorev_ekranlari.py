"""Görevler ekranları (liste / pano / takvim), görev penceresi, geliştirme ekranı ve yetkiler."""

from datetime import date, datetime, timedelta

import pytest
from PyQt6.QtWidgets import QMessageBox

from src.core.models import Gorev
from src.desktop.services.dev_tracker_store import DevTracker
from src.desktop.services.gorev_service import GorevService


@pytest.fixture
def dev(tmp_path):
    return DevTracker(tmp_path / "dev_tracker.db")


def _ekran(db, **kw):
    from src.desktop.ui.gorevler_screen import GorevlerScreen
    return GorevlerScreen(db_session=db, **kw)


def test_gorev_penceresi_kaydeder_dogrular_ve_yeniden_yukler(qapp, db_session, monkeypatch):
    from src.desktop.ui.widgets.gorev_dialog import GorevDialog
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    d = GorevDialog(db_session, kullanici="ayse", varsayilan={"tur": "randevu", "ilgili_tur": "servis", "ilgili_id": 42, "ilgili_ad": "Servis #42"})
    assert d.chk_bas.isChecked() and d.cmb_atanan.currentText() == "ayse" and d.cmb_ilgili.currentData() == "servis"
    d.kaydet()                                                                               # başlık boş
    assert d.kaydedilen is None and "Başlık" in d.lbl_hata.text()
    d.txt_baslik.setText("Servis ziyareti")
    d.chk_bit.setChecked(True)
    d.cmb_hatirlat.setCurrentIndex(d.cmb_hatirlat.findData(30))
    d.cmb_tekrar.setCurrentIndex(d.cmb_tekrar.findData("haftalik"))
    d.kaydet()
    g = d.kaydedilen
    assert g.tur == "randevu" and g.hatirlat_dk == 30 and g.tekrar == "haftalik" and (g.ilgili_tur, g.ilgili_id, g.ilgili_ad) == ("servis", 42, "Servis #42")
    d2 = GorevDialog(db_session, gorev_id=g.id)
    assert d2.txt_baslik.text() == "Servis ziyareti" and d2.chk_bas.isChecked() and d2.chk_bit.isChecked() and d2.cmb_hatirlat.currentData() == 30
    d2.chk_bit.setChecked(False)
    d2.cmb_tekrar.setCurrentIndex(d2.cmb_tekrar.findData("yok"))
    d2.cmb_durum.setCurrentIndex(d2.cmb_durum.findData("tamam"))
    d2.kaydet()
    assert d2.kaydedilen.bitis is None and d2.kaydedilen.durum == "tamam" and d2.kaydedilen.tamamlandi is not None
    d.close()
    d2.close()


def test_gorevler_ekrani_liste_filtre_hizli_filtre_durum_ve_gizleme(qapp, db_session, monkeypatch):
    svc = GorevService(db_session)
    svc.kaydet({"baslik": "Gecikmiş tahsilat", "bitis": datetime.now() - timedelta(days=2), "atanan": "ayse", "oncelik": 4, "kategori": "tahsilat"})
    svc.kaydet({"baslik": "Bugünkü toplantı", "tur": "randevu", "baslangic": datetime.now().replace(hour=23, minute=0), "atanan": "veli"})
    svc.kaydet({"baslik": "Bitmiş iş", "durum": "tamam"})
    sc = _ekran(db_session, kullanici="ayse")
    assert sc.table_model.rowCount() == 3 and "Gecikmiş: 1" in sc.lbl_ozet.text()
    basliklar = {sc.table_model.item(r, 1).text(): r for r in range(3)}
    assert sc.table_model.item(basliklar["Gecikmiş tahsilat"], 8).text().startswith("⚠")
    sc.set_hizli("benim")
    assert sc.table_model.rowCount() == 1 and sc.table_model.item(0, 1).text() == "Gecikmiş tahsilat"
    sc.set_hizli("gecikmis")
    assert sc.table_model.rowCount() == 1
    sc.set_hizli("acik")
    assert sc.table_model.rowCount() == 2
    sc.clear_filters()
    sc.search_box.setText("toplantı")
    assert sc.table_model.rowCount() == 1
    sc.clear_filters()
    sc.table_view.selectRow(0)
    assert "Gecikmiş tahsilat" in sc.lbl_detay.text()
    sc.on_durum_clicked("tamam")
    assert sc.svc.ozet().tamam == 2
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    sc.table_view.selectRow(0)
    sc.on_hide_clicked()
    assert sc.table_model.rowCount() == 2 and db_session.query(Gorev).count() == 3               # gizlendi, silinmedi
    sc.close()


def test_gorevler_ekrani_pano_surukle_birak_durumu_degistirir_takvim_gununu_gosterir(qapp, db_session, monkeypatch):
    import src.desktop.ui.gorevler_screen as m
    monkeypatch.setattr(m, "GorevDialog", type("Sahte", (), {"__init__": lambda self, *a, **k: None, "exec": lambda self: 0}))
    svc = GorevService(db_session)
    g = svc.kaydet({"baslik": "Pano kartı", "bitis": datetime.now().replace(hour=23, minute=30)})
    svc.kaydet({"baslik": "Takvim olayı", "baslangic": datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)})
    sc = _ekran(db_session, kullanici="ayse")
    sc.show()
    sc.set_gorunum("pano")
    assert sc.kanban.isVisible() and not sc.filterable_table.isVisible() and not sc.takvim.isVisible()
    assert sc.kanban.listeler["yapilacak"].count() == 2 and "YAPILACAK  (2)" in sc.kanban.basliklar["yapilacak"].text()
    sc.kanban.durum_degisti.emit(g.id, "devam")                                             # sürükle-bırak sinyali
    assert db_session.get(Gorev, g.id).durum == "devam" and sc.kanban.listeler["devam"].count() == 1
    sc.set_gorunum("takvim")
    assert sc.takvim.isVisible()
    cell = sc.takvim.gunler[date.today()]
    assert cell.liste.count() == 2 and "10:00 Takvim olayı" in [cell.liste.item(i).text() for i in range(2)]
    acilan = []
    sc.takvim.gorev_acildi.connect(acilan.append)
    cell.liste.itemDoubleClicked.emit(cell.liste.item(0))
    assert len(acilan) == 1
    sc.takvim.git(1)                                                                       # sonraki ay
    assert sc.takvim.ay != date.today().month or sc.takvim.yil != date.today().year
    assert all(c.liste.count() == 0 for d, c in sc.takvim.gunler.items() if d.month == sc.takvim.ay)
    sc.set_gorunum("liste")
    assert sc.filterable_table.isVisible() and not sc.kanban.isVisible()
    sc.close()


def test_gorevler_ekrani_ilgili_kayit_kipinde_yalniz_o_kaydin_gorevleri(qapp, db_session, monkeypatch):
    svc = GorevService(db_session)
    svc.iliskili_olustur("servis", 42, "Servis #42", "Parça sipariş")
    svc.iliskili_olustur("servis", 43, "Servis #43", "Başka")
    svc.kaydet({"baslik": "Genel"})
    sc = _ekran(db_session, ilgili=("servis", 42, "Servis #42"), kullanici="ayse")
    assert sc.table_model.rowCount() == 1 and sc.table_model.item(0, 1).text() == "Parça sipariş"
    acilan = []

    class Sahte:
        def __init__(self, db, **kw):
            acilan.append(kw)

        def exec(self):
            return 0

    import src.desktop.ui.gorevler_screen as m
    monkeypatch.setattr(m, "GorevDialog", Sahte)
    sc.btn_yeni["gorev"].click()
    v = acilan[0]["varsayilan"]
    assert (v["ilgili_tur"], v["ilgili_id"], v["atanan"]) == ("servis", 42, "ayse")
    sc.close()


def test_gelistirme_ekrani_liste_filtre_durum_ve_gizleme(qapp, dev, monkeypatch):
    from src.desktop.ui.dev_tracker_screen import DevTrackerScreen
    dev.ekle("Kasa hareketleri", modul="Kasa", durum="tamam")
    dev.ekle("Denetim günlüğü", tur="oneri", modul="Sistem", oncelik=4)
    dev.ekle("Yedek hatası", tur="hata", modul="Yedekleme", durum="devam")
    sc = DevTrackerScreen(tracker=dev, kullanici="alparslan")
    assert sc.table_model.rowCount() == 2 and "Açık: 2" in sc.lbl_ozet.text()                    # varsayılan: açık kayıtlar
    sc.cmb_durum.setCurrentIndex(sc.cmb_durum.findData(None))
    assert sc.table_model.rowCount() == 3
    sc.cmb_modul.setCurrentIndex(sc.cmb_modul.findData("Sistem"))
    assert sc.table_model.rowCount() == 1
    sc.clear_filters()
    sc.cmb_durum.setCurrentIndex(sc.cmb_durum.findData(None))
    sc.search_box.setText("Denetim")
    sc.table_view.selectRow(0)
    sc.on_durum_clicked("tamam")
    assert dev.ozet().get("tamam") == 2
    assert dev.gecmis(dev.liste(arama="Denetim")[0]["id"])[0]["kim"] == "alparslan"
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    sc.table_view.selectRow(0)
    sc.on_hide_clicked()
    assert len(dev.liste()) == 2
    sc.close()


def test_gelistirme_kaydi_penceresi_ve_gecmis(qapp, dev, monkeypatch):
    from src.desktop.ui.widgets.dev_item_dialog import DevItemDialog
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    d = DevItemDialog(dev, kim="claude", varsayilan={"tur": "hata"})
    assert d.cmb_tur.currentData() == "hata" and d.txt_ekleyen.text() == "claude"
    d.kaydet()
    assert d.result() == 0 and "Başlık" in d.lbl_hata.text()
    d.txt_baslik.setText("Kilitli fiş hatası")
    d.txt_modul.setText("Kasa")
    d.kaydet()
    assert d.result() == 1 and dev.getir(d.item_id)["modul"] == "Kasa"
    d2 = DevItemDialog(dev, item_id=d.item_id, kim="claude")
    d2.cmb_durum.setCurrentIndex(d2.cmb_durum.findData("tamam"))
    d2.txt_commit.setText("abc123456")
    d2.kaydet()
    assert dev.getir(d.item_id)["durum"] == "tamam"
    d3 = DevItemDialog(dev, item_id=d.item_id, kim="claude")
    assert d3.grid.rowCount() >= 3 and d3.txt_commit.text() == "abc123456"
    for x in (d, d2, d3):
        x.close()


def test_izinler_ve_roller_gorev_yetkisini_icerir():
    from src.desktop.security.permissions import ALL_PERMISSIONS, DEFAULT_ROLES
    assert {"gorev.view", "gorev.create", "gorev.edit", "gorev.delete"} <= set(ALL_PERMISSIONS)
    assert "gorev.create" in DEFAULT_ROLES["Satış"][1] and "gorev.delete" not in DEFAULT_ROLES["Satış"][1]
    assert DEFAULT_ROLES["Salt Okunur"][1].count("gorev.view") == 1
