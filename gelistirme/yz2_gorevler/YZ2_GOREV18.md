# YZ 2 — Görev 18: Teklif DB Kayıt Entegrasyonu

> **Değiştirilecek Dosya:** `src/desktop/ui/dialogs/transaction_document_dialog.py`  
> **Yeni Dosyalar:** `src/desktop/services/quotation_save_service.py` ve `src/desktop/services/__init__.py`  
> **Kural:** Sadece belirtilen dosyaları değiştir.

---

## Adım 1 — Yeni Klasör ve Dosyaları Oluştur

### `src/desktop/services/__init__.py`
```python
"""ToyaUI Servis Katmanı."""
from .quotation_save_service import QuotationSaveService, SaveResult

__all__ = ["QuotationSaveService", "SaveResult"]
```

### `src/desktop/services/quotation_save_service.py`

Aşağıdaki tam kodu yaz:

```python
"""
ToyaUI — Teklif Kayıt Servisi
transaction_document_dialog.py'deki ekran verilerini DB'ye kaydeder.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SaveResult:
    success: bool
    quotation_id: int | None = None
    quotation_number: str | None = None
    error: str | None = None


class QuotationSaveService:
    def __init__(self, db_session=None, company_id: int = 1):
        self.db = db_session
        self.company_id = company_id

    def save_from_dialog(self, dialog) -> SaveResult:
        if not self.db:
            return SaveResult(success=False, error="Veritabanı bağlantısı yok.")
        try:
            from src.core.models import Quotation, QuotationLine

            doc_id = getattr(dialog, "doc_id", None)
            if doc_id:
                q = self.db.get(Quotation, doc_id)
                if not q:
                    return SaveResult(success=False, error=f"Teklif bulunamadı: ID={doc_id}")
                is_new = False
            else:
                q = Quotation()
                q.company_id = self.company_id
                q.is_deleted = False
                self.db.add(q)
                is_new = True

            self._set_belge(q, dialog)
            self._set_cari(q, dialog)
            self._set_finans(q, dialog)
            q.notes = getattr(dialog, "doc_note1", "") or ""
            if getattr(dialog, "doc_note2", ""):
                q.notes += "\n" + dialog.doc_note2

            self.db.flush()
            self._save_lines(q, dialog)
            self._set_toplamlar(q, dialog)

            if is_new and not q.quotation_number:
                q.quotation_number = self._generate_number(q.id)

            self.db.commit()
            return SaveResult(
                success=True,
                quotation_id=q.id,
                quotation_number=q.quotation_number,
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Kayıt hatası: {e}")
            return SaveResult(success=False, error=str(e))

    def _set_belge(self, q, dialog):
        if hasattr(dialog, "txt_top_doc_no"):
            q.quotation_number = dialog.txt_top_doc_no.text().strip() or q.quotation_number
        if hasattr(dialog, "cmb_doc_type"):
            q.quotation_type = dialog.cmb_doc_type.currentText()
        if hasattr(dialog, "date_belge"):
            d = dialog.date_belge.date()
            q.date = datetime(d.year(), d.month(), d.day())
        if hasattr(dialog, "date_vade"):
            v = dialog.date_vade.date()
            q.valid_until = datetime(v.year(), v.month(), v.day())
        if hasattr(dialog, "cmb_odeme_plani"):
            q.payment_plan = dialog.cmb_odeme_plani.currentText()
        if not q.status:
            q.status = "draft"

    def _set_cari(self, q, dialog):
        if not self.db:
            return
        cari_kodu = ""
        if hasattr(dialog, "txt_cari_kodu"):
            cari_kodu = dialog.txt_cari_kodu.text().strip()
        if cari_kodu:
            try:
                from sqlalchemy import select
                from src.core.models import Customer
                c = self.db.scalar(
                    select(Customer).where(
                        Customer.customer_code == cari_kodu,
                        Customer.is_deleted == False,
                    )
                )
                if c:
                    q.customer_id = c.id
            except Exception as e:
                logger.warning(f"Cari bulunamadı ({cari_kodu}): {e}")
        # Serbest ad
        if hasattr(dialog, "txt_cari_unvan"):
            q.customer_name_free = dialog.txt_cari_unvan.text().strip()

    def _set_finans(self, q, dialog):
        if hasattr(dialog, "cmb_doviz"):
            txt = dialog.cmb_doviz.currentText()
            q.currency = txt.split("(")[0].strip() if "(" in txt else txt
        if hasattr(dialog, "txt_doviz_kuru"):
            try:
                q.exchange_rate = float(
                    dialog.txt_doviz_kuru.text().replace(",", ".") or "1"
                )
            except Exception:
                q.exchange_rate = 1.0

    def _save_lines(self, q, dialog):
        from src.core.models import QuotationLine
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
            line.line_order   = row + 1
            line.sku          = row_data.get("code", "")
            line.name         = row_data.get("name", "")
            line.note2        = row_data.get("note2", "")
            line.quantity     = float(row_data.get("qty", 1) or 1)
            line.unit         = row_data.get("unit", "Adet")
            line.unit_price   = float(row_data.get("price", 0) or 0)
            line.discount1    = float(row_data.get("disc1", 0) or 0)
            line.discount2    = float(row_data.get("disc2", 0) or 0)
            line.discount3    = float(row_data.get("disc3", 0) or 0)
            line.vat_rate     = int(row_data.get("vat", 20) or 20)
            line.currency     = row_data.get("currency", "TRY")
            line.total_amount = (
                dialog._calc_line_total(row_data)
                if hasattr(dialog, "_calc_line_total")
                else self._calc(row_data)
            )
            self.db.add(line)

    def _set_toplamlar(self, q, dialog):
        def parse(attr) -> float:
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

        q.subtotal       = parse("lbl_subtotal")
        q.total_discount = parse("lbl_discount")
        q.total_expense  = parse("lbl_expense_total")
        q.total_vat      = parse("lbl_vat_total")
        q.grand_total    = parse("lbl_grand_total")
        q.tax_base       = q.grand_total - q.total_vat

    @staticmethod
    def _calc(row_data: dict) -> float:
        try:
            qty   = float(row_data.get("qty", 1) or 1)
            price = float(row_data.get("price", 0) or 0)
            d1    = float(row_data.get("disc1", 0) or 0)
            d2    = float(row_data.get("disc2", 0) or 0)
            d3    = float(row_data.get("disc3", 0) or 0)
            vat   = float(row_data.get("vat", 20) or 20)
            base  = qty * price
            after = base * (1 - d1/100) * (1 - d2/100) * (1 - d3/100)
            return round(after * (1 + vat/100), 2)
        except Exception:
            return 0.0

    @staticmethod
    def _read_row(tbl, row: int) -> dict:
        from PyQt6.QtWidgets import QLineEdit, QComboBox
        def get(col):
            w = tbl.cellWidget(row, col)
            if isinstance(w, QLineEdit): return w.text()
            if isinstance(w, QComboBox): return w.currentText()
            item = tbl.item(row, col)
            return item.text() if item else ""
        return {
            "code": get(3), "name": get(4), "note2": get(5),
            "qty": get(6), "unit": get(7), "price": get(8),
            "currency": get(9), "disc1": get(10), "disc2": get(12),
            "disc3": "0", "vat": get(14).replace("%","").strip(),
        }

    @staticmethod
    def _generate_number(quotation_id: int) -> str:
        now = datetime.now()
        return f"TEK-{now.year}{now.month:02d}-{quotation_id:04d}"

    def update_status(self, quotation_id: int, new_status: str) -> SaveResult:
        VALID = {"draft", "sent", "accepted", "rejected", "converted"}
        if new_status not in VALID:
            return SaveResult(success=False, error=f"Geçersiz durum: {new_status}")
        try:
            from src.core.models import Quotation
            q = self.db.get(Quotation, quotation_id)
            if not q:
                return SaveResult(success=False, error=f"Bulunamadı: ID={quotation_id}")
            q.status = new_status
            self.db.commit()
            return SaveResult(success=True, quotation_id=q.id, quotation_number=q.quotation_number)
        except Exception as e:
            self.db.rollback()
            return SaveResult(success=False, error=str(e))

    def convert_to_order(self, quotation_id: int) -> SaveResult:
        try:
            from src.core.models import Quotation, QuotationLine
            src = self.db.get(Quotation, quotation_id)
            if not src:
                return SaveResult(success=False, error=f"Bulunamadı: ID={quotation_id}")

            order = Quotation()
            for attr in ["company_id", "customer_id", "customer_name_free",
                         "currency", "exchange_rate", "payment_plan", "notes",
                         "subtotal", "total_discount", "total_expense",
                         "tax_base", "total_vat", "grand_total"]:
                setattr(order, attr, getattr(src, attr, None))
            order.quotation_type = "SİPARİŞ: (1) ALINAN MÜŞTERİ SİPARİŞİ"
            order.status = "draft"
            order.is_deleted = False
            order.date = datetime.now()
            self.db.add(order)
            self.db.flush()
            order.quotation_number = f"SIP-{datetime.now().year}{datetime.now().month:02d}-{order.id:04d}"

            for sl in (src.lines or []):
                nl = QuotationLine()
                for attr in ["product_id", "sku", "name", "note2", "quantity",
                             "unit", "unit_price", "discount1", "discount2",
                             "vat_rate", "total_amount", "currency", "line_order"]:
                    setattr(nl, attr, getattr(sl, attr, None))
                nl.quotation_id = order.id
                nl.discount3 = getattr(sl, "discount3", 0)
                self.db.add(nl)

            src.status = "converted"
            self.db.commit()
            return SaveResult(success=True, quotation_id=order.id, quotation_number=order.quotation_number)
        except Exception as e:
            self.db.rollback()
            return SaveResult(success=False, error=str(e))

    def load_to_dialog(self, quotation_id: int, dialog) -> bool:
        try:
            from src.core.models import Quotation, Customer
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
                for line in sorted(q.lines or [], key=lambda l: l.line_order or 0):
                    if hasattr(dialog, "add_item_row"):
                        dialog.add_item_row(
                            item_type="Malzeme",
                            code=line.sku or "",
                            name=line.name or "",
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
            logger.error(f"Yükleme hatası: {e}")
            return False
```

---

## Adım 2 — transaction_document_dialog.py Değişiklikleri

### 2.1 Import Ekle

```python
# ESKİ (mevcut son import satırına ekle):
from src.desktop.services.quotation_save_service import QuotationSaveService
```

### 2.2 __init__ — doc_id parametresi

```python
# BUNU BUL:
def __init__(self, db_session=None, company_id: int = 1, initial_type_idx: int = 0, parent=None):

# YENİ:
def __init__(self, db_session=None, company_id: int = 1, doc_id: int | None = None, initial_type_idx: int = 0, parent=None):
```

Ve `super().__init__(parent)` sonrasına ekle:
```python
        self.doc_id = doc_id
```

### 2.3 save_document metodunu değiştir

```python
    def save_document(self):
        if not self.db:
            doc_no = self.txt_top_doc_no.text()
            QMessageBox.information(
                self, "Demo Mod",
                f"Demo modda çalışıyor — kayıt yapılmadı.\nBelge: {doc_no}"
            )
            self.document_saved.emit({"quotation_id": None, "quotation_number": doc_no})
            self.accept()
            return

        svc = QuotationSaveService(db_session=self.db, company_id=self.company_id)
        result = svc.save_from_dialog(self)

        if result.success:
            self.doc_id = result.quotation_id
            self.document_saved.emit({
                "quotation_id":     result.quotation_id,
                "quotation_number": result.quotation_number,
            })
            QMessageBox.information(
                self, "✅ Kaydedildi",
                f"{result.quotation_number} başarıyla kaydedildi."
            )
            self.accept()
        else:
            QMessageBox.critical(self, "❌ Kayıt Hatası", f"Kayıt başarısız:\n{result.error}")
```

### 2.4 save_and_new_document metodunu değiştir

```python
    def save_and_new_document(self):
        if not self.db:
            self.table_items.setRowCount(0)
            self.add_item_row(item_type="Malzeme")
            return

        svc = QuotationSaveService(db_session=self.db, company_id=self.company_id)
        result = svc.save_from_dialog(self)

        if result.success:
            self.document_saved.emit({
                "quotation_id":     result.quotation_id,
                "quotation_number": result.quotation_number,
            })
            # Formu temizle
            self.doc_id = None
            self.txt_top_doc_no.setText(f"TOY{datetime.now().strftime('%Y%m%d%H%M')}")
            self.txt_cari_kodu.clear()
            self.txt_cari_unvan.clear()
            self.txt_vergi_daire.clear()
            self.txt_vergi_no.clear()
            self.txt_sevk_adres.clear()
            self.table_items.setRowCount(0)
            self.add_item_row(item_type="Malzeme")
            self.calculate_totals()
        else:
            QMessageBox.critical(self, "Kayıt Hatası", f"Kayıt başarısız:\n{result.error}")
```

---

## Test

```
1. Yeni teklif aç → doldur → Kaydet (F2)
   → "Kaydedildi: TEK-XXXX" mesajı çıkıyor mu?

2. Teklif listesine dön
   → Listede görünüyor mu?

3. Üzerine çift tıkla
   → Form açılıyor, veriler dolu geliyor mu?

4. Değiştir → Kaydet
   → Liste güncellendi mi?

5. Siparişe Dönüştür
   → Yeni sipariş oluştu mu?

6. Kaydet & Yeni
   → Form temizlendi mi?
```

---

## Özet

| Dosya | Değişiklik |
|-------|-----------|
| `src/desktop/services/__init__.py` | YENİ — oluştur |
| `src/desktop/services/quotation_save_service.py` | YENİ — oluştur |
| `transaction_document_dialog.py` | import + doc_id + save_document + save_and_new |
