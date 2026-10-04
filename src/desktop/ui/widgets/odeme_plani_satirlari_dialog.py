"""TOYA ERP - OdemePlaniSatirlariDialog: bir Ödeme Planı'nın ÇOK TÜRLÜ bölüştürme satırlarını düzenler
(2026-10-02, 04.11 — bkz. gelistirme/04_odeme_planlari/tasarim.md).

Kullanıcı isteği: "yarısı peşin yarısı taksitle ya da bir bölümü açık hesap bir bölümü banka havalesi ve
kalanı kredi kartı gibi" — tek bir Ödeme Planı'nın BİRDEN FAZLA ödeme türüne bölünebilmesi. Her satırın
kendi Ödeme Tipi + Tutar Formülü (bkz. `odeme_formul_motoru.py` — TOYA'ya özgü: TUTAR/ARATOPLAM/KDV/KALAN
değişkenleri, dört işlem, round/abs/min/max/sum fonksiyonları) + Gün (vade) + Hedef Hesap + (yalnız banka ile ilgili
tiplerde anlamlı) Banka Ödeme Planı vardır. Bir planın satırı YOKSA, o plan hâlâ eski (04.05-04.09)
"tek tip" davranışını kullanır — bu dialog YALNIZCA çok türlü bölüştürme isteyen planlar için."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy import select

from src.core.models import PaymentPlanLine
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.grid_delegates import ComboDelegate

_SUTUNLAR = ["Sıra", "Ödeme Tipi", "Tutar Formülü", "Gün", "Hedef Hesap", "Banka Ödeme Planı"]


class OdemePlaniSatirlariDialog(QDialog):
    def __init__(
        self, db, plan_id: int, plan_kod: str,
        odeme_tipi_secenekleri: list[str], hesap_secenekleri: list[str], banka_odeme_plani_secenekleri: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.db, self.plan_id = db, plan_id
        self.setWindowTitle(f"Ödeme Planı Satırları — {plan_kod}")
        self.resize(820, 420)
        apply_light_dialog_style(self)

        lyt = QVBoxLayout(self)
        ipucu = QLabel(
            "Her satır bu planın bir BÖLÜMÜ (farklı ödeme tipleri karışık kullanılabilir). "
            "<b>Tutar Formülü</b>: TUTAR (genel toplam), ARATOPLAM, KDV, KALAN (önceki satırlardan arta "
            "kalan) + dört işlem + round/abs/min/max/sum fonksiyonları. Boş bırakılırsa KALAN'a eşittir — "
            "SON satırı genelde boş bırakın (yuvarlama farkı kaybolmasın). Örnek: <code>TUTAR/2</code>, "
            "<code>round(TUTAR*0.3,2)</code>.",
        )
        ipucu.setWordWrap(True)
        ipucu.setStyleSheet("color:#475569;font-size:11px;background:#f8fafc;border:1px solid #e2e8f0;"
                             "border-radius:6px;padding:8px;")
        lyt.addWidget(ipucu)

        self.tbl = QTableWidget(0, len(_SUTUNLAR))
        self.tbl.setHorizontalHeaderLabels(_SUTUNLAR)
        self.tbl.horizontalHeaderItem(2).setToolTip(
            "TUTAR/ARATOPLAM/KDV/KALAN değişkenleri + dört işlem + round/abs/min/max/sum. "
            "Boş = KALAN. Örnek: TUTAR/2",
        )
        self.tbl.horizontalHeader().setStretchLastSection(True)
        for col, genislik in ((0, 45), (1, 110), (2, 120), (3, 45), (4, 160)):
            self.tbl.setColumnWidth(col, genislik)
        self.tbl.setItemDelegateForColumn(1, ComboDelegate(lambda: odeme_tipi_secenekleri, self.tbl))
        self.tbl.setItemDelegateForColumn(4, ComboDelegate(lambda: hesap_secenekleri, self.tbl))
        self.tbl.setItemDelegateForColumn(5, ComboDelegate(lambda: banka_odeme_plani_secenekleri, self.tbl))
        lyt.addWidget(self.tbl, 1)

        satir_bar = QHBoxLayout()
        b_ekle = QPushButton("➕ Satır Ekle")
        b_sil = QPushButton("🗑️ Satırı Sil")
        b_ekle.clicked.connect(lambda: self._satir_ekle())
        b_sil.clicked.connect(self._satir_sil)
        satir_bar.addWidget(b_ekle)
        satir_bar.addWidget(b_sil)
        satir_bar.addStretch()
        lyt.addLayout(satir_bar)

        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_kapat = QPushButton("💾 Kaydet"), QPushButton("✖ Kapat")
        b_kaydet.setDefault(True)
        b_kaydet.clicked.connect(self._kaydet)
        b_kapat.clicked.connect(self.reject)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_kapat)
        lyt.addLayout(bar)

        self._yukle()

    def _yukle(self) -> None:
        self.tbl.setRowCount(0)
        satirlar = self.db.scalars(
            select(PaymentPlanLine).where(
                PaymentPlanLine.payment_plan_id == self.plan_id, PaymentPlanLine.is_deleted == False,  # noqa: E712
            ).order_by(PaymentPlanLine.sira_no),
        ).all()
        for s in satirlar:
            hesap = f"{s.hedef_hesap.kod} — {s.hedef_hesap.ad}" if s.hedef_hesap else "(Seçilmedi)"
            banka_plani = f"{s.banka_odeme_plani.kod} — {s.banka_odeme_plani.aciklama or ''}".rstrip(" —") if s.banka_odeme_plani else "(Seçilmedi)"
            self._satir_ekle([str(s.sira_no), s.odeme_tipi or "", s.tutar_formulu or "", str(s.gun), hesap, banka_plani], satir_id=s.id)
        if self.tbl.rowCount() == 0:
            self._satir_ekle()

    def _satir_ekle(self, degerler: list[str] | None = None, satir_id: int | None = None) -> None:
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        varsayilan = degerler or [str(r + 1), "", "", "0", "(Seçilmedi)", "(Seçilmedi)"]
        for c, val in enumerate(varsayilan):
            it = QTableWidgetItem(val)
            if c == 0 and satir_id is not None:
                it.setData(1000, satir_id)   # Qt.ItemDataRole.UserRole; mevcut satırın id'sini taşır
            self.tbl.setItem(r, c, it)

    def _satir_sil(self) -> None:
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz satırı seçin.")
            return
        self.tbl.removeRow(row)

    def _kaydet(self) -> None:
        try:
            mevcut = {
                s.id: s
                for s in self.db.scalars(
                    select(PaymentPlanLine).where(
                        PaymentPlanLine.payment_plan_id == self.plan_id, PaymentPlanLine.is_deleted == False,  # noqa: E712
                    ),
                )
            }
            kalan_id: set[int] = set()
            for r in range(self.tbl.rowCount()):
                def _metin(col: int, _r=r) -> str:
                    it = self.tbl.item(_r, col)
                    return it.text().strip() if it else ""

                tip = _metin(1)
                if not tip:
                    continue   # ödeme tipi seçilmemiş satır yok sayılır
                sira_item = self.tbl.item(r, 0)
                satir_id = sira_item.data(1000) if sira_item else None
                try:
                    sira_no = int(_metin(0) or (r + 1))
                except ValueError:
                    sira_no = r + 1
                try:
                    gun = int(_metin(3) or 0)
                except ValueError:
                    gun = 0
                hesap_id = self._hesap_id_coz(_metin(4))
                banka_plani_id = self._banka_plani_id_coz(_metin(5))

                if satir_id and satir_id in mevcut:
                    s = mevcut[satir_id]
                    kalan_id.add(satir_id)
                else:
                    s = PaymentPlanLine(payment_plan_id=self.plan_id)
                    self.db.add(s)
                s.sira_no, s.odeme_tipi = sira_no, tip
                s.tutar_formulu = _metin(2) or None
                s.gun = gun
                s.hedef_finans_hesap_id = hesap_id
                s.banka_odeme_plani_id = banka_plani_id
            for sid, s in mevcut.items():
                if sid not in kalan_id:
                    s.is_deleted = True
            self.db.commit()
        except Exception as e:  # noqa: BLE001
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Satırlar kaydedilemedi: {e}")
            return
        self.accept()

    def _hesap_id_coz(self, metin: str) -> int | None:
        from src.core.models import FinansHesap
        kod = metin.split(" — ", 1)[0].strip() if " — " in metin else ""
        if not kod:
            return None
        h = self.db.scalar(select(FinansHesap).where(FinansHesap.kod == kod, FinansHesap.is_deleted == False))  # noqa: E712
        return h.id if h else None

    def _banka_plani_id_coz(self, metin: str) -> int | None:
        from src.core.models import BankaOdemePlani
        kod = metin.split(" — ", 1)[0].strip() if " — " in metin else ""
        if not kod:
            return None
        p = self.db.scalar(
            select(BankaOdemePlani).where(BankaOdemePlani.kod == kod, BankaOdemePlani.is_deleted == False),  # noqa: E712
        )
        return p.id if p else None
