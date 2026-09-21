"""
TOYA ERP - GitReportDialog

Git durumunu GRAFİKSEL ve işlem ayrıntısıyla gösteren rapor penceresi. İki kullanım:
  • Durum raporu  : "Rapor" işlemi → dal, uzak depo, gönderilmemiş/gelen commit, değişiklik türleri, klasör dağılımı,
                    son 14 günün commit grafiği, tablolar.
  • İşlem raporu  : bir Git işlemi (Fetch, Pull, Push…) bitince → işlemin sonucu, öncesi/sonrası karşılaştırması
                    (ör. Fetch ile kaç yeni commit geldi) ve işlem günlüğü; altında güncel durum raporu.
Pencere veriyi hazır `snapshot` sözlüğünden alır (bkz. GitService.snapshot); kendisi git çalıştırmaz.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.widgets.git_charts import PALETTE, BarChart, HBarChart, StackBar

TYPE_LABELS = {"modified": ("Değişti", PALETTE["amber"]), "untracked": ("Yeni (izlenmeyen)", PALETTE["primary"]),
               "added": ("Eklendi", PALETTE["green"]), "deleted": ("Silindi", PALETTE["red"]), "renamed": ("Yeniden adlandı", PALETTE["violet"])}
_STATUS_COLOR = {"success": "#15803d", "info": "#1d4ed8", "warning": "#b45309", "danger": "#b91c1c"}


def _preset(pid: str, cols: list[str], ratios: list[float], align: list[str]) -> None:
    if pid not in GRID_PRESETS:
        register_preset(pid, cols, ratios, align)


def _grid(pid: str, rows: list[list[Any]], height: int = 170) -> AppGrid:
    g = AppGrid(pid)
    g.setData(rows)
    g.setMinimumHeight(height)
    g.setMaximumHeight(height)
    return g


class GitReportDialog(QDialog):
    def __init__(self, snapshot: dict[str, Any], operation: dict[str, Any] | None = None, parent=None,
                 on_save_md: Callable[[], None] | None = None, on_refresh: Callable[[], dict[str, Any]] | None = None) -> None:
        super().__init__(parent)
        self.snapshot = snapshot
        self.operation = operation
        self._on_save_md = on_save_md
        self._on_refresh = on_refresh
        self.setWindowTitle("📊 Git İşlem Raporu" if operation else "📊 Git Durum Raporu")
        self.resize(940, 760)
        apply_light_dialog_style(self)
        _preset("dbgrid_git_rapor_commit", ["COMMIT", "TARİH", "YAZAR", "MESAJ"], [0.12, 0.14, 0.2, 0.54], ["C", "C", "L", "L"])
        _preset("dbgrid_git_rapor_dosya", ["DURUM", "KLASÖR", "DOSYA"], [0.16, 0.2, 0.64], ["C", "L", "L"])
        self._build()

    # ------------------------------------------------------------------ iskelet
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none; background:transparent;}")
        root.addWidget(self.scroll, 1)
        row = QHBoxLayout()
        self.btn_md = QPushButton("📄 .md Olarak Kaydet")
        self.btn_refresh = QPushButton("🔄 Yenile")
        self.btn_close = QPushButton("Kapat")
        self.btn_close.setDefault(True)
        self.btn_md.clicked.connect(self._save_md)
        self.btn_refresh.clicked.connect(self._refresh)
        self.btn_close.clicked.connect(self.accept)
        self.btn_md.setVisible(self._on_save_md is not None)
        self.btn_refresh.setVisible(self._on_refresh is not None)
        row.addWidget(self.btn_md)
        row.addWidget(self.btn_refresh)
        row.addStretch()
        row.addWidget(self.btn_close)
        root.addLayout(row)
        self._fill()

    def _save_md(self) -> None:
        if self._on_save_md:
            self._on_save_md()

    def _refresh(self) -> None:
        if self._on_refresh:
            self.snapshot = self._on_refresh()
            self.operation = None       # yenilenen görünüm yalnızca güncel durumdur
            self._fill()

    def _fill(self) -> None:
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(10)
        s = self.snapshot
        if not s.get("ok"):
            lbl = QLabel("❌ " + s.get("message", "Git durumu okunamadı."))
            lbl.setStyleSheet("font-size:14px; color:#b91c1c; font-weight:700;")
            lay.addWidget(lbl)
            lay.addStretch()
            self.scroll.setWidget(body)
            return
        lay.addWidget(self._header())
        if self.operation:
            lay.addWidget(self._operation_card())
        lay.addLayout(self._cards())
        charts = QHBoxLayout()
        charts.setSpacing(10)
        charts.addWidget(self._chart_types(), 1)
        charts.addWidget(self._chart_folders(), 1)
        lay.addLayout(charts)
        charts2 = QHBoxLayout()
        charts2.setSpacing(10)
        charts2.addWidget(self._chart_sync(), 1)
        charts2.addWidget(self._chart_days(), 2)
        lay.addLayout(charts2)
        for title, key, rows_fn in (
            ("⬆ Uzak depoya gönderilmemiş commit'ler", "outgoing", self._commit_rows),
            ("⬇ Uzakta olup henüz çekilmemiş commit'ler", "incoming", self._commit_rows),
            ("🕘 Son commit'ler", "history", self._commit_rows),
        ):
            data = s.get(key) or []
            sec = CollapsibleSection(f"{title} ({len(data)})", is_expanded=key != "history" and bool(data))
            sec.add_widget(_grid("dbgrid_git_rapor_commit", rows_fn(data)) if data else self._muted("Kayıt yok."))
            lay.addWidget(sec)
        files = s.get("files") or []
        sec = CollapsibleSection(f"🟡 Değişen dosyalar ({len(files)})", is_expanded=bool(files))
        sec.add_widget(_grid("dbgrid_git_rapor_dosya", self._file_rows(files[:300]), 220) if files else self._muted("Değişiklik yok."))
        lay.addWidget(sec)
        if s.get("sensitive"):
            warn = QLabel("⚠ Hassas görünen dosyalar değişiklikler arasında: " + ", ".join(s["sensitive"][:6]) + ". Gizli bilgi içeriyorsa .gitignore'a ekleyin.")
            warn.setWordWrap(True)
            warn.setStyleSheet("background:#fef2f2; border:1px solid #fca5a5; border-radius:6px; padding:8px; color:#991b1b;")
            lay.addWidget(warn)
        lay.addStretch()
        self.scroll.setWidget(body)

    # ------------------------------------------------------------------ parçalar
    @staticmethod
    def _muted(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#94a3b8; padding:6px;")
        return lbl

    @staticmethod
    def _commit_rows(data: list[dict[str, str]]) -> list[list[Any]]:
        return [[c["hash"][:7], c["date"][:10], c["author"], c["message"]] for c in data]

    @staticmethod
    def _file_rows(files: list[dict[str, Any]]) -> list[list[Any]]:
        return [[TYPE_LABELS.get(f["type"], (f["type"], ""))[0], f["category"], f["file"]] for f in files]

    def _header(self) -> QWidget:
        s = self.snapshot
        adv = s.get("advice")
        f = QFrame()
        f.setStyleSheet("QFrame{background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px;} QLabel{border:none; background:transparent;}")
        lay = QVBoxLayout(f)
        title = QLabel("Git Durumu" + (f" — {adv.title}" if adv else ""))
        color = _STATUS_COLOR.get(adv.status if adv else "info", "#1d4ed8")
        title.setStyleSheet(f"font-size:15px; font-weight:800; color:{color};")
        taken = s.get("taken") or datetime.now()
        sub = QLabel(f"🌿 {s['branch']}   •   🌐 {s['remote'] or '(uzak depo yok)'}   •   👤 {s.get('user') or '-'}   •   🕒 {taken:%d.%m.%Y %H:%M:%S}")
        sub.setStyleSheet("color:#475569; font-size:11px;")
        sub.setWordWrap(True)
        lay.addWidget(title)
        lay.addWidget(sub)
        if adv:
            hint = QLabel(adv.advice)
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#334155;")
            lay.addWidget(hint)
        return f

    def _operation_card(self) -> QWidget:
        op = self.operation or {}
        ok = op.get("ok", True)
        bg, border, fg = ("#f0fdf4", "#86efac", "#166534") if ok else ("#fef2f2", "#fca5a5", "#991b1b")
        f = QFrame()
        f.setObjectName("OpCard")
        f.setStyleSheet(f"QFrame#OpCard{{background:{bg}; border:1px solid {border}; border-radius:8px;}} QLabel{{border:none; background:transparent;}}")
        lay = QVBoxLayout(f)
        head = QLabel(f"{'✅' if ok else '❌'} {op.get('title', 'İşlem')} — {'Başarılı' if ok else 'Başarısız'}"
                      + (f"   ({op['seconds']:.1f} sn)" if op.get("seconds") is not None else ""))
        head.setStyleSheet(f"font-size:14px; font-weight:800; color:{fg};")
        lay.addWidget(head)
        msg = QLabel(op.get("message", ""))
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#334155;")
        lay.addWidget(msg)

        b, a = op.get("before") or {}, op.get("after") or {}
        if b.get("ok") and a.get("ok"):
            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            for c, h in enumerate(("", "Öncesi", "Sonrası", "Fark")):
                lbl = QLabel(h)
                lbl.setStyleSheet("font-weight:700; color:#475569;")
                grid.addWidget(lbl, 0, c)
            for r, (name, key) in enumerate((("⬆ Gönderilmemiş commit", "ahead"), ("⬇ Uzakta çekilmemiş commit", "behind"),
                                               ("🟡 Değişen dosya", "changed")), start=1):
                d = a[key] - b[key]
                arrow = "—" if d == 0 else (f"▲ +{d}" if d > 0 else f"▼ {d}")
                col = "#64748b" if d == 0 else ("#b45309" if key != "behind" or d > 0 else "#15803d")
                for c, txt in enumerate((name, str(b[key]), str(a[key]), arrow)):
                    lbl = QLabel(txt)
                    if c == 3:
                        lbl.setStyleSheet(f"color:{col}; font-weight:700;")
                    grid.addWidget(lbl, r, c)
            if b.get("head") != a.get("head"):
                lbl = QLabel(f"HEAD: {b.get('head') or '-'} → {a.get('head') or '-'}")
                lbl.setStyleSheet("color:#334155;")
                grid.addWidget(lbl, 4, 0, 1, 4)
            lay.addLayout(grid)
        if op.get("action") == "fetch":
            ft = self.snapshot.get("fetch_time")
            n = self.snapshot.get("behind", 0)
            line = QLabel(f"📡 Fetch durumu: son fetch {ft:%d.%m.%Y %H:%M:%S}" if ft else "📡 Fetch durumu: henüz fetch yapılmamış")
            line.setStyleSheet("font-weight:700; color:#1e3a8a;")
            lay.addWidget(line)
            lay.addWidget(QLabel(f"Uzak depoda çekilmeyi bekleyen {n} commit var." if n else "Uzak depoda yeni commit yok; yerel depo güncel."))
        if op.get("log"):
            sec = CollapsibleSection("🖥 İşlem günlüğü", is_expanded=False)
            box = QPlainTextEdit(op["log"])
            box.setReadOnly(True)
            box.setMaximumHeight(140)
            box.setStyleSheet("background:#0f172a; color:#38bdf8; font-family:Consolas,monospace; font-size:11px;")
            sec.add_widget(box)
            lay.addWidget(sec)
        return f

    def _cards(self) -> QGridLayout:
        s = self.snapshot
        ft = s.get("fetch_time")
        items = [
            ("⬆ Gönderilmemiş", str(s["ahead"]) if s["tracking"] else "?", PALETTE["amber"] if s["ahead"] else PALETTE["green"]),
            ("⬇ Çekilmemiş", str(s["behind"]) if s["tracking"] else "?", PALETTE["red"] if s["behind"] else PALETTE["green"]),
            ("🟡 Değişen dosya", str(s["summary"]["total"]), PALETTE["amber"] if s["summary"]["total"] else PALETTE["green"]),
            ("📡 Son fetch", ft.strftime("%d.%m %H:%M") if ft else "yok", PALETTE["slate"]),
            ("🕘 Son commit", (s["last_commit"]["hash"][:7] if s.get("last_commit") else "-"), PALETTE["primary"]),
        ]
        g = QGridLayout()
        g.setSpacing(8)
        for i, (label, value, color) in enumerate(items):
            f = QFrame()
            f.setStyleSheet("QFrame{background:#ffffff; border:1px solid #cbd5e1; border-radius:8px;} QLabel{border:none; background:transparent;}")
            v = QVBoxLayout(f)
            v.setContentsMargins(10, 6, 10, 6)
            lv = QLabel(value)
            lv.setStyleSheet(f"font-size:20px; font-weight:800; color:{color};")
            ll = QLabel(label)
            ll.setStyleSheet("font-size:10px; color:#64748b;")
            v.addWidget(lv)
            v.addWidget(ll)
            g.addWidget(f, 0, i)
        return g

    def _chart_types(self) -> QWidget:
        c = StackBar("Değişiklik türleri")
        c.set_segments([(TYPE_LABELS[k][0], self.snapshot["summary"].get(k, 0), TYPE_LABELS[k][1]) for k in TYPE_LABELS])
        c.setMinimumHeight(130)
        return c

    def _chart_folders(self) -> QWidget:
        c = HBarChart("Klasöre göre değişen dosya")
        c.set_data([(name, n, PALETTE["primary"]) for name, n in self.snapshot["categories"][:6]])
        return c

    def _chart_sync(self) -> QWidget:
        s = self.snapshot
        c = HBarChart("Uzak depo ile fark")
        c.empty_text = "✔ Yerel ve uzak depo aynı (fark yok)" if s["tracking"] else "Uzak dal bilinmiyor — önce Fetch yapın"
        c.set_data([("Gönderilmemiş (⬆)", s["ahead"] if s["tracking"] else 0, PALETTE["amber"]),
                    ("Çekilmemiş (⬇)", s["behind"] if s["tracking"] else 0, PALETTE["red"])])
        return c

    def _chart_days(self) -> QWidget:
        c = BarChart("Son 14 günde commit")
        c.set_data([(d[8:10] + "." + d[5:7], n) for d, n in self.snapshot["per_day"]])
        return c
