"""
TOYA ERP - CurrencyRateReportWidget

Döviz & Kur panelinde "📊 Kur Raporları" bölümünün içeriği: seçilen döviz ve
tarih aralığı için `CurrencyRateHistory` kayıtlarını (M.B./S.P. alış-satış)
tablo halinde listeler; aralık için en düşük/en yüksek/ortalama satış kurunu
özetler.

Kullanım:
    w = CurrencyRateReportWidget(db_session=db)
    w.refresh()  # döviz kodu listesini DB'den yükler ve son 30 günü gösterir
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Currency
from src.desktop.services import currency_rate_service as svc

logger = logging.getLogger(__name__)


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    s = f"{v:,.4f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


class CurrencyRateReportWidget(QWidget):
    """Belirli bir döviz kodu ve tarih aralığı için M.B./S.P. kur geçmişini
    tablo + özet (min/maks/ortalama) olarak gösteren salt-okunur rapor."""

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        filt_row = QHBoxLayout()
        self.cmb_kod = QComboBox()
        self.cmb_kod.setStyleSheet("""
            QComboBox {
                combobox-popup: 0;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 6px;
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
        """)
        self.cmb_kod.currentIndexChanged.connect(self._reload_table)
        filt_row.addWidget(QLabel("Döviz:"))
        filt_row.addWidget(self.cmb_kod)

        self.dt_bas = QDateEdit(QDate.currentDate().addDays(-30))
        self.dt_bas.setCalendarPopup(True)
        self.dt_bas.setDisplayFormat("dd.MM.yyyy")
        self.dt_bit = QDateEdit(QDate.currentDate())
        self.dt_bit.setCalendarPopup(True)
        self.dt_bit.setDisplayFormat("dd.MM.yyyy")
        filt_row.addWidget(QLabel("—"))
        filt_row.addWidget(self.dt_bas)
        filt_row.addWidget(QLabel("—"))
        filt_row.addWidget(self.dt_bit)

        btn_yenile = QPushButton("🔄")
        btn_yenile.setToolTip("Raporu yenile")
        btn_yenile.setFixedWidth(30)
        btn_yenile.clicked.connect(self._reload_table)
        filt_row.addWidget(btn_yenile)
        filt_row.addStretch()
        root.addLayout(filt_row)

        self.lbl_ozet = QLabel("—")
        self.lbl_ozet.setStyleSheet("font-size:10px; font-weight:700; color:#334155;")
        root.addWidget(self.lbl_ozet)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Tarih", "M.B. Alış", "M.B. Satış", "S.P. Alış", "S.P. Satış"],
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setFixedHeight(220)
        root.addWidget(self.table)

        self.lbl_empty = QLabel("Seçili aralıkta kayıtlı kur geçmişi bulunmuyor.")
        self.lbl_empty.setStyleSheet("color:#94a3b8; font-size:10px; font-style:italic;")
        self.lbl_empty.setVisible(False)
        root.addWidget(self.lbl_empty)

        self.dt_bas.dateChanged.connect(self._reload_table)
        self.dt_bit.dateChanged.connect(self._reload_table)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Döviz kodu listesini DB'den yeniden yükler ve tabloyu tazeler.
        (Panel her aktifleştiğinde çağrılır ki yeni eklenen dövizler combo'da görünsün.)"""
        self.cmb_kod.blockSignals(True)
        secili = self.cmb_kod.currentData()
        self.cmb_kod.clear()
        kodlar: list[str] = []
        if self.db:
            try:
                kodlar = list(self.db.scalars(
                    select(Currency.code).where(
                        Currency.is_deleted == False,  # noqa: E712
                        Currency.code != "TRY",
                    ).distinct().order_by(Currency.code),
                ).all())
            except Exception:  # noqa: BLE001
                logger.exception("Döviz kodu listesi yüklenemedi")
        for kod in kodlar:
            self.cmb_kod.addItem(kod, kod)
        if secili:
            idx = self.cmb_kod.findData(secili)
            if idx >= 0:
                self.cmb_kod.setCurrentIndex(idx)
        self.cmb_kod.blockSignals(False)
        self._reload_table()

    def _reload_table(self) -> None:
        self.table.setRowCount(0)
        kod = self.cmb_kod.currentData()
        if not (self.db and kod):
            self.lbl_ozet.setText("—")
            self.lbl_empty.setVisible(True)
            return

        d1 = self.dt_bas.date().toPyDate()
        d2 = self.dt_bit.date().toPyDate()
        try:
            rows = svc.get_rate_history_range(self.db, d1, d2, code=kod)
        except Exception:  # noqa: BLE001
            logger.exception("Kur geçmişi yüklenemedi")
            rows = []

        self.lbl_empty.setVisible(not rows)
        satislar: list[float] = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            cells = [
                row.rate_date.strftime("%d.%m.%Y"),
                _fmt(row.mb_alis), _fmt(row.mb_satis),
                _fmt(row.sp_alis), _fmt(row.sp_satis),
            ]
            for c_idx, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c_idx > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c_idx, item)
            satis = row.mb_satis if row.mb_satis is not None else row.sp_satis
            if satis is not None:
                satislar.append(satis)

        if satislar:
            self.lbl_ozet.setText(
                f"{kod} — Min: {_fmt(min(satislar))}  Maks: {_fmt(max(satislar))}  "
                f"Ort: {_fmt(sum(satislar) / len(satislar))}  ({len(rows)} gün)",
            )
        else:
            self.lbl_ozet.setText("—")
