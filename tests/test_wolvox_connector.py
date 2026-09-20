"""Wolvox salt okunur bağlayıcısı + portal hesap/toplu senkron testleri."""

from __future__ import annotations

import json
import os
from datetime import date, datetime

import pytest

from src.core.models import Customer
from src.desktop.connectors.wolvox_connector import WolvoxConnector, WolvoxError
from src.desktop.services import portal_sync_service as svc
from src.desktop.services.settings_store import get_setting, set_setting

BASE = "https://ornek.example/portal"


class FakeCursor:
    def __init__(self, tables):
        self.tables = tables
        self.description = []
        self._rows = []

    def execute(self, sql, params=()):
        s = " ".join(sql.lower().split())
        assert s.startswith("select"), "yalnızca SELECT beklenir"
        if "from cari c left join carihr" in s:
            self._set(["blkodu", "carikodu", "ticari_unvani", "adi_soyadi", "borc", "alacak"], self.tables["cari"])
        elif "from carihr where" in s:
            self._set(["blcrkodu", "tarihi", "evrak_no", "aciklama", "kpb_btut", "kpb_atut"], self.tables["carihr"])
        elif "from teklif where" in s:
            self._set(["blkodu", "teklif_no", "tarihi", "carikodu", "ticari_unvani",
                       "toplam_genel_kpb", "gecerlilik_tarihi", "aciklama"], self.tables["teklif"])
        elif "from teklifhr" in s:
            self._set(["bltkkodu", "stokkodu", "stok_adi", "birimi", "miktari", "kpb_kdv_haricfy",
                       "kdv_orani", "kpb_toplam_tutar", "sira_no"], self.tables["teklifhr"])
        elif "count(*) as n from cari" in s:
            self._set(["n"], [(13,)])
        else:
            raise AssertionError(f"beklenmeyen sorgu: {sql}")

    def _set(self, cols, rows):
        self.description = [(c.upper(),) for c in cols]
        self._rows = rows

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class FakeConn:
    def __init__(self, tables):
        self.tables = tables
        self.closed = False

    def cursor(self):
        return FakeCursor(self.tables)

    def close(self):
        self.closed = True


def _tables():
    return {
        "cari": [(1, "KONYA2", "MJJ Production", None, 5000.0, 200.0), (2, "GENEL", None, "Genel Müşteri", 0, 0)],
        "carihr": [
            (1, datetime(2026, 9, 1), "FTR-1", "Satış", 5000.0, 0.0),
            (1, datetime(2026, 9, 2), "TAH-1", "Tahsilat", 0.0, 200.0),
        ],
        "teklif": [(10, "TKL-7", date(2026, 9, 3), "KONYA2", "MJJ Production", 1180.0, date(2026, 10, 3), "Not")],
        "teklifhr": [(10, "ST1", "Kalem", "ADET", 2.0, 500.0, 18.0, 1000.0, 1)],
    }


def _connector(tables=None):
    tables = tables or _tables()
    return WolvoxConnector(database="x.fdb", connect=lambda **kw: FakeConn(tables))


# ---- bağlayıcı --------------------------------------------------------
def test_accounts_balance_is_debit_minus_credit_and_statement_attached():
    accs = {a["external_ref"]: a for a in _connector().list_accounts()}
    a = accs["KONYA2"]
    assert a["source"] == "wolvox" and a["customer_name"] == "MJJ Production"
    assert a["balance"] == 4800.0
    assert [r["doc_no"] for r in a["statement"]] == ["FTR-1", "TAH-1"]
    assert a["statement"][0]["debit"] == 5000.0 and a["statement"][1]["credit"] == 200.0
    assert accs["GENEL"]["customer_name"] == "Genel Müşteri"  # ünvan yoksa ad-soyad
    assert accs["GENEL"]["balance"] == 0.0 and accs["GENEL"]["statement"] == []


def test_quotations_carry_lines_and_totals():
    q = _connector().list_quotations()[0]
    assert q["external_ref"] == "TKL-7" and q["grand_total"] == 1180.0
    assert q["valid_until"] == "2026-10-03"
    line = q["snapshot"]["lines"][0]
    assert line["name"] == "Kalem" and line["qty"] == 2.0 and line["unit_price"] == 500.0


def test_connector_refuses_non_select():
    c = _connector()
    with pytest.raises(WolvoxError):
        c._query(FakeConn(_tables()), "delete from cari")


def test_connection_errors_become_wolvox_error():
    def boom(**kw):
        raise OSError("bağlantı reddedildi")
    with pytest.raises(WolvoxError) as e:
        WolvoxConnector(database="x", connect=boom).test_connection()
    assert "bağlanılamadı" in str(e.value)


def test_from_settings_requires_database_path(db_session):
    with pytest.raises(WolvoxError):
        WolvoxConnector.from_settings(db_session)
    set_setting(db_session, "wolvox.database", r"C:\x\WOLVOX.FDB")
    c = WolvoxConnector.from_settings(db_session)
    assert c.database == r"C:\x\WOLVOX.FDB" and c.port == 3050 and c.user == "SYSDBA"


# ---- portal hesap yayını / toplu senkron ---------------------------------
def _configure(db):
    set_setting(db, svc.KEY_BASE_URL, BASE)
    set_setting(db, svc.KEY_API_KEY, "k")


def test_publish_customer_account_sends_balance(db_session, mock_api):
    _configure(db_session)
    c = Customer(fullname="ACME", marketplace="local", customer_code="C1", balance=150.5)
    db_session.add(c)
    db_session.commit()
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/accounts", status=200, json={"ok": True, "token": "e" * 64})
    r = svc.publish_customer_account(db_session, c.id)
    assert r.success and r.url == f"{BASE}/account.php?t={'e' * 64}"
    sent = json.loads(mock_api.calls[0].request.body)
    assert sent["external_ref"] == "C1" and sent["balance"] == 150.5 and sent["source"] == "toya"
    assert json.loads(get_setting(db_session, "portal.acc.toya:C1"))["token"] == "e" * 64


def test_sync_connector_publishes_accounts_and_quotations(db_session, mock_api):
    _configure(db_session)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/accounts", status=200, json={"ok": True, "token": "a" * 64})
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/accounts", status=200, json={"ok": True, "token": "b" * 64})
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/publications", status=200, json={"ok": True, "token": "c" * 64})
    r = svc.sync_connector(db_session, _connector())
    assert r.success and "2 cari, 1 teklif" in r.message
    assert get_setting(db_session, "portal.pub.wolvox:TKL-7") is not None


def test_sync_skips_decided_quotations_and_reports_errors(db_session, mock_api):
    _configure(db_session)
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/accounts", status=200, json={"ok": True, "token": "a" * 64})
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/accounts", status=422, json={"ok": False, "error": "invalid_payload"})
    mock_api.add(mock_api.POST, f"{BASE}/api/v1/publications", status=409,
                 json={"ok": False, "error": "already_decided"})
    r = svc.sync_connector(db_session, _connector())
    assert r.success is False
    assert "1 cari, 0 teklif" in r.message and "1 teklif kararlı" in r.message and "1 hata" in r.message


# ---- gerçek Wolvox örnek veritabanı (yalnızca yerelde, Firebird ayaktaysa) -----
_FDB = r"C:\AKINSOFT\Wolvox9\Database_FB\WOLVOX.FDB"


@pytest.mark.skipif(not os.path.exists(_FDB), reason="Wolvox örnek veritabanı bu makinede yok")
def test_real_wolvox_sample_database_balances():
    c = WolvoxConnector(database=_FDB)
    try:
        c.test_connection()
    except WolvoxError:
        pytest.skip("Firebird sunucusuna ulaşılamıyor")
    accs = {a["external_ref"]: a for a in c.list_accounts()}
    assert len(accs) >= 1
    assert all(isinstance(a["balance"], float) for a in accs.values())
    assert c.list_quotations() is not None
