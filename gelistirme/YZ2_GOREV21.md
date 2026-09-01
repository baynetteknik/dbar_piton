# YZ 2 — Görev 21: Kritik Düzeltmeler

> **Dosyalar:** `transaction_document_dialog.py`, `quotations.py`  
> **Kural:** Sadece belirtilen metodları değiştir.

---

## 21.1 — Yeni Teklif Açılınca Cari Temizle

### quotations.py — on_new_clicked içinde:

```python
def on_new_clicked(self):
    dlg = TransactionDocumentDialog(
        db_session=self.db,
        company_id=self.company_id,
        initial_type_idx=self._get_type_index(),
        parent=self,
    )
    dlg.doc_id = None

    # YENİ — Widget'ları temizle
    if hasattr(dlg, "cari_widget"):
        dlg.cari_widget.clear()
    if hasattr(dlg, "belge_widget"):
        dlg.belge_widget.clear()

    dlg.document_saved.connect(self._on_document_saved)
    dlg.exec()
```

---

## 21.2 — Belge No Sorunu — Kalıcı Çözüm

### transaction_document_dialog.py:

**txt_top_doc_no oluşturulduğu yerde:**
```python
# BUNU BUL (ne şekilde olursa olsun):
self.txt_top_doc_no = QLineEdit("FTR2026-0001")
# veya
self.txt_top_doc_no = QLineEdit(f"TOY{datetime.now()...}")
# veya herhangi bir değer

# BUNUNLA DEĞİŞTİR:
self.txt_top_doc_no = QLineEdit()
self.txt_top_doc_no.setPlaceholderText("Kaydedilince otomatik atanır")
self.txt_top_doc_no.setReadOnly(True)
self.txt_top_doc_no.setStyleSheet("""
    QLineEdit {
        background: #f1f5f9;
        color: #64748b;
        border: 1px solid #e2e8f0;
        border-radius: 3px;
        padding: 1px 6px;
        font-size: 10px;
        font-weight: 600;
    }
""")
```

**save_document içinde başarılı kayıt sonrası:**
```python
if result.success:
    self.doc_id = result.quotation_id
    # Belge numarasını göster
    self.txt_top_doc_no.setText(result.quotation_number or "")
    self.document_saved.emit({...})
    ...
```

---

## 21.3 — F6/F7 Kısayolları

### transaction_document_dialog.py — init_ui veya __init__ içinde:

```python
from PyQt6.QtGui import QKeySequence, QShortcut

# F6 — Alt Panel toggle
self._sc_f6 = QShortcut(QKeySequence("F6"), self)
self._sc_f6.setContext(Qt.ShortcutContext.WindowShortcut)
self._sc_f6.activated.connect(self.toggle_bottom_panel)

# F7 — Üst Panel toggle
self._sc_f7 = QShortcut(QKeySequence("F7"), self)
self._sc_f7.setContext(Qt.ShortcutContext.WindowShortcut)
self._sc_f7.activated.connect(self.toggle_info_panel)

# F5 — Yenile (kalemler)
self._sc_f5 = QShortcut(QKeySequence("F5"), self)
self._sc_f5.setContext(Qt.ShortcutContext.WindowShortcut)
self._sc_f5.activated.connect(self.calculate_totals)
```

**ÖNEMLİ:** `Qt.ShortcutContext.WindowShortcut` — bu olmadan
iç widget'lar focus aldığında kısayol çalışmıyor.

---

## 21.4 — HareketFinansWidget Dropdown Yükseklikleri

### hareket_finans_widget.py — tüm ComboBox'lara:

```python
# Mevcut FIELD_H = 24 — tüm widget'lara uygula
self.cmb_doviz.setFixedHeight(self.FIELD_H)
self.txt_kur.setFixedHeight(self.FIELD_H)
self.cmb_kdv.setFixedHeight(self.FIELD_H)
self.cmb_sekil.setFixedHeight(self.FIELD_H)
self.cmb_kasa.setFixedHeight(self.FIELD_H)
```

---

## 21.5 — Alt Bar Kısayol Bilgisini Güncelle

```python
# lbl_keys metnini güncelle:
lbl_keys.setText(
    "F2: Kaydet | F9: Yazdır | F6: Alt Panel | "
    "F7: Üst Panel | Alt+Enter: Satır | "
    "Ctrl+Del: Sil | Esc: Vazgeç"
)
```

---

## Test

```
1. Yeni teklif aç → Cari alanı BOŞ geliyor mu?
2. Belge No alanı boş + gri + "Kaydedilince atanır" yazıyor mu?
3. Kaydet → Belge No otomatik atandı mı? (TEK-202608-0001)
4. F6 → Alt panel kapandı/açıldı mı?
5. F7 → Üst panel kapandı/açıldı mı?
6. HareketFinansWidget dropdown'lar 24px mi?
```

---

## Özet

| # | Sorun | Çözüm |
|---|-------|-------|
| 21.1 | Yeni teklifte TATU geliyor | on_new_clicked'da clear() |
| 21.2 | FTR2026-0001 hatası | txt_top_doc_no readonly + boş |
| 21.3 | F6/F7 çalışmıyor | WindowShortcut context |
| 21.4 | Dropdown yükseklikleri | setFixedHeight(24) |
| 21.5 | Alt bar kısayol metni | F6/F7 ekle |
