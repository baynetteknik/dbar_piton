import sqlite3
import os

# DB yolunu bul
possible_paths = [
    "data/app.db",
    "app.db", 
    "src/data/app.db",
]

db_path = None
for p in possible_paths:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print("DB bulunamadi! Mevcut klasordeki .db dosyalari:")
    for f in os.listdir("."):
        if f.endswith(".db"):
            print(f"  {f}")
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Mevcut teklifler
    cur.execute("SELECT id, quotation_number, status FROM quotations")
    rows = cur.fetchall()
    print(f"Mevcut teklifler ({len(rows)} adet):")
    for r in rows:
        print(f"  ID={r[0]}, No={r[1]}, Durum={r[2]}")
    
    # FTR2026-0001 varsa sil
    cur.execute("DELETE FROM quotations WHERE quotation_number = 'FTR2026-0001'")
    deleted = cur.rowcount
    conn.commit()
    
    if deleted > 0:
        print(f"\nSilindi: {deleted} adet FTR2026-0001 kaydı")
    else:
        print("\nFTR2026-0001 bulunamadı veya zaten silinmiş")
    
    conn.close()
    print("\nBitti. Tekrar kaydet deneyin.")
