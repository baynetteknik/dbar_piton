"""TOYA ERP - Belge zinciri (sipariş → irsaliye → fatura, iade, rezerv) diyalogları.

- `KalemMiktarDialog`: hedef belgeye (irsaliye / fatura / iade) alınacak satırları ve miktarlarını seçtirir. Varsayılan miktar KALAN miktardır;
  kısmi sevk / faturalama / iade için miktar düzenlenir, 0 olan satır alınmaz. Sonuç `{satir_id: miktar}`.
- `RezervDialog`: siparişin stok rezervlerini listeler; yeni (süreli / süresiz, müşteri dönüşü bekleyen) rezerv ekler, serbest bırakır,
  süresi dolanları kapatır; her ürün için kullanılabilir stoğu (eldeki − aktif rezerv) gösterir.

Hesap ve iş kuralı `BelgeHareketService`'tedir; buradaki kod yalnızca girdiyi toplar ve sonucu gösterir."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from sqlalchemy import select

from src.core.models import Customer, Product, QuotationLine, StokRezerv
from src.desktop.services import money_service
from src.desktop.services.belge_hareket_service import (
    BelgeHareketError,
    BelgeHareketService,
    kullanilabilir_stok,
)
from src.desktop.services.finans_fis_service import FinansFisService
from src.desktop.ui.components import dialog_style
from src.desktop.ui.components.button_style import (
    DANGER_BG,
    DANGER_FG,
    PRIMARY,
    btn_style,
)
from src.desktop.ui.components.entry_table_view import standart_grid
from src.desktop.ui.components.grid_delegates import MoneyDelegate

_COMBO_STYLE = """
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
"""
from src.desktop.ui.widgets.money_edit import MoneyEdit, bicimle, sayiya

_SALT_OKUNUR = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_ID_ROLE = Qt.ItemDataRole.UserRole


def _hucre(metin: str, sag: bool = False) -> QStandardItem:
    it = QStandardItem(metin)
    it.setFlags(_SALT_OKUNUR)
    if sag:
        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return it


class KalemMiktarDialog(QDialog):
    """`satirlar`: [{"id", "belge", "sira", "urun", "birim", "kalan"}]. `sonuc()` -> {satir_id: miktar}."""

    KOLONLAR = [("belge", "BELGE"), ("sira", "SIRA"), ("urun", "ÜRÜN / HİZMET"), ("birim", "BİRİM"), ("kalan", "KALAN"), ("miktar", "MİKTAR")]
    ONDALIK = 3

    def __init__(self, baslik: str, aciklama: str, satirlar: list[dict], parent=None) -> None:
        super().__init__(parent)
        dialog_style.apply_light_dialog_style(self)
        self.setWindowTitle(baslik)
        self.resize(820, 460)
        self.satirlar = satirlar
        lyt = QVBoxLayout(self)
        t = QLabel(baslik)
        t.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(t)
        a = QLabel(aciklama)
        a.setWordWrap(True)
        a.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(a)
        self.entry = standart_grid("dlg_belge_kalem_miktar", self.KOLONLAR)
        self.grid = self.entry.table_view
        self.grid.setItemDelegateForColumn(5, MoneyDelegate(self.ONDALIK, allow_empty=False, parent=self.grid))
        lyt.addWidget(self.entry, 1)
        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        lyt.addWidget(self.lbl_hata)
        alt = QHBoxLayout()
        self.btn_hepsi = QPushButton("Hepsini kalan yap")
        self.btn_sifir = QPushButton("Sıfırla")
        self.btn_hepsi.setStyleSheet(btn_style())
        self.btn_sifir.setStyleSheet(btn_style())
        self.btn_hepsi.clicked.connect(lambda: self._doldur(kalan=True))
        self.btn_sifir.clicked.connect(lambda: self._doldur(kalan=False))
        self.btn_tamam = QPushButton("✔ Oluştur")
        self.btn_tamam.setStyleSheet(btn_style(PRIMARY, "#ffffff"))
        self.btn_tamam.clicked.connect(self._onayla)
        self.btn_vazgec = QPushButton("Vazgeç")
        self.btn_vazgec.setStyleSheet(btn_style())
        self.btn_vazgec.clicked.connect(self.reject)
        for b in (self.btn_hepsi, self.btn_sifir):
            alt.addWidget(b)
        alt.addStretch()
        alt.addWidget(self.btn_vazgec)
        alt.addWidget(self.btn_tamam)
        lyt.addLayout(alt)
        for s in satirlar:
            r = self.grid.rowCount()
            self.grid.insertRow(r)
            hucreler = [_hucre(str(s.get("belge", ""))), _hucre(str(s.get("sira", "")), True), _hucre(str(s.get("urun", ""))),
                        _hucre(str(s.get("birim", "")), True), _hucre(bicimle(s["kalan"], self.ONDALIK), True), QStandardItem(bicimle(s["kalan"], self.ONDALIK))]
            hucreler[5].setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            hucreler[0].setData(s["id"], _ID_ROLE)
            for c, it in enumerate(hucreler):
                self.grid.setItem(r, c, it)

    def _doldur(self, kalan: bool) -> None:
        for r, s in enumerate(self.satirlar):
            self.grid.item(r, 5).setText(bicimle(s["kalan"] if kalan else 0, self.ONDALIK))

    def sonuc(self) -> dict[int, float]:
        out: dict[int, float] = {}
        for r, s in enumerate(self.satirlar):
            d = sayiya(self.grid.item(r, 5).text())
            m = float(d) if d is not None else 0.0
            if m > 1e-9:
                out[int(s["id"])] = m
        return out

    def hata(self) -> str:
        """Miktar kalanı aşıyorsa ya da hiçbir satır seçilmediyse mesaj, uygunsa ''."""
        sec = self.sonuc()
        if not sec:
            return "En az bir satırın miktarı sıfırdan büyük olmalıdır."
        for s in self.satirlar:
            if sec.get(int(s["id"]), 0.0) - s["kalan"] > 1e-6:
                return f"{s.get('belge', '')} satır {s.get('sira', '')}: miktar kalan {s['kalan']:g}'i aşamaz."
        return ""

    def _onayla(self) -> None:
        self.grid.commit_editor()
        h = self.hata()
        self.lbl_hata.setText(h)
        if not h:
            self.accept()


class RezervDialog(QDialog):
    """Bir siparişin stok rezervleri: listele, ekle (süreli/süresiz, müşteri dönüşü bekleyen), serbest bırak, süresi dolanları kapat."""

    KOLONLAR = [("urun", "ÜRÜN"), ("miktar", "REZERV"), ("bitis", "BİTİŞ"), ("donus", "MÜŞTERİ DÖNÜŞÜ"), ("durum", "DURUM"), ("kullanilabilir", "KULLANILABİLİR STOK")]
    DURUMLAR = {"aktif": "Aktif", "kullanildi": "Kullanıldı", "serbest": "Serbest", "suresi_doldu": "Süresi doldu"}

    def __init__(self, db, siparis_id: int, parent=None) -> None:
        super().__init__(parent)
        dialog_style.apply_light_dialog_style(self)
        self.db, self.siparis_id = db, siparis_id
        self.svc = BelgeHareketService(db)
        self.setWindowTitle("Stok Rezervi")
        self.resize(900, 560)
        lyt = QVBoxLayout(self)
        t = QLabel("🔒 Stok Rezervi")
        t.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(t)
        a = QLabel("Rezerv, siparişin kalemleri için stoku ayırır; kullanılabilir stok = eldeki − aktif rezervler. "
                   "Süresiz rezerv elle bırakılana ya da sevk edilene kadar tutulur.")
        a.setWordWrap(True)
        a.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(a)
        self.entry = standart_grid("dlg_stok_rezerv", self.KOLONLAR)
        self.grid = self.entry.table_view
        lyt.addWidget(self.entry, 1)
        # yeni rezerv formu
        form = QFormLayout()
        self.cmb_urun = QComboBox()
        self.cmb_urun.setStyleSheet(_COMBO_STYLE)
        for satir in db.scalars(select(QuotationLine).where(QuotationLine.quotation_id == siparis_id).order_by(QuotationLine.line_order)):
            if satir.product_id:
                self.cmb_urun.addItem(f"{satir.line_order or ''}. {satir.name or satir.sku}  (sipariş: {satir.quantity:g})", (satir.id, satir.product_id, satir.quantity))
        self.ed_miktar = MoneyEdit(decimals=3, allow_empty=False)
        self.chk_suresiz = QCheckBox("Süresiz")
        self.chk_suresiz.setChecked(True)
        self.dt_bitis = QDateEdit(QDate.currentDate().addDays(7))
        self.dt_bitis.setCalendarPopup(True)
        self.dt_bitis.setDisplayFormat("dd.MM.yyyy")
        self.dt_bitis.setEnabled(False)
        self.chk_suresiz.toggled.connect(lambda b: self.dt_bitis.setEnabled(not b))
        self.chk_donus = QCheckBox("Müşteri dönüşü bekleniyor (süre dolsa da otomatik kapatma)")
        bitis_satiri = QHBoxLayout()
        bitis_satiri.addWidget(self.chk_suresiz)
        bitis_satiri.addWidget(self.dt_bitis)
        bitis_satiri.addStretch()
        form.addRow("Ürün:", self.cmb_urun)
        form.addRow("Miktar:", self.ed_miktar)
        form.addRow("Bitiş:", bitis_satiri)
        form.addRow("", self.chk_donus)
        lyt.addLayout(form)
        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        lyt.addWidget(self.lbl_hata)
        alt = QHBoxLayout()
        self.btn_ekle = QPushButton("➕ Rezerv Ekle")
        self.btn_ekle.setStyleSheet(btn_style(PRIMARY, "#ffffff"))
        self.btn_birak = QPushButton("🔓 Seçili Rezervi Serbest Bırak")
        self.btn_birak.setStyleSheet(btn_style())
        self.btn_kapat_sure = QPushButton("⌛ Süresi Dolanları Kapat")
        self.btn_kapat_sure.setStyleSheet(btn_style())
        self.btn_kapat = QPushButton("Kapat")
        self.btn_kapat.setStyleSheet(btn_style())
        self.btn_ekle.clicked.connect(self.ekle)
        self.btn_birak.clicked.connect(self.birak)
        self.btn_kapat_sure.clicked.connect(self.suresi_dolanlari_kapat)
        self.btn_kapat.clicked.connect(self.accept)
        for b in (self.btn_ekle, self.btn_birak, self.btn_kapat_sure):
            alt.addWidget(b)
        alt.addStretch()
        alt.addWidget(self.btn_kapat)
        lyt.addLayout(alt)
        self.yenile()

    def yenile(self) -> None:
        self.grid.setRowCount(0)
        rezervler = list(self.db.scalars(select(StokRezerv).where(StokRezerv.siparis_id == self.siparis_id, StokRezerv.is_deleted == False)  # noqa: E712
                                         .order_by(StokRezerv.id)))
        for rz in rezervler:
            p = self.db.get(Product, rz.product_id)
            r = self.grid.rowCount()
            self.grid.insertRow(r)
            hucreler = [
                _hucre(f"{p.sku} — {p.name}" if p else str(rz.product_id)), _hucre(bicimle(rz.miktar, 3), True),
                _hucre(rz.bitis.strftime("%d.%m.%Y") if rz.bitis else "Süresiz"), _hucre("Bekleniyor" if rz.musteri_donus_bekle else "—"),
                _hucre(self.DURUMLAR.get(rz.durum, rz.durum)), _hucre(bicimle(kullanilabilir_stok(self.db, rz.product_id, rz.depo_id), 3), True),
            ]
            hucreler[0].setData(rz.id, _ID_ROLE)
            for c, it in enumerate(hucreler):
                self.grid.setItem(r, c, it)

    def _secili_rezerv(self) -> int | None:
        r = self.grid.currentRow()
        it = self.grid.item(r, 0) if r >= 0 else None
        return int(it.data(_ID_ROLE)) if it is not None and it.data(_ID_ROLE) is not None else None

    def ekle(self) -> None:
        d = self.cmb_urun.currentData()
        miktar = self.ed_miktar.value()
        if d is None:
            self.lbl_hata.setText("Siparişte ürüne bağlı kalem yok.")
            return
        satir_id, product_id, _sip = d
        bitis = None if self.chk_suresiz.isChecked() else date(self.dt_bitis.date().year(), self.dt_bitis.date().month(), self.dt_bitis.date().day())
        try:
            self.svc.rezerv_olustur(self.siparis_id, satir_id, product_id, miktar, bitis=bitis, musteri_donus_bekle=self.chk_donus.isChecked())
        except BelgeHareketError as e:
            self.lbl_hata.setText(str(e))
            return
        self.lbl_hata.setText("")
        self.yenile()

    def birak(self) -> None:
        rid = self._secili_rezerv()
        if rid is None:
            self.lbl_hata.setText("Önce listeden bir rezerv seçin.")
            return
        try:
            self.svc.rezerv_serbest_birak(rid)
        except BelgeHareketError as e:
            self.lbl_hata.setText(str(e))
            return
        self.lbl_hata.setText("")
        self.yenile()

    def suresi_dolanlari_kapat(self) -> None:
        n = self.svc.rezerv_suresi_dolanlari_kapat()
        self.lbl_hata.setText("")
        self.yenile()
        dialog_style.bilgi(self, "Rezerv", f"{n} rezervin süresi dolduğu için kapatıldı." if n else "Süresi dolan rezerv yok.")


class TahsilatDialog(QDialog):
    """Bir faturaya kasa/banka hesabıyla tahsilat (satış) ya da ödeme (alış) girer; mevcut tahsilatları listeler, kaldırır (gizler)."""

    KOLONLAR = [("tarih", "TARİH"), ("hesap", "HESAP"), ("tutar", "TUTAR"), ("aciklama", "AÇIKLAMA")]

    def __init__(self, db, belge_id: int, parent=None) -> None:
        super().__init__(parent)
        dialog_style.apply_light_dialog_style(self)
        self.db, self.belge_id = db, belge_id
        self.svc = BelgeHareketService(db)
        self.belge = self.svc._belge_getir(belge_id)
        self.alis = self.belge.yon == "alis"
        self.ad = "Ödeme" if self.alis else "Tahsilat"
        self.setWindowTitle(f"Fatura {self.ad}i")
        self.resize(760, 520)
        lyt = QVBoxLayout(self)
        t = QLabel(f"💰 {self.belge.quotation_number} — {self.ad}")
        t.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(t)
        self.lbl_ozet = QLabel("")
        self.lbl_ozet.setStyleSheet("color:#475569; font-size:12px; font-weight:600;")
        lyt.addWidget(self.lbl_ozet)
        self.entry = standart_grid("dlg_fatura_tahsilat", self.KOLONLAR)
        self.grid = self.entry.table_view
        lyt.addWidget(self.entry, 1)
        form = QFormLayout()
        self.cmb_hesap = QComboBox()
        self.cmb_hesap.setStyleSheet(_COMBO_STYLE)
        for h in FinansFisService(db).hesaplar("kasa") + FinansFisService(db).hesaplar("banka"):
            self.cmb_hesap.addItem(f"{h.kod} — {h.ad} ({h.para_birimi})", h.id)
        self.ed_tutar = MoneyEdit(decimals=2, allow_empty=False)
        self.dt_tarih = QDateEdit(QDate.currentDate())
        self.dt_tarih.setCalendarPopup(True)
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        form.addRow("Kasa / Banka:", self.cmb_hesap)
        form.addRow("Tutar:", self.ed_tutar)
        form.addRow("Tarih:", self.dt_tarih)
        self.yerel = money_service.yerel_para(db)
        self.dovizli = (self.belge.currency or self.yerel).upper() != self.yerel
        self.ed_kur = MoneyEdit(decimals=4, allow_empty=False)
        if self.dovizli:                                     # döviz cinsinden fatura: tahsilat kuru tarihe göre gelir, elle değiştirilebilir
            form.addRow(f"Kur ({self.belge.currency}/{self.yerel}):", self.ed_kur)
            self.dt_tarih.dateChanged.connect(lambda _d: self._kur_yenile())
            self._kur_yenile()
        lyt.addLayout(form)
        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        lyt.addWidget(self.lbl_hata)
        alt = QHBoxLayout()
        self.btn_ekle = QPushButton(f"➕ {self.ad} Ekle")
        self.btn_ekle.setStyleSheet(btn_style(PRIMARY, "#ffffff"))
        self.btn_kaldir = QPushButton("🗑 Seçiliyi Kaldır")
        self.btn_kaldir.setStyleSheet(btn_style(DANGER_BG, DANGER_FG))
        self.btn_kapat = QPushButton("Kapat")
        self.btn_kapat.setStyleSheet(btn_style())
        self.btn_ekle.clicked.connect(self.ekle)
        self.btn_kaldir.clicked.connect(self.kaldir)
        self.btn_kapat.clicked.connect(self.accept)
        alt.addWidget(self.btn_ekle)
        alt.addWidget(self.btn_kaldir)
        alt.addStretch()
        alt.addWidget(self.btn_kapat)
        lyt.addLayout(alt)
        self.yenile()

    def yenile(self) -> None:
        self.grid.setRowCount(0)
        for c in self.svc.tahsilatlar(self.belge_id):
            r = self.grid.rowCount()
            self.grid.insertRow(r)
            hucreler = [_hucre(c.tarih.strftime("%d.%m.%Y")), _hucre(c.hesap or ""), _hucre(bicimle(c.tutar, 2) + f" {c.para_birimi}", True), _hucre(c.aciklama or "")]
            hucreler[0].setData(c.id, _ID_ROLE)
            for k, it in enumerate(hucreler):
                self.grid.setItem(r, k, it)
        kalan = self.svc.kalan_tutar(self.belge_id)
        para = self.belge.currency or "TRY"
        self.lbl_ozet.setText(f"Fatura toplamı: {bicimle(self.belge.grand_total or 0.0, 2)} {para}   ·   {self.ad}: {bicimle(self.svc.odenen(self.belge_id), 2)}   ·   "
                              f"Kalan: {bicimle(kalan, 2)} {para}")
        self.ed_tutar.setValue(max(kalan, 0.0))

    def _tarih(self) -> date:
        d = self.dt_tarih.date()
        return date(d.year(), d.month(), d.day())

    def _kur_yenile(self) -> None:
        try:
            self.ed_kur.setValue(money_service.kur_bul(self.db, self.belge.currency, self._tarih()))
        except money_service.UnknownCurrencyError:
            self.lbl_hata.setText(f"{self.belge.currency} için kur tanımlı değil; kuru elle girin.")

    def ekle(self) -> None:
        tarih, kur = self._tarih(), (self.ed_kur.value() if self.dovizli else None)
        try:
            fark = self.svc.kur_farki_onizle(self.belge_id, self.ed_tutar.value(), tarih, kur) if self.dovizli else 0.0
            isle, fatura_kes = False, False
            if abs(fark) >= 0.005:
                pb = "TL" if self.yerel == "TRY" else self.yerel
                secim = dialog_style.secenek_sor(
                    self, "Kur Farkı",
                    f"Tahsilat kuru fatura (borç) kurundan farklı: {'+' if fark > 0 else '−'}{bicimle(abs(fark), 2)} {pb} kur farkı oluştu.\n\n"
                    "Bu fark nasıl işlensin?\n"
                    "· Sadece cari harekete işle: hızlı, gayri resmi bir kayıttır.\n"
                    "· Fatura kes: KDVK Md. 24 gereği gerçek, numaralı bir taslak fatura oluşturulur; siz düzenleyip resmileştirirsiniz.\n"
                    "· İşleme: yalnız döviz bakiyesi kapanır, fark cari yerel bakiyede açık kalır.",
                    ["Sadece Cari Harekete İşle", "Fatura Kes (Taslak)", "İşleme"],
                )
                isle = secim in (0, 1)
                fatura_kes = secim == 1
            self.svc.tahsilat_ekle(self.belge_id, self.ed_tutar.value(), self.cmb_hesap.currentData() or 0, tarih=tarih, kur=kur, kur_farki_isle=isle)
            if fatura_kes:
                kfler = self.svc.kur_farklari(self.belge_id)
                if kfler:
                    taslak = self.svc.kur_farki_faturasi_olustur(kfler[-1].id)
                    dialog_style.bilgi(self, "Kur Farkı Faturası",
                                       f"Taslak fatura oluşturuldu: {taslak.quotation_number}.\n\n"
                                       "Faturalar listesinden açıp KDV oranını/açıklamayı kontrol edip resmileştirebilirsiniz.")
        except BelgeHareketError as e:
            self.lbl_hata.setText(str(e))
            return
        self.lbl_hata.setText("")
        self.yenile()

    def kaldir(self) -> None:
        r = self.grid.currentRow()
        it = self.grid.item(r, 0) if r >= 0 else None
        if it is None or it.data(_ID_ROLE) is None:
            self.lbl_hata.setText("Önce listeden bir kayıt seçin.")
            return
        try:
            self.svc.tahsilat_kaldir(int(it.data(_ID_ROLE)))
        except BelgeHareketError as e:
            self.lbl_hata.setText(str(e))
            return
        self.lbl_hata.setText("")
        self.yenile()


class GenelTahsilatDialog(QDialog):
    """Cariye Genel Tahsilat: müşteri TEK bir tutarı (TL) öder, sistem bunu açık faturalara (hangi para biriminde
    olursa olsun) eski→yeni (FIFO) otomatik dağıtır — "müşteri sadece TL öder, USD/EUR borcu da kapansın"
    senaryosu (bkz. `gelistirme/06_fatura_irsaliye/belge_zinciri_tasarim.md` Faz B). Önce ÖNİZLEME gösterir
    (`tahsilat_dagit_onizle`, hiçbir kayıt yazmaz); kullanıcı "Onayla ve Uygula"ya basınca gerçek dağıtım yapılır."""

    def __init__(self, db, customer_id: int, parent=None) -> None:
        super().__init__(parent)
        dialog_style.apply_light_dialog_style(self)
        self.db, self.customer_id = db, customer_id
        self.svc = BelgeHareketService(db)
        cust = db.get(Customer, customer_id)
        self.setWindowTitle("Cariye Genel Tahsilat")
        self.resize(740, 500)
        lyt = QVBoxLayout(self)
        t = QLabel(f"💰 {cust.fullname if cust else ''} — Genel Tahsilat")
        t.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(t)
        info = QLabel(
            "Girdiğiniz tutar, açık faturalara EN ESKİ tarihliden başlayarak (FIFO) otomatik dağıtılır; her "
            "fatura kendi para biriminde, aşağıdaki tarihin kuruyla kapanır. Önce 'Dağılımı Göster'e basıp "
            "sonucu kontrol edin, ardından uygulayın.",
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(info)

        form = QFormLayout()
        self.cmb_hesap = QComboBox()
        self.cmb_hesap.setStyleSheet(_COMBO_STYLE)
        for h in FinansFisService(db).hesaplar("kasa") + FinansFisService(db).hesaplar("banka"):
            self.cmb_hesap.addItem(f"{h.kod} — {h.ad} ({h.para_birimi})", h.id)
        self.ed_tutar = MoneyEdit(decimals=2, allow_empty=False)
        self.dt_tarih = QDateEdit(QDate.currentDate())
        self.dt_tarih.setCalendarPopup(True)
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        self.cmb_kur_farki = QComboBox()
        self.cmb_kur_farki.setStyleSheet(_COMBO_STYLE)
        self.cmb_kur_farki.addItem("Sadece Cari Harekete İşle", "cari")
        self.cmb_kur_farki.addItem("Hepsi İçin Fatura Kes (Taslak)", "fatura")
        self.cmb_kur_farki.addItem("İşleme", "yok")
        form.addRow("Kasa / Banka:", self.cmb_hesap)
        form.addRow("Tutar (TL):", self.ed_tutar)
        form.addRow("Tarih:", self.dt_tarih)
        form.addRow("Bu dağıtımda kur farkı:", self.cmb_kur_farki)
        lyt.addLayout(form)

        self.entry = standart_grid("dlg_genel_tahsilat", [("fatura", "FATURA"), ("tutar", "TUTAR"), ("kur", "KUR")])
        self.grid = self.entry.table_view
        lyt.addWidget(self.entry, 1)

        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        lyt.addWidget(self.lbl_hata)

        alt = QHBoxLayout()
        self.btn_oner = QPushButton("🔍 Dağılımı Göster")
        self.btn_oner.setStyleSheet(btn_style())
        self.btn_uygula = QPushButton("✅ Onayla ve Uygula")
        self.btn_uygula.setStyleSheet(btn_style(PRIMARY, "#ffffff"))
        self.btn_uygula.setEnabled(False)
        self.btn_kapat = QPushButton("Vazgeç")
        self.btn_kapat.setStyleSheet(btn_style())
        self.btn_oner.clicked.connect(self._oner)
        self.btn_uygula.clicked.connect(self._uygula)
        self.btn_kapat.clicked.connect(self.reject)
        alt.addWidget(self.btn_oner)
        alt.addWidget(self.btn_uygula)
        alt.addStretch()
        alt.addWidget(self.btn_kapat)
        lyt.addLayout(alt)

        self._onizleme: list[dict] = []
        self.ed_tutar.editingFinished.connect(lambda: self.btn_uygula.setEnabled(False))

    def _tarih(self) -> date:
        d = self.dt_tarih.date()
        return date(d.year(), d.month(), d.day())

    def _oner(self) -> None:
        self.grid.setRowCount(0)
        self.btn_uygula.setEnabled(False)
        try:
            self._onizleme = self.svc.tahsilat_dagit_onizle(self.customer_id, self.ed_tutar.value(), tarih=self._tarih())
        except BelgeHareketError as e:
            self.lbl_hata.setText(str(e))
            return
        self.lbl_hata.setText("")
        for d in self._onizleme:
            r = self.grid.rowCount()
            self.grid.insertRow(r)
            hucreler = [_hucre(f"{d['belge'].quotation_number} ({d['belge'].currency or 'TRY'})"),
                       _hucre(f"{bicimle(d['tutar_doviz'], 2)} {d['belge'].currency or 'TRY'}", True),
                       _hucre(bicimle(d["kur"], 4), True)]
            for k, it in enumerate(hucreler):
                self.grid.setItem(r, k, it)
        self.btn_uygula.setEnabled(bool(self._onizleme))

    def _uygula(self) -> None:
        try:
            sonuc = self.svc.tahsilat_dagit(self.customer_id, self.ed_tutar.value(), self.cmb_hesap.currentData() or 0,
                                            tarih=self._tarih(), kur_farki_modu=self.cmb_kur_farki.currentData())
        except BelgeHareketError as e:
            self.lbl_hata.setText(str(e))
            return
        taslaklar = [d["kur_farki_taslak"].quotation_number for d in sonuc if d.get("kur_farki_taslak")]
        mesaj = f"{len(sonuc)} faturaya tahsilat dağıtıldı."
        if taslaklar:
            mesaj += "\n\nOluşan taslak kur farkı faturaları: " + ", ".join(taslaklar)
        dialog_style.bilgi(self, "Genel Tahsilat", mesaj)
        self.accept()
        self.yenile()
