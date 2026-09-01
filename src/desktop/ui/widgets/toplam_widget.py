"""
ToyaUI — ToplamWidget
Fiş detay ekranlarındaki TL + Döviz toplam bilgileri paneli.

Kullanım:
    widget = ToplamWidget()
    widget.update_totals(
        ara_toplam=1000.0,
        iskonto=50.0,
        masraflar=25.0,
        kdv_toplam=195.0,
        genel_toplam=1170.0,
        doviz_sembol="$",
        doviz_kur=38.5,
    )
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ToplamWidget(QFrame):
    """
    Fiş toplam bilgileri widget'ı.
    TL + Döviz karşılığı yan yana gösterir.

    Sinyaller:
        totals_updated(dict): Toplamlar güncellendiğinde
    """

    totals_updated = pyqtSignal(dict)

    ROW_H     = 22
    LBL_STYLE = "font-size:10px; font-weight:600; color:#334155;"
    VAL_STYLE = "font-size:11px; font-weight:700; color:#0f172a; padding-right:4px;"
    DOV_STYLE = "font-size:10px; color:#64748b; padding-right:4px;"

    # Toplam satırları tanımı
    ROWS = [
        ("ara_toplam",    "Ara Toplam:",    "#0f172a"),
        ("masraflar",     "Masraf:",        "#0284c7"),
        ("iskonto",       "İndirim:",       "#dc2626"),
        ("net_toplam",    "Toplam:",        "#0f172a"),
        ("ozel_vergi",    "Özel Vergi:",    "#7c3aed"),
        ("kdv_toplam",    "KDV:",           "#7c3aed"),
        ("kdv_tevkifat",  "KDV Tevkifat:", "#94a3b8"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doviz_sembol = "₺"
        self._doviz_kur    = 1.0
        self._values: dict[str, float] = {
            k: 0.0 for k, _, _ in self.ROWS
        }
        self._values["genel_toplam"] = 0.0

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ToplamWidget {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
        """)
        self.setMinimumWidth(220)

        self._init_ui()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(6, 4, 6, 4)
        main_lyt.setSpacing(2)

        # ── 1. EN ÜST BAŞLIK SATIRI (Kompakt / Küçük) ──
        hdr = QGridLayout()
        hdr.setContentsMargins(4, 0, 4, 1)
        hdr.setColumnStretch(0, 4)
        hdr.setColumnStretch(1, 3)
        hdr.setColumnStretch(2, 3)

        lbl_empty = QLabel("")
        lbl_tl    = QLabel("TL (₺)")
        self.lbl_dov_hdr = QLabel("Döviz")
        lbl_tl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_dov_hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for lbl in [lbl_tl, self.lbl_dov_hdr]:
            lbl.setStyleSheet(
                "font-size:8px; font-weight:700; color:#64748b; padding-right:4px;",
            )
            lbl.setFixedHeight(13)

        hdr.addWidget(lbl_empty,         0, 0)
        hdr.addWidget(lbl_tl,            0, 1)
        hdr.addWidget(self.lbl_dov_hdr,  0, 2)
        main_lyt.addLayout(hdr)

        # Ayırıcı
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0; margin:0;")
        main_lyt.addWidget(sep)

        # ── 2. ARA TOPLAM SATIRLARI (Daha Belirgin ve Okunaklı) ──
        self._grid = QGridLayout()
        self._grid.setContentsMargins(4, 2, 4, 2)
        self._grid.setSpacing(3)
        self._grid.setColumnStretch(0, 4)
        self._grid.setColumnStretch(1, 3)
        self._grid.setColumnStretch(2, 3)

        self._lbl_values: dict[str, tuple[QLabel, QLabel]] = {}

        for r, (key, baslik, renk) in enumerate(self.ROWS):
            lbl_b = QLabel(f"{baslik}")
            lbl_b.setStyleSheet(self.LBL_STYLE)

            lbl_tl = QLabel("0,00 ₺")
            lbl_tl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            lbl_tl.setStyleSheet(
                f"font-size:11px; font-weight:700; "
                f"color:{renk}; padding-right:4px;",
            )

            lbl_dov = QLabel("0,00 $")
            lbl_dov.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            lbl_dov.setStyleSheet(self.DOV_STYLE)

            self._grid.addWidget(lbl_b,   r, 0)
            self._grid.addWidget(lbl_tl,  r, 1)
            self._grid.addWidget(lbl_dov, r, 2)
            self._lbl_values[key] = (lbl_tl, lbl_dov)

        main_lyt.addLayout(self._grid)

        # Ayırıcı
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#e2e8f0; margin:0;")
        main_lyt.addWidget(sep2)

        # ── 3. GENEL TOPLAM KARTI (1/3 Oranında Kompaktlaştırılmış) ──
        gt_frame = QFrame()
        gt_frame.setFixedHeight(28)
        gt_frame.setStyleSheet("""
            QFrame {
                background: #1e3a8a;
                border-radius: 4px;
                border: none;
            }
        """)
        gt_lyt = QGridLayout(gt_frame)
        gt_lyt.setContentsMargins(6, 2, 6, 2)
        gt_lyt.setSpacing(2)
        gt_lyt.setColumnStretch(0, 4)
        gt_lyt.setColumnStretch(1, 3)
        gt_lyt.setColumnStretch(2, 3)

        lbl_gt_b = QLabel("G. TOPLAM:")
        lbl_gt_b.setStyleSheet(
            "font-size:10px; font-weight:800; color:#bfdbfe;",
        )

        self.lbl_grand_total = QLabel("0,00 ₺")
        self.lbl_grand_total.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.lbl_grand_total.setStyleSheet(
            "font-size:13px; font-weight:900; color:#ffffff; padding-right:4px;",
        )

        self.lbl_grand_total_doviz = QLabel("")
        self.lbl_grand_total_doviz.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.lbl_grand_total_doviz.setStyleSheet(
            "font-size:9px; color:#93c5fd; padding-right:4px;",
        )

        gt_lyt.addWidget(lbl_gt_b,                   0, 0)
        gt_lyt.addWidget(self.lbl_grand_total,       0, 1)
        gt_lyt.addWidget(self.lbl_grand_total_doviz, 0, 2)

        main_lyt.addWidget(gt_frame)

    # ─────────────────────────────────────────────
    # GÜNCELLEME
    # ─────────────────────────────────────────────

    def update_totals(
        self,
        ara_toplam:   float = 0.0,
        iskonto:      float = 0.0,
        masraflar:    float = 0.0,
        kdv_matrahi:  float = 0.0,
        kdv_toplam:   float = 0.0,
        kdv_tevkifat: float = 0.0,
        ozel_vergi:   float = 0.0,
        genel_toplam: float | None = None,
        doviz_sembol: str = "₺",
        doviz_kur:    float = 1.0,
    ):
        """Toplam değerlerini güncelle ve ekranda göster."""
        self._doviz_sembol = doviz_sembol
        self._doviz_kur    = doviz_kur

        # Net toplam hesapla
        net_toplam = ara_toplam - iskonto + masraflar

        # Genel toplam
        if genel_toplam is None:
            genel_toplam = net_toplam + ozel_vergi + kdv_toplam - kdv_tevkifat

        values = {
            "ara_toplam":   ara_toplam,
            "masraflar":    masraflar,
            "iskonto":      iskonto,
            "net_toplam":   net_toplam,
            "ozel_vergi":   ozel_vergi,
            "kdv_toplam":   kdv_toplam,
            "kdv_tevkifat": kdv_tevkifat,
            "genel_toplam": genel_toplam,
        }
        self._values = values

        # Satırları güncelle
        for key, (lbl_tl, lbl_dov) in self._lbl_values.items():
            val = values.get(key, 0.0)
            prefix = ""
            if key == "iskonto" and val > 0:
                prefix = "-"
            elif key in ("masraflar", "ozel_vergi", "kdv_toplam") and val > 0:
                prefix = "+"
            elif key == "kdv_tevkifat" and val > 0:
                prefix = "-"

            lbl_tl.setText(
                f"{prefix}{self._fmt(val)} ₺",
            )
            # Döviz karşılığı — TRY değilse göster
            if doviz_kur != 1.0 and doviz_sembol != "₺":
                dov_val = val / doviz_kur if doviz_kur else 0
                lbl_dov.setText(
                    f"{prefix}{self._fmt(dov_val)} {doviz_sembol}",
                )
            else:
                lbl_dov.setText("")

        # Genel toplam
        self.lbl_grand_total.setText(
            f"{self._fmt(genel_toplam)} ₺",
        )
        if doviz_kur != 1.0 and doviz_sembol != "₺":
            gt_dov = genel_toplam / doviz_kur if doviz_kur else 0
            self.lbl_grand_total_doviz.setText(
                f"{self._fmt(gt_dov)} {doviz_sembol}",
            )
        else:
            self.lbl_grand_total_doviz.setText("")

        # Header döviz başlığı
        if doviz_kur != 1.0 and doviz_sembol != "₺":
            self.lbl_dov_hdr.setText(f"Döviz ({doviz_sembol})")
        else:
            self.lbl_dov_hdr.setText("")

        self.totals_updated.emit(values)

    def set_doviz(self, sembol: str, kur: float):
        """Döviz sembolü ve kurunu güncelle, toplamları yeniden hesapla."""
        self._doviz_sembol = sembol
        self._doviz_kur    = kur
        # Mevcut değerlerle yeniden güncelle
        self.update_totals(
            ara_toplam   = self._values.get("ara_toplam", 0),
            iskonto      = self._values.get("iskonto", 0),
            masraflar    = self._values.get("masraflar", 0),
            kdv_toplam   = self._values.get("kdv_toplam", 0),
            kdv_tevkifat = self._values.get("kdv_tevkifat", 0),
            ozel_vergi   = self._values.get("ozel_vergi", 0),
            genel_toplam = self._values.get("genel_toplam", 0),
            doviz_sembol = sembol,
            doviz_kur    = kur,
        )

    @staticmethod
    def _fmt(value: float) -> str:
        """Sayıyı Türkçe para formatına çevirir."""
        try:
            return (
                f"{abs(value):,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
        except Exception:
            return "0,00"

    def get_grand_total(self) -> float:
        """Genel toplamı döndürür."""
        return self._values.get("genel_toplam", 0.0)

    def get_data(self) -> dict[str, float]:
        """Tüm toplam değerlerini döndürür."""
        return dict(self._values)

    def clear(self):
        """Tüm değerleri sıfırlar."""
        self.update_totals()


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = ToplamWidget()
    widget.update_totals(
        ara_toplam=26258.44,
        iskonto=487.50,
        masraflar=0,
        kdv_toplam=5154.19,
        kdv_tevkifat=0,
        ozel_vergi=0,
        doviz_sembol="$",
        doviz_kur=38.5,
    )

    win = QWidget()
    win.setWindowTitle("ToplamWidget Test")
    win.setMinimumWidth(320)
    lyt = QVBoxLayout(win)
    lyt.addWidget(widget)

    lyt.addStretch()

    win.show()
    sys.exit(app.exec())
