"""Yedek diski tanımı (seri numarası), çoklu bildirim olayları ve Google JSON içe aktarma."""

import json
import os
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from src.desktop.services.backup import disk_registry, disk_watch, notify, service
from src.desktop.services.backup.disk_registry import DiskStore, RegisteredDisk
from src.desktop.services.backup.disk_watch import Volume
from src.desktop.services.backup.models import BackupJob, JobStore, validate
from src.desktop.services.backup.providers import ProviderError
from src.desktop.ui.widgets.backup_disks_dialog import BackupDisksDialog
from src.desktop.ui.widgets.backup_job_dialog import BackupJobDialog
from src.desktop.ui.widgets.backup_target_dialog import BackupTargetDialog

V_E = Volume("E:\\", "YEDEK", 2, "1A2B3C4D")


# ---------------------------------------------------------------- kayıtlı disk
def test_disk_seri_numarasiyla_taninir_harf_ve_etiket_degisse_de(db_session):
    d = disk_registry.from_volume("Yedek Disk 1", V_E)
    assert (d.serial, d.label) == ("1A2B3C4D", "YEDEK")
    assert disk_registry.matches(d, Volume("G:\\", "BASKA-ETIKET", 2, "1a2b3c4d"))            # harf + etiket değişti, seri aynı
    assert not disk_registry.matches(d, Volume("E:\\", "YEDEK", 2, "FFFFFFFF"))               # aynı etiket, farklı disk
    eski = RegisteredDisk(name="Eski", serial="", label="Depo")                                # seri yoksa etikete düşülür
    assert disk_registry.matches(eski, Volume("F:\\", "depo", 2, "11111111")) and not disk_registry.matches(eski, V_E)
    assert disk_registry.roots([d, eski], [Volume("G:\\", "X", 2, "1A2B3C4D")]) == {d.id: "G:\\"}


def test_yer_tutucular_kayitli_disk_ve_tetikleyen_disk_icin_cozulur_takili_degilse_none(db_session):
    r = {"abc": "G:\\"}
    assert disk_registry.resolve(r"{disk:abc}\TOYA_Yedek", r) == r"G:\TOYA_Yedek"
    assert disk_registry.resolve(r"{disk:yok}\Y", r) is None
    assert disk_registry.resolve(r"{disk}\Y", r) is None and disk_registry.resolve(r"{disk}\Y", r, "H:\\") == r"H:\Y"
    assert disk_watch.resolve_dest(r"D:\Yedek", None) == r"D:\Yedek"
    assert disk_watch.resolve_dest(r"{disk:abc}\Y", None, r) == r"G:\Y"


def test_disk_store_kaydeder_tekrari_reddeder_gizler_ve_harf_degisimini_isler(db_session):
    s = DiskStore(db_session)
    ok, _ = s.save(disk_registry.from_volume("Disk 1", V_E))
    assert ok and [d.name for d in s.list()] == ["Disk 1"]
    assert s.save(disk_registry.from_volume("Baska Ad", V_E))[0] is False                     # aynı seri numarası
    assert s.save(disk_registry.from_volume("disk 1", Volume("F:\\", "X", 2, "99999999")))[0] is False   # aynı ad
    d = s.list()[0]
    s.touch([Volume("H:\\", "YENI-ETIKET", 2, "1A2B3C4D")])                                     # harf/etiket değişti
    d2 = s.get(d.id)
    assert (d2.last_root, d2.label) == ("H:\\", "YENI-ETIKET") and d2.serial == "1A2B3C4D"
    s.hide(d.id)
    assert s.list() == [] and len(s.list(include_hidden=True)) == 1


def test_arrivals_kayitli_diski_seri_numarasiyla_eski_isleri_etiketle_eslestirir(db_session):
    d = disk_registry.from_volume("Disk 1", V_E)
    yeni = BackupJob(name="Yeni", schedule={"type": "disk", "disk_id": d.id}, dest_dir="{disk:%s}\\Y" % d.id, sources=["x"])
    eski = BackupJob(name="Eski", schedule={"type": "disk", "disk_label": "YEDEK"}, dest_dir="{disk}\\Y", sources=["x"])
    degisik = Volume("K:\\", "TAMAMEN-BASKA", 2, "1A2B3C4D")                                    # etiket farklı, seri aynı
    out = disk_watch.arrivals(set(), [degisik], [yeni, eski], [d])
    assert [(j.name, v.root) for j, v in out] == [("Yeni", "K:\\")]                           # yalnız seriyle eşleşen
    out2 = disk_watch.arrivals(set(), [Volume("E:\\", "YEDEK", 2, "77777777")], [yeni, eski], [d])
    assert [j.name for j, _v in out2] == ["Eski"]                                              # etiket eşleşmesi eskisi gibi
    assert disk_watch.arrivals({"K:\\"}, [degisik], [yeni], [d]) == []                          # zaten takılıydı


def test_disk_zamanlamasi_kayitli_disk_ya_da_etiketle_gecerli(db_session):
    j = BackupJob(name="A", dest_dir="D:\\Y", sources=["C:\\x"], schedule={"type": "disk"})
    assert "disk" in validate(j).lower()
    j.schedule = {"type": "disk", "disk_id": "abc", "disk_name": "Disk 1"}
    assert validate(j) is None
    from src.desktop.services.backup import schedule
    assert "Disk 1" in schedule.describe(j)


@pytest.mark.skipif(os.name != "nt", reason="Windows sürücü bilgisi")
def test_windows_suruculeri_seri_numarasi_dondurur():
    vols = disk_watch.list_volumes()
    assert vols and any(v.serial for v in vols) and all(len(v.serial) in (0, 8) for v in vols)


def test_prepare_yerel_hedefteki_kayitli_disk_yer_tutucusunu_cozer_takili_degilse_atlar(db_session, tmp_path, monkeypatch):
    usb = tmp_path / "usb"
    usb.mkdir()
    d = disk_registry.from_volume("Disk 1", Volume(str(usb), "YEDEK", 2, "1A2B3C4D"))
    DiskStore(db_session).save(d)
    hedef = {"id": "t1", "type": "local", "label": "Harici", "path": "{disk:%s}\\TOYA" % d.id}
    job = BackupJob(name="Is", dest_dir=str(tmp_path / "d"), sources=[str(tmp_path)], cloud=[hedef])
    monkeypatch.setattr(disk_watch, "list_volumes", lambda: [Volume(str(usb), "YEDEK", 2, "1A2B3C4D")])
    ctx, notes = service.prepare(db_session, job)
    assert notes == [] and len(ctx.providers) == 1 and ctx.disks == {d.id: str(usb)}
    monkeypatch.setattr(disk_watch, "list_volumes", lambda: [])                                  # disk çıkarıldı
    ctx2, notes2 = service.prepare(db_session, job)
    assert ctx2.providers == [] and "takılı değil" in notes2[0]


# ---------------------------------------------------------------- disk tanım penceresi
def test_disk_penceresi_takili_diski_tanitir_durum_ve_kapasiteyi_gosterir(qapp, db_session, tmp_path, monkeypatch):
    vols = [Volume(str(tmp_path), "YEDEK", 2, "1A2B3C4D")]
    d = BackupDisksDialog(db_session, volumes_provider=lambda: list(vols))
    assert d.grid.rowCount() == 0 and "Henüz kayıtlı disk yok" in d.lbl.text()
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (a[3][0], True)))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Yedek Disk 1", True)))
    d.ekle()
    assert d.grid.rowCount() == 1 and d.grid.item(0, 0).text() == "Yedek Disk 1" and d.grid.item(0, 1).text() == "1A2B3C4D"
    assert d.grid.item(0, 3).text().startswith("✔ Takılı") and "/" in d.grid.item(0, 4).text()
    vols.clear()                                                                                # disk çıkarıldı
    d.yenile()
    assert d.grid.item(0, 3).text() == "✘ Takılı değil" and d.grid.item(0, 4).text() == ""
    shown = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a[2])))
    d.ekle()                                                                                    # takılı kayıtsız disk yok
    assert shown and "bulunamadı" in shown[0]
    vols.append(Volume("Z:\\", "YEDEK", 2, "1A2B3C4D"))                                          # aynı disk başka harfle takıldı
    d.yenile()
    assert d.grid.item(0, 3).text() == "✔ Takılı (Z:\\)"
    d.grid.selectRow(0)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Ofis Diski", True)))
    d.adlandir()
    assert d.grid.item(0, 0).text() == "Ofis Diski"
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    d.grid.selectRow(0)
    d.kaldir()
    assert d.grid.rowCount() == 0
    d.close()


def test_is_diyalogu_kayitli_diski_hedef_ve_zamanlamada_secer(qapp, db_session, tmp_path):
    disk = disk_registry.from_volume("Disk 1", V_E)
    DiskStore(db_session).save(disk)
    dlg = BackupJobDialog(None, db=db_session)
    acts = [a for a in dlg.btn_disk.menu().actions() if "Disk 1" in a.text()]
    assert acts
    acts[0].trigger()
    assert dlg.txt_dest.text() == "{disk:%s}\\TOYA_Yedek" % disk.id
    dlg.txt_name.setText("Disk İşi")
    dlg.cmb_kind.setCurrentIndex(dlg.cmb_kind.findData("files"))
    dlg.lst_sources.addItem(str(tmp_path))
    dlg.cmb_sched.setCurrentIndex(dlg.cmb_sched.findData("disk"))
    dlg.cmb_disk.setCurrentIndex(dlg.cmb_disk.findData(disk.id))
    j = dlg.build_job()
    assert j.schedule == {"type": "disk", "disk_id": disk.id, "disk_name": "Disk 1", "disk_label": "YEDEK"} and validate(j) is None
    dlg.cmb_disk.setCurrentText("SERBEST-ETIKET")                                               # kayıtsız etiket: eski usul
    assert dlg.build_job().schedule == {"type": "disk", "disk_label": "SERBEST-ETIKET"}
    dlg.close()


# ---------------------------------------------------------------- bildirim olayları
def _res(status):
    return SimpleNamespace(status=status)


def test_eski_bildirim_modu_olaylara_cevrilir_yeni_kayit_olay_ve_kanalla_karar_verir():
    never, fail, always = ({"mode": m} for m in ("never", "failure", "always"))
    assert notify.events_of(never) == set() and notify.events_of(fail) == {"error", "warning"} and notify.events_of(always) == set(notify.EVENTS)
    j = BackupJob(name="A", notify={"events": ["ok", "error"], "channels": ["email"], "to": "a@b.com"})
    assert notify.should_notify(j, _res("ok")) and notify.should_notify(j, _res("error")) and not notify.should_notify(j, _res("warning"))
    assert not notify.should_toast(j, _res("ok"))                                                # uygulama içi kanal kapalı
    j2 = BackupJob(name="B", notify={"events": ["error"], "channels": ["app"]})
    assert notify.should_toast(j2, _res("error")) and not notify.should_toast(j2, _res("ok")) and not notify.should_notify(j2, _res("error"))
    assert notify.should_toast(BackupJob(name="C", notify={"mode": "never"}), _res("ok"))         # eski kayıt: önceki davranış (hep göster)


def test_is_diyalogu_bildirim_olaylarini_coklu_secim_olarak_kaydeder_ve_yukler(qapp, tmp_path):
    j = BackupJob(name="X", dest_dir=str(tmp_path / "d"), sources=[str(tmp_path)], notify={"mode": "failure", "to": "a@b.com"})
    d = BackupJobDialog(j)
    assert [k for k, c in d.chk_events.items() if c.isChecked()] == ["warning", "error"]         # eski 'failure' → uyarı + hata
    d.chk_events["ok"].setChecked(True)
    d.chk_events["warning"].setChecked(False)
    d.chk_channels["app"].setChecked(False)
    n = d.build_job().notify
    assert n == {"events": ["ok", "error"], "channels": ["email"], "mode": "failure", "to": "a@b.com"}
    for c in d.chk_events.values():
        c.setChecked(False)
    assert d.build_job().notify["mode"] == "never" and d.build_job().notify["events"] == []
    d.close()


# ---------------------------------------------------------------- Google JSON içe aktarma
@pytest.fixture
def hedef(qapp):
    d = BackupTargetDialog({"type": "gdrive"})
    yield d
    d.close()


def test_oauth_istemci_json_dosyasi_kimlik_ve_gizli_anahtari_doldurur(hedef, tmp_path):
    p = tmp_path / "client_secret.json"
    p.write_text(json.dumps({"installed": {"client_id": "123.apps.googleusercontent.com", "client_secret": "GIZLI", "project_id": "p"}}), encoding="utf-8")
    assert hedef.import_google_json(str(p)) is True
    cfg, secret = hedef.values()
    assert cfg["client_id"] == "123.apps.googleusercontent.com" and cfg["auth_mode"] == "oauth" and "GIZLI" not in str(cfg)
    assert secret == {"client_secret": "GIZLI"} and "Google ile Bağlan" in hedef.lbl_status.text()
    p.write_text(json.dumps({"web": {"client_id": "w.apps", "client_secret": "S2"}}), encoding="utf-8")
    assert hedef.import_google_json(str(p)) and "Masaüstü uygulaması" in hedef.lbl_status.text()      # web türü uyarısı


def test_servis_hesabi_json_dosyasi_otomatik_taninir_kipi_degistirir(hedef, tmp_path):
    p = tmp_path / "sa.json"
    p.write_text(json.dumps({"type": "service_account", "client_email": "yedek@p.iam.gserviceaccount.com", "private_key": "-----BEGIN PRIVATE KEY-----\nX\n"}), encoding="utf-8")
    assert hedef.import_google_json(str(p)) is True
    cfg, secret = hedef.values()
    assert cfg["auth_mode"] == "service_account" and json.loads(secret["sa_json"])["client_email"].startswith("yedek@")
    assert "sa_json" not in str(cfg) and "yüklü" in hedef.lbl_google.text()


def test_gecersiz_ve_taninmayan_json_dosyalari_reddedilir(hedef, tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{bozuk", encoding="utf-8")
    assert hedef.import_google_json(str(p)) is False and "geçerli bir JSON değil" in hedef.lbl_status.text()
    p.write_text(json.dumps({"foo": 1}), encoding="utf-8")
    assert hedef.import_google_json(str(p)) is False and "Tanınmayan" in hedef.lbl_status.text()
    p.write_text(json.dumps({"type": "service_account", "client_email": "a@b"}), encoding="utf-8")
    assert hedef.import_google_json(str(p)) is False and "private_key" in hedef.lbl_status.text()
    assert hedef.values()[1] == {}


def test_json_ice_aktar_dugmesi_dosya_secicisini_kullanir(hedef, tmp_path, monkeypatch):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"installed": {"client_id": "cid2", "client_secret": "cs2"}}), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(p), "")))
    hedef.btn_json.click()
    assert hedef.fields["client_id"].text() == "cid2"
