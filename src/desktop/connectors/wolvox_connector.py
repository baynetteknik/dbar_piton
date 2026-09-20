"""
TOYA ERP - Wolvox 9 (Firebird) SALT OKUNUR bağlayıcısı

Akınsoft Wolvox 9'un yerel Firebird veritabanından (WOLVOX.FDB) cari hesap özeti
ve teklifleri okuyup online portalın (`portal/`) beklediği yük (payload) biçimine
çevirir. Wolvox veritabanına ASLA yazmaz: yalnızca SELECT çalıştırılır.

Şema notları (Wolvox 9 örnek veritabanından):
- Birincil anahtar her tabloda `BLKODU`; silinme bayrağı `SILINDI` (0 = geçerli).
- Cari bakiyesi kartta tutulmaz; `CARIHR` hareketlerinden hesaplanır:
  bakiye = SUM(KPB_BTUT) - SUM(KPB_ATUT)  (+ = müşteri bize borçlu), KPB = ana para birimi (TL).
- Teklif başlığı `TEKLIF`, kalemleri `TEKLIFHR` (`BLTKKODU` -> `TEKLIF.BLKODU`).
- Firebird 2.5 (32-bit) sunucusuna, 64-bit Python'dan `firebirdsql` (saf Python) ile TCP üzerinden bağlanılır.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)

SOURCE = "wolvox"

# VARSAYIM (örnek veritabanı içeriğinden çıkarıldı; Wolvox arayüzünden doğrulanmalı):
# FATURA_DURUMU 1,3,6 = satış türevleri (cari borç), 2,4,5 = alış türevleri (cari alacak).
_SATIS = {1, 3, 6}
_ALIS = {2, 4, 5}

KEY_HOST = "wolvox.host"
KEY_PORT = "wolvox.port"
KEY_DATABASE = "wolvox.database"
KEY_USER = "wolvox.user"
KEY_PASSWORD = "wolvox.password"


class WolvoxError(Exception):
    """Bağlantı veya sorgu hatası (kullanıcıya gösterilebilir mesaj taşır)."""


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _ref(value: Any) -> str | None:
    return str(value) if value is not None else None


def _fatura_ref(entegrasyon: Any) -> str | None:
    """CARIHR.ENTEGRASYON 'FTO_<FATURA.BLKODU>' ise bağlı fatura kaydının kimliği."""
    t = _text(entegrasyon)
    return t[4:] if t.startswith("FTO_") and t[4:].isdigit() else None


class WolvoxConnector:
    source_name = SOURCE
    capabilities = frozenset({"read"})

    def __init__(
        self, *, database: str, host: str = "127.0.0.1", port: int = 3050,
        user: str = "SYSDBA", password: str = "masterkey", charset: str = "WIN1254",
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self.database = database
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.charset = charset
        self._connect = connect

    @classmethod
    def from_settings(cls, db, **kw) -> "WolvoxConnector":
        from src.desktop.services.settings_store import get_int, get_setting

        database = get_setting(db, KEY_DATABASE, "") or ""
        if not database:
            raise WolvoxError("Wolvox veritabanı yolu tanımlı değil.")
        return cls(
            database=database,
            host=get_setting(db, KEY_HOST, "127.0.0.1") or "127.0.0.1",
            port=get_int(db, KEY_PORT, 3050),
            user=get_setting(db, KEY_USER, "SYSDBA") or "SYSDBA",
            password=get_setting(db, KEY_PASSWORD, "masterkey") or "masterkey",
            **kw,
        )

    # ------------------------------------------------------------------
    def _open(self):
        connect = self._connect
        if connect is None:
            import firebirdsql
            connect = firebirdsql.connect
        try:
            return connect(
                host=self.host, port=self.port, database=self.database,
                user=self.user, password=self.password, charset=self.charset,
            )
        except Exception as exc:  # noqa: BLE001 - sürücü istisnaları çeşitli
            raise WolvoxError(f"Wolvox veritabanına bağlanılamadı: {exc}") from exc

    def _query(self, conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        if not sql.lstrip().lower().startswith("select"):
            raise WolvoxError("Wolvox bağlayıcısı yalnızca SELECT çalıştırabilir.")
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            cur.close()

    def test_connection(self) -> str:
        conn = self._open()
        try:
            rows = self._query(conn, "select count(*) as n from cari where silindi = 0")
            return f"Bağlantı başarılı. {rows[0]['n']} aktif cari kaydı."
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Ayna okuması (TOYA `wolvox_*` tablolarını besler). Anahtar her zaman BLKODU.
    # ------------------------------------------------------------------
    def _select_all(self, sql: str) -> list[dict[str, Any]]:
        conn = self._open()
        try:
            return self._query(conn, sql)
        finally:
            conn.close()

    def fetch_cariler(self) -> list[dict]:
        rows = self._select_all(
            "select blkodu, carikodu, ticari_unvani, adi_soyadi, e_mail, tel1, vergi_no, aktif, silindi from cari",
        )
        return [{
            "ext_id": str(r["blkodu"]), "cari_kodu": _text(r["carikodu"]),
            "unvan": _text(r["ticari_unvani"]) or _text(r["adi_soyadi"]),
            "email": _text(r["e_mail"]), "telefon": _text(r["tel1"]), "vergi_no": _text(r["vergi_no"]),
            "aktif": r["aktif"] == 1, "silindi": bool(r["silindi"]),
        } for r in rows]

    def fetch_cari_hareketleri(self) -> list[dict]:
        rows = self._select_all(
            "select blkodu, blcrkodu, tarihi, vadesi, evrak_no, islem_turu, kpb_btut, kpb_atut, "
            "aciklama, entegrasyon, silindi from carihr",
        )
        return [{
            "ext_id": str(r["blkodu"]), "cari_ext_id": _ref(r["blcrkodu"]), "tarihi": r["tarihi"],
            "vadesi": r["vadesi"], "evrak_no": _text(r["evrak_no"]), "kaynak_tur": _text(r["islem_turu"]),
            "borc": _num(r["kpb_btut"]), "alacak": _num(r["kpb_atut"]), "aciklama": _text(r["aciklama"]),
            "ilgili_ext_id": _fatura_ref(r["entegrasyon"]), "silindi": bool(r["silindi"]),
        } for r in rows]

    def fetch_faturalar(self) -> list[dict]:
        rows = self._select_all(
            "select blkodu, fatura_seri, fatura_no, tarihi, vadesi, blcrkodu, carikodu, fatura_durumu, "
            "iptal, silindi, toplam_ara_kpb, toplam_isk_kpb, toplam_kdv_kpb, toplam_genel_kpb, "
            "doviz_birimi, ekbilgi_1, aciklama from fatura",
        )
        return [{
            "ext_id": str(r["blkodu"]),
            "fatura_no": _text(r["fatura_no"]),
            "tarihi": r["tarihi"], "vadesi": r["vadesi"], "cari_ext_id": _ref(r["blcrkodu"]),
            "yon": "satis" if r["fatura_durumu"] in _SATIS else ("alis" if r["fatura_durumu"] in _ALIS else None),
            "kaynak_durum": _text(r["fatura_durumu"]),
            "iptal": bool(r["iptal"]), "silindi": bool(r["silindi"]),
            "ara_toplam": _num(r["toplam_ara_kpb"]), "iskonto": _num(r["toplam_isk_kpb"]),
            "kdv": _num(r["toplam_kdv_kpb"]), "genel_toplam": _num(r["toplam_genel_kpb"]),
            "doviz": _text(r["doviz_birimi"]), "ek_bilgi": _text(r["ekbilgi_1"]), "aciklama": _text(r["aciklama"]),
        } for r in rows]

    def fetch_fatura_kalemleri(self) -> list[dict]:
        rows = self._select_all(
            "select blkodu, blftkodu, stokkodu, stok_adi, birimi, miktari, kpb_kdv_haricfy, kdv_orani, "
            "kpb_toplam_tutar, kpb_kdvli_tutar, sira_no from faturahr",
        )
        return [{
            "ext_id": str(r["blkodu"]), "fatura_ext_id": str(r["blftkodu"]), "stok_kodu": _text(r["stokkodu"]),
            "stok_adi": _text(r["stok_adi"]), "birim": _text(r["birimi"]), "miktar": _num(r["miktari"]),
            "fiyat": _num(r["kpb_kdv_haricfy"]), "kdv_orani": _num(r["kdv_orani"]),
            "tutar": _num(r["kpb_toplam_tutar"]), "kdvli_tutar": _num(r["kpb_kdvli_tutar"]),
            "sira_no": r["sira_no"], "silindi": False,
        } for r in rows]

    def fetch_stoklar(self) -> list[dict]:
        stoklar = self._select_all(
            "select blkodu, stokkodu, stok_adi, birimi, kdv_orani, aktif from stok",
        )
        fiyat = {r["blstkodu"]: _num(r["fiyati"]) for r in self._select_all(
            "select blstkodu, fiyati from stok_fiyat where alis_satis = 2 and fiyat_no = 1",
        )}
        miktar = {r["blstkodu"]: _num(r["miktar"]) for r in self._select_all(
            "select blstkodu, sum(coalesce(kpb_gmik, 0) - coalesce(kpb_cmik, 0)) as miktar "
            "from stokhr where silindi = 0 group by blstkodu",
        )}
        return [{
            "ext_id": str(s["blkodu"]), "stok_kodu": _text(s["stokkodu"]), "stok_adi": _text(s["stok_adi"]),
            "birim": _text(s["birimi"]), "kdv_orani": _num(s["kdv_orani"]), "aktif": s["aktif"] == 1,
            "silindi": False, "satis_fiyati": fiyat.get(s["blkodu"], 0.0),
            "miktar": miktar.get(s["blkodu"], 0.0),
        } for s in stoklar]

    # ------------------------------------------------------------------
    def list_accounts(self, *, statement_limit: int = 50) -> list[dict]:
        """Her aktif cari için portalın `/accounts` yükünü döner (bakiye + son hareketler)."""
        conn = self._open()
        try:
            cariler = self._query(
                conn,
                "select c.blkodu, c.carikodu, c.ticari_unvani, c.adi_soyadi, "
                "coalesce(sum(h.kpb_btut), 0) as borc, coalesce(sum(h.kpb_atut), 0) as alacak "
                "from cari c left join carihr h on h.blcrkodu = c.blkodu and h.silindi = 0 "
                "where c.silindi = 0 and c.aktif = 1 "
                "group by c.blkodu, c.carikodu, c.ticari_unvani, c.adi_soyadi",
            )
            hareketler = self._query(
                conn,
                "select blcrkodu, tarihi, evrak_no, aciklama, kpb_btut, kpb_atut "
                "from carihr where silindi = 0 order by tarihi desc, blkodu desc",
            )
        finally:
            conn.close()

        by_cari: dict[Any, list[dict]] = {}
        for h in hareketler:
            rows = by_cari.setdefault(h["blcrkodu"], [])
            if len(rows) < statement_limit:
                rows.append({
                    "date": _iso(h["tarihi"]), "doc_no": _text(h["evrak_no"]),
                    "description": _text(h["aciklama"]),
                    "debit": _num(h["kpb_btut"]), "credit": _num(h["kpb_atut"]),
                })
        out = []
        for c in cariler:
            out.append({
                "source": SOURCE,
                "external_ref": _text(c["carikodu"]) or str(c["blkodu"]),
                "customer_name": _text(c["ticari_unvani"]) or _text(c["adi_soyadi"]),
                "currency": "TRY",
                "balance": round(_num(c["borc"]) - _num(c["alacak"]), 2),
                "as_of": _iso(datetime.now()),
                "statement": by_cari.get(c["blkodu"], []),
            })
        return out

    def list_quotations(self) -> list[dict]:
        """Geçerli (silinmemiş) teklifleri, kalemleriyle birlikte portalın `/publications` yükü olarak döner."""
        conn = self._open()
        try:
            basliklar = self._query(
                conn,
                "select blkodu, teklif_no, tarihi, carikodu, ticari_unvani, toplam_genel_kpb, "
                "gecerlilik_tarihi, aciklama from teklif where silindi = 0 order by blkodu",
            )
            kalemler = self._query(
                conn,
                "select bltkkodu, stokkodu, stok_adi, birimi, miktari, kpb_kdv_haricfy, "
                "kdv_orani, kpb_toplam_tutar, sira_no from teklifhr order by bltkkodu, sira_no",
            )
        finally:
            conn.close()

        lines_by: dict[Any, list[dict]] = {}
        for k in kalemler:
            lines_by.setdefault(k["bltkkodu"], []).append({
                "sku": _text(k["stokkodu"]), "name": _text(k["stok_adi"]), "unit": _text(k["birimi"]),
                "qty": _num(k["miktari"]), "unit_price": _num(k["kpb_kdv_haricfy"]),
                "vat_rate": _num(k["kdv_orani"]), "total": _num(k["kpb_toplam_tutar"]),
            })
        out = []
        for b in basliklar:
            out.append({
                "source": SOURCE,
                "external_ref": _text(b["teklif_no"]) or str(b["blkodu"]),
                "title": f"Teklif {_text(b['teklif_no'])}".strip(),
                "customer_name": _text(b["ticari_unvani"]),
                "currency": "TRY",
                "grand_total": _num(b["toplam_genel_kpb"]),
                "valid_until": _iso(b["gecerlilik_tarihi"]),
                "snapshot": {"lines": lines_by.get(b["blkodu"], []), "notes": _text(b["aciklama"])},
            })
        return out
