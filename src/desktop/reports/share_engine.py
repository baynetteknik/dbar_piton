"""
ToyaUI — Teklif Paylaşım Motoru
Dolibarr offer modülünden uyarlanan Python versiyonu.
Token bazlı güvenli link, WhatsApp paylaşımı.

Kullanım:
    engine = ShareEngine(base_url="https://baynetbilisim.tr")
    token = engine.generate_token(teklif_id=42, days=30)
    url = engine.get_public_url(token)
    engine.share_whatsapp(url, musteri_adi="EMRE BEY", teklif_no="TEK-001")
"""

import hashlib
import logging
import secrets
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class ShareEngine:
    """
    Token bazlı güvenli teklif paylaşım motoru.
    Dolibarr offer modülündeki token.lib.php + public/view.php mantığının Python karşılığı.
    """

    def __init__(
        self,
        base_url: str = "",
        db_session=None,
    ):
        self.base_url   = base_url.rstrip("/")
        self.db         = db_session

    # ─────────────────────────────────────────────
    # TOKEN
    # ─────────────────────────────────────────────

    @staticmethod
    def generate_token(teklif_id: int, days: int = 30) -> str:
        """
        Dolibarr'daki generatePublicToken() fonksiyonunun Python karşılığı.
        Güvenli, tahmin edilemez token üretir.
        """
        random_part = secrets.token_hex(16)
        hash_part   = hashlib.sha256(
            f"{teklif_id}:{random_part}:{secrets.token_hex(8)}".encode()
        ).hexdigest()[:16]
        return f"{random_part}{hash_part}"

    def save_token(
        self,
        teklif_id: int,
        token: str,
        expires_days: int = 30,
    ) -> bool:
        """Token'ı DB'deki teklif kaydına kaydet."""
        if not self.db:
            return False
        try:
            from src.core.models import Quotation
            from sqlalchemy import select
            q = self.db.scalar(
                select(Quotation).where(Quotation.id == teklif_id)
            )
            if not q:
                return False
            expires_at = datetime.now() + timedelta(days=expires_days)
            q.public_token         = token
            q.public_token_expires = expires_at
            q.public_view_count    = 0
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Token kaydedilemedi: {e}")
            self.db.rollback()
            return False

    def get_or_create_token(
        self,
        teklif_id: int,
        expires_days: int = 30,
    ) -> str:
        """
        Mevcut token varsa döndür, yoksa yeni üret ve kaydet.
        Dolibarr'daki send.php davranışıyla aynı.
        """
        if self.db:
            try:
                from src.core.models import Quotation
                from sqlalchemy import select
                q = self.db.scalar(
                    select(Quotation).where(Quotation.id == teklif_id)
                )
                if q and hasattr(q, "public_token") and q.public_token:
                    # Süresi dolmamışsa mevcut token'ı kullan
                    if hasattr(q, "public_token_expires") and q.public_token_expires:
                        if q.public_token_expires > datetime.now():
                            return q.public_token
            except Exception:
                pass

        # Yeni token üret
        token = self.generate_token(teklif_id, expires_days)
        self.save_token(teklif_id, token, expires_days)
        return token

    # ─────────────────────────────────────────────
    # URL OLUŞTURMA
    # ─────────────────────────────────────────────

    def get_public_url(self, token: str) -> str:
        """Dolibarr'daki public/view.php?token=... mantığının Python karşılığı."""
        if self.base_url:
            return f"{self.base_url}/teklif/view?token={token}"
        # Local mod — token'ı direkt döndür
        return f"teklif://view?token={token}"

    # ─────────────────────────────────────────────
    # PANO'YA KOPYALA
    # ─────────────────────────────────────────────

    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        """Metni sistem panosuna kopyala."""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.clipboard().setText(text)
                return True
        except Exception:
            pass

        # Fallback — platform araçları
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["clip"], input=text.encode("utf-16"), check=True
                )
            elif sys.platform == "darwin":
                subprocess.run(
                    ["pbcopy"], input=text.encode(), check=True
                )
            else:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode(), check=True
                )
            return True
        except Exception as e:
            logger.error(f"Pano kopyalama hatası: {e}")
            return False

    # ─────────────────────────────────────────────
    # WHATSAPP PAYLAŞIM
    # ─────────────────────────────────────────────

    def share_whatsapp(
        self,
        url: str,
        musteri_adi: str = "",
        teklif_no: str = "",
        firma_adi: str = "",
    ) -> bool:
        """
        Dolibarr'daki "PAYLAŞ" butonunun Python karşılığı.
        WhatsApp Web ile mesaj gönder.
        """
        mesaj = f"Sayın {musteri_adi},\n\n"
        mesaj += f"{firma_adi} tarafından hazırlanan "
        mesaj += f"*{teklif_no}* numaralı teklifiniz hazır.\n\n"
        mesaj += f"Teklifi incelemek ve yanıtlamak için:\n{url}\n\n"
        mesaj += "_Saygılarımızla_"

        wa_url = f"https://wa.me/?text={quote(mesaj)}"
        try:
            webbrowser.open(wa_url)
            return True
        except Exception as e:
            logger.error(f"WhatsApp açılamadı: {e}")
            return False

    # ─────────────────────────────────────────────
    # PAYLAŞIM DİALOGU VERİSİ
    # ─────────────────────────────────────────────

    def get_share_data(
        self,
        teklif_id: int,
        teklif_data: dict[str, Any],
        expires_days: int = 30,
    ) -> dict[str, Any]:
        """
        Paylaşım dialogu için gereken tüm veriyi hazırla.
        Dolibarr'daki send.php'nin döndürdüğü veri yapısına karşılık gelir.
        """
        token      = self.get_or_create_token(teklif_id, expires_days)
        public_url = self.get_public_url(token)

        belge   = teklif_data.get("belge", {})
        musteri = teklif_data.get("musteri", {})
        firma   = teklif_data.get("firma", {})

        return {
            "token":       token,
            "public_url":  public_url,
            "teklif_no":   belge.get("teklif_no", ""),
            "musteri_adi": musteri.get("adi", ""),
            "musteri_email": musteri.get("email", ""),
            "firma_adi":   firma.get("adi", ""),
            "expires_days": expires_days,
            "expires_date": (
                datetime.now() + timedelta(days=expires_days)
            ).strftime("%d.%m.%Y"),
        }
