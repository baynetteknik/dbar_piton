"""DatabaseManager - eski (legacy) NOT NULL kısıtlamalarının otomatik onarımı.

`products.site_id` / `remote_id` gibi alanlar ilk migration'da NOT NULL olarak
oluşturulmuştu; model artık bunları nullable=True yapıyor ama SQLite
`ALTER TABLE` bu kısıtlamayı kaldıramaz. Bu testler, var olan (eski şemalı)
bir veritabanı dosyası açıldığında `DatabaseManager`'ın tabloyu güncel modele
göre yeniden kurup veriyi koruduğunu ve yeni kayıtların artık `site_id`/
`remote_id` verilmeden kaydedilebildiğini doğrular.
"""

import sqlite3

from src.core.database import DatabaseManager
from src.core.models import Product


def _create_legacy_products_table(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            site_id INTEGER NOT NULL,
            remote_id TEXT NOT NULL,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_deleted BOOLEAN NOT NULL DEFAULT 0,
            version_id INTEGER NOT NULL DEFAULT 1
        )
        """,
    )
    conn.execute(
        "INSERT INTO products (id, site_id, remote_id, sku, name) "
        "VALUES (1, 1, 'R1', 'OLD-SKU', 'Eski Ürün')",
    )
    conn.commit()
    conn.close()


def test_legacy_not_null_site_id_is_relaxed_and_data_kept(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    _create_legacy_products_table(db_path)

    dbm = DatabaseManager(db_path=db_path)
    session = dbm.get_db()
    try:
        old = session.query(Product).filter_by(sku="OLD-SKU").first()
        assert old is not None
        assert old.name == "Eski Ürün"

        # Artık site_id / remote_id verilmeden yeni ürün kaydedilebilmeli.
        p = Product(sku="NEW-SKU", name="Yeni Ürün")
        session.add(p)
        session.commit()
        assert p.id is not None
        assert p.site_id is None
    finally:
        session.close()
