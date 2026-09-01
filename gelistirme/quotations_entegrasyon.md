# quotations.py — Yapılacak Değişiklikler
# YZ 2 Görev 16 bittikten sonra uygula

## 1. Import Ekle (en üste)

```python
from src.desktop.services.quotation_save_service import QuotationSaveService
```

## 2. BaseQuotationOrderWidget.__init__'e Ekle

```python
# Kayıt servisi
self._save_service = QuotationSaveService(
    db_session=self.db,
    company_id=self.company_id,
)
```

## 3. on_new_clicked Metodunu Güncelle

```python
def on_new_clicked(self):
    from src.desktop.ui.dialogs.transaction_document_dialog import (
        TransactionDocumentDialog
    )
    dlg = TransactionDocumentDialog(
        db_session=self.db,
        company_id=self.company_id,
        initial_type_idx=self._get_type_index(),
        parent=self,
    )
    # doc_id yok → yeni kayıt
    dlg.doc_id = None
    dlg.document_saved.connect(self._on_document_saved)
    dlg.exec()

def _get_type_index(self) -> int:
    """Mevcut quotation_type'a göre cmb_doc_type index döndür."""
    TYPE_MAP = {
        "Quotation": 5,   # TEKLİF: (1) VERİLEN SATIŞ TEKLİFİ
        "Order":     7,   # SİPARİŞ: (1) ALINAN MÜŞTERİ SİPARİŞİ
    }
    return TYPE_MAP.get(self.quotation_type, 5)
```

## 4. on_edit_clicked Metodunu Güncelle

```python
def on_edit_clicked(self):
    selected_id = self._get_selected_id()
    if not selected_id:
        QMessageBox.information(self, "Uyarı", "Düzenlenecek kaydı seçin.")
        return

    from src.desktop.ui.dialogs.transaction_document_dialog import (
        TransactionDocumentDialog
    )
    dlg = TransactionDocumentDialog(
        db_session=self.db,
        company_id=self.company_id,
        doc_id=selected_id,   # Düzenleme modu
        parent=self,
    )
    # DB'den yükle
    svc = QuotationSaveService(db_session=self.db, company_id=self.company_id)
    svc.load_to_dialog(selected_id, dlg)

    dlg.document_saved.connect(self._on_document_saved)
    dlg.exec()

def _get_selected_id(self) -> int | None:
    """Grid'de seçili satırın ID'sini döndür."""
    sel = self.table_view.selectionModel().selectedRows()
    if not sel:
        return None
    item = self.table_model.item(sel[0].row(), 0)
    return int(item.text()) if item and item.text().isdigit() else None

def _on_document_saved(self, data: dict):
    """Dialog kaydettikten sonra listeyi yenile."""
    self.refresh_table()
    teklif_no = data.get("quotation_number", "")
    self.toast_requested.emit(f"Kaydedildi: {teklif_no}", "success")
```

## 5. on_convert_clicked Metodunu Güncelle

```python
def on_convert_clicked(self):
    selected_id = self._get_selected_id()
    if not selected_id:
        QMessageBox.information(self, "Uyarı", "Dönüştürülecek teklifi seçin.")
        return

    reply = QMessageBox.question(
        self, "Siparişe Dönüştür",
        "Seçili teklif siparişe dönüştürülecek. Devam?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    svc = QuotationSaveService(db_session=self.db, company_id=self.company_id)
    result = svc.convert_to_order(selected_id)

    if result.success:
        self.refresh_table()
        self.toast_requested.emit(
            f"Sipariş oluşturuldu: {result.quotation_number}", "success"
        )
    else:
        QMessageBox.critical(self, "Hata", result.error or "Dönüştürme başarısız.")
```

## 6. TransactionDocumentDialog'a doc_id Parametresi Ekle

transaction_document_dialog.py __init__'ine:

```python
def __init__(
    self,
    db_session=None,
    company_id: int = 1,
    doc_id: int | None = None,      # ← YENİ: Düzenleme için
    initial_type_idx: int = 5,
    parent=None,
):
    ...
    self.doc_id = doc_id  # None=yeni, int=düzenleme
```

## 7. save_document Metodunu Güncelle

```python
def save_document(self):
    from src.desktop.services.quotation_save_service import QuotationSaveService

    svc = QuotationSaveService(
        db_session=self.db,
        company_id=self.company_id,
    )
    result = svc.save_from_dialog(self)

    if result.success:
        # doc_id güncelle (yeni kayıt ise)
        self.doc_id = result.quotation_id
        # Listeye sinyal gönder
        self.document_saved.emit({
            "quotation_id":     result.quotation_id,
            "quotation_number": result.quotation_number,
        })
        QMessageBox.information(
            self, "Kaydedildi",
            f"{result.quotation_number} başarıyla kaydedildi."
        )
        self.accept()
    else:
        QMessageBox.critical(
            self, "Kayıt Hatası",
            f"Kayıt başarısız:\n{result.error}"
        )
```

## 8. document_saved Sinyalini dict Olarak Güncelle

```python
# ESKİ:
document_saved = pyqtSignal(dict)

# Zaten dict — sadece save_document içindeki emit güncellendi (Madde 7)
```

## 9. Dosya Konumu

```
src/desktop/services/quotation_save_service.py  ← yeni dosya
src/desktop/ui/dialogs/transaction_document_dialog.py  ← güncelle
src/desktop/ui/quotations.py  ← güncelle
```
