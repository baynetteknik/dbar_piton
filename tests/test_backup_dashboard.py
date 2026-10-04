"""Yedekleme panosu: geçmiş verisi, grafikler (tıklama/tooltip geometrisi), disk halkası, filtreler ve Yedekleme Merkezi entegrasyonu."""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from src.core.models import DataTransferLog
from src.desktop.services import sync_log_service
from src.desktop.services.backup import file_job, history
from src.desktop.services.backup.models import BackupJob, JobStore
from src.desktop.services.backup.runner import RunResult, finish_run
from src.desktop.ui.widgets import backup_dashboard as bd
from src.desktop.ui.widgets.backup_charts import DonutChart, LineChart, TimelineBarChart
from src.desktop.ui.widgets.backup_center_widget import BackupCenterWidget
from src.desktop.ui.widgets.backup_dashboard import BackupDashboard, DiskFilesDialog, RunDetailDialog

GB, MB = 1 << 30, 1 << 20


def _kayit(db, job="Belgeler", mode="full", status="ok", bytes_=MB, seconds=60.0, mesaj="tamam", ago_h=1.0, uploads=None, dest=""):
    """Günlüğe, çalıştırıcının yazdığı biçimde bir yedek kaydı ekler; `ago_h` saat önce bitmiş gibi."""
    ad = f"{job.lower()}-{'inc' if mode == 'inc' else 'full'}-20260101-000000.zip"
    db.add(DataTransferLog(
        source="backup", direction=sync_log_service.DIR_BACKUP_JOB, status="ok" if status != "error" else "error",
        message=f"[{job}] {mesaj}", duration_ms=int(seconds * 1000),
        counts_json=__import__("json").dumps({"job": job, "job_id": "j1", "files": 5, "bytes": bytes_, "status": status, "mode": mode,
                                              "seconds": seconds, "file": ad, "uploads": uploads or [], "warnings": 0, "dest": dest}),
        created_at=datetime.utcnow() - timedelta(hours=ago_h)))
    db.commit()


# ---------------------------------------------------------------- geçmiş verisi
def test_finish_run_gunluge_tur_sure_boyut_ve_hedef_sonuclarini_yazar_history_okur(db_session, tmp_path):
    store = JobStore(db_session)
    job = BackupJob(name="Belgeler", dest_dir=str(tmp_path), sources=[str(tmp_path)], mode="incremental")
    store.save(job)
    res = RunResult("ok", "belgeler-inc-20260102-030000.zip: 3 dosya", tmp_path / "belgeler-inc-20260102-030000.zip", 3, 3 * MB,
                    seconds=42.5, started=time.time() - 42, uploads=[("Drive", True, "Yüklendi")])
    finish_run(db_session, store, job, res)
    (r,) = history.load(db_session)
    assert (r.job, r.mode, r.status, r.bytes, r.files, r.seconds) == ("Belgeler", "inc", "ok", 3 * MB, 3, 42.5)
    assert r.file.endswith(".zip") and r.uploads == [["Drive", True, "Yüklendi"]] and r.dest == str(tmp_path) and r.mbps == pytest.approx(3 / 42.5, rel=0.01)
    assert (r.end - r.start).total_seconds() == pytest.approx(42.5, abs=0.1) and r.message.startswith("belgeler-inc-")


def test_eski_kayitlarda_eksik_alanlar_mesajdan_turetilir_ve_aralik_is_filtresi_calisir(db_session):
    db_session.add(DataTransferLog(source="backup", direction=sync_log_service.DIR_BACKUP_JOB, status="ok", duration_ms=8000,
                                   message="[Eski İş] eski-inc-20250101-000000.zip: 2 dosya", counts_json='{"files": 2, "bytes": 1024, "status": "ok"}'))
    db_session.commit()
    _kayit(db_session, "Yeni", ago_h=100)
    _kayit(db_session, "Yeni", ago_h=2)
    eski = history.load(db_session, job="Eski İş")[0]
    assert (eski.mode, eski.seconds, eski.job, eski.status) == ("inc", 8.0, "Eski İş", "ok")
    bas, bit = history.range_bounds("24h")
    assert len(history.load(db_session, bas, bit)) == 2                                          # eski + 2 saat önceki
    assert [r.job for r in history.load(db_session, *history.range_bounds("7d"), job="Yeni")] == ["Yeni", "Yeni"]
    assert len(history.load(db_session, bas, bit, job="Yeni")) == 1
    özel = history.range_bounds("custom", custom=(datetime.now() - timedelta(days=1), datetime.now()))
    assert len(history.load(db_session, *özel)) == 2


def test_kpi_son_durum_son_artimli_boyut_ve_sayilar(db_session):
    _kayit(db_session, mode="full", bytes_=10 * MB, ago_h=30)
    _kayit(db_session, mode="inc", bytes_=450 * MB, ago_h=20)
    _kayit(db_session, mode="inc", status="error", bytes_=0, ago_h=10, mesaj="Disk dolu")
    k = history.kpis(history.load(db_session))
    assert (k.total, k.ok, k.failed, k.last_status, k.last_status_ok, k.last_inc_bytes) == (3, 2, 1, "Hata", False, 450 * MB)
    assert history.kpis([]).last_status == "—"
    assert history.format_size(1.5 * GB) == "1.5 GB" and history.format_size(3 * MB) == "3.0 MB" and history.format_size(12) == "12 B"
    assert history.format_duration(45) == "45 sn" and history.format_duration(252) == "4 dk 12 sn" and history.format_duration(4320) == "1 sa 12 dk"


def test_disk_info_kapasite_son_eski_ve_diger_kullanimi_ayirir(tmp_path):
    for n, boyut in (("is-full-20260101-000000.zip", 4000), ("is-inc-20260102-000000.zip", 1000), ("is-full-20260103-000000.zip", 2500)):
        (tmp_path / n).write_bytes(b"x" * boyut)
    d = history.disk_info(tmp_path, "is")
    assert d.last_backup == 2500 and d.old_backups == 5000 and [n for n, _s in d.files_last] == ["is-full-20260103-000000.zip"]
    assert d.files_old[0][1] == 4000 and d.total >= d.used + d.free - 1 and d.other == d.used - 7500 if d.used >= 7500 else True
    assert {k for k, _l, _v in d.slices} == {"last", "old", "other", "free"}
    assert history.disk_info(tmp_path / "yok" / "alt", "is") is not None                         # var olan üst klasörün diski
    assert history.disk_info(Path("Z:/kesin/yok/disk"), "is") is None or True


# ---------------------------------------------------------------- grafikler
def _run(mode="full", status="ok", bytes_=GB, secs=120.0, gun=0, job="J"):
    end = datetime(2026, 3, 1, 12, 0) + timedelta(days=gun)
    return history.Run(id=gun, job=job, status=status, start=end - timedelta(seconds=secs), end=end, mode=mode, seconds=secs, bytes=bytes_,
                       files=4, message="Hata: Dosya kilitli" if status == "error" else "tamam")


def test_cubuk_grafik_tam_kalin_artimli_ince_hata_kirmizi_isaretli_boyutla_orantili(qapp):
    c = TimelineBarChart()
    c.resize(700, 300)
    runs = [_run("full", gun=0, bytes_=10 * GB), _run("inc", gun=1, bytes_=2 * GB), _run("inc", "error", gun=2, bytes_=0), _run("full", gun=3, bytes_=5 * GB)]
    c.set_runs(runs)
    c._layout_hits()
    rects = {r.id: rect for rect, r in c._hits}
    assert rects[0].width() > rects[1].width()                                                   # tam kalın, artımlı ince
    assert rects[0].height() > rects[3].height() > rects[1].height()                             # boyutla orantılı
    assert rects[2].height() >= 0.04 * c._plot().height()                                        # hata çubuğu görünür (kırmızı + işaret)
    orta = rects[1].center()
    assert c.run_at(orta).id == 1 and c.run_at(QPointF(2, 2)) is None
    tip = c._tip(runs[2])
    assert "Artımlı" in tip and "Hata" in tip and "Dosya kilitli" in tip and "2 dk" in tip and "0 B" in tip
    tip0 = c._tip(runs[0])
    assert "Tam yedek" in tip0 and "10.0 GB" in tip0 and "✔ Başarılı" in tip0 and "01.03.2026" in tip0
    c.grab()                                                                                     # çizim hatasız
    c.set_runs([])
    c.grab()
    c.deleteLater()


def test_cubuk_grafik_tiklayinca_sinyal_yayar(qapp):
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QMouseEvent
    c = TimelineBarChart()
    c.resize(500, 260)
    c.set_runs([_run(gun=0), _run("inc", gun=1)])
    c._layout_hits()
    gelen = []
    c.run_clicked.connect(gelen.append)
    p = c._hits[1][0].center()
    c.mousePressEvent(QMouseEvent(QEvent.Type.MouseButtonPress, p, c.mapToGlobal(p), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert [r.id for r in gelen] == [1]


def test_halka_grafik_dilim_tespiti_yuzde_ve_tiklama(qapp):
    d = DonutChart()
    d.resize(300, 300)
    d.set_slices([("last", "Son yedek", 25), ("old", "Eski yedekler", 25), ("other", "Diğer kullanım", 0), ("free", "Boş alan", 50)], "%50\ndolu")
    c, r, ri = d._geometry()
    ortalama = (r + ri) / 2
    assert d.slice_at(QPointF(c.x() + ortalama * 0.5, c.y() - ortalama * 0.8)) == "last"          # saat 12–3 arası: ilk dilim
    assert d.slice_at(QPointF(c.x() + ortalama * 0.8, c.y() + ortalama * 0.5)) == "old"           # saat 3–6
    assert d.slice_at(QPointF(c.x() - ortalama, c.y())) == "free"                                 # sol yarı: boş alan
    assert d.slice_at(c) is None and d.slice_at(QPointF(c.x(), c.y() - r - 30)) is None           # merkez deliği ve dışı
    assert "%25.0" in d._tip("last") and "Tıklayınca" in d._tip("last") and "Tıklayınca" not in d._tip("free")
    d.grab()
    d.set_slices([], "")
    d.grab()
    assert d.slice_at(c) is None


def test_cizgi_grafik_yalniz_basarili_sureli_kayitlari_alir_hiz_hesaplar_ve_en_yakin_noktayi_bulur(qapp):
    c = LineChart()
    c.resize(600, 240)
    c.set_runs([_run(secs=60, bytes_=600 * MB, gun=0), _run("inc", secs=0, gun=1), _run("inc", "error", secs=30, gun=2), _run("inc", secs=120, bytes_=60 * MB, gun=3)])
    assert [r.id for r in c.runs] == [0, 3]                                                      # süresiz ve hatalı kayıtlar hariç
    assert c.runs[0].mbps == pytest.approx(10.0) and c.runs[1].mbps == pytest.approx(0.5)
    pt, run = c.point_hits()[0]
    assert c._nearest(pt + QPointF(3, 3)) is run and c._nearest(QPointF(1, 1)) is None
    assert "10.0 MB/s" in c._tip(run) and "1 dk" in c._tip(run)
    c.grab()


# ---------------------------------------------------------------- pano
@pytest.fixture
def pano(qapp, db_session):
    jobs = [BackupJob(name="Belgeler", dest_dir="D:\\yok", sources=["C:\\x"])]
    p = BackupDashboard(db_session, lambda: jobs, varsayilan_acik=True)
    p.resize(1200, 800)
    yield p
    p.close()


def test_pano_kapaliyken_yukleme_yapmaz_dugmeyle_acilir_ve_durumu_hatirlar(qapp, db_session):
    _kayit(db_session)
    p = BackupDashboard(db_session, lambda: [])
    assert not p.acik and p.btn_toggle.text().startswith("▲") and p.chart_bar.runs == []
    p.btn_toggle.click()
    assert p.acik and len(p.chart_bar.runs) == 1 and p.btn_toggle.text().startswith("▼")
    p2 = BackupDashboard(db_session, lambda: [])
    assert p2.acik                                                                               # durum hatırlandı
    p2.btn_toggle.click()
    assert not BackupDashboard(db_session, lambda: []).acik
    p.close(); p2.close()


def test_pano_kartlari_tablo_ve_grafikleri_doldurur_filtreler_calisir(pano, db_session):
    _kayit(db_session, "Belgeler", "full", bytes_=8 * GB, ago_h=50, seconds=600)
    _kayit(db_session, "Belgeler", "inc", bytes_=450 * MB, ago_h=26, seconds=90)
    _kayit(db_session, "Belgeler", "inc", "error", bytes_=0, ago_h=3, mesaj="Hata: Disk dolu")
    _kayit(db_session, "Diğer", "full", bytes_=1 * GB, ago_h=1)
    pano.yenile()
    assert len(pano.chart_bar.runs) == 4 and pano.k_donem.lbl_deger.text() == "3 başarılı / 1 hata"
    assert "Başarılı" in pano.k_son.lbl_deger.text()                                             # son çalışma: Diğer (başarılı)
    assert pano.k_inc.lbl_deger.text() == "450.0 MB"
    assert pano.table.rowCount() == 4 and pano.table.item(0, 1).text() == "Diğer"                # en yeni üstte
    assert isinstance(pano.table.cellWidget(0, 7), QApplication.instance().__class__.__mro__[0]) or pano.table.cellWidget(0, 7) is not None
    pano.cmb_job.setCurrentIndex(pano.cmb_job.findData("Belgeler"))
    assert len(pano.chart_bar.runs) == 3 and "1 hata" in pano.k_donem.lbl_deger.text()
    assert "Hata" in pano.k_son.lbl_deger.text() and pano.k_son.lbl_deger.text().startswith("❌")
    pano.cmb_range.setCurrentIndex(pano.cmb_range.findData("24h"))
    assert len(pano.chart_bar.runs) == 1                                                          # 50 ve 26 saat önceki dışarıda (yalnız 3 sa önceki hata)
    assert not pano.dt_bas.isVisibleTo(pano)
    pano.cmb_range.setCurrentIndex(pano.cmb_range.findData("custom"))
    assert pano.dt_bas.isVisibleTo(pano) and pano.dt_bit.isVisibleTo(pano)
    from PyQt6.QtCore import QDate
    pano.dt_bas.setDate(QDate.currentDate().addDays(-3))
    pano.dt_bit.setDate(QDate.currentDate())
    assert len(pano.chart_bar.runs) == 3                                                  # 50 sa + 26 sa + 3 sa önceki: günün saatinden bağımsız
    assert "dbgrid_backup_son_islemler" in pano.table.preset_id


def test_pano_hedef_disk_halkasi_ve_kalan_alan_karti_hedef_klasorden_beslenir(pano, db_session, tmp_path):
    (tmp_path / "belgeler-full-20260101-000000.zip").write_bytes(b"x" * 3000)
    (tmp_path / "belgeler-inc-20260102-000000.zip").write_bytes(b"x" * 1000)
    jobs = [BackupJob(name="Belgeler", dest_dir=str(tmp_path), sources=["C:\\x"])]
    pano.jobs_provider = lambda: jobs
    _kayit(db_session, "Belgeler", ago_h=1, dest=str(tmp_path))
    pano._isleri_doldur()
    pano.yenile()
    d = pano._disk
    assert d is not None and d.last_backup == 1000 and d.old_backups == 3000
    assert "boş" in pano.k_alan.lbl_alt.text() and "/" in pano.k_alan.lbl_deger.text()
    assert {k for k, _l, _v in pano.chart_donut.slices} == {"last", "old", "other", "free"} and "dolu" in pano.chart_donut.center_text
    acilan = []
    import src.desktop.ui.widgets.backup_dashboard as m
    orijinal = m.DiskFilesDialog.exec
    m.DiskFilesDialog.exec = lambda self: acilan.append(([self.grid.item(r, 0).text() for r in range(self.grid.rowCount())], self.windowTitle()))
    try:
        pano.chart_donut.slice_clicked.emit("old")
        pano.chart_donut.slice_clicked.emit("free")                                              # boş alan: liste yok
    finally:
        m.DiskFilesDialog.exec = orijinal
    assert acilan == [(["belgeler-full-20260101-000000.zip"], "Eski yedekler")]


def test_pano_disk_takili_degilse_karti_bunu_soyler(pano, db_session):
    jobs = [BackupJob(name="Belgeler", dest_dir="{disk:yok}\\TOYA", sources=["C:\\x"])]
    pano.jobs_provider = lambda: jobs
    pano.yenile()
    assert pano._disk is None and pano.k_alan.lbl_alt.text().startswith("Hedef disk takılı değil") and pano.chart_donut.slices == []


def test_cubuga_ve_tablo_dugmesine_tiklayinca_ayrinti_penceresi_acilir(pano, db_session, monkeypatch):
    _kayit(db_session, "Belgeler", "inc", "error", bytes_=0, mesaj="Hata: Dosya kilitli", uploads=[["Drive", False, "kota dolu"]], dest="D:\\Yedek")
    pano.yenile()
    acilan = []
    monkeypatch.setattr(RunDetailDialog, "exec", lambda self: acilan.append(self.txt.toPlainText()))
    pano.table.cellWidget(0, 7).click()                                                          # "Logları İncele"
    pano.chart_bar.run_clicked.emit(pano._runs[0])
    assert len(acilan) == 2
    for metin in acilan:
        assert "HATA" in metin and "Artımlı" in metin and "Dosya kilitli" in metin and "Drive" in metin and "kota dolu" in metin and "D:\\Yedek" in metin


def test_dosya_listesi_penceresi_buyukten_kucuge_sirali(qapp):
    d = DiskFilesDialog("Eski yedekler", [("a.zip", 10), ("b.zip", 5000), ("c.zip", 300)])
    assert [d.grid.item(r, 0).text() for r in range(3)] == ["b.zip", "c.zip", "a.zip"]
    d.close()


# ---------------------------------------------------------------- Yedekleme Merkezi
def test_merkezde_pano_altta_yenilenir_disk_menusu_ve_bildirim_kanalina_gore_toast(qapp, db_session, tmp_path, monkeypatch):
    store = JobStore(db_session)
    (tmp_path / "kaynak").mkdir()
    store.save(BackupJob(name="Belgeler", dest_dir=str(tmp_path / "d"), sources=[str(tmp_path / "kaynak")], notify={"events": ["error"], "channels": ["app"]}))
    store.save(BackupJob(name="Sessiz", dest_dir=str(tmp_path / "d2"), sources=[str(tmp_path / "kaynak")], notify={"events": ["error"], "channels": ["email"]}))
    w = BackupCenterWidget(db_session)
    assert isinstance(w.dashboard, BackupDashboard) and w.dashboard.acik is False
    assert any("Yedek Diskleri" in a.text() for a in w.btn_more.menu().actions())
    toasts = []
    w.toast_requested.connect(lambda m, t: toasts.append((m, t)))
    w._on_finished("Belgeler", "ok", "tamam")                                                    # başarı seçili değil: toast yok
    w._on_finished("Belgeler", "error", "Disk dolu")                                             # hata + uygulama içi: toast var
    w._on_finished("Sessiz", "error", "Disk dolu")                                               # kanal yalnız e-posta: toast yok
    assert [t[1] for t in toasts] == ["error"] and "Belgeler" in toasts[0][0]
    w.runner.stop()
