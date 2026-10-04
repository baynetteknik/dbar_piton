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

from src.core.models import Bildirim, Quotation
from src.desktop.services import portal_secret_store
from src.desktop.services.settings_store import get_setting, set_setting

logger = logging.getLogger(__name__)

SOURCE = "toya"
KEY_BASE_URL = "portal.base_url"
KEY_API_KEY = "portal.api_key"
KEY_CURSOR = "portal.last_event_id"
REQUEST_TIMEOUT = 15
#: Bazı paylaşımlı barındırma güvenlik duvarları (Imunify360 vb.) varsayılan
#: `python-requests/x.y` istemci imzasını bot sayıp 403 ile engelliyor; normal
#: bir tarayıcı gibi görünen bir User-Agent bu engeli aşar.
USER_AGENT = "TOYA-ERP-Agent/1.0"


MAX_LOGO_CHARS = 300_000


def build_company(quotation: Quotation) -> dict:
    """Portal teklif sayfasında gösterilecek firma bilgisi (logo, adres, iletişim, banka); teklif anındaki anlık görüntü."""
    from sqlalchemy.orm import object_session

    from src.core.models import Company

    session = object_session(quotation)
    c = session.get(Company, quotation.company_id or 1) if session is not None else None
    if c is None:
        return {}
    banks = []
    if c.bank_accounts_json:
        try:
            for b in json.loads(c.bank_accounts_json) or []:
                if b.get("iban"):
                    banks.append({k: b.get(k, "") for k in ("banka", "sube", "iban", "para_birimi")})
        except (ValueError, AttributeError):
            pass
    logo = c.logo_base64 or ""
    if logo and not logo.startswith("data:"):
        logo = "data:image/png;base64," + logo
    return {
        "name": c.title or c.short_name, "tax_office": c.tax_office or "", "tax_number": c.tax_number or "",
        "address": ", ".join(x for x in (c.address, c.district, c.city) if x),
        "phone": c.phone1 or "", "email": c.email or "", "website": c.website or "",
        "authorized": c.authorized_person or "", "banks": banks,
        "logo": logo if len(logo) <= MAX_LOGO_CHARS else "",
    }


def _pub_key(quotation_number: str) -> str:
    return f"portal.pub.{quotation_number}"


@dataclass
class PortalResult:
    success: bool
    message: str = ""
    url: str = ""
    applied: list[dict] = field(default_factory=list)


def is_configured(db) -> bool:
    return bool(get_setting(db, KEY_BASE_URL) and portal_secret_store.al(db, KEY_API_KEY))


def _base(db) -> str:
    return (get_setting(db, KEY_BASE_URL, "") or "").rstrip("/")


def _headers(db) -> dict:
    return {
        "X-API-Key": portal_secret_store.al(db, KEY_API_KEY),
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


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
            "currency": (it.doviz or "TRY"),          # satırın kendi para birimi (unit_price / total bu birimdedir)
            "kur": it.kur or 1.0,                     # TL'ye çevirme kuru
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
        "snapshot": {
            "lines": lines, "notes": quotation.notes or "",
            "issue_date": quotation.issue_date.strftime("%Y-%m-%d") if quotation.issue_date else None,
            "payment_plan": quotation.payment_plan or "",
            "totals": {
                "subtotal": quotation.subtotal, "discount": quotation.total_discount or quotation.discount_total,
                "vat": quotation.total_vat or quotation.vat_total, "grand_total": quotation.grand_total,
            },
            "company": build_company(quotation),
        },
    }


def _post(db, path: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{_base(db)}/api/v1{path}", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_headers(db), timeout=REQUEST_TIMEOUT,
    )


def trigger_apply(db, package_name: str, *, reinstall: bool = False) -> PortalResult:
    """FTP ile `update_inbox/`'a bırakılan güncelleme paketini sunucuda OTOMATİK kurar (bkz. PHP tarafı
    `bootstrap.php::portal_route` '/update/apply') — kullanıcının ayrıca `update.php`'ye girip elle
    'Kur'a basmasına gerek kalmaz. Online Portal (API adresi + anahtarı) tanımlı değilse bu adım
    SESSİZCE atlanır (hata değildir) — paket zaten sunucuda durur, elle kurulum her zaman geçerlidir."""
    if not is_configured(db):
        return PortalResult(False, "Online Portal API adresi/anahtarı tanımlı değil; otomatik kurulum atlandı "
                                   "(paket sunucuda — update.php'den elle kurabilirsiniz).")
    try:
        resp = _post(db, "/update/apply", {"package": package_name, "reinstall": reinstall})
    except requests.RequestException as exc:
        logger.warning("Otomatik kurulum isteği başarısız: %s", exc)
        return PortalResult(False, f"Otomatik kurulum isteğine ulaşılamadı: {exc}")
    body = _safe_json(resp)
    if resp.status_code != 200 or not body.get("ok"):
        return PortalResult(False, body.get("error") or f"Otomatik kurulum başarısız (HTTP {resp.status_code}).")
    return PortalResult(
        True, f"Kuruldu: {body.get('from')} → {body.get('to')} · {body.get('files', 0)} dosya",
        applied=[body],
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


def decisions_request(db) -> tuple[str, dict, int] | None:
    """Karar çekme isteğinin (adres, başlıklar, imleç) bilgisi; ağ çağrısı arka plan iş parçacığında yapılabilsin diye
    veritabanı okuması burada, ağ çağrısı `fetch_decisions`'ta ayrılmıştır. Portal tanımlı değilse None."""
    if not is_configured(db):
        return None
    return f"{_base(db)}/api/v1/decisions", _headers(db), int(get_setting(db, KEY_CURSOR, "0") or 0)


def fetch_decisions(url: str, headers: dict, cursor: int, timeout: int = REQUEST_TIMEOUT) -> tuple[dict | None, str]:
    """Yalnızca ağ (veritabanına dokunmaz; iş parçacığı güvenli). (gövde, hata) döner."""
    try:
        resp = requests.get(url, params={"after": cursor}, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return None, f"Portala erişilemedi: {exc}"
    body = _safe_json(resp)
    if resp.status_code != 200 or not body.get("ok"):
        return None, f"Kararlar alınamadı: HTTP {resp.status_code}"
    return body, ""


def pull_decisions(db, *, timeout: int = REQUEST_TIMEOUT) -> PortalResult:
    """Portaldaki yeni karar olaylarını çeker ve yerel tekliflere uygular.

    accept -> status 'accepted', reject -> 'rejected'; counter statüyü değiştirmez,
    tutar/not teklif notlarına eklenir. İmleç yalnızca başarılı uygulamadan sonra ilerler."""
    req = decisions_request(db)
    if req is None:
        return PortalResult(False, "Portal adresi veya API anahtarı tanımlı değil.")
    body, err = fetch_decisions(*req, timeout=timeout)
    if body is None:
        return PortalResult(False, err)
    return apply_decisions(db, req[2], body)


def apply_decisions(db, cursor: int, body: dict) -> PortalResult:
    """Çekilen karar olaylarını yerel tekliflere uygular, bildirim üretir, imleci ilerletir (ana iş parçacığında çağrılmalı)."""
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
        who = q.customer.fullname if q.customer else (q.customer_name_free or "Müşteri")
        no = q.quotation_number
        bildirim = None
        if kind == "accept":
            q.status = "accepted"
            bildirim = ("portal_kabul", f"{who} teklifi KABUL ETTİ", f"{no} numaralı teklif kabul edildi.", q.grand_total)
        elif kind == "reject":
            q.status = "rejected"
            bildirim = ("portal_red", f"{who} teklifi REDDETTİ", f"{no} numaralı teklif reddedildi.", q.grand_total)
        elif kind == "expire":
            if q.status == "sent":
                q.status = "expired"
                bildirim = ("portal_sure", f"{no} teklifinin süresi doldu", f"{who} için gönderilen teklif geçerlilik süresi içinde cevaplanmadı.", q.grand_total)
        elif kind == "counter":
            line = f"[Portal karşı teklif] {ev.get('counter_amount')} — {ev.get('counter_note') or ''}".strip()
            q.notes = "\n".join(x for x in (q.notes, line) if x)
            bildirim = ("portal_karsi", f"{who} karşı teklif verdi",
                        f"{no}: teklif {q.grand_total:,.2f} {q.currency}, karşı teklif {float(ev.get('counter_amount') or 0):,.2f} {q.currency}"
                        + (f" — {ev['counter_note']}" if ev.get("counter_note") else ""), ev.get("counter_amount"))
        if kind in ("accept", "reject") and ev.get("decision_note"):
            line = f"[Portal müşteri notu] {ev['decision_note']}"
            q.notes = "\n".join(x for x in (q.notes, line) if x)
            if bildirim is not None:
                bildirim = (*bildirim[:2], f"{bildirim[2]} Not: {ev['decision_note']}", bildirim[3])
        item = {"quotation_number": no, "event": kind}
        if bildirim is not None:
            db.add(Bildirim(tur=bildirim[0], baslik=bildirim[1], mesaj=bildirim[2], ilgili_tur="teklif", ilgili_no=no,
                            tutar=bildirim[3], okundu=False))
            item["baslik"], item["tur"] = bildirim[1], bildirim[0]
        applied.append(item)
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


def build_customer_account_payload(db, customer) -> dict:
    """TOYA carisinin güncel bakiyesi ve hareket dökümü, `CariHareketService`'in gerçek defterinden (yerel para
    karşılığı; bkz. `money_service.yerel_para`). `account.php` her satırda `{date, doc_no, description, debit,
    credit}` bekler — bkz. `portal/public/account.php`. Tam geçmiş gönderilir (sayfalama yok, "hesap özeti"
    müşterinin görebileceği TEK doğru kaynak olsun diye kısmi/kesik gönderilmez)."""
    from datetime import date as _date

    from src.desktop.services import money_service
    from src.desktop.services.cari_hareket_service import CariHareketService

    svc = CariHareketService(db)
    statement = [
        {
            "date": satir["hareket"].tarih.strftime("%d.%m.%Y") if satir["hareket"].tarih else "",
            "doc_no": satir["hareket"].belge_no or (satir["hareket"].fis.fis_no if satir["hareket"].fis else ""),
            "description": satir["hareket"].aciklama or "",
            "debit": satir["borc"],
            "credit": satir["alacak"],
        }
        for satir in svc.ekstre(customer.id)
    ]
    return {
        "source": SOURCE,
        "external_ref": customer.customer_code or str(customer.id),
        "customer_name": customer.fullname,
        "currency": money_service.yerel_para(db),
        "balance": svc.cari_bakiye(customer.id),
        "as_of": _date.today().strftime("%d.%m.%Y"),
        "statement": statement,
    }


def publish_customer_account(db, customer_id: int) -> PortalResult:
    from src.core.models import Customer

    customer = db.get(Customer, customer_id)
    if customer is None:
        return PortalResult(False, "Cari bulunamadı.")
    return publish_account_payload(db, build_customer_account_payload(db, customer))


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
