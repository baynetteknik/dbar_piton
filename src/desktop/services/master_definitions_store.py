"""TOYA ERP - Dinamik Tanımlar Veri Modeli ve Servis Katmanı (master_definitions_store).

Adres Tanımları (Ülkeler, Şehirler/İller, İlçeler, Semtler/Mahalleler),
Vergi Daireleri ve Banka/Şube Tanımlarını yönetir.
Başlangıçta Türkiye'nin 81 ili, popüler ülkeler ve bankalar otomatik yüklenir.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

_KOK = Path(__file__).resolve().parents[3]


def varsayilan_db_yolu() -> Path:
    return Path(os.environ.get("TOYA_MASTER_DEF_DB") or _KOK / "toya_erp.db")


def _simdi() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class MasterDefError(ValueError):
    """Tanım doğrulama hatası."""


class MasterDefinitionsStore:
    """Adres, Vergi Dairesi ve Banka master verilerini yöneten servis."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else varsayilan_db_yolu()
        self._init_db()

    @contextmanager
    def _baglan(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def _init_db(self) -> None:
        with self._baglan() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS def_countries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    phone_code TEXT,
                    currency TEXT DEFAULT 'TRY',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS def_cities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    country_code TEXT NOT NULL DEFAULT 'TR',
                    plate_code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone_code TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(country_code, plate_code)
                );
                CREATE TABLE IF NOT EXISTS def_districts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city_plate TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(city_plate, name)
                );
                CREATE TABLE IF NOT EXISTS def_sub_districts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city_plate TEXT NOT NULL,
                    district_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    postcode TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS def_tax_offices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE,
                    name TEXT NOT NULL,
                    city_plate TEXT,
                    district_name TEXT,
                    treasury_code TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS def_banks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    swift_code TEXT,
                    eft_code TEXT,
                    is_active INTEGER DEFAULT 1,
                    logo_path TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS def_bank_branches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_code TEXT NOT NULL,
                    branch_code TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    city_plate TEXT,
                    district_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(bank_code, branch_code)
                );
                CREATE TABLE IF NOT EXISTS def_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    symbol TEXT,
                    unit_type TEXT DEFAULT 'adet',
                    is_base INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_def_cities_plate ON def_cities(plate_code);
                CREATE INDEX IF NOT EXISTS ix_def_districts_city ON def_districts(city_plate);
                CREATE INDEX IF NOT EXISTS ix_def_tax_offices_city ON def_tax_offices(city_plate);
                CREATE INDEX IF NOT EXISTS ix_def_banks_code ON def_banks(code);
                CREATE INDEX IF NOT EXISTS ix_def_bank_branches_bank ON def_bank_branches(bank_code);
                CREATE INDEX IF NOT EXISTS ix_def_units_code ON def_units(code);
            """)

            # Başlangıç verilerini tohumla (seed)
            self._seed_initial_data(c)

    def _seed_initial_data(self, c: sqlite3.Connection) -> None:
        # 1. Ülkeler
        cnt = c.execute("SELECT COUNT(*) FROM def_countries").fetchone()[0]
        if cnt == 0:
            countries = [
                ("TR", "Türkiye", "+90", "TRY"),
                ("DE", "Almanya", "+49", "EUR"),
                ("US", "Amerika Birleşik Devletleri", "+1", "USD"),
                ("GB", "Birleşik Krallık", "+44", "GBP"),
                ("NL", "Hollanda", "+31", "EUR"),
                ("FR", "Fransa", "+33", "EUR"),
                ("IT", "İtalya", "+39", "EUR"),
                ("RU", "Rusya Federasyonu", "+7", "RUB"),
                ("AZ", "Azerbaycan", "+994", "AZN"),
                ("CN", "Çin", "+86", "CNY"),
                ("AE", "Birleşik Arap Emirlikleri", "+971", "AED"),
                ("SA", "Suudi Arabistan", "+966", "SAR"),
            ]
            simdi = _simdi()
            c.executemany(
                "INSERT OR IGNORE INTO def_countries (code, name, phone_code, currency, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                [(code, name, phone, curr, simdi, simdi) for code, name, phone, curr in countries],
            )

        # 2. Türkiye 81 İl
        cnt_cities = c.execute("SELECT COUNT(*) FROM def_cities WHERE country_code='TR'").fetchone()[0]
        if cnt_cities == 0:
            cities = [
                ("01", "Adana", "322"), ("02", "Adıyaman", "416"), ("03", "Afyonkarahisar", "272"),
                ("04", "Ağrı", "472"), ("05", "Amasya", "358"), ("06", "Ankara", "312"),
                ("07", "Antalya", "242"), ("08", "Artvin", "466"), ("09", "Aydın", "256"),
                ("10", "Balıkesir", "266"), ("11", "Bilecik", "228"), ("12", "Bingöl", "426"),
                ("13", "Bitlis", "434"), ("14", "Bolu", "374"), ("15", "Burdur", "248"),
                ("16", "Bursa", "224"), ("17", "Çanakkale", "286"), ("18", "Çankırı", "376"),
                ("19", "Çorum", "364"), ("20", "Denizli", "258"), ("21", "Diyarbakır", "412"),
                ("22", "Edirne", "284"), ("23", "Elazığ", "424"), ("24", "Erzincan", "446"),
                ("25", "Erzurum", "442"), ("26", "Eskişehir", "222"), ("27", "Gaziantep", "342"),
                ("28", "Giresun", "454"), ("29", "Gümüşhane", "456"), ("30", "Hakkari", "438"),
                ("31", "Hatay", "326"), ("32", "Isparta", "246"), ("33", "Mersin", "324"),
                ("34", "İstanbul", "212"), ("35", "İzmir", "232"), ("36", "Kars", "474"),
                ("37", "Kastamonu", "366"), ("38", "Kayseri", "352"), ("39", "Kırklareli", "288"),
                ("40", "Kırşehir", "386"), ("41", "Kocaeli", "262"), ("42", "Konya", "332"),
                ("43", "Kütahya", "274"), ("44", "Malatya", "422"), ("45", "Manisa", "236"),
                ("46", "Kahramanmaraş", "344"), ("47", "Mardin", "482"), ("48", "Muğla", "252"),
                ("49", "Muş", "436"), ("50", "Nevşehir", "384"), ("51", "Niğde", "388"),
                ("52", "Ordu", "452"), ("53", "Rize", "464"), ("54", "Sakarya", "264"),
                ("55", "Samsun", "362"), ("56", "Siirt", "484"), ("57", "Sinop", "368"),
                ("58", "Sivas", "346"), ("59", "Tekirdağ", "282"), ("60", "Tokat", "356"),
                ("61", "Trabzon", "462"), ("62", "Tunceli", "428"), ("63", "Şanlıurfa", "414"),
                ("64", "Uşak", "276"), ("65", "Van", "432"), ("66", "Yozgat", "354"),
                ("67", "Zonguldak", "372"), ("68", "Aksaray", "382"), ("69", "Bayburt", "458"),
                ("70", "Karaman", "338"), ("71", "Kırıkkale", "318"), ("72", "Batman", "488"),
                ("73", "Şırnak", "486"), ("74", "Bartın", "378"), ("75", "Ardahan", "478"),
                ("76", "Iğdır", "476"), ("77", "Yalova", "226"), ("78", "Karabük", "370"),
                ("79", "Kilis", "348"), ("80", "Osmaniye", "328"), ("81", "Düzce", "380"),
            ]
            simdi = _simdi()
            c.executemany(
                "INSERT OR IGNORE INTO def_cities (country_code, plate_code, name, phone_code, is_active, created_at, updated_at) VALUES ('TR', ?, ?, ?, 1, ?, ?)",
                [(plaka, name, phone, simdi, simdi) for plaka, name, phone in cities],
            )

        # 3. Örnek İlçeler
        cnt_districts = c.execute("SELECT COUNT(*) FROM def_districts").fetchone()[0]
        if cnt_districts == 0:
            districts = [
                # İstanbul
                ("34", "Kadıköy"), ("34", "Beşiktaş"), ("34", "Şişli"), ("34", "Üsküdar"),
                ("34", "Bakırköy"), ("34", "Ataşehir"), ("34", "Ümraniye"), ("34", "Maltepe"),
                ("34", "Kartal"), ("34", "Pendik"), ("34", "Beylikdüzü"), ("34", "Fatih"),
                # Ankara
                ("06", "Çankaya"), ("06", "Yenimahalle"), ("06", "Keçiören"), ("06", "Mamak"),
                ("06", "Etimesgut"), ("06", "Sincan"), ("06", "Altındağ"), ("06", "Gölbaşı"),
                # İzmir
                ("35", "Konak"), ("35", "Karşıyaka"), ("35", "Bornova"), ("35", "Bayraklı"),
                ("35", "Buca"), ("35", "Çiğli"), ("35", "Gaziemir"), ("35", "Alsancak"),
                # Bursa
                ("16", "Osmangazi"), ("16", "Nilüfer"), ("16", "Yıldırım"), ("16", "İnegöl"),
                # Antalya
                ("07", "Muratpaşa"), ("07", "Konyaaltı"), ("07", "Kepez"), ("07", "Alanya"),
            ]
            simdi = _simdi()
            c.executemany(
                "INSERT OR IGNORE INTO def_districts (city_plate, name, is_active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                [(plaka, name, simdi, simdi) for plaka, name in districts],
            )

        # 4. Bankalar
        cnt_banks = c.execute("SELECT COUNT(*) FROM def_banks").fetchone()[0]
        if cnt_banks == 0:
            banks = [
                ("0010", "T.C. Ziraat Bankası A.Ş.", "TCZBTR2A", "0010"),
                ("0012", "Türkiye Halk Bankası A.Ş.", "TRHBTRIS", "0012"),
                ("0015", "Türkiye Vakıflar Bankası T.A.O.", "TVBATR2A", "0015"),
                ("0064", "Türkiye İş Bankası A.Ş.", "ISBKTRIS", "0064"),
                ("0062", "Türkiye Garanti Bankası A.Ş. (Garanti BBVA)", "TGBATRTR", "0062"),
                ("0046", "Akbank T.A.Ş.", "AKBKTRIS", "0046"),
                ("0067", "Yapı ve Kredi Bankası A.Ş.", "YAPITRIS", "0067"),
                ("0111", "QNB Finansbank A.Ş.", "FNBATRTR", "0111"),
                ("0032", "Türk Ekonomi Bankası A.Ş. (TEB)", "TEBATR2W", "0032"),
                ("0124", "Denizbank A.Ş.", "DENITRTR", "0124"),
                ("0123", "HSBC Bank A.Ş.", "HSBCTRTR", "0123"),
                ("0100", "ING Bank A.Ş.", "INGBTRIS", "0100"),
                ("0205", "Kuveyt Türk Katılım Bankası A.Ş.", "KTESTRIS", "0205"),
                ("0206", "Türkiye Finans Katılım Bankası A.Ş.", "TFKBTRIS", "0206"),
                ("0203", "Albaraka Türk Katılım Bankası A.Ş.", "BTFHTRIS", "0203"),
                ("0209", "Ziraat Katılım Bankası A.Ş.", "ZIRATR2A", "0209"),
                ("0210", "Vakıf Katılım Bankası A.Ş.", "VAKFTR2A", "0210"),
            ]
            simdi = _simdi()
            c.executemany(
                "INSERT OR IGNORE INTO def_banks (code, name, swift_code, eft_code, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                [(code, name, swift, eft, simdi, simdi) for code, name, swift, eft in banks],
            )

        # 5. Vergi Daireleri
        cnt_tax = c.execute("SELECT COUNT(*) FROM def_tax_offices").fetchone()[0]
        if cnt_tax == 0:
            tax_offices = [
                ("034251", "Kadıköy Vergi Dairesi", "34", "Kadıköy", "34251"),
                ("034252", "Beşiktaş Vergi Dairesi", "34", "Beşiktaş", "34252"),
                ("034253", "Şişli Vergi Dairesi", "34", "Şişli", "34253"),
                ("034254", "Mecidiyeköy Vergi Dairesi", "34", "Şişli", "34254"),
                ("034255", "Beyoğlu Vergi Dairesi", "34", "Beyoğlu", "34255"),
                ("034256", "Üsküdar Vergi Dairesi", "34", "Üsküdar", "34256"),
                ("034257", "Bakırköy Vergi Dairesi", "34", "Bakırköy", "34257"),
                ("006251", "Çankaya Vergi Dairesi", "06", "Çankaya", "06251"),
                ("006252", "Başkent Vergi Dairesi", "06", "Çankaya", "06252"),
                ("006253", "Yenimahalle Vergi Dairesi", "06", "Yenimahalle", "06253"),
                ("035251", "Konak Vergi Dairesi", "35", "Konak", "35251"),
                ("035252", "Kordon Vergi Dairesi", "35", "Konak", "35252"),
                ("035253", "Karşıyaka Vergi Dairesi", "35", "Karşıyaka", "35253"),
                ("016251", "Osmangazi Vergi Dairesi", "16", "Osmangazi", "16251"),
                ("016252", "Nilüfer Vergi Dairesi", "16", "Nilüfer", "16252"),
                ("007251", "Muratpaşa Vergi Dairesi", "07", "Muratpaşa", "07251"),
            ]
            simdi = _simdi()
            c.executemany(
                "INSERT OR IGNORE INTO def_tax_offices (code, name, city_plate, district_name, treasury_code, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                [(code, name, plate, dist, trs, simdi, simdi) for code, name, plate, dist, trs in tax_offices],
            )

        # 5. Standart Ölçü Birimleri (Units)
        u_cnt = c.execute("SELECT COUNT(*) FROM def_units").fetchone()[0]
        if u_cnt == 0:
            units = [
                ("C62", "Adet", "Adet", "adet", 1),
                ("KGM", "Kilogram", "Kg", "agirlik", 1),
                ("GRM", "Gram", "g", "agirlik", 0),
                ("TNE", "Ton", "Ton", "agirlik", 0),
                ("MTR", "Metre", "m", "uzunluk", 1),
                ("CMT", "Santimetre", "cm", "uzunluk", 0),
                ("MTK", "Metrekare", "m²", "alan", 1),
                ("MTQ", "Metreküp", "m³", "hacim", 1),
                ("LTR", "Litre", "Lt", "hacim", 1),
                ("PA", "Paket", "Paket", "paket", 1),
                ("BX", "Koli", "Koli", "paket", 1),
                ("PX", "Palet", "Palet", "paket", 1),
                ("HUR", "Saat", "Sa", "zaman", 1),
                ("DAY", "Gün", "Gün", "zaman", 1),
                ("MON", "Ay", "Ay", "zaman", 1),
                ("SET", "Set", "Set", "adet", 1),
                ("DZN", "Düzine", "Dzn", "adet", 0),
            ]
            simdi = _simdi()
            c.executemany(
                "INSERT OR IGNORE INTO def_units (code, name, symbol, unit_type, is_base, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                [(code, name, sym, utype, is_b, simdi, simdi) for code, name, sym, utype, is_b in units],
            )

    # ---- ÜLKELER (Countries) -----------------------------------------------
    def get_countries(self, active_only: bool = True) -> list[dict[str, Any]]:
        w = "WHERE is_active=1" if active_only else ""
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_countries {w} ORDER BY CASE WHEN code='TR' THEN 0 ELSE 1 END, name ASC").fetchall()
            return [dict(r) for r in rows]

    def add_country(self, code: str, name: str, phone_code: str = "", currency: str = "TRY") -> int:
        cd, nm = (code or "").strip().upper(), (name or "").strip()
        if not cd or not nm:
            raise MasterDefError("Ülke kodu ve adı boş olamaz.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_countries (code, name, phone_code, currency, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (cd, nm, phone_code.strip(), currency.strip().upper(), simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_country(self, country_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("code", "name", "phone_code", "currency", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_countries SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), country_id))

    def delete_country(self, country_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_countries SET is_active=0, updated_at=? WHERE id=?", (_simdi(), country_id))

    # ---- İLLER / ŞEHİRLER (Cities) -----------------------------------------
    def get_cities(self, country_code: str = "TR", active_only: bool = True) -> list[dict[str, Any]]:
        w = ["country_code=?"]
        p: list[Any] = [country_code.upper()]
        if active_only:
            w.append("is_active=1")
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_cities WHERE {' AND '.join(w)} ORDER BY plate_code ASC, name ASC", p).fetchall()
            return [dict(r) for r in rows]

    def add_city(self, plate_code: str, name: str, country_code: str = "TR", phone_code: str = "") -> int:
        pl, nm = (plate_code or "").strip().zfill(2), (name or "").strip()
        if not pl or not nm:
            raise MasterDefError("Plaka kodu ve şehir adı boş olamaz.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_cities (country_code, plate_code, name, phone_code, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (country_code.upper(), pl, nm, phone_code.strip(), simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_city(self, city_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("country_code", "plate_code", "name", "phone_code", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_cities SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), city_id))

    def delete_city(self, city_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_cities SET is_active=0, updated_at=? WHERE id=?", (_simdi(), city_id))

    # ---- İLÇELER (Districts) -----------------------------------------------
    def get_districts(self, city_plate: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        w, p = [], []
        if city_plate:
            w.append("city_plate=?")
            p.append(city_plate.strip().zfill(2))
        if active_only:
            w.append("is_active=1")
        where_clause = f"WHERE {' AND '.join(w)}" if w else ""
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_districts {where_clause} ORDER BY city_plate ASC, name ASC", p).fetchall()
            return [dict(r) for r in rows]

    def add_district(self, city_plate: str, name: str) -> int:
        pl, nm = (city_plate or "").strip().zfill(2), (name or "").strip()
        if not pl or not nm:
            raise MasterDefError("İl plaka kodu ve ilçe adı boş olamaz.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_districts (city_plate, name, is_active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                (pl, nm, simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_district(self, district_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("city_plate", "name", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_districts SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), district_id))

    def delete_district(self, district_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_districts SET is_active=0, updated_at=? WHERE id=?", (_simdi(), district_id))

    # ---- SEMTLER / MAHALLELER (Sub-districts) ------------------------------
    def get_sub_districts(self, city_plate: str | None = None, district_name: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        w, p = [], []
        if city_plate:
            w.append("city_plate=?")
            p.append(city_plate.strip().zfill(2))
        if district_name:
            w.append("district_name=?")
            p.append(district_name.strip())
        if active_only:
            w.append("is_active=1")
        where_clause = f"WHERE {' AND '.join(w)}" if w else ""
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_sub_districts {where_clause} ORDER BY name ASC", p).fetchall()
            return [dict(r) for r in rows]

    def add_sub_district(self, city_plate: str, district_name: str, name: str, postcode: str = "") -> int:
        pl, dist, nm = (city_plate or "").strip().zfill(2), (district_name or "").strip(), (name or "").strip()
        if not pl or not dist or not nm:
            raise MasterDefError("İl, ilçe ve semt/mahalle adı zorunludur.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_sub_districts (city_plate, district_name, name, postcode, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (pl, dist, nm, postcode.strip(), simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_sub_district(self, sub_district_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("city_plate", "district_name", "name", "postcode", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_sub_districts SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), sub_district_id))

    def delete_sub_district(self, sub_district_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_sub_districts SET is_active=0, updated_at=? WHERE id=?", (_simdi(), sub_district_id))

    # ---- VERGİ DAİRELERİ (Tax Offices) ------------------------------------
    def get_tax_offices(self, city_plate: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        w, p = [], []
        if city_plate:
            w.append("city_plate=?")
            p.append(city_plate.strip().zfill(2))
        if active_only:
            w.append("is_active=1")
        where_clause = f"WHERE {' AND '.join(w)}" if w else ""
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_tax_offices {where_clause} ORDER BY city_plate ASC, name ASC", p).fetchall()
            return [dict(r) for r in rows]

    def add_tax_office(self, code: str, name: str, city_plate: str = "", district_name: str = "", treasury_code: str = "") -> int:
        nm = (name or "").strip()
        if not nm:
            raise MasterDefError("Vergi dairesi adı boş olamaz.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_tax_offices (code, name, city_plate, district_name, treasury_code, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (code.strip(), nm, city_plate.strip().zfill(2) if city_plate else "", district_name.strip(), treasury_code.strip(), simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_tax_office(self, tax_office_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("code", "name", "city_plate", "district_name", "treasury_code", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_tax_offices SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), tax_office_id))

    def delete_tax_office(self, tax_office_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_tax_offices SET is_active=0, updated_at=? WHERE id=?", (_simdi(), tax_office_id))

    # ---- BANKALAR (Banks) --------------------------------------------------
    def get_banks(self, active_only: bool = True) -> list[dict[str, Any]]:
        w = "WHERE is_active=1" if active_only else ""
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_banks {w} ORDER BY code ASC").fetchall()
            return [dict(r) for r in rows]

    def add_bank(self, code: str, name: str, swift_code: str = "", eft_code: str = "", logo_path: str = "") -> int:
        cd, nm = (code or "").strip(), (name or "").strip()
        if not cd or not nm:
            raise MasterDefError("Banka kodu ve adı boş olamaz.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_banks (code, name, swift_code, eft_code, logo_path, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (cd, nm, swift_code.strip().upper(), (eft_code or cd).strip(), logo_path.strip(), simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_bank(self, bank_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("code", "name", "swift_code", "eft_code", "logo_path", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_banks SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), bank_id))

    def delete_bank(self, bank_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_banks SET is_active=0, updated_at=? WHERE id=?", (_simdi(), bank_id))

    # ---- BANKA ŞUBELERİ (Bank Branches) ------------------------------------
    def get_bank_branches(self, bank_code: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        w, p = [], []
        if bank_code:
            w.append("bank_code=?")
            p.append(bank_code.strip())
        if active_only:
            w.append("is_active=1")
        where_clause = f"WHERE {' AND '.join(w)}" if w else ""
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_bank_branches {where_clause} ORDER BY bank_code ASC, branch_code ASC", p).fetchall()
            return [dict(r) for r in rows]

    def add_bank_branch(self, bank_code: str, branch_code: str, branch_name: str, city_plate: str = "", district_name: str = "") -> int:
        bcode, scode, sname = (bank_code or "").strip(), (branch_code or "").strip(), (branch_name or "").strip()
        if not bcode or not scode or not sname:
            raise MasterDefError("Banka kodu, şube kodu ve şube adı boş olamaz.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_bank_branches (bank_code, branch_code, branch_name, city_plate, district_name, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (bcode, scode, sname, city_plate.strip().zfill(2) if city_plate else "", district_name.strip(), simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_bank_branch(self, branch_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("bank_code", "branch_code", "branch_name", "city_plate", "district_name", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_bank_branches SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), branch_id))

    def delete_bank_branch(self, branch_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_bank_branches SET is_active=0, updated_at=? WHERE id=?", (_simdi(), branch_id))

    # ---- ÖLÇÜ BİRİMLERİ (Units) --------------------------------------------
    def get_units(self, active_only: bool = True) -> list[dict[str, Any]]:
        w = "WHERE is_active=1" if active_only else ""
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM def_units {w} ORDER BY is_base DESC, name ASC").fetchall()
            return [dict(r) for r in rows]

    def add_unit(self, code: str, name: str, symbol: str = "", unit_type: str = "adet", is_base: bool = True) -> int:
        cd, nm = (code or "").strip().upper(), (name or "").strip()
        if not cd or not nm:
            raise MasterDefError("Birim kodu ve adı boş olamaz.")
        simdi = _simdi()
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO def_units (code, name, symbol, unit_type, is_base, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (cd, nm, symbol.strip() or nm, unit_type.strip(), 1 if is_base else 0, simdi, simdi),
            )
            return int(cur.lastrowid)

    def update_unit(self, unit_id: int, **kwargs) -> None:
        simdi = _simdi()
        sets = {k: v for k, v in kwargs.items() if k in ("code", "name", "symbol", "unit_type", "is_base", "is_active")}
        if not sets:
            return
        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE def_units SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), unit_id))

    def delete_unit(self, unit_id: int) -> None:
        with self._baglan() as c:
            c.execute("UPDATE def_units SET is_active=0, updated_at=? WHERE id=?", (_simdi(), unit_id))
