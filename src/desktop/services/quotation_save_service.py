"""ToyaUI — Teklif Kayıt Servisi.

transaction_document_dialog.py'deki ekran verilerini DB'ye kaydeder.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.core.models import Customer, Product, Quotation, QuotationLine

logger = logging.getLogger(__name__)


@dataclass
class SaveResult:
    """Kayıt işlemi sonucu."""

    success: bool
    quotation_id: int | None = None
    quotation_number: str | None = None
    error: str | None = None


class QuotationSaveService:
    """Teklif ve sipariş belgelerini DB'ye kaydeden, güncelleyen ve yükleyen servis."""

    def __init__(self, db_session=None, company_id: int = 1) -> None:
        self.db = db_session
        self.company_id = company_id

    def save_from_dialog(self, dialog: Any) -> SaveResult:
        """Dialog'daki widget verilerini okuyup veritabanına kaydeder."""
        if not self.db:
            return SaveResult(success=False, error="Veritabanı bağlantısı yok.")
        try:
            with self.db.no_autoflush:
                doc_id = getattr(dialog, "doc_id", None)
                if doc_id:
                    q = self.db.get(Quotation, doc_id)
                    if not q:
                        return SaveResult(
                            success=False,
                            error=f"Teklif bulunamadı: ID={doc_id}",
                        )
                else:
                    q = Quotation()
                    q.company_id = self.company_id
                    q.is_deleted = False
                    self.db.add(q)

                self._set_belge(q, dialog)
                self._set_cari(q, dialog)
                self._set_finans(q, dialog)

                if not q.quotation_number:
                    q.quotation_number = self._generate_number(q.id)

                q.notes = getattr(dialog, "doc_note1", "") or ""
                if getattr(dialog, "doc_note2", ""):
                    q.notes += "\n" + dialog.doc_note2

            self.db.flush()
            self._save_lines(q, dialog)
            self._set_toplamlar(q, dialog)

            self.db.commit()
            logger.info(
                f"Teklif başarıyla kaydedildi: {q.quotation_number} (ID={q.id})",
            )
            return SaveResult(
                success=True,
                quotation_id=q.id,
                quotation_number=q.quotation_number,
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Kayıt hatası: {e}", exc_info=True)
            return SaveResult(success=False, error=str(e))

    def _set_belge(self, q: Quotation, dialog: Any) -> None:
        """Belge numarası, fiş türü, tarih, vade ve ödeme planını ayarlar."""
        if hasattr(dialog, "txt_top_doc_no"):
            doc_no = dialog.txt_top_doc_no.text().strip()
            if doc_no:
                q.quotation_number = doc_no
            elif not q.quotation_number:
                q.quotation_number = self._generate_number(q.id)
        if hasattr(dialog, "cmb_doc_type"):
            raw_type = dialog.cmb_doc_type.currentText().upper()
            if "TEKLİF" in raw_type or "QUOTATION" in raw_type or "TEK" in raw_type:
                q.quotation_type = "Quotation"
            elif "SİPARİŞ" in raw_type or "ORDER" in raw_type or "SIP" in raw_type:
                q.quotation_type = "Order"
            elif "İRSALİYE" in raw_type or "WAYBILL" in raw_type or "IRS" in raw_type:
                q.quotation_type = "Waybill"
            elif "FATURA" in raw_type or "INVOICE" in raw_type or "FTR" in raw_type:
                q.quotation_type = "Invoice"
            else:
                q.quotation_type = dialog.cmb_doc_type.currentText()
        if not q.quotation_type:
            q.quotation_type = "Quotation"

        if hasattr(dialog, "date_belge"):
            d = dialog.date_belge.date()
            dt = datetime(d.year(), d.month(), d.day())
            q.date = dt
            q.issue_date = dt
        if hasattr(dialog, "date_vade"):
            v = dialog.date_vade.date()
            q.valid_until = datetime(v.year(), v.month(), v.day())
        if hasattr(dialog, "cmb_odeme_plani"):
            q.payment_plan = dialog.cmb_odeme_plani.currentText()
        if not q.status:
            q.status = "draft"

    # Backward compatibility alias
    _set_belge_bilgileri = _set_belge

    def _set_cari(self, q: Quotation, dialog: Any) -> None:
        """Cari müşteri ve serbest ünvan bilgilerini ayarlar."""
        if not self.db:
            return
        cari_kodu = ""
        if hasattr(dialog, "txt_cari_kodu"):
            cari_kodu = dialog.txt_cari_kodu.text().strip()
        if cari_kodu:
            try:
                c = self.db.scalar(
                    select(Customer).where(
                        Customer.customer_code == cari_kodu,
                        Customer.is_deleted == False,  # noqa: E712
                    ),
                )
                if c:
                    q.customer_id = c.id
            except Exception as e:
                logger.warning(f"Cari bulunamadı ({cari_kodu}): {e}")

        # Serbest ad ve Başlık
        if hasattr(dialog, "txt_cari_unvan"):
            unvan = dialog.txt_cari_unvan.text().strip()
            q.customer_name_free = unvan
            if not q.title:
                q.title = unvan

    # Backward compatibility alias
    _set_cari_bilgileri = _set_cari

    def _set_finans(self, q: Quotation, dialog: Any) -> None:
        """Para birimi ve döviz kuru bilgilerini ayarlar."""
        if hasattr(dialog, "cmb_doviz"):
            txt = dialog.cmb_doviz.currentText()
            q.currency = txt.split("(")[0].strip() if "(" in txt else txt
        if hasattr(dialog, "txt_doviz_kuru"):
            try:
                q.exchange_rate = float(
                    dialog.txt_doviz_kuru.text().replace(",", ".") or "1",
                )
            except Exception:
                q.exchange_rate = 1.0

    # Backward compatibility alias
    _set_finans_bilgileri = _set_finans

    def _save_lines(self, q: Quotation, dialog: Any) -> None:
        """Evrak kalem satırlarını veritabanına kaydeder."""
        for line in list(q.lines or []):
            self.db.delete(line)
        self.db.flush()

        if not hasattr(dialog, "table_items"):
            return

        tbl = dialog.table_items
        for row in range(tbl.rowCount()):
            row_data = (
                dialog.get_row_data(row)
                if hasattr(dialog, "get_row_data")
                else self._read_row(tbl, row)
            )
            if not row_data.get("name") and not row_data.get("code"):
                continue

            line = QuotationLine()
            line.quotation_id = q.id
            line.line_order = row + 1
            item_code = row_data.get("code", "") or ""
            item_name = row_data.get("name", "") or "Kalem"
            line.sku = item_code
            line.name = item_name
            line.product_name_free = item_name
            line.product_code_free = item_code
            line.note2 = row_data.get("note2", "")
            line.quantity = float(row_data.get("qty", 1) or 1)
            line.unit = row_data.get("unit", "Adet")
            line.unit_price = float(row_data.get("price", 0) or 0)
            line.discount1 = float(row_data.get("disc1", 0) or 0)
            line.discount2 = float(row_data.get("disc2", 0) or 0)
            line.discount3 = float(row_data.get("disc3", 0) or 0)
            line.vat_rate = float(row_data.get("vat", 20) or 20)
            line.currency = row_data.get("currency", "TRY")
            line.total_amount = (
                dialog._calc_line_total(row_data)
                if hasattr(dialog, "_calc_line_total")
                else self._calc(row_data)
            )
            line.total_price = line.total_amount

            # Ürün eşleşmesi
            if line.sku and self.db:
                try:
                    p = self.db.scalar(
                        select(Product).where(
                            Product.sku == line.sku,
                            Product.is_deleted == False,  # noqa: E712
                        ),
                    )
                    if p:
                        line.product_id = p.id
                except Exception:
                    pass

            self.db.add(line)

    def _set_toplamlar(self, q: Quotation, dialog: Any) -> None:
        """Özet toplam bilgilerini hesaplayıp model nesnesine atar."""

        def parse(attr: str) -> float:
            try:
                lbl = getattr(dialog, attr, None)
                if not lbl:
                    return 0.0
                txt = lbl.text()
                for ch in ["₺", "$", "€", "£", "+", " ", "."]:
                    txt = txt.replace(ch, "")
                return float(txt.replace(",", ".").replace("-", "") or "0")
            except Exception:
                return 0.0

        q.subtotal = parse("lbl_subtotal")
        q.total_discount = parse("lbl_discount")
        q.total_expense = parse("lbl_expense_total")
        q.total_vat = parse("lbl_vat_total")
        q.grand_total = parse("lbl_grand_total")
        q.tax_base = q.grand_total - q.total_vat

    @staticmethod
    def _calc(row_data: dict[str, Any]) -> float:
        """Satır net tutarını hesaplar."""
        try:
            qty = float(row_data.get("qty", 1) or 1)
            price = float(row_data.get("price", 0) or 0)
            d1 = float(row_data.get("disc1", 0) or 0)
            d2 = float(row_data.get("disc2", 0) or 0)
            d3 = float(row_data.get("disc3", 0) or 0)
            vat = float(row_data.get("vat", 20) or 20)
            base = qty * price
            after = base * (1 - d1 / 100) * (1 - d2 / 100) * (1 - d3 / 100)
            return round(after * (1 + vat / 100), 2)
        except Exception:
            return 0.0

    _calc_total = _calc

    @staticmethod
    def _read_row(tbl: Any, row: int) -> dict[str, Any]:
        """QTableWidget satırından manuel hücre verisi okur."""
        from PyQt6.QtWidgets import QComboBox, QLineEdit

        def get(col: int) -> str:
            w = tbl.cellWidget(row, col)
            if isinstance(w, QLineEdit):
                return w.text()
            if isinstance(w, QComboBox):
                return w.currentText()
            item = tbl.item(row, col)
            return item.text() if item else ""

        return {
            "code": get(3),
            "name": get(4),
            "note2": get(5),
            "qty": get(6),
            "unit": get(7),
            "price": get(8),
            "currency": get(9),
            "disc1": get(10),
            "disc2": get(12),
            "disc3": "0",
            "vat": get(14).replace("%", "").strip() if tbl.columnCount() > 14 else "20",
        }

    _read_row_manually = _read_row

    def _generate_number(self, quotation_id: int | None = None) -> str:
        """Otomatik teklif evrak numarası üretir."""
        now = datetime.now()
        if quotation_id is None or quotation_id == 0:
            from sqlalchemy import func
            max_id = self.db.scalar(select(func.max(Quotation.id))) or 0
            quotation_id = max_id + 1
        return f"TEK-{now.year}{now.month:02d}-{quotation_id:04d}"

    def update_status(self, quotation_id: int, new_status: str) -> SaveResult:
        """Teklif durumunu günceller."""
        valid = {"draft", "sent", "accepted", "rejected", "converted"}
        if new_status not in valid:
            return SaveResult(
                success=False,
                error=f"Geçersiz durum: {new_status}. Geçerli durumlar: {valid}",
            )
        try:
            q = self.db.get(Quotation, quotation_id)
            if not q:
                return SaveResult(
                    success=False,
                    error=f"Bulunamadı: ID={quotation_id}",
                )
            q.status = new_status
            self.db.commit()
            return SaveResult(
                success=True,
                quotation_id=q.id,
                quotation_number=q.quotation_number,
            )
        except Exception as e:
            self.db.rollback()
            return SaveResult(success=False, error=str(e))

    def convert_to_order(self, quotation_id: int) -> SaveResult:
        """Teklifi müşteri siparişine dönüştürür."""
        try:
            src = self.db.get(Quotation, quotation_id)
            if not src:
                return SaveResult(
                    success=False,
                    error=f"Bulunamadı: ID={quotation_id}",
                )

            order = Quotation()
            for attr in [
                "company_id",
                "customer_id",
                "customer_name_free",
                "currency",
                "exchange_rate",
                "payment_plan",
                "notes",
                "subtotal",
                "total_discount",
                "total_expense",
                "tax_base",
                "total_vat",
                "grand_total",
            ]:
                setattr(order, attr, getattr(src, attr, None))

            order.quotation_type = "SİPARİŞ: (1) ALINAN MÜŞTERİ SİPARİŞİ"
            order.status = "draft"
            order.is_deleted = False
            order.date = datetime.now()
            order.quotation_number = (
                f"SIP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            self.db.add(order)
            self.db.flush()
            order.quotation_number = (
                f"SIP-{datetime.now().year}{datetime.now().month:02d}-{order.id:04d}"
            )

            for sl in src.lines or []:
                nl = QuotationLine()
                for attr in [
                    "product_id",
                    "sku",
                    "name",
                    "note2",
                    "product_name_free",
                    "product_code_free",
                    "quantity",
                    "unit",
                    "unit_price",
                    "discount1",
                    "discount2",
                    "discount3",
                    "vat_rate",
                    "total_amount",
                    "total_price",
                    "currency",
                    "line_order",
                ]:
                    setattr(nl, attr, getattr(sl, attr, None))
                nl.quotation_id = order.id
                nl.product_name_free = nl.name or getattr(sl, "product_name_free", "") or "Kalem"
                nl.product_code_free = nl.sku or getattr(sl, "product_code_free", "") or ""
                self.db.add(nl)

            src.status = "converted"
            self.db.commit()
            return SaveResult(
                success=True,
                quotation_id=order.id,
                quotation_number=order.quotation_number,
            )
        except Exception as e:
            self.db.rollback()
            return SaveResult(success=False, error=str(e))

    def load_to_dialog(self, quotation_id: int, dialog: Any) -> bool:
        """Veritabanındaki teklifi dialog ekranına yükler."""
        try:
            from PyQt6.QtCore import QDate

            q = self.db.get(Quotation, quotation_id)
            if not q:
                return False

            if hasattr(dialog, "txt_top_doc_no") and q.quotation_number:
                dialog.txt_top_doc_no.setText(q.quotation_number)
            if hasattr(dialog, "cmb_doc_type") and q.quotation_type:
                idx = dialog.cmb_doc_type.findText(q.quotation_type)
                if idx >= 0:
                    dialog.cmb_doc_type.setCurrentIndex(idx)
            if hasattr(dialog, "date_belge") and q.date:
                d = q.date
                dialog.date_belge.setDate(QDate(d.year, d.month, d.day))
            if hasattr(dialog, "date_vade") and q.valid_until:
                v = q.valid_until
                dialog.date_vade.setDate(QDate(v.year, v.month, v.day))
            if hasattr(dialog, "cmb_doviz") and q.currency:
                for i in range(dialog.cmb_doviz.count()):
                    if q.currency in dialog.cmb_doviz.itemText(i):
                        dialog.cmb_doviz.setCurrentIndex(i)
                        break
            if hasattr(dialog, "txt_doviz_kuru") and q.exchange_rate:
                dialog.txt_doviz_kuru.setText(f"{q.exchange_rate:.4f}")

            if q.customer_id:
                c = self.db.get(Customer, q.customer_id)
                if c and hasattr(dialog, "apply_customer_info"):
                    dialog.apply_customer_info({
                        "code": c.customer_code or "",
                        "name": c.fullname or "",
                        "tax_office": getattr(c, "tax_office", "") or "",
                        "tax_no": c.tax_number or "",
                        "address": getattr(c, "address", "") or "",
                        "balance": "0,00 ₺",
                        "terms": 30,
                    })
            elif hasattr(dialog, "txt_cari_unvan") and q.customer_name_free:
                dialog.txt_cari_unvan.setText(q.customer_name_free)

            if q.notes and hasattr(dialog, "doc_note1"):
                parts = (q.notes or "").split("\n", 1)
                dialog.doc_note1 = parts[0]
                dialog.doc_note2 = parts[1] if len(parts) > 1 else ""

            dialog.doc_id = quotation_id

            if hasattr(dialog, "table_items"):
                dialog.table_items.setRowCount(0)
                for line in sorted(
                    q.lines or [],
                    key=lambda it: it.line_order or 0,
                ):
                    line_name = line.name or getattr(line, "product_name_free", "") or ""
                    line_code = line.sku or getattr(line, "product_code_free", "") or ""
                    if hasattr(dialog, "add_item_row"):
                        dialog.add_item_row(
                            item_type="Malzeme",
                            code=line_code,
                            name=line_name,
                            note2=line.note2 or "",
                            qty=float(line.quantity or 1),
                            unit=line.unit or "Adet",
                            price=float(line.unit_price or 0),
                            currency=line.currency or "TRY",
                            vat=int(line.vat_rate or 20),
                            disc1=float(line.discount1 or 0),
                            disc2=float(line.discount2 or 0),
                            disc3=float(getattr(line, "discount3", 0) or 0),
                        )

            if hasattr(dialog, "calculate_totals"):
                dialog.calculate_totals()
            return True
        except Exception as e:
            logger.error(f"Yükleme hatası: {e}", exc_info=True)
            return False
