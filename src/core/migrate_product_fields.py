# src/core/migrate_product_fields.py
"""Tek seferlik çalıştır: Product tablosuna eksik alanları ekler.

SQLite ALTER TABLE ile güvenli ekleme yapar (alan zaten varsa atlar).
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/app.db")

COLUMNS_TO_ADD = [
    ("purchase_price", "REAL DEFAULT 0.0"),
    ("unit", "VARCHAR(50) DEFAULT 'Adet'"),
    ("vat_rate", "INTEGER DEFAULT 20"),
    ("category", "VARCHAR(100)"),
    ("brand", "VARCHAR(100)"),
    ("min_stock", "REAL DEFAULT 0.0"),
    ("description", "TEXT"),
    ("is_active", "BOOLEAN DEFAULT 1"),
    ("company_id", "INTEGER"),
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

    print(f"[+] Eklenen alanlar   : {eklenen or 'Yok'}")
    print(f"[*] Zaten var (atlandi): {atlanan or 'Yok'}")
    print("Migration tamamlandi.")


if __name__ == "__main__":
    migrate()
