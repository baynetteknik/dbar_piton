# YZ 2 — Görev 13: Kart Detay Formları + main_window Bağlantıları

> **Dosyalar:** `main_window.py`, `customers.py`, `models.py`  
> **Yeni Dosyalar:** `stok_kart_dialog.py`  
> **Kural:** Belirtilen dosyaların dışına çıkma.

---

## Görev 13.1 — main_window.py: Modül Bağlantıları

`main_window.py` içindeki `open_module_in_tab` metodunu bul.
Aşağıdaki modülleri bağla:

```python
# Import satırlarına ekle (en üste, diğer importların yanına):
from src.desktop.ui.stok_list_screen import StokListScreen
from src.desktop.ui.cari_list_screen import CariListScreen

# open_module_in_tab metodu içine ekle:

# STOK
elif menu_name in (
    "Stok", "Stok Kartları", "Stok Yönetimi",
    self.tr("Stok"), self.tr("Stok Kartları")
):
    new_widget = StokListScreen(
        db_session=self.db,
        company_id=company_id,
        parent=self,
    )
    new_widget.toast_requested.connect(self.show_toast)

# CARİ (eğer hâlâ MusteriYonetimiWidget kullanıyorsa değiştir)
elif menu_name in (
    "Cari", "Müşteriler & Cariler", "Cari Bakiye",
    self.tr("Cari"), self.tr("Müşteriler & Cariler")
):
    new_widget = CariListScreen(
        db_session=self.db,
        company_id=company_id,
        parent=self,
    )
    new_widget.toast_requested.connect(self.show_toast)
```

---

## Görev 13.2 — Stok Kart Dialog (YENİ DOSYA)

`src/desktop/ui/stok_kart_dialog.py` oluştur.
`customers.py`'deki `CustomerDialog`'u referans al — aynı yapıda olacak.

### Sekmeler
```
1. Genel Bilgiler   → Temel stok bilgileri
2. Fiyat & KDV      → Alış/satış fiyatı, KDV oranı
3. Stok & Depo      → Miktar, kritik stok, depo
4. Ek Bilgiler      → Açıklama, notlar
```

### Genel Bilgiler Sekmesi
```python
# Alanlar:
self.txt_sku        = QLineEdit()   # Stok Kodu (otomatik veya manuel)
self.txt_barcode    = QLineEdit()   # Barkod
self.txt_name       = QLineEdit()   # Ürün Adı
self.cmb_unit       = QComboBox()   # Birim
self.cmb_category   = QComboBox()   # Kategori
self.txt_brand      = QLineEdit()   # Marka
self.chk_is_active  = QCheckBox("Aktif") # Durum

# Birim seçenekleri:
UNITS = ["Adet", "Kg", "Gram", "Litre", "Metre", 
         "Paket", "Kutu", "Koli", "Hizmet", "Sefer"]

# Kategori seçenekleri:
CATEGORIES = ["Malzeme", "Hizmet", "Sarf Malzeme", 
              "Demirbaş", "Hammadde", "Yarı Mamul"]
```

### Fiyat & KDV Sekmesi
```python
self.txt_purchase_price = QLineEdit("0.00")  # Alış Fiyatı
self.txt_sale_price     = QLineEdit("0.00")  # Satış Fiyatı
self.cmb_vat_rate       = QComboBox()        # KDV %
self.txt_min_price      = QLineEdit("0.00")  # Min. Satış Fiyatı

# KDV seçenekleri:
VAT_RATES = ["% 20", "% 10", "% 1", "% 0"]

# Fiyat marjı göster (salt okunur):
# Marj % = (Satış - Alış) / Alış * 100
self.lbl_margin = QLabel("Marj: % 0.00")
```

### Stok & Depo Sekmesi
```python
self.txt_stock_qty  = QLineEdit("0.00")  # Mevcut Stok
self.txt_min_stock  = QLineEdit("0.00")  # Kritik Stok
self.txt_max_stock  = QLineEdit("0.00")  # Maksimum Stok
self.cmb_depo       = QComboBox()        # Depo

# Stok uyarısı göster:
# Eğer mevcut stok < kritik stok → kırmızı uyarı
self.lbl_stock_warning = QLabel("")
```

### Kaydet / İptal Butonları
```python
# Alt bar — transaction_document_dialog gibi sabit bar
btn_save   = QPushButton("💾 Kaydet (F2)")
btn_cancel = QPushButton("🚪 Vazgeç (Esc)")

def save_product(self):
    """Stok kartını kaydet (yeni veya güncelle)."""
    if not self.db:
        QMessageBox.warning(self, "Uyarı", "Veritabanı bağlantısı yok.")
        return

    try:
        if self.product_id:
            # Güncelle
            product = self.db.get(Product, self.product_id)
        else:
            # Yeni
            product = Product()
            self.db.add(product)

        product.sku            = self.txt_sku.text().strip()
        product.barcode        = self.txt_barcode.text().strip()
        product.name           = self.txt_name.text().strip()
        product.unit           = self.cmb_unit.currentText()
        product.category       = self.cmb_category.currentText()
        product.brand          = self.txt_brand.text().strip()
        product.is_active      = self.chk_is_active.isChecked()
        product.purchase_price = float(self.txt_purchase_price.text().replace(",", ".") or 0)
        product.sale_price     = float(self.txt_sale_price.text().replace(",", ".") or 0)
        product.vat_rate       = int(self.cmb_vat_rate.currentText().replace("%", "").strip())
        product.stock_quantity = float(self.txt_stock_qty.text().replace(",", ".") or 0)
        product.min_stock      = float(self.txt_min_stock.text().replace(",", ".") or 0)

        self.db.commit()
        self.accept()

    except Exception as e:
        self.db.rollback()
        QMessageBox.critical(self, "Hata", f"Kayıt başarısız:\n{e}")
```

### Constructor
```python
class StokKartDialog(QDialog):
    def __init__(
        self,
        db_session=None,
        company_id: int = 1,
        product_id: int | None = None,  # None = Yeni, int = Düzenle
        parent=None,
    ):
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.product_id = product_id
        
        title = "Stok Kart Düzenle" if product_id else "Yeni Stok Kartı"
        self.setWindowTitle(f"📦 {title}")
        self.setMinimumSize(600, 450)
        
        self.init_ui()
        
        if product_id:
            self.load_product()  # Mevcut veriyi doldur
```

---

## Görev 13.3 — StokListScreen: Dialog Bağlantısı

`stok_list_screen.py` içindeki CRUD metodlarını güncelle:

```python
# on_new_clicked:
def on_new_clicked(self):
    from src.desktop.ui.stok_kart_dialog import StokKartDialog
    dlg = StokKartDialog(
        db_session=self.db,
        company_id=self.company_id,
        parent=self,
    )
    if dlg.exec():
        self.refresh_table()
        self.toast_requested.emit("Yeni stok kartı eklendi.", "success")

# on_edit_clicked:
def on_edit_clicked(self):
    pid = self.get_selected_id()
    if not pid:
        QMessageBox.information(self, "Uyarı", "Düzenlenecek stok kartını seçin.")
        return
    from src.desktop.ui.stok_kart_dialog import StokKartDialog
    dlg = StokKartDialog(
        db_session=self.db,
        company_id=self.company_id,
        product_id=pid,
        parent=self,
    )
    if dlg.exec():
        self.refresh_table()
        self.toast_requested.emit("Stok kartı güncellendi.", "success")
```

---

## Görev 13.4 — CariListScreen: customers.py Dialog Bağlantısı

`cari_list_screen.py` içinde `CustomerDialog` zaten import edilmiş.
Kontrol et — doğru çalışıyor mu test et:

```python
# on_new_clicked içinde:
def on_new_clicked(self):
    try:
        from src.desktop.ui.customers import CustomerDialog
        dlg = CustomerDialog(
            db_session=self.db,
            company_id=self.company_id,
            parent=self,
        )
        if dlg.exec():
            self.refresh_table()
            self.toast_requested.emit("Yeni cari eklendi.", "success")
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"Form açılamadı:\n{e}")

# on_edit_clicked içinde:
def on_edit_clicked(self):
    cid = self.get_selected_id()
    if not cid:
        QMessageBox.information(self, "Uyarı", "Düzenlenecek cariyi seçin.")
        return
    try:
        from src.desktop.ui.customers import CustomerDialog
        dlg = CustomerDialog(
            db_session=self.db,
            company_id=self.company_id,
            customer_id=cid,
            parent=self,
        )
        if dlg.exec():
            self.refresh_table()
            self.toast_requested.emit("Cari güncellendi.", "success")
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"Form açılamadı:\n{e}")
```

---

## Test Senaryosu

```
1. Programı çalıştır → STOK menüsüne tıkla
   → Stok liste ekranı açılıyor mu?

2. Stok listesinde ➕ Yeni butonuna bas
   → StokKartDialog açılıyor mu?

3. Stok kartı doldur → Kaydet
   → Liste yenileniyor mu? Kayıt görünüyor mu?

4. Stok kartına çift tıkla
   → Düzenle formu açılıyor mu? Veriler dolu geliyor mu?

5. CARİ menüsüne tıkla
   → Cari liste açılıyor mu?

6. Cari listede ➕ Yeni
   → CustomerDialog açılıyor mu?
```

---

## Özet

| Görev | Dosya | Açıklama |
|-------|-------|----------|
| 13.1 | `main_window.py` | Stok + Cari menü bağlantısı |
| 13.2 | `stok_kart_dialog.py` (YENİ) | Stok kart detay formu |
| 13.3 | `stok_list_screen.py` | Dialog bağlantısı |
| 13.4 | `cari_list_screen.py` | CustomerDialog bağlantısı test |

> Görev 13.2 en önemli — önce onu yap.  
> `customers.py`'yi referans al, aynı yapıda yaz.
