# YZ 2 — Görev 11: Product Modeli Güncelleme

> **Dosya:** `src/core/models.py`  
> **Kural:** Sadece `Product` sınıfını güncelle. Başka hiçbir sınıfa dokunma.

---

## Yapılacak Tek Şey

`models.py` içindeki `Product` sınıfını bul, mevcut alanların altına şu alanları ekle:

```python
class Product(BaseModel):
    # --- MEVCUT ALANLAR (dokunma) ---
    name: Mapped[str]
    sku: Mapped[str | None]
    barcode: Mapped[str | None]
    sale_price: Mapped[float | None]
    stock_quantity: Mapped[float | None]
    is_deleted: Mapped[bool]

    # --- YENİ EKLENECEK ALANLAR ---
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Adet")
    vat_rate: Mapped[int | None] = mapped_column(Integer, nullable=True, default=20)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_stock: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

---

## DB Migration (Otomatik)

Alanları ekledikten sonra şu Python dosyasını `src/core/` içine yaz ve bir kez çalıştır:

```python
# src/core/migrate_product_fields.py
"""
Tek seferlik çalıştır: Product tablosuna eksik alanları ekler.
SQLite ALTER TABLE ile güvenli ekleme yapar (alan zaten varsa atlar).
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/app.db")

COLUMNS_TO_ADD = [
    ("purchase_price", "REAL DEFAULT 0.0"),
    ("unit",           "VARCHAR(50) DEFAULT 'Adet'"),
    ("vat_rate",       "INTEGER DEFAULT 20"),
    ("category",       "VARCHAR(100)"),
    ("brand",          "VARCHAR(100)"),
    ("min_stock",      "REAL DEFAULT 0.0"),
    ("description",    "TEXT"),
    ("is_active",      "BOOLEAN DEFAULT 1"),
    ("company_id",     "INTEGER"),
]

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Mevcut sütunları al
    cur.execute("PRAGMA table_info(products)")
    existing = {row[1] for row in cur.fetchall()}

    eklenen = []
    atlanan = []

    for col_name, col_type in COLUMNS_TO_ADD:
        if col_name not in existing:
            cur.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            eklenen.append(col_name)
        else:
            atlanan.append(col_name)

    conn.commit()
    conn.close()

    print(f"✅ Eklenen alanlar  : {eklenen or 'Yok'}")
    print(f"⏭️  Zaten var (atlandı): {atlanan or 'Yok'}")
    print("Migration tamamlandı.")

if __name__ == "__main__":
    migrate()
```

---

## Çalıştırma

Migration dosyasını yazdıktan sonra terminalde:

```bash
cd C:\toya_erp
.venv\Scripts\python.exe src/core/migrate_product_fields.py
```

Çıktı şöyle olmalı:
```
✅ Eklenen alanlar  : ['purchase_price', 'unit', 'vat_rate', ...]
⏭️  Zaten var (atlandı): []
Migration tamamlandı.
```

---

## Test

Migration çalıştıktan sonra şunu yap:

```python
# Terminal'de Python aç:
.venv\Scripts\python.exe -c "
import sqlite3
conn = sqlite3.connect('data/app.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(products)')
cols = [row[1] for row in cur.fetchall()]
print('Sütunlar:', cols)
conn.close()
"
```

`purchase_price`, `unit`, `vat_rate` listede görünüyorsa migration başarılı.

---

## Özet

| Adım | Ne Yapılacak |
|------|-------------|
| 1 | `models.py` → Product sınıfına 9 alan ekle |
| 2 | `migrate_product_fields.py` dosyasını oluştur |
| 3 | Terminal'de migration çalıştır |
| 4 | Test et |

> Sadece `models.py` ve yeni `migrate_product_fields.py` değişiyor.  
> Başka hiçbir dosyaya dokunma.
