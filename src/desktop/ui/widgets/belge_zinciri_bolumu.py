"""TOYA ERP - "BELGE ZİNCİRİ" sol panel bölümü: sipariş → irsaliye → fatura, iade, hareket işleme, e-Devlet işareti, rezerv.

Sipariş / İrsaliye / Fatura liste ekranlarının sol paneline eklenir; düğmeler seçili belgenin durumuna göre açılır/kapanır. İş kuralı ve hesap
`BelgeHareketService`'tedir; bu bileşen yalnızca seçimi okur, gerekirse `KalemMiktarDialog`/`RezervDialog` ile girdi toplar ve sonucu bildirir.

Liste ekranından beklenenler (`owner`): `db`, `quotation_type` (`Order` | `Waybill` | `Invoice`), `get_selected_id()`, `get_checked_ids()`,
`refresh_table()`, `table_view` (seçim değişince düğmeleri günceller)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QPushButton, QWidget
from sqlalchemy import select

from src.core import belge_turleri
from src.core.models import Quotation, WarehouseDefinition
from src.desktop.services.belge_hareket_service import BelgeHareketError, BelgeHareketService, YetersizStokError
from src.desktop.services.belge_kilit_servisi import BelgeKilitServisi, KilitHatasi
from src.desktop.services.quotation_save_service import QuotationSaveService
from src.desktop.ui.components import dialog_style
from src.desktop.ui.components.button_style import DANGER_BG, DANGER_FG, btn_style
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.widgets.belge_zinciri_dialogs import KalemMiktarDialog, RezervDialog, TahsilatDialog


class TekBelgeSahibi(QWidget):
    """Liste ekranı olmayan yerde (belge detay ekranı) `BelgeZinciriBolumu`'nun beklediği "sahip" arayüzü: tek bir belgeyi temsil eder."""

    toast_requested = pyqtSignal(str, str)

    def __init__(self, db, belge_id: int, yenile_cb, parent=None) -> None:
        super().__init__(parent)
        self.db, self._belge_id, self._yenile_cb = db, belge_id, yenile_cb
        q = db.get(Quotation, belge_id)
        self.quotation_type = q.quotation_type if q is not None else ""
        self.hide()

    def get_selected_id(self) -> int | None:
        return self._belge_id

    def get_checked_ids(self) -> list[int]:
        return []

    def refresh_table(self) -> None:
        self._yenile_cb()


class BelgeZinciriBolumu(CollapsibleSection):
    def __init__(self, owner, parent=None) -> None:
        super().__init__("BELGE ZİNCİRİ", is_expanded=True)
        self.owner = owner
        self.tur = owner.quotation_type
        self.btn: dict[str, QPushButton] = {}
        tanim = {
            "Quotation": [("siparis", "🔄 Siparişe Dönüştür", btn_style(), self.tekliften_siparis)],
            "Order": [("irsaliye", "🚚 İrsaliye Oluştur…", btn_style(), self.siparisten_irsaliye),
                      ("rezerv", "🔒 Stok Rezervi…", btn_style(), self.rezerv),
                      ("bag", "🔗 Kaynak Bağını Kopar…", btn_style(), self.bag_kopar)],
            "Waybill": [("fatura", "🧾 Faturaya Dönüştür…", btn_style(), self.irsaliyeden_fatura),
                        ("iade", "↩ İade Oluştur…", btn_style(), self.iade),
                        ("isle", "⚙️ Hareketleri İşle", btn_style(), self.isle),
                        ("geri", "↶ İşlemi Geri Al", btn_style(DANGER_BG, DANGER_FG), self.geri_al),
                        ("bag", "🔗 Kaynak Bağını Kopar…", btn_style(), self.bag_kopar)],
            "Invoice": [("tahsilat", "💰 Tahsilat / Ödeme…", btn_style(), self.tahsilat),
                        ("iade", "↩ İade Oluştur…", btn_style(), self.iade),
                        ("isle", "⚙️ Hareketleri İşle", btn_style(), self.isle),
                        ("geri", "↶ İşlemi Geri Al", btn_style(DANGER_BG, DANGER_FG), self.geri_al),
                        ("resmi", "📨 e-Devlete Gönderildi", btn_style(), self.resmi_isaretle),
                        ("resmi_kaldir", "⏏ Gönderildi İşaretini Kaldır", btn_style(), self.resmi_kaldir),
                        ("bag", "🔗 Kaynak Bağını Kopar…", btn_style(), self.bag_kopar)],
        }.get(self.tur, [])
        for anahtar, metin, stil, fn in tanim:
            b = QPushButton(metin)
            b.setStyleSheet(stil)
            b.clicked.connect(fn)
            self.add_widget(b)
            self.btn[anahtar] = b
        secim = getattr(getattr(owner, "table_view", None), "selectionModel", None)
        if secim is not None:
            secim().selectionChanged.connect(lambda *_a: self.guncelle())
        self.guncelle()

    # ---- yardımcılar ----------------------------------------------------------------------
    def _svc(self) -> BelgeHareketService:
        return BelgeHareketService(self.owner.db)

    def _secili(self) -> Quotation | None:
        bid = self.owner.get_selected_id()
        return self.owner.db.get(Quotation, bid) if bid else None

    def _isaretli_ya_da_secili(self) -> list[int]:
        ids = list(self.owner.get_checked_ids())
        if not ids:
            bid = self.owner.get_selected_id()
            ids = [bid] if bid else []
        return ids

    def _bildir(self, mesaj: str, tip: str = "success") -> None:
        if hasattr(self.owner, "toast_requested"):
            self.owner.toast_requested.emit(mesaj, tip)
        elif hasattr(self.owner, "status_message"):
            self.owner.status_message.emit(mesaj)

    def _yenile(self, belge_id: int | None) -> None:
        """Listeyi yeniler ve işlem yapılan belgeyi yeniden seçer (düğmeler seçime bağlıdır; yenileme seçimi temizler)."""
        self.owner.refresh_table()
        if not hasattr(self.owner, "table_model"):
            self.guncelle()
            return
        model = self.owner.table_model
        for r in range(model.rowCount()):
            it = model.item(r, 1)
            if belge_id and it is not None and it.text() == str(belge_id):
                self.owner.table_view.selectRow(r)
                break
        self.guncelle()

    def _hata(self, e: Exception) -> None:
        dialog_style.uyari(self.owner.window(), "Belge Zinciri", str(e))

    def _uyarilari_goster(self, svc: BelgeHareketService) -> None:
        if svc.uyarilar:
            dialog_style.uyari(self.owner.window(), "Uyarı", "\n".join(svc.uyarilar))

    def _depo_hazirla(self, q: Quotation) -> bool:
        """Stok etkili satırı olup deposu belirsiz belgede depo belirler: tek depo varsa kendiliğinden, birden çoksa sorarak. Vazgeçilirse False."""
        if q.belge_turu not in belge_turleri.STOK_ETKILI or q.depo_id is not None:
            return True
        if not any(l.depo_id is None and l.product_id and l.stok_etkisi == "kendi" for l in q.lines):
            return True
        db = self.owner.db
        depolar = list(db.scalars(select(WarehouseDefinition).where(WarehouseDefinition.is_active == True,  # noqa: E712
                                                                    WarehouseDefinition.is_deleted == False).order_by(WarehouseDefinition.code)))  # noqa: E712
        if not depolar:
            dialog_style.uyari(self.owner.window(), "Depo", "Tanımlı depo yok. Genel Ayarlar › Stok Tanımları › Depolar bölümünden depo ekleyin.")
            return False
        if len(depolar) == 1:
            secilen = depolar[0]
        else:
            etiketler = [f"{d.code} — {d.name}" for d in depolar]
            i = dialog_style.sec(self.owner.window(), "Depo Seçimi", "Hareketin işleneceği depo:", etiketler)
            if i is None:
                return False
            secilen = depolar[i]
        q.depo_id = secilen.id
        db.commit()
        return True

    def guncelle(self) -> None:
        """Seçili belgenin durumuna göre düğmeleri açar/kapatır."""
        q = self._secili()
        var = q is not None
        turu = q.belge_turu if var else None
        islendi = var and q.hareket_durumu == "islendi"
        for ad, b in self.btn.items():
            if ad == "siparis":
                b.setEnabled(var and turu == "teklif")
            elif ad == "irsaliye":
                b.setEnabled(var and turu == "siparis")
            elif ad == "rezerv":
                b.setEnabled(var and turu == "siparis")
            elif ad == "fatura":
                b.setEnabled(var and turu == "irsaliye")
            elif ad == "tahsilat":
                b.setEnabled(bool(islendi and turu == "fatura"))
            elif ad == "iade":
                b.setEnabled(var and turu in ("fatura", "irsaliye"))
            elif ad == "isle":
                b.setEnabled(var and turu in ("irsaliye", "fatura", "iade_fatura") and q.hareket_durumu == "islenmedi")
            elif ad == "geri":
                b.setEnabled(bool(islendi and not q.resmi_gonderildi))
            elif ad == "resmi":
                b.setEnabled(bool(islendi and not q.resmi_gonderildi))
            elif ad == "bag":
                b.setEnabled(bool(var and BelgeKilitServisi(self.owner.db).ustler(q)))
            elif ad == "resmi_kaldir":
                b.setEnabled(bool(var and q.resmi_gonderildi))

    # ---- eylemler -------------------------------------------------------------------------
    def tekliften_siparis(self) -> None:
        q = self._secili()
        if q is None:
            return
        r = QuotationSaveService(db_session=self.owner.db, company_id=q.company_id or 1).convert_to_order(q.id)
        if not r.success:
            self._hata(ValueError(r.error or "Siparişe dönüştürülemedi."))
            return
        self._bildir(f"Sipariş oluşturuldu: {r.quotation_number}")
        self._yenile(q.id)

    def siparisten_irsaliye(self) -> None:
        q = self._secili()
        if q is None:
            return
        svc = self._svc()
        try:
            adaylar = svc.sevk_edilebilir(q.id)
            if not adaylar:
                dialog_style.bilgi(self.owner.window(), "İrsaliye", "Bu siparişte sevk edilecek miktar kalmadı.")
                return
            satirlar = [{"id": a["satir"].id, "belge": q.quotation_number, "sira": a["satir"].line_order, "urun": a["satir"].name or a["satir"].sku,
                         "birim": a["satir"].unit, "kalan": a["kalan"]} for a in adaylar]
            dlg = KalemMiktarDialog("Siparişten İrsaliye", "Sevk edilecek miktarları girin (varsayılan: kalan). Kısmi sevk yapılabilir; sipariş satırı "
                                    "sevk edildikçe rezerv (varsa) düşer.", satirlar, self.owner)
            if not dlg.exec():
                return
            irs = svc.siparisden_irsaliye(q.id, miktarlar=dlg.sonuc())
        except BelgeHareketError as e:
            self._hata(e)
            return
        self._bildir(f"İrsaliye oluşturuldu: {irs.quotation_number}")
        self._yenile(q.id if q is not None else None)

    def irsaliyeden_fatura(self) -> None:
        ids = self._isaretli_ya_da_secili()
        if not ids:
            return
        svc = self._svc()
        try:
            satirlar = []
            for bid in ids:
                irs = svc._belge_getir(bid)
                for a in svc.faturalanabilir(bid):
                    satirlar.append({"id": a["satir"].id, "belge": irs.quotation_number, "sira": a["satir"].line_order,
                                     "urun": a["satir"].name or a["satir"].sku, "birim": a["satir"].unit, "kalan": a["kalan"]})
            if not satirlar:
                dialog_style.bilgi(self.owner.window(), "Fatura", "Seçilen irsaliyelerde faturalanacak miktar kalmadı.")
                return
            dlg = KalemMiktarDialog("İrsaliyeden Fatura", "Birden çok irsaliye seçtiyseniz (kutucuklarla) hepsi TEK faturada birleşir; "
                                    "irsaliyeler aynı cariye ve aynı yöne (satış/alış) ait olmalıdır. Kısmi faturalama için miktarı azaltın.",
                                    satirlar, self.owner)
            if not dlg.exec():
                return
            fatura = svc.irsaliyeden_fatura(ids, miktarlar=dlg.sonuc())
        except BelgeHareketError as e:
            self._hata(e)
            return
        self._uyarilari_goster(svc)
        self._bildir(f"Fatura oluşturuldu: {fatura.quotation_number}")
        self._yenile(ids[0])

    def iade(self) -> None:
        q = self._secili()
        if q is None:
            return
        svc = self._svc()
        try:
            satirlar = [{"id": s.id, "belge": q.quotation_number, "sira": s.line_order, "urun": s.name or s.sku, "birim": s.unit, "kalan": s.quantity or 0.0}
                        for s in sorted(q.lines, key=lambda x: x.line_order or 0) if (s.quantity or 0) > 1e-9]
            if not satirlar:
                dialog_style.bilgi(self.owner.window(), "İade", "Belgede iade edilecek kalem yok.")
                return
            dlg = KalemMiktarDialog("İade", "İade edilecek miktarları girin (varsayılan: tamamı). Oluşan iade belgesi taslaktır; "
                                    "'Hareketleri İşle' ile stok/cari etkisi ters yönde işlenir.", satirlar, self.owner)
            if not dlg.exec():
                return
            iade = svc.iade(q.id, satirlar=dlg.sonuc())
        except BelgeHareketError as e:
            self._hata(e)
            return
        self._bildir(f"İade belgesi oluşturuldu: {iade.quotation_number}")
        self._yenile(q.id if q is not None else None)

    def isle(self) -> None:
        q = self._secili()
        if q is None:
            return
        if not dialog_style.onay(self.owner.window(), "Hareketleri İşle",
                                 f"{q.quotation_number} için stok" + (" ve cari" if q.belge_turu in ("fatura", "iade_fatura") else "")
                                 + " hareketleri üretilecek. Devam edilsin mi?"):
            return
        self._isle_calistir(q)

    def _isle_calistir(self, q: Quotation) -> bool:
        """`isle()` düğmesinin onay sonrası ortak gövdesi: depo, yetersiz stok onayı, hareket üretimi, bildirim, yenileme.
        Otomatik işleme (belge kaydında "Kaydedince Hareketleri İşle" işaretliyse) de bunu çağırır."""
        if not self._depo_hazirla(q):
            return False
        svc = self._svc()
        try:
            try:
                svc.isle(q.id)
            except YetersizStokError as e:
                if not dialog_style.onay(self.owner.window(), "Yetersiz Stok",
                                         f"{e}\n\nStok negatife düşecek. Yine de bu belge için işlemeye devam edilsin mi?\n"
                                         "(Kalıcı ayar: Genel Ayarlar › Stok › Negatif stok politikası)"):
                    return False
                svc.isle(q.id, politika="uyari_devam")
        except BelgeHareketError as e:
            self._hata(e)
            return False
        self._uyarilari_goster(svc)
        self._bildir(f"{q.quotation_number} işlendi.")
        self._yenile(q.id)
        return True

    def otomatik_isle(self) -> bool:
        """Belge kaydında "Kaydedince Hareketleri İşle" işaretliyse çağrılır: onay sormadan `_isle_calistir` çalıştırır
        (işaret zaten kullanıcının onayıdır). Belge hareket üretmiyorsa (teklif/sipariş) ya da zaten işlenmişse hiçbir şey yapmaz."""
        q = self._secili()
        if q is None or q.hareket_durumu != "islenmedi" or (q.belge_turu not in belge_turleri.STOK_ETKILI and q.belge_turu not in belge_turleri.CARI_ETKILI):
            return False
        return self._isle_calistir(q)

    def geri_al(self) -> None:
        q = self._secili()
        if q is None:
            return
        if not dialog_style.onay(self.owner.window(), "İşlemi Geri Al",
                                 f"{q.quotation_number} belgesinin ürettiği hareketler ters kayıtlarla düzeltilecek (hiçbir kayıt silinmez). Devam?"):
            return
        svc = self._svc()
        try:
            svc.geri_al(q.id)
        except BelgeHareketError as e:
            self._hata(e)
            return
        self._uyarilari_goster(svc)
        self._bildir(f"{q.quotation_number} geri alındı.", "warning")
        self._yenile(q.id if q is not None else None)

    def resmi_isaretle(self) -> None:
        q = self._secili()
        if q is None:
            return
        if not dialog_style.onay(self.owner.window(), "e-Devlete Gönderildi",
                                 f"{q.quotation_number} e-Devlete gönderildi olarak işaretlenecek. İşaretlendikten sonra belge geri alınamaz; "
                                 "düzeltme iade faturasıyla yapılır. Devam?"):
            return
        try:
            self._svc().resmi_isaretle(q.id, True)
        except BelgeHareketError as e:
            self._hata(e)
            return
        self._bildir(f"{q.quotation_number}: e-Devlete gönderildi işaretlendi.")
        self._yenile(q.id if q is not None else None)

    def resmi_kaldir(self) -> None:
        q = self._secili()
        if q is None:
            return
        if not dialog_style.onay(self.owner.window(), "İşareti Kaldır", "e-Devlete gönderildi işareti kaldırılacak. Devam?"):
            return
        try:
            self._svc().resmi_isaretle(q.id, False)
        except BelgeHareketError as e:
            self._hata(e)
            return
        self._bildir(f"{q.quotation_number}: işaret kaldırıldı.", "warning")
        self._yenile(q.id if q is not None else None)

    def rezerv(self) -> None:
        q = self._secili()
        if q is None:
            return
        RezervDialog(self.owner.db, q.id, self.owner).exec()

    def tahsilat(self) -> None:
        q = self._secili()
        if q is None:
            return
        TahsilatDialog(self.owner.db, q.id, self.owner).exec()
        self._yenile(q.id)

    def bag_kopar(self) -> None:
        q = self._secili()
        if q is None:
            return
        ks = BelgeKilitServisi(self.owner.db)
        ustler = ks.ustler(q)
        if not ustler:
            dialog_style.bilgi(self.owner.window(), "Bağ", "Bu belgenin koparılacak bir kaynak bağı yok.")
            return
        if not dialog_style.onay(self.owner.window(), "Kaynak Bağını Kopar",
                                 f"{q.quotation_number} belgesinin şu kaynaklarla bağı koparılacak: {', '.join(u.quotation_number for u in ustler)}.\n\n"
                                 "Kaynak belgeler serbest kalır (yeniden faturalanabilir/dönüştürülebilir). İşlem günlüğe yazılır. Devam?"):
            return
        try:
            ks.bag_kopar(q.id)
        except KilitHatasi as e:
            self._hata(e)
            return
        self._bildir(f"{q.quotation_number}: kaynak bağı koparıldı.", "warning")
        self._yenile(q.id)
