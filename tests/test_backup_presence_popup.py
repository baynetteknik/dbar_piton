"""Yedek: bağlı kullanıcı varken başlamama, ana pencere durum popup'ı, hedef sonuçları/sağlık metni, kompakt pano + tam ekran."""

from datetime import datetime, timedelta

import pytest
from PyQt6.QtWidgets import QMessageBox

from src.desktop.services import settings_store
from src.desktop.services.backup import presence, schedule
from src.desktop.services.backup.models import BackupJob, JobStore
from src.desktop.services.backup.runner import RunContext, RunResult, finish_run, run_job
from src.desktop.ui.widgets.backup_center_widget import BackupCenterWidget
from src.desktop.ui.widgets.backup_dashboard import BackupDashboard, BackupDashboardDialog
from src.desktop.ui.widgets.backup_runner import BackupRunner
from src.desktop.ui.widgets.backup_status_popup import ActivityFilter, BackupStatusPopup


def _job(tmp_path, **kw):
    kaynak = tmp_path / "kaynak"
    kaynak.mkdir(exist_ok=True)
    (kaynak / "a.txt").write_text("merhaba")
    return BackupJob(name=kw.pop("name", "Belgeler"), dest_dir=str(tmp_path / "hedef"), sources=[str(kaynak)], **kw)


# ---------------------------------------------------------------- varlık
def test_presence_baska_oturum_taze_ise_bagli_sayilir_eski_ve_kendisi_sayilmaz(db_session):
    presence.beat(db_session, "ayse", "S1", now=1000.0)
    presence.beat(db_session, "veli", "S2", now=980.0)
    presence.beat(db_session, "ben", "BEN", now=1000.0)
    presence.leave(db_session, "S3")
    liste = presence.others(db_session, session_id="BEN", now=1050.0, timeout=90)
    assert [s.id for s in liste] == ["S1", "S2"] and liste[0].label.startswith("ayse@")
    assert [s.id for s in presence.others(db_session, session_id="BEN", now=1200.0, timeout=90)] == []          # herkes eskidi
    presence.leave(db_session, "S1")
    assert [s.id for s in presence.others(db_session, session_id="BEN", now=1050.0, timeout=200)] == ["S2"]      # çıkan sayılmaz


def test_yedek_baska_kullanici_bagliyken_baslamaz_cikinca_baslar_zorla_baslatilabilir(qapp, db_session, tmp_path):
    JobStore(db_session).save(_job(tmp_path))
    presence.beat(db_session, "ayse", "S1")
    r = BackupRunner(db_session, engine_factory=lambda: None)
    bekleyen, biten = [], []
    r.job_waiting.connect(lambda n, u: bekleyen.append((n, u)))
    r.job_finished.connect(lambda n, s, m: biten.append(s))
    job = JobStore(db_session).list()[0]
    assert r.enqueue(job.id) and not r.is_busy() and len(bekleyen) == 1 and "ayse" in bekleyen[0][1]
    r.tick(datetime.now())                                                                       # tekrar denenir ama bildirim tekrarlanmaz
    assert not r.is_busy() and len(bekleyen) == 1
    presence.leave(db_session, "S1")                                                             # kullanıcı çıktı
    r._next()
    assert r.is_busy()
    r._thread.wait(20000)
    for _ in range(200):
        qapp.processEvents()
        if biten:
            break
    assert biten == ["ok"]


def test_bagli_kullanici_ayari_kapaliysa_beklemez_ve_elle_calistirma_onay_ister(qapp, db_session, tmp_path, monkeypatch):
    JobStore(db_session).save(_job(tmp_path))
    presence.beat(db_session, "ayse", "S1")
    settings_store.set_setting(db_session, presence.SETTING_WAIT, "0")
    r = BackupRunner(db_session, engine_factory=lambda: None)
    assert r.connected_users() == []
    settings_store.set_setting(db_session, presence.SETTING_WAIT, "1")
    w = BackupCenterWidget(db_session, runner=r)
    w.table.selectRow(0)
    soruldu = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: soruldu.append(a[2]) or QMessageBox.StandardButton.No))
    w.run_selected()                                                                             # Hayır: başlamaz, bekler
    assert soruldu and "ayse" in soruldu[0] and not r.is_busy()


# ---------------------------------------------------------------- hedef sonuçları
def test_hedef_sonuclari_klasor_ve_dis_hedefleri_ayri_gosterir_basarisiz_hedef_uyari_yapar(db_session, tmp_path):
    store = JobStore(db_session)
    job = _job(tmp_path, schedule={"type": "daily", "time": "03:00"})
    store.save(job)
    yol = tmp_path / "hedef" / "belgeler-full-20260101-000000.zip"
    yol.parent.mkdir()
    yol.write_bytes(b"x")
    res = RunResult("warning", "ok", yol, 1, 1, started=1.0, uploads=[("Google Drive", False, "kota dolu")])
    res.targets = [(f"Klasör/disk: {yol.parent}", True, "Yazıldı")] + res.uploads
    finish_run(db_session, store, job, res)
    j = store.list()[0]
    assert [t[1] for t in j.state["last_targets"]] == [True, False]
    (h,) = schedule.health([j], datetime.now())
    assert h[1] == "warn" and "✔ Klasör/disk" in h[2] and "✘ Google Drive (kota dolu)" in h[2]


def test_run_job_hedefleri_yerel_klasoru_de_icerir(tmp_path):
    job = _job(tmp_path)
    res = run_job(job, RunContext())
    assert res.status == "ok" and res.targets[0][0].startswith("Klasör/disk:") and res.targets[0][1] is True


def test_nochange_sonucu_son_basarili_sayilir_ve_duzenleme_durumu_ezmez(db_session, tmp_path):
    store = JobStore(db_session)
    job = _job(tmp_path, schedule={"type": "daily", "time": "03:00"})
    store.save(job)
    finish_run(db_session, store, job, RunResult("nochange", "Değişiklik yok", started=1.0))
    j = store.list()[0]
    assert j.state["last_success"] and schedule.health([j], datetime.now())[0][1] == "ok"
    eski_kopya = BackupJob(**{**j.__dict__, "state": {"last_status": "eski"}})
    store.save(eski_kopya)                                                                        # eski kopyayla kayıt durumu bozmaz
    assert store.list()[0].state["last_success"]


# ---------------------------------------------------------------- popup
def test_popup_asama_ilerleme_sonuc_ve_kullanici_uyarisi(qapp):
    from PyQt6.QtWidgets import QWidget
    ana = QWidget()
    ana.resize(900, 600)
    ana.show()
    p = BackupStatusPopup(ana)
    assert not p.isVisible() and p.note_activity() is False                                       # yedek yokken uyarı yok
    p.on_started("Toya Yedek")
    assert p.isVisible() and "Toya Yedek" in p.lbl_title.text() and p.bar.maximum() == 0
    p.on_line("Yükleniyor: Google Drive…")
    p.on_progress(50, 100)
    assert p.lbl_stage.text() == "Yükleniyor: Google Drive…" and p.bar.value() == 50 and p.bar.maximum() == 100
    assert p.lbl_warn.isHidden()
    assert p.note_activity() and not p.lbl_warn.isHidden()                                        # kullanıcı işlem yaptı
    assert p.geometry().right() <= ana.width() and p.geometry().bottom() <= ana.height()
    p.on_finished("Toya Yedek", "error", "Disk dolu")
    assert not p.running and "başarısız" in p.lbl_title.text() and p.lbl_warn.isHidden() and p.note_activity() is False
    p.on_waiting("Toya Yedek", "ayse@PC1")
    assert "ayse@PC1" in p.lbl_stage.text() and "bekliyor" in p.lbl_title.text()
    f = ActivityFilter(p)
    p.on_started("X")
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtCore import Qt
    f.eventFilter(ana, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier, "a"))
    assert not p.lbl_warn.isHidden()
    ana.close()


# ---------------------------------------------------------------- pano kompakt / tam ekran
def test_merkezde_pano_kompakt_grafikler_gizli_tam_ekran_dugmesi_pencere_acar(qapp, db_session, monkeypatch):
    w = BackupCenterWidget(db_session)
    d = w.dashboard
    assert d.kompakt and not d.btn_tam.isHidden() and d.grafikler.isHidden() and d.table.maximumHeight() <= 260
    acilan = []
    monkeypatch.setattr(BackupDashboardDialog, "exec", lambda self: acilan.append(self))
    d.btn_tam.click()
    assert len(acilan) == 1
    tam = acilan[0].pano
    assert not tam.kompakt and not tam.grafikler.isHidden() and tam.btn_toggle.isHidden() and tam.btn_tam.isHidden()
    assert acilan[0].windowState() & acilan[0].windowState().WindowMaximized
    acilan[0].close()
    from src.desktop.ui.components.app_grid import AppGrid
    assert isinstance(w.table, AppGrid)
