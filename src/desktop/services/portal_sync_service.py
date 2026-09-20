"""
TOYA ERP - Online Teklif Portalı Senkron Servisi

Yerel teklifi cPanel'deki PHP portalına (bkz. `portal/`) yayınlar ve müşterinin
portalda verdiği kabul / ret / karşı teklif kararlarını geri çekip yerel
teklife uygular. Ağ yalnızca bu servisten çıkar; portal ERP'yi tanımaz.

Yayın bilgisi (token/link) teklif tablosuna kolon eklenmeden, `settings_store`
üzerinde `portal.pub.<teklif_no>` anahtarıyla saklanır.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import requests
from sqlalchemy import select

from src.core.models import Quotation
from src.desktop.services.settings_store import get_setting, set_setting

logger = logging.getLogger(__name__)

SOURCE = "toya"
KEY_BASE_URL = "portal.base_url"
KEY_API_KEY = "portal.api_key"
KEY_CURSOR = "portal.last_event_id"
REQUEST_TIMEOUT = 15


def _pub_key(quotation_number: str) -> str:
    return f"portal.pub.{quotation_number}"


@dataclass
class PortalResult:
    success: bool
    message: str = ""
    url: str = ""
    applied: list[dict] = field(default_factory=list)


def is_configured(db) -> bool:
    return bool(get_setting(db, KEY_BASE_URL) and get_setting(db, KEY_API_KEY))


def _base(db) -> str:
    return (get_setting(db, KEY_BASE_URL, "") or "").rstrip("/")


def _headers(db) -> dict:
    return {"X-API-Key": get_setting(db, KEY_API_KEY, "") or "", "Content-Type": "application/json"}


def build_payload(quotation: Quotation, *, allow_counter: bool = True) -> dict:
    """Teklifin portala gönderilecek anlık görüntüsü (kalem ek alanları `extras`)."""
    lines = []
    for it in sorted(quotation.lines, key=lambda x: x.line_order or 0):
        lines.append({
            "name": it.name or it.product_name_free or "",
            "sku": it.sku or it.product_code_free or "",
            "note": it.note2 or "",
            "qty": it.quantity,
            "unit": it.unit,
            "unit_price": it.unit_price,
            "discount_rate": it.discount_rate,
            "vat_rate": it.vat_rate,
            "total": it.total_price or it.total_amount,
        })
    return {
        "source": SOURCE,
        "external_ref": quotation.quotation_number,
        "title": quotation.title,
        "customer_name": quotation.customer.fullname if quotation.customer else quotation.customer_name_free,
        "customer_email": quotation.email_free,
        "currency": quotation.currency,
        "grand_total": quotation.grand_total,
        "valid_until": quotation.valid_until.strftime("%Y-%m-%d %H:%M:%S") if quotation.valid_until else None,
        "allow_counter": allow_counter,
        "snapshot": {"lines": lines, "notes": quotation.notes or ""},
    }


def _post(db, path: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{_base(db)}/api/v1{path}", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_headers(db), timeout=REQUEST_TIMEOUT,
    )


def publish_quotation(db, quotation_id: int, *, allow_counter: bool = True) -> PortalResult:
    if not is_configured(db):
        return PortalResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
    q = db.get(Quotation, quotation_id)
    if q is None:
        return PortalResult(False, "Teklif bulunamadı.")
    try:
        resp = _post(db, "/publications", build_payload(q, allow_counter=allow_counter))
    except requests.RequestException as exc:
        logger.warning("Portala yayın başarısız: %s", exc)
        return PortalResult(False, f"Portala erişilemedi: {exc}")

    body = _safe_json(resp)
    if resp.status_code != 200 or not body.get("ok"):
        err = body.get("error") or f"HTTP {resp.status_code}"
        msg = "Bu teklif için müşteri kararı zaten verilmiş." if err == "already_decided" else f"Yayın reddedildi: {err}"
        return PortalResult(False, msg)

    url = f"{_base(db)}/view.php?t={body['token']}"
    set_setting(db, _pub_key(q.quotation_number), json.dumps({"token": body["token"], "url": url}))
    if q.status == "draft":
        q.status = "sent"
        db.commit()
    return PortalResult(True, "Teklif portalda yayınlandı.", url=url)


def get_publication(db, quotation_number: str) -> dict | None:
    raw = get_setting(db, _pub_key(quotation_number))
    return json.loads(raw) if raw else None


def revoke_quotation(db, quotation_id: int) -> PortalResult:
    q = db.get(Quotation, quotation_id)
    if q is None or not is_configured(db):
        return PortalResult(False, "Teklif bulunamadı veya portal tanımlı değil.")
    try:
        resp = _post(db, "/publications/revoke", {"source": SOURCE, "external_ref": q.quotation_number})
    except requests.RequestException as exc:
        return PortalResult(False, f"Portala erişilemedi: {exc}")
    ok = resp.status_code == 200 and _safe_json(resp).get("ok")
    if ok:
        set_setting(db, _pub_key(q.quotation_number), "")
    return PortalResult(bool(ok), "Yayın iptal edildi." if ok else "Yayın iptal edilemedi.")


def pull_decisions(db, *, timeout: int = REQUEST_TIMEOUT) -> PortalResult:
    """Portaldaki yeni karar olaylarını çeker ve yerel tekliflere uygular.

    accept -> status 'accepted', reject -> 'rejected'; counter statüyü değiştirmez,
    tutar/not teklif notlarına eklenir. İmleç yalnızca başarılı uygulamadan sonra ilerler."""
    if not is_configured(db):
        return PortalResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
    cursor = int(get_setting(db, KEY_CURSOR, "0") or 0)
    try:
        resp = requests.get(
            f"{_base(db)}/api/v1/decisions", params={"after": cursor},
            headers=_headers(db), timeout=timeout,
        )
    except requests.RequestException as exc:
        return PortalResult(False, f"Portala erişilemedi: {exc}")
    body = _safe_json(resp)
    if resp.status_code != 200 or not body.get("ok"):
        return PortalResult(False, f"Kararlar alınamadı: HTTP {resp.status_code}")

    applied: list[dict] = []
    last_id = cursor
    for ev in body.get("decisions", []):
        last_id = max(last_id, int(ev["event_id"]))
        if ev.get("source") != SOURCE:
            continue
        q = db.scalar(select(Quotation).where(Quotation.quotation_number == ev["external_ref"]))
        if q is None:
            continue
        kind = ev["event_type"]
        if kind == "accept":
            q.status = "accepted"
        elif kind == "reject":
            q.status = "rejected"
        elif kind == "counter":
            line = f"[Portal karşı teklif] {ev.get('counter_amount')} — {ev.get('counter_note') or ''}".strip()
            q.notes = f"{q.notes}\n{line}" if q.notes else line
        if kind in ("accept", "reject") and ev.get("decision_note"):
            line = f"[Portal müşteri notu] {ev['decision_note']}"
            q.notes = f"{q.notes}\n{line}" if q.notes else line
        applied.append({"quotation_number": q.quotation_number, "event": kind})
    db.commit()
    set_setting(db, KEY_CURSOR, str(last_id))
    return PortalResult(True, f"{len(applied)} karar uygulandı.", applied=applied)


def _acc_key(source: str, ref: str) -> str:
    return f"portal.acc.{source}:{ref}"


def publish_account_payload(db, payload: dict) -> PortalResult:
    """Hazır bir hesap özeti yükünü (`/accounts`) portala gönderir ve linki saklar."""
    if not is_configured(db):
        return PortalResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
    try:
        resp = _post(db, "/accounts", payload)
    except requests.RequestException as exc:
        return PortalResult(False, f"Portala erişilemedi: {exc}")
    body = _safe_json(resp)
    if resp.status_code != 200 or not body.get("ok"):
        return PortalResult(False, f"Hesap yayını reddedildi: {body.get('error') or resp.status_code}")
    url = f"{_base(db)}/account.php?t={body['token']}"
    set_setting(db, _acc_key(payload["source"], payload["external_ref"]),
                json.dumps({"token": body["token"], "url": url}))
    return PortalResult(True, "Cari hesap özeti portalda yayınlandı.", url=url)


def build_customer_account_payload(customer) -> dict:
    """TOYA carisinin bakiyesi (`Customer.balance`, + = müşteri borçlu). Gerçek hareket defteri
    henüz olmadığından hareket listesi boş gönderilir."""
    return {
        "source": SOURCE,
        "external_ref": customer.customer_code or str(customer.id),
        "customer_name": customer.fullname,
        "currency": "TRY",
        "balance": float(getattr(customer, "balance", 0) or 0),
        "statement": [],
    }


def publish_customer_account(db, customer_id: int) -> PortalResult:
    from src.core.models import Customer

    customer = db.get(Customer, customer_id)
    if customer is None:
        return PortalResult(False, "Cari bulunamadı.")
    return publish_account_payload(db, build_customer_account_payload(customer))


def sync_connector(db, connector) -> PortalResult:
    """Bir kaynak bağlayıcıdan (örn. Wolvox) cari hesap özetlerini ve teklifleri okuyup portala yayınlar.

    Bağlayıcı salt okunurdur; portalda verilen kararlar kaynağa geri yazılmaz."""
    if not is_configured(db):
        return PortalResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
    accounts = connector.list_accounts()
    quotations = connector.list_quotations()
    ok_acc = ok_q = skipped = 0
    errors: list[str] = []

    for payload in accounts:
        r = publish_account_payload(db, payload)
        if r.success:
            ok_acc += 1
        elif "erişilemedi" in r.message:
            return PortalResult(False, r.message)
        else:
            errors.append(f"{payload['external_ref']}: {r.message}")

    for payload in quotations:
        try:
            resp = _post(db, "/publications", payload)
        except requests.RequestException as exc:
            return PortalResult(False, f"Portala erişilemedi: {exc}")
        body = _safe_json(resp)
        if resp.status_code == 200 and body.get("ok"):
            ok_q += 1
            url = f"{_base(db)}/view.php?t={body['token']}"
            set_setting(db, f"portal.pub.{payload['source']}:{payload['external_ref']}",
                        json.dumps({"token": body["token"], "url": url}))
        elif body.get("error") == "already_decided":
            skipped += 1
        else:
            errors.append(f"{payload['external_ref']}: {body.get('error') or resp.status_code}")

    msg = f"{ok_acc} cari, {ok_q} teklif yayınlandı"
    if skipped:
        msg += f", {skipped} teklif kararlı olduğundan atlandı"
    if errors:
        msg += f"; {len(errors)} hata ({errors[0]})"
    return PortalResult(not errors, msg + ".")


def test_connection(db) -> PortalResult:
    """Adres ve API anahtarını, yan etkisiz bir karar sorgusuyla doğrular."""
    if not is_configured(db):
        return PortalResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
    try:
        resp = requests.get(
            f"{_base(db)}/api/v1/decisions", params={"after": 2147483647},
            headers=_headers(db), timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        return PortalResult(False, f"Portala erişilemedi: {exc}")
    if resp.status_code == 200 and _safe_json(resp).get("ok"):
        return PortalResult(True, "Bağlantı başarılı.")
    if resp.status_code == 401:
        return PortalResult(False, "API anahtarı geçersiz.")
    return PortalResult(False, f"Beklenmeyen yanıt: HTTP {resp.status_code}")


def _safe_json(resp: requests.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
