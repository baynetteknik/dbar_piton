"""
TOYA ERP - Yedek Raporu E-postası

`build_report` metni üretir (kullanıcı girdileri HTML'de kaçırılır). `send_report` yalnızca işin bildirim modu
izin veriyorsa gönderir ("failure": hata/uyarıda, "always": her zaman, "never": hiç). Gönderim hatası yedeği
başarısız yapmaz; yalnızca döndürülen mesajda bildirilir. Mevcut SMTP ayarları (`EmailEngine`) kullanılır.
"""

from __future__ import annotations

import html
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.desktop.services.backup.models import BackupJob
from src.desktop.services.backup.runner import RunResult

logger = logging.getLogger(__name__)

_LABEL = {"ok": "BAŞARILI", "warning": "UYARI", "error": "HATA", "nochange": "DEĞİŞİKLİK YOK"}


EVENTS = {"ok": "✅ Başarıyla tamamlanan görevler", "warning": "⚠ Uyarıyla tamamlananlar (dosya/hedef atlandı)",
          "error": "❌ Hatalar", "nochange": "⏭ Değişiklik yok (yedek alınmadı)"}
CHANNELS = {"email": "📧 E-posta", "app": "🔔 Uygulama içi bildirim"}


def events_of(notify: dict) -> set[str]:
    """Bildirim istenen sonuçlar. Yeni kayıtlarda `events` listesi; eski kayıtlarda `mode` (never/failure/always) buna çevrilir."""
    if "events" in notify:
        return {e for e in notify["events"] if e in EVENTS}
    return {"never": set(), "failure": {"error", "warning"}, "always": set(EVENTS)}.get(notify.get("mode", "never"), set())


def channels_of(notify: dict) -> set[str]:
    """Bildirim kanalları. Eski kayıtlarda e-posta (mode != never ise) + uygulama içi bildirim."""
    if "channels" in notify:
        return {c for c in notify["channels"] if c in CHANNELS}
    return {"email", "app"}


def should_notify(job: BackupJob, res: RunResult) -> bool:
    """E-posta gönderilmeli mi: sonuç türü seçili olaylardan biri ve e-posta kanalı açık."""
    return res.status in events_of(job.notify) and "email" in channels_of(job.notify)


def should_toast(job: BackupJob, res: RunResult) -> bool:
    """Uygulama içi bildirim gösterilmeli mi. Eski kayıtlarda (`events` yok) her sonuç gösterilir (önceki davranış)."""
    if "events" not in job.notify:
        return True
    return res.status in events_of(job.notify) and "app" in channels_of(job.notify)


def build_report(job: BackupJob, res: RunResult) -> tuple[str, str, str]:
    """(konu, düz metin, html)"""
    label = _LABEL.get(res.status, res.status)
    subject = f"[TOYA Yedek] {job.name}: {label}"
    lines = [f"İş: {job.name}", f"Sonuç: {label}", f"Süre: {res.seconds:.1f} sn", res.message]
    for name, ok, msg in res.uploads:
        lines.append(f"  {'✔' if ok else '✘'} {name}: {msg}")
    lines += [f"  ! {w}" for w in res.warnings[:20]]
    text = "\n".join(lines)
    color = {"ok": "#15803d", "warning": "#b45309", "error": "#b91c1c"}.get(res.status, "#334155")
    rows = "".join(f"<li>{'✔' if ok else '✘'} <b>{html.escape(n)}</b>: {html.escape(m)}</li>" for n, ok, m in res.uploads)
    warn = "".join(f"<li>{html.escape(w)}</li>" for w in res.warnings[:20])
    body = (f"<div style='font-family:Segoe UI,sans-serif;max-width:560px'><h2 style='color:{color}'>{html.escape(job.name)} — {label}</h2>"
            f"<p>{html.escape(res.message)}</p><p style='color:#64748b'>Süre: {res.seconds:.1f} sn</p>"
            + (f"<ul>{rows}</ul>" if rows else "") + (f"<p><b>Atlanan dosyalar</b></p><ul>{warn}</ul>" if warn else "") + "</div>")
    return subject, text, body


def send_report(job: BackupJob, res: RunResult, engine, default_to: str = "") -> tuple[bool, str]:
    """@return (gönderildi mi, açıklama). Gönderilmesi gerekmiyorsa (False, '')."""
    if not should_notify(job, res):
        return False, ""
    to = (job.notify.get("to") or default_to or "").strip()
    if not to or "@" not in to:
        return False, "Bildirim alıcısı tanımlı değil."
    subject, text, body = build_report(job, res)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{engine.config.from_name} <{engine.config.from_email}>"
    msg["To"] = to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(body, "html", "utf-8"))
    try:
        engine._send(msg, [to])
        return True, f"Rapor gönderildi: {to}"
    except Exception as exc:  # noqa: BLE001 - e-posta hatası yedeği bozmamalı
        logger.warning("Yedek raporu gönderilemedi: %s", exc.__class__.__name__)
        return False, f"Rapor e-postası gönderilemedi ({exc.__class__.__name__})."
