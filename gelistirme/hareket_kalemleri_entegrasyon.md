# transaction_document_dialog.py — HareketKalemleriWidget Entegrasyonu
# VS Code'da Ctrl+H ile bul/değiştir yap

## ADIM 1 — Import Ekle

### BUNU BUL:
```python
from src.desktop.ui.components.filterable_table import FilterableTableView
```

### BUNUNLA DEĞİŞTİR:
```python
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.widgets.hareket_kalemleri_widget import HareketKalemleriWidget
```

---

## ADIM 2 — __init__ içinde widget oluştur

### BUNU BUL (table_items oluşturan satırı):
```python
        self.table_items = QTableWidget(0, 16)
        self.table_items.setHorizontalHeaderLabels(self.COLUMN_NAMES)
```

### BUNUNLA DEĞİŞTİR:
```python
        # HareketKalemleriWidget — bağımsız widget
        self.hareket_kalemleri = HareketKalemleriWidget(
            products_catalog=self.products_catalog,
            profile_key="transaction_doc_items",
            theme_row_height=ThemeManager().row_height,
            parent=self,
        )
        # Geriye dönük uyumluluk — eski kodlar self.table_items kullanıyor
        self.table_items = self.hareket_kalemleri.table

        # Toplam hesaplama sinyali
        self.hareket_kalemleri.totals_changed.connect(self.calculate_totals)

        # ThemeManager bağlantısı
        theme_mgr = ThemeManager()
        theme_mgr.row_height_changed.connect(
            self.hareket_kalemleri.update_row_height
        )
```

---

## ADIM 3 — Layout'a ekle

### BUNU BUL (table_items'ı layout'a ekleyen satırı):
```python
        body_layout.addWidget(self.table_items, 1)
```

### BUNUNLA DEĞİŞTİR:
```python
        body_layout.addWidget(self.hareket_kalemleri, 1)
```

---

## ADIM 4 — add_item_row metodunu güncelle

Mevcut `add_item_row` metodunu tamamen şununla değiştir:

```python
    def add_item_row(
        self,
        item_type: str = "Malzeme",
        barcode: str = "",
        code: str = "",
        name: str = "",
        note2: str = "",
        qty: float = 1.0,
        unit: str = "Adet",
        price: float = 0.0,
        currency: str = "TRY",
        vat: int = 20,
        disc1: float = 0.0,
        disc2: float = 0.0,
        disc3: float = 0.0,
        insert_index: int | None = None,
    ) -> int:
        """HareketKalemleriWidget'a satır ekler."""
        return self.hareket_kalemleri.add_row(
            item_type=item_type,
            barcode=barcode,
            code=code,
            name=name,
            note2=note2,
            qty=qty,
            unit=unit,
            price=price,
            currency=currency,
            vat=vat,
            disc1=disc1,
            disc2=disc2,
            disc3=disc3,
            insert_at=insert_index,
        )
```

---

## ADIM 5 — remove_item_row metodunu güncelle

```python
    def remove_item_row(self, row: int):
        """Satırı sil — son satır silinemez."""
        self.hareket_kalemleri._safe_remove_row(row)
```

---

## ADIM 6 — get_row_data metodunu güncelle

```python
    def get_row_data(self, row: int) -> dict:
        """Satır verisini widget'tan oku."""
        return self.hareket_kalemleri.get_row_data(row)
```

---

## ADIM 7 — set_row_data metodunu güncelle

```python
    def set_row_data(self, row: int, data: dict):
        """Satıra veri yaz."""
        self.hareket_kalemleri.set_row_data(row, data)
```

---

## ADIM 8 — move_row_up/down metodlarını güncelle

```python
    def move_row_up(self, row: int | None = None):
        self.hareket_kalemleri.move_row_up(row)

    def move_row_down(self, row: int | None = None):
        self.hareket_kalemleri.move_row_down(row)
```

---

## ADIM 9 — delete_selected_rows metodunu güncelle

```python
    def delete_selected_rows(self):
        self.hareket_kalemleri.delete_selected_rows()
```

---

## ADIM 10 — _get_current_teklif_data metodunda get_all_rows kullan

### BUNU BUL:
```python
        kalemler = []
        for r in range(self.table_items.rowCount()):
            row_data = self.get_row_data(r)
            if not row_data.get("name"):
                continue
```

### BUNUNLA DEĞİŞTİR:
```python
        kalemler = []
        for row_data in self.hareket_kalemleri.get_all_rows():
```

---

## ADIM 11 — __init__ başlangıç satırını güncelle

### BUNU BUL (en sondaki demo satırı):
```python
        self.add_item_row(item_type="Malzeme", code="STK-001", ...)
```

### SİL — HareketKalemleriWidget zaten 1 boş satırla başlıyor

---

## Test

```
1. Programı çalıştır → Teklif Yönetimi → Yeni
2. Kalemler grid'inde 1 boş satır var mı?
3. Sağ tık → menü açılıyor mu?
   → Satır Ekle / Sil / Yukarı / Aşağı var mı?
   → Artan / Azalan Sırala var mı?
   → Sütun Gizle var mı?
   → Görünümü Kaydet var mı?
4. Başlığa tıkla → sıralama oluyor mu?
5. Sütunu sürükle → genişlik değişiyor mu?
6. Görünümü Kaydet → programı kapat/aç → genişlikler korunuyor mu?
7. Son satırı silmeye çalış → silinmiyor, temizleniyor mu?
8. Alt+Enter → yeni satır ekleniyor mu?
9. Ctrl+Del → seçili satırlar siliniyor mu?
```
