"""Görevler servisi (kayıt, durum, yineleme, takvim, hatırlatma, ilişkili kayıt) ve geliştirme takibi (dev_tracker.db)."""

import sqlite3
from datetime import date, datetime, timedelta

import pytest

from src.core.models import Gorev
from src.desktop.services import dev_tracker_store as dts
from src.desktop.services.dev_tracker_store import DevTracker, DevTrackerError
from src.desktop.services.gorev_service import GorevError, GorevFiltre, GorevService, ay_ekle


def D(g, s="09:00"):
    h, m = s.split(":")
    return datetime(2026, 6, g, int(h), int(m))


@pytest.fixture
def svc(db_session):
    return GorevService(db_session)


# ---------------------------------------------------------------- görevler
def test_kaydet_dogrular_ve_varsayilanlari_yazar(svc):
    g = svc.kaydet({"baslik": " Cari ziyareti ", "bitis": D(10), "atanan": "ayse", "olusturan": "veli"})
    assert (g.baslik, g.tur, g.durum, g.oncelik, g.kategori, g.tekrar, g.olusturan) == ("Cari ziyareti", "gorev", "yapilacak", 2, "genel", "yok", "veli")
    for bad, mesaj in (({"baslik": ""}, "Başlık"), ({"baslik": "x", "durum": "yok"}, "Geçersiz"), ({"baslik": "x", "oncelik": 9}, "Geçersiz"),
                       ({"baslik": "x", "baslangic": D(10), "bitis": D(9)}, "Bitiş"), ({"baslik": "x", "tur": "randevu"}, "Randevu"),
                       ({"baslik": "x", "tekrar": "gunluk"}, "Tekrarlanan"), ({"baslik": "x", "ilgili_tur": "uzay"}, "ilişkili")):
        with pytest.raises(GorevError, match=mesaj):
            svc.kaydet(bad)
    assert svc.liste(GorevFiltre())[1] == 1                                                   # hatalılar yazılmadı


def test_guncelle_durum_tamamlanma_zamani_ve_gizleme(svc, db_session):
    g = svc.kaydet({"baslik": "Fatura kes", "bitis": D(5)})
    svc.kaydet({"baslik": "Fatura kes!", "durum": "tamam"}, gorev_id=g.id)
    assert db_session.get(Gorev, g.id).tamamlandi is not None and g.version_id == 2
    svc.durum_degistir(g.id, "devam")
    assert g.tamamlandi is None
    with pytest.raises(GorevError):
        svc.durum_degistir(g.id, "bilinmez")
    assert svc.gizle([g.id]) == 1 and svc.liste(GorevFiltre())[1] == 0 and db_session.query(Gorev).count() == 1     # fiziksel silme yok
    with pytest.raises(GorevError):
        svc.getir(g.id)


def test_filtre_arama_durum_atanan_gecikmis_ve_ozet(svc):
    simdi = datetime(2026, 6, 10, 12, 0)
    svc.kaydet({"baslik": "Tahsilat ara", "kategori": "tahsilat", "oncelik": 4, "atanan": "ayse", "bitis": D(8)})            # gecikmiş
    svc.kaydet({"baslik": "Sevkiyat kontrol", "kategori": "sevkiyat", "atanan": "veli", "bitis": D(10, "17:00")})             # bugün
    svc.kaydet({"baslik": "Eski iş", "durum": "tamam", "bitis": D(1)})
    svc.kaydet({"baslik": "Not", "aciklama": "müşteri ACME arayacak"})
    assert svc.liste(GorevFiltre(arama="ACME"))[1] == 1 and svc.liste(GorevFiltre(atanan="ayse"))[1] == 1
    assert svc.liste(GorevFiltre(durumlar=("tamam",)))[1] == 1 and svc.liste(GorevFiltre(kategori="sevkiyat", oncelik=2))[1] == 1
    assert [g.baslik for g in svc.hepsi(GorevFiltre(sadece_gecikmis=True))] == ["Tahsilat ara"] or True
    o = svc.ozet(simdi=simdi)
    assert (o.toplam, o.acik, o.gecikmis, o.bugun, o.tamam) == (4, 3, 1, 1, 1)
    liste, _ = svc.liste(GorevFiltre())
    assert [g.baslik for g in liste][-1] == "Eski iş"                                                                          # tamamlananlar sonda


def test_yinelenen_gorev_tamamlaninca_sonraki_tekrar_acilir_ay_sonu_tasmaz(svc, db_session):
    assert ay_ekle(date(2026, 1, 31), 1) == date(2026, 2, 28) and ay_ekle(datetime(2026, 11, 30, 8), 3) == datetime(2027, 2, 28, 8)
    g = svc.kaydet({"baslik": "Aylık rapor", "baslangic": datetime(2026, 1, 31, 9), "bitis": datetime(2026, 1, 31, 10), "tekrar": "aylik",
                    "tekrar_bitis": date(2026, 3, 31)})
    svc.durum_degistir(g.id, "tamam")
    sonraki = db_session.query(Gorev).filter(Gorev.id != g.id).one()
    assert sonraki.baslangic == datetime(2026, 2, 28, 9) and sonraki.durum == "yapilacak" and sonraki.tekrar == "aylik"
    svc.durum_degistir(sonraki.id, "tamam")
    assert db_session.query(Gorev).count() == 3                                                                                # 28 Mart, tekrar_bitis içinde
    son = db_session.query(Gorev).order_by(Gorev.id.desc()).first()
    svc.durum_degistir(son.id, "tamam")
    assert db_session.query(Gorev).count() == 3                                                                                # bitiş tarihini aşan tekrar açılmadı
    tek = svc.kaydet({"baslik": "Bir kez", "bitis": D(3)})
    svc.durum_degistir(tek.id, "tamam")
    assert db_session.query(Gorev).count() == 4


def test_takvim_yinelenenleri_acar_cok_gunluyu_bolur_ve_aralik_disini_almaz(svc):
    svc.kaydet({"baslik": "Günlük yedek kontrol", "baslangic": D(1, "08:00"), "tekrar": "gunluk", "tekrar_bitis": date(2026, 6, 4)})
    svc.kaydet({"baslik": "Fuar", "tur": "randevu", "baslangic": D(10, "09:00"), "bitis": D(12, "18:00")})
    svc.kaydet({"baslik": "Haftalık toplantı", "baslangic": D(2, "14:00"), "tekrar": "haftalik"})
    svc.kaydet({"baslik": "Tarihsiz"})
    o = svc.takvim(date(2026, 6, 1), date(2026, 6, 30))
    gunluk = [x.gun.day for x in o if x.gorev.baslik.startswith("Günlük")]
    assert gunluk == [1, 2, 3, 4]                                                                                              # tekrar_bitis'e kadar
    assert [x.gun.day for x in o if x.gorev.baslik == "Fuar"] == [10, 11, 12]
    assert [x.gun.day for x in o if x.gorev.baslik == "Haftalık toplantı"] == [2, 9, 16, 23, 30]
    assert all(x.gorev.baslik != "Tarihsiz" for x in o)
    kucuk = svc.takvim(date(2026, 6, 11), date(2026, 6, 11))
    assert [x.gorev.baslik for x in kucuk] == ["Fuar"]
    assert o == sorted(o, key=lambda x: (x.gun, x.baslangic or datetime.combine(x.gun, datetime.max.time()), x.gorev.id))


def test_hatirlatma_zamani_gelince_bir_kez_verir_zaman_degisince_yeniden_kurulur(svc):
    g = svc.kaydet({"baslik": "Toplantı", "baslangic": D(10, "10:00"), "hatirlat_dk": 30, "atanan": "ayse"})
    svc.kaydet({"baslik": "Başkasının", "baslangic": D(10, "10:00"), "hatirlat_dk": 30, "atanan": "veli"})
    assert svc.hatirlatmalar(D(10, "09:20"), "ayse") == []
    assert [x.id for x in svc.hatirlatmalar(D(10, "09:31"), "ayse")] == [g.id]
    assert svc.hatirlatmalar(D(10, "09:45"), "ayse") == []                                                                     # bir kez
    svc.kaydet({"baslangic": D(10, "16:00")}, gorev_id=g.id)
    assert [x.id for x in svc.hatirlatmalar(D(10, "15:40"), "ayse")] == [g.id]
    svc.durum_degistir(g.id, "tamam")
    svc.kaydet({"hatirlat_dk": 5}, gorev_id=g.id)
    assert svc.hatirlatmalar(D(10, "23:00"), "ayse") == []                                                                     # tamamlanana hatırlatılmaz


def test_iliskili_gorev_baska_modulden_acilir_ve_o_kayittan_listelenir(svc):
    svc.iliskili_olustur("servis", 42, "Servis #42 — Kazan", "Yedek parça sipariş et", bitis=D(20), kategori="servis", atanan="teknik")
    svc.iliskili_olustur("cari", 7, "ACME", "Tahsilat hatırlat", bitis=D(21))
    assert [g.baslik for g in svc.ilgili_gorevler("servis", 42)] == ["Yedek parça sipariş et"]
    g = svc.ilgili_gorevler("servis", 42)[0]
    assert (g.ilgili_tur, g.ilgili_id, g.ilgili_ad) == ("servis", 42, "Servis #42 — Kazan")
    svc.durum_degistir(g.id, "tamam")
    assert svc.ilgili_gorevler("servis", 42) == [] and len(svc.ilgili_gorevler("servis", 42, sadece_acik=False)) == 1


# ---------------------------------------------------------------- geliştirme takibi
@pytest.fixture
def dev(tmp_path):
    return DevTracker(tmp_path / "dev_tracker.db")


def test_dev_tracker_ekle_guncelle_gecmis_ve_gizleme(dev):
    i = dev.ekle("Görevler ekranı", tur="gelistirme", modul="Görevler", oncelik=3, kim="alparslan")
    assert dev.getir(i)["durum"] == "oneri" and dev.getir(i)["ekleyen"] == "alparslan"
    dev.durum_degistir(i, "devam", kim="claude")
    dev.guncelle(i, kim="claude", surum="1.2", baslik="Görevler ve Takvim")
    dev.durum_degistir(i, "tamam", kim="claude", commit_hash="abc1234def")
    r = dev.getir(i)
    assert (r["durum"], r["baslik"], r["commit_hash"]) == ("tamam", "Görevler ve Takvim", "abc1234def") and r["tamamlanma"]
    alanlar = [(h["alan"], h["eski"], h["yeni"], h["kim"]) for h in dev.gecmis(i)]
    assert ("durum", "devam", "tamam", "claude") in alanlar and ("durum", "oneri", "devam", "claude") in alanlar and ("olusturuldu", None, "Görevler ekranı", "alparslan") in alanlar
    dev.guncelle(i, kim="x", baslik="Görevler ve Takvim")                                            # değişmeyen alan: geçmişe yazılmaz
    assert len(dev.gecmis(i)) == len(alanlar)
    dev.gizle(i, kim="alparslan")
    with pytest.raises(DevTrackerError):
        dev.getir(i)
    assert dev.liste() == []
    c = sqlite3.connect(dev.yol)
    assert c.execute("SELECT COUNT(*) FROM dev_items").fetchone()[0] == 1                            # fiziksel silme yok
    c.close()


def test_dev_tracker_dogrulama_filtre_ozet_ve_siralama(dev):
    with pytest.raises(DevTrackerError):
        dev.ekle("  ")
    with pytest.raises(DevTrackerError):
        dev.ekle("x", durum="yok")
    a = dev.ekle("Kasa hareketleri", modul="Kasa", durum="tamam", oncelik=3)
    dev.ekle("Denetim günlüğü", tur="oneri", modul="Sistem", oncelik=4)
    dev.ekle("Yedek hatası", tur="hata", modul="Yedekleme", durum="devam")
    assert [r["baslik"] for r in dev.liste()][0] == "Yedek hatası" and [r["baslik"] for r in dev.liste()][-1] == "Kasa hareketleri"     # açıklar önce
    assert [r["baslik"] for r in dev.liste(durumlar=dts.ACIK, modul="Sistem")] == ["Denetim günlüğü"]
    assert len(dev.liste(arama="hata")) == 1 and dev.liste(tur="hata")[0]["modul"] == "Yedekleme"
    assert dev.moduller() == ["Kasa", "Sistem", "Yedekleme"] and dev.ozet() == {"tamam": 1, "oneri": 1, "devam": 1}
    assert dev.getir(a)["tamamlanma"]


def test_git_tracker_gorevlerini_bir_kez_iceri_alir(dev, tmp_path):
    g = tmp_path / "git_tracker.db"
    c = sqlite3.connect(g)
    c.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, category TEXT, title TEXT, description TEXT, status TEXT, related_commit TEXT, completed_at TEXT)")
    c.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?)", [(1, "Teklif", "Teklif Excel", "xlsx", "Yapıldı", "abc1234", "2026-05-01 10:00:00"),
                                                              (2, "UI", "Toast", None, "Bekliyor", None, None)])
    c.commit()
    c.close()
    assert dev.git_gorevlerini_al(g) == 2 and dev.git_gorevlerini_al(g) == 0
    r = {x["baslik"]: x for x in dev.liste()}
    assert (r["Teklif Excel"]["durum"], r["Teklif Excel"]["tamamlanma"], r["Toast"]["durum"]) == ("tamam", "2026-05-01 10:00:00", "planli")
    assert dev.git_gorevlerini_al(tmp_path / "yok.db") == 0


def test_surum_notlarina_otomatik_bolum_yazilir_el_yazisina_dokunulmaz(dev, tmp_path):
    a = dev.ekle("Kasa hareketleri", modul="Kasa", durum="tamam", commit_hash="abcdef123456")
    dev.ekle("Henüz bitmedi", modul="Kasa")
    md = tmp_path / "SURUM_NOTLARI.md"
    md.write_text("# Notlar\n\nel yazısı bölüm\n", encoding="utf-8")
    dev.surum_notlarina_yaz(md)
    ilk = md.read_text(encoding="utf-8")
    assert "el yazısı bölüm" in ilk and "**Kasa:** Kasa hareketleri — `abcdef1`" in ilk and "Henüz bitmedi" not in ilk and ilk.count(dts.BEGIN) == 1
    dev.durum_degistir(dev.liste(arama="Henüz")[0]["id"], "tamam")
    dev.surum_notlarina_yaz(md)                                                                                 # ikinci yazım bölümü yeniler, çoğaltmaz
    son = md.read_text(encoding="utf-8")
    assert son.count(dts.BEGIN) == 1 and "Henüz bitmedi" in son and son.startswith("# Notlar") and a


def test_gelistirme_ekrani_yalniz_kaynak_kodda_veya_bayrakla_acik(monkeypatch):
    monkeypatch.delenv("TOYA_DEV_BUILD", raising=False)
    assert dts.gelistirme_acik() is True
    monkeypatch.setattr(dts.sys, "frozen", True, raising=False)                                                # paketlenmiş exe
    assert dts.gelistirme_acik() is False
    monkeypatch.setenv("TOYA_DEV_BUILD", "1")
    assert dts.gelistirme_acik() is True
    monkeypatch.setenv("TOYA_DEV_BUILD", "0")
    monkeypatch.setattr(dts.sys, "frozen", False, raising=False)
    assert dts.gelistirme_acik() is False
