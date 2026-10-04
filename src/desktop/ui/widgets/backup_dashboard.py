"""TOYA ERP - BackupDashboard: Yedekleme Merkezi'nin altında açılıp kapanan grafikli pano.

İçerik: iş ve tarih aralığı filtresi (son 24 saat / 7 gün / 30 gün / özel), özet kartları (son yedek durumu, son artımlı boyut,
hedefte kalan alan, dönem sonucu), yedek geçmişi ve boyut grafiği (tam mavi kalın, artımlı yeşil ince, hata kırmızı "!"),
hedef disk doluluk halkası (dilime tıklayınca dosya listesi), süre/hız trendi ve "Son Yedekleme İşlemleri" tablosu
("Logları İncele" ile ayrıntı penceresi). Bölüm kapalıyken veri yüklenmez; açık/kapalı durumu hatırlanır."""

from __future__ import annotations

from datetime import datetime, time

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.services import settings_store
from src.desktop.services.backup import disk_registry, disk_watch, history
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.grid_delegates import apply_calendar_style
from src.desktop.ui.widgets.backup_charts import DonutChart, LineChart, TimelineBarChart

PRESET_ID = "dbgrid_backup_son_islemler"
_COLS = ["TARİH", "İŞ", "TÜR", "DURUM", "BOYUT", "SÜRE", "NOT", "İNCELE"]
_TUR = {"full": "Tam", "inc": "Artımlı", "mirror": "Senkron"}
_DURUM = {"ok": ("✔ Başarılı", "#15803d"), "warning": ("⚠ Uyarı", "#b45309"), "error": ("✘ HATA", "#b91c1c"), "nochange": ("⏭ Değişiklik yok", "#64748b")}
_KART = "QFrame#Kart { background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; }"


def resolve_job_dest(db, job) -> str | None:
    """İşin hedef klasörü (harici disk yer tutucuları takılı diske çevrilir); disk takılı değilse None."""
    roots = disk_registry.roots(disk_registry.DiskStore(db).list(), disk_watch.list_volumes())
    return disk_watch.resolve_dest(job.dest_dir, None, roots)


class _Kart(QFrame):
    def __init__(self, baslik: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Kart")
        self.setStyleSheet(_KART)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 6)
        v.setSpacing(1)
        t = QLabel(baslik)
        t.setStyleSheet("font-size:10px; font-weight:700; color:#64748b; letter-spacing:0.5px;")
        self.lbl_deger = QLabel("—")
        self.lbl_deger.setStyleSheet("font-size:15px; font-weight:800; color:#0f172a;")
        self.lbl_alt = QLabel("")
        self.lbl_alt.setStyleSheet("font-size:10px; color:#64748b;")
        for w in (t, self.lbl_deger, self.lbl_alt):
            v.addWidget(w)

    def set(self, deger: str, alt: str = "", renk: str = "#0f172a") -> None:
        self.lbl_deger.setText(deger)
        self.lbl_deger.setStyleSheet(f"font-size:15px; font-weight:800; color:{renk};")
        self.lbl_alt.setText(alt)


class RunDetailDialog(QDialog):
    """Bir yedek çalışmasının ayrıntıları (tür, süre, boyut, hedef sonuçları, tam mesaj)."""

    def __init__(self, run: history.Run, parent=None) -> None:
        super().__init__(parent)
        self.run = run
        self.setWindowTitle(f"Yedek Ayrıntısı — {run.job}")
        self.setMinimumSize(560, 420)
        apply_light_dialog_style(self)
        durum, renk = _DURUM.get(run.status, (run.status, "#334155"))
        yukleme = "".join(f"<li>{'✔' if u[1] else '✘'} <b>{u[0]}</b>: {u[2]}</li>" for u in run.uploads if len(u) >= 3)
        html = (f"<h3 style='color:{renk}'>{durum}</h3>"
                f"<table cellpadding='3'>"
                f"<tr><td><b>İş</b></td><td>{run.job}</td></tr><tr><td><b>Tür</b></td><td>{_TUR.get(run.mode, run.mode)}</td></tr>"
                f"<tr><td><b>Başlangıç</b></td><td>{run.start:%d.%m.%Y %H:%M:%S}</td></tr><tr><td><b>Bitiş</b></td><td>{run.end:%d.%m.%Y %H:%M:%S}</td></tr>"
                f"<tr><td><b>Süre</b></td><td>{history.format_duration(run.seconds)}</td></tr>"
                f"<tr><td><b>Boyut</b></td><td>{history.format_size(run.bytes)} ({run.files} dosya)</td></tr>"
                f"<tr><td><b>Yedek dosyası</b></td><td>{run.file or '—'}</td></tr><tr><td><b>Hedef klasör</b></td><td>{run.dest or '—'}</td></tr></table>"
                + (f"<p><b>Dış hedefler</b></p><ul>{yukleme}</ul>" if yukleme else "")
                + (f"<p><b>Atlanan dosya:</b> {run.warnings}</p>" if run.warnings else "")
                + f"<p><b>Mesaj</b></p><p>{run.message}</p>")
        lyt = QVBoxLayout(self)
        self.txt = QTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setHtml(html)
        lyt.addWidget(self.txt, 1)
        row = QHBoxLayout()
        b_kopya = QPushButton("📋 Kopyala")
        b_kopya.clicked.connect(lambda: QApplication.clipboard().setText(self.txt.toPlainText()))
        b_kapat = QPushButton("Kapat")
        b_kapat.clicked.connect(self.accept)
        row.addWidget(b_kopya)
        row.addStretch()
        row.addWidget(b_kapat)
        lyt.addLayout(row)


class DiskFilesDialog(QDialog):
    """Halka grafikte tıklanan dilime en çok yer kaplayan yedek dosyaları."""

    def __init__(self, baslik: str, dosyalar: list[tuple[str, int]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(baslik)
        self.setMinimumSize(520, 360)
        apply_light_dialog_style(self)
        if "dbgrid_backup_disk_dosya" not in GRID_PRESETS:
            register_preset("dbgrid_backup_disk_dosya", ["YEDEK DOSYASI", "BOYUT"], [0.75, 0.25], ["L", "R"], name="Yedek Dosyaları")
        lyt = QVBoxLayout(self)
        lyt.addWidget(QLabel(f"{len(dosyalar)} dosya · toplam {history.format_size(sum(s for _n, s in dosyalar))}"))
        self.grid = AppGrid("dbgrid_backup_disk_dosya")
        for ad, boyut in sorted(dosyalar, key=lambda x: -x[1]):
            r = self.grid.rowCount()
            self.grid.insertRow(r)
            self.grid.setRowHeight(r, self.grid.effective_row_height)
            for c, t in enumerate((ad, history.format_size(boyut))):
                it = QTableWidgetItem(t)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setTextAlignment((Qt.AlignmentFlag.AlignRight if c else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
                self.grid.setItem(r, c, it)
        lyt.addWidget(self.grid, 1)
        b = QPushButton("Kapat")
        b.clicked.connect(self.accept)
        lyt.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)


class BackupDashboard(QFrame):
    def __init__(self, db, jobs_provider, parent=None, varsayilan_acik: bool = False, kompakt: bool = False) -> None:
        super().__init__(parent)
        self.kompakt = kompakt          # merkezin altında: yalnız kartlar + işlem tablosu; grafikler '⛶ Tam ekran' penceresinde
        self.db = db
        self.jobs_provider = jobs_provider
        self._runs: list[history.Run] = []
        self._disk: history.DiskInfo | None = None
        self.setObjectName("BackupDashboard")
        self.setStyleSheet("#BackupDashboard { background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; }")
        if PRESET_ID not in GRID_PRESETS:
            register_preset(PRESET_ID, _COLS, [0.17, 0.12, 0.07, 0.12, 0.09, 0.09, 0.14, 0.20], ["C", "L", "C", "L", "R", "R", "L", "C"],
                            name="Son Yedekleme İşlemleri")
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)
        self.btn_toggle = QPushButton()
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("QPushButton { background:#1e3a8a; color:white; border:none; border-radius:4px; padding:5px 12px;"
                                      " font-size:11px; font-weight:700; text-align:left; } QPushButton:hover { background:#2563eb; }")
        self.btn_toggle.clicked.connect(self.toggle)
        v.addWidget(self.btn_toggle)

        self.body = QWidget()
        b = QVBoxLayout(self.body)
        b.setContentsMargins(0, 0, 0, 0)
        b.setSpacing(6)
        # filtreler
        f = QHBoxLayout()
        combo_style = """
            QComboBox {
                combobox-popup: 0;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 3px 6px;
                background-color: white;
                color: #0f172a;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                outline: 0;
                padding: 0px;
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                color: #0f172a;
            }
            QComboBox QAbstractItemView::item {
                padding: 3px 6px;
                min-height: 20px;
            }
        """
        self.cmb_job = QComboBox()
        self.cmb_job.setStyleSheet(combo_style)
        self.cmb_range = QComboBox()
        self.cmb_range.setStyleSheet(combo_style)
        for k, ad in history.RANGES.items():
            self.cmb_range.addItem(ad, k)
        self.cmb_range.setCurrentIndex(2)                                         # son 30 gün
        self.dt_bas = QDateEdit(QDate.currentDate().addDays(-30))
        self.dt_bit = QDateEdit(QDate.currentDate())
        for d in (self.dt_bas, self.dt_bit):
            apply_calendar_style(d)
            d.setDisplayFormat("dd.MM.yyyy")
            d.hide()
        self.btn_yenile = QPushButton("🔄 Yenile")
        self.btn_tam = QPushButton("⛶ Tam ekran")
        self.btn_tam.setToolTip("Grafiklerle birlikte tam ekran pano penceresini açar")
        self.btn_tam.clicked.connect(self.tam_ekran)
        self.btn_tam.setVisible(kompakt)
        for w in (QLabel("İş:"), self.cmb_job, QLabel("Aralık:"), self.cmb_range, self.dt_bas, self.dt_bit):
            f.addWidget(w)
        f.addStretch()
        f.addWidget(self.btn_tam)
        f.addWidget(self.btn_yenile)
        b.addLayout(f)
        # özet kartları
        k = QHBoxLayout()
        self.k_son, self.k_inc, self.k_alan, self.k_donem = _Kart("SON YEDEK DURUMU"), _Kart("SON ARTIMLI BOYUT"), _Kart("HEDEFTE KALAN ALAN"), _Kart("DÖNEM SONUCU")
        for c in (self.k_son, self.k_inc, self.k_alan, self.k_donem):
            k.addWidget(c)
        b.addLayout(k)
        # grafikler
        self.chart_bar, self.chart_donut, self.chart_line = TimelineBarChart(), DonutChart(), LineChart()
        self.grafikler = QWidget()                                                 # kompakt kipte gizlenir
        g1 = QHBoxLayout(self.grafikler)
        g1.setContentsMargins(0, 0, 0, 0)
        g1.addWidget(self.chart_bar, 3)
        g1.addWidget(self.chart_donut, 1)
        g1.addWidget(self.chart_line, 3)
        self.grafikler.setMinimumHeight(260)
        self.grafikler.setVisible(not kompakt)
        b.addWidget(self.grafikler)
        self.table = AppGrid(PRESET_ID)
        self.table.setMinimumHeight(150 if kompakt else 190)
        if kompakt:
            self.table.setMaximumHeight(230)
        if db is not None:
            self.table.enable_layout_persistence(db)
        b.addWidget(self.table, 1)
        v.addWidget(self.body)

        self.cmb_job.currentIndexChanged.connect(self.yenile)
        self.cmb_range.currentIndexChanged.connect(self._aralik_degisti)
        self.dt_bas.dateChanged.connect(lambda _d: self.yenile())
        self.dt_bit.dateChanged.connect(lambda _d: self.yenile())
        self.btn_yenile.clicked.connect(self.yenile)
        self.chart_bar.run_clicked.connect(self.ayrinti_ac)
        self.chart_line.run_clicked.connect(self.ayrinti_ac)
        self.chart_donut.slice_clicked.connect(self.dilim_ac)

        acik = settings_store.get_bool(db, "panel.backup_dashboard.acik", varsayilan_acik) if db is not None else varsayilan_acik
        self._uygula(acik)
        self._isleri_doldur()

    def tam_ekran(self) -> None:
        """Grafikli tam pano penceresi (büyütülüp küçültülebilir, kapatılınca merkeze dönülür)."""
        dlg = BackupDashboardDialog(self.db, self.jobs_provider, self)
        dlg.exec()

    # ---- açık / kapalı -----------------------------------------------------------------
    @property
    def acik(self) -> bool:
        return not self.body.isHidden()

    def toggle(self) -> None:
        self._uygula(not self.acik)
        if self.db is not None:
            try:
                settings_store.set_setting(self.db, "panel.backup_dashboard.acik", "1" if self.acik else "0")
            except Exception:  # noqa: BLE001
                pass
        if self.acik:
            self.yenile()

    def _uygula(self, acik: bool) -> None:
        self.body.setVisible(acik)
        self.btn_toggle.setText(("▼ " if acik else "▲ ") + "📊 Yedekleme Panosu")

    # ---- filtreler ---------------------------------------------------------------------
    def _isleri_doldur(self) -> None:
        secili = self.cmb_job.currentData()
        self.cmb_job.blockSignals(True)
        self.cmb_job.clear()
        self.cmb_job.addItem("Tüm işler", None)
        for j in self.jobs_provider():
            self.cmb_job.addItem(j.name, j.name)
        i = self.cmb_job.findData(secili)
        self.cmb_job.setCurrentIndex(max(i, 0))
        self.cmb_job.blockSignals(False)

    def _aralik_degisti(self) -> None:
        ozel = self.cmb_range.currentData() == "custom"
        self.dt_bas.setVisible(ozel)
        self.dt_bit.setVisible(ozel)
        self.yenile()

    def _sinirlar(self) -> tuple[datetime, datetime]:
        if self.cmb_range.currentData() == "custom":
            bas = datetime.combine(self.dt_bas.date().toPyDate(), time.min)
            bit = datetime.combine(self.dt_bit.date().toPyDate(), time.max)
            return bas, bit
        return history.range_bounds(self.cmb_range.currentData())

    # ---- veri ----------------------------------------------------------------------------
    def yenile(self) -> None:
        if self.cmb_job.count() <= 1:
            self._isleri_doldur()
        if not self.acik or self.db is None:
            return
        bas, bit = self._sinirlar()
        job = self.cmb_job.currentData()
        self._runs = history.load(self.db, bas, bit, job)
        self.chart_bar.set_runs(self._runs)
        self.chart_line.set_runs(self._runs)
        self._tabloyu_doldur()
        self._kartlari_doldur()

    def _hedef_is(self):
        isler = self.jobs_provider()
        ad = self.cmb_job.currentData()
        if ad:
            return next((j for j in isler if j.name == ad), None)
        son = self._runs[-1].job if self._runs else None                      # tüm işler: en son çalışan işin hedefi
        return next((j for j in isler if j.name == son), isler[0] if isler else None)

    def _kartlari_doldur(self) -> None:
        k = history.kpis(self._runs)
        if k.total:
            self.k_son.set(("✅ " if k.last_status_ok else "❌ ") + k.last_status, k.last_time, "#15803d" if k.last_status_ok else "#b91c1c")
        else:
            self.k_son.set("—", "Bu aralıkta çalışma yok")
        self.k_inc.set(history.format_size(k.last_inc_bytes) if k.last_inc_bytes is not None else "—", "son artımlı yedek")
        self.k_donem.set(f"{k.ok} başarılı / {k.failed} hata", f"{k.total} çalışma", "#b91c1c" if k.failed else "#0f172a")
        is_ = self._hedef_is()
        yol = resolve_job_dest(self.db, is_) if is_ else None
        self._disk = history.disk_info(yol, is_.slug) if (is_ and yol) else None
        d = self._disk
        if d:
            yuzde = d.free * 100 / d.total if d.total else 0
            self.k_alan.set(f"{history.format_size(d.free)} / {history.format_size(d.total)}", f"%{yuzde:.0f} boş · {d.path}",
                            "#b91c1c" if yuzde < 10 else "#0f172a")
            self.chart_donut.set_slices(d.slices, f"%{100 - yuzde:.0f}\ndolu")
        else:
            self.k_alan.set("—", "Hedef disk takılı değil / bulunamadı" if is_ else "")
            self.chart_donut.set_slices([], "")

    def _tabloyu_doldur(self) -> None:
        t = self.table
        t.setRowCount(0)
        for r in reversed(self._runs[-50:]):                                     # en yeni üstte
            i = t.rowCount()
            t.insertRow(i)
            t.setRowHeight(i, max(t.effective_row_height, 28))
            durum, renk = _DURUM.get(r.status, (r.status, "#334155"))
            for c, txt in enumerate((r.end.strftime("%d.%m.%Y %H:%M"), r.job, _TUR.get(r.mode, r.mode), durum, history.format_size(r.bytes),
                                     history.format_duration(r.seconds), r.message[:90])):
                it = QTableWidgetItem(txt)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setTextAlignment({4: Qt.AlignmentFlag.AlignRight, 5: Qt.AlignmentFlag.AlignRight}.get(c, Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
                if c == 3:
                    from PyQt6.QtGui import QBrush, QColor
                    it.setForeground(QBrush(QColor(renk)))
                it.setToolTip(r.message)
                t.setItem(i, c, it)
            b = QPushButton("Logları İncele")
            b.setStyleSheet("QPushButton { padding:2px 8px; font-size:10px; }")
            b.clicked.connect(lambda _=False, run=r: self.ayrinti_ac(run))
            t.setCellWidget(i, 7, b)

    # ---- ayrıntılar ----------------------------------------------------------------------
    def ayrinti_ac(self, run: history.Run) -> None:
        RunDetailDialog(run, self).exec()

    def dilim_ac(self, anahtar: str) -> None:
        d = self._disk
        if not d or anahtar not in ("last", "old"):
            return
        dosyalar = d.files_last if anahtar == "last" else d.files_old
        DiskFilesDialog("Son yedek" if anahtar == "last" else "Eski yedekler", dosyalar, self).exec()


class BackupDashboardDialog(QDialog):
    """Tam ekran açılan yedekleme panosu: grafikler + tablo. Pencere kapatılınca yalnız pencere kapanır."""

    def __init__(self, db, jobs_provider, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📊 Yedekleme Panosu")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        apply_light_dialog_style(self)
        lyt = QVBoxLayout(self)
        self.pano = BackupDashboard(db, jobs_provider, self, varsayilan_acik=True, kompakt=False)
        self.pano.btn_toggle.hide()
        self.pano._uygula(True)
        lyt.addWidget(self.pano, 1)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("✖ Kapat")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lyt.addLayout(row)
        self.pano.yenile()
        self.setWindowState(Qt.WindowState.WindowMaximized)
