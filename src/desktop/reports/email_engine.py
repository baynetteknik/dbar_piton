"""
ToyaUI — E-posta Gönderme Motoru
Dolibarr offer modülünden uyarlanan Python versiyonu.
SMTP ile e-posta, güvenli token ile paylaşım linki.

Kullanım:
    engine = EmailEngine(smtp_config)
    engine.send_teklif_email(
        to_email="musteri@example.com",
        teklif_data=data,
        pdf_bytes=pdf_bytes,
        public_url="https://...",
    )
"""

import logging
import secrets
import smtplib
import string
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


def generate_public_token(length: int = 32) -> str:
    """Güvenli rastgele token üret (URL-safe)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SMTPConfig:
    """SMTP ayarları."""

    def __init__(
        self,
        host: str = "smtp.gmail.com",
        port: int = 587,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        from_name: str = "TOYA ERP",
        from_email: str = "",
    ):
        self.host      = host
        self.port      = port
        self.username  = username
        self.password  = password
        self.use_tls   = use_tls
        self.from_name = from_name
        self.from_email = from_email or username

    @classmethod
    def from_db(cls, db_session) -> "SMTPConfig":
        """DB'deki sistem ayarlarından SMTP config oluştur."""
        try:
            from sqlalchemy import select, text
            from src.core.models import SystemSetting

            def get(key, default=""):
                row = db_session.scalar(
                    select(SystemSetting).where(SystemSetting.key == key)
                )
                return row.value if row else default

            return cls(
                host=get("smtp.host", "smtp.gmail.com"),
                port=int(get("smtp.port", "587")),
                username=get("smtp.username", ""),
                password=get("smtp.password", ""),
                use_tls=get("smtp.use_tls", "1") == "1",
                from_name=get("smtp.from_name", "TOYA ERP"),
                from_email=get("smtp.from_email", ""),
            )
        except Exception as e:
            logger.error(f"SMTP config DB'den yüklenemedi: {e}")
            return cls()


class EmailEngine:
    """
    SMTP e-posta motoru.
    Dolibarr offer modülündeki send_mail.php mantığının Python karşılığı.
    """

    def __init__(self, smtp_config: SMTPConfig | None = None):
        self.config = smtp_config or SMTPConfig()

    def _build_teklif_html_body(
        self,
        musteri_adi: str,
        teklif_no: str,
        firma_adi: str,
        public_url: str | None,
        vade_tarihi: str | None = None,
    ) -> str:
        """Dolibarr send_mail.php'deki HTML e-posta şablonunun Python versiyonu."""
        link_button = ""
        if public_url:
            link_button = f"""
            <div style="text-align:center; margin:28px 0;">
                <a href="{public_url}"
                   style="background-color:#22c55e; color:#ffffff;
                          padding:14px 28px; text-decoration:none;
                          border-radius:8px; display:inline-block;
                          font-weight:600; font-size:16px;
                          box-shadow:0 4px 6px -1px rgba(34,197,94,0.2);">
                    📄 Teklifi İncele ve Yanıtla
                </a>
            </div>
            """

        vade_uyari = ""
        if vade_tarihi:
            vade_uyari = f"""
            <p style="color:#ef4444; font-size:13px; font-weight:500; margin-top:20px;">
                ⚠️ Not: Bu teklif <strong>{vade_tarihi}</strong> tarihine kadar geçerlidir.
            </p>
            """

        return f"""
        <div style="font-family:'Inter',sans-serif; max-width:600px; margin:0 auto;
                    padding:20px; border:1px solid #e2e8f0; border-radius:12px;
                    background-color:#ffffff;">

            <h2 style="color:#3b82f6; font-size:20px; font-weight:700; margin-bottom:16px;">
                Sayın {musteri_adi},
            </h2>

            <p style="color:#475569; font-size:15px; line-height:1.6; margin-bottom:20px;">
                Sizin için hazırladığımız <strong>{teklif_no}</strong> referans numaralı
                teklifimiz onaylanmış ve incelemenize sunulmuştur.
            </p>

            <p style="color:#475569; font-size:15px; line-height:1.6; margin-bottom:20px;">
                Teklif detaylarını incelemek, onaylamak veya revizyon talep etmek için
                aşağıdaki butona tıklayabilirsiniz:
            </p>

            {link_button}
            {vade_uyari}

            <hr style="border:0; border-top:1px solid #e2e8f0; margin:24px 0;">

            <p style="color:#64748b; font-size:12px; line-height:1.5; margin-bottom:0;">
                Saygılarımızla,<br>
                <strong>{firma_adi}</strong>
            </p>
        </div>
        """

    def send_teklif_email(
        self,
        to_email: str,
        teklif_data: dict[str, Any],
        pdf_bytes: bytes | None = None,
        public_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        Teklif e-postası gönder.

        Returns:
            (success: bool, message: str)
        """
        try:
            firma   = teklif_data.get("firma", {})
            musteri = teklif_data.get("musteri", {})
            belge   = teklif_data.get("belge", {})

            musteri_adi = musteri.get("adi", "Sayın Müşterimiz")
            teklif_no   = belge.get("teklif_no", "")
            firma_adi   = firma.get("adi", "TOYA ERP")
            vade_tarihi = belge.get("vade", "")

            subject = f"Teklif {teklif_no} - Yeni Teklifiniz Hazır | {firma_adi}"
            html_body = self._build_teklif_html_body(
                musteri_adi=musteri_adi,
                teklif_no=teklif_no,
                firma_adi=firma_adi,
                public_url=public_url,
                vade_tarihi=vade_tarihi,
            )

            # MIME mesajı oluştur
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"]      = to_email

            # HTML gövde
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # PDF eki (varsa)
            if pdf_bytes:
                attachment = MIMEBase("application", "pdf")
                attachment.set_payload(pdf_bytes)
                encoders.encode_base64(attachment)
                filename = f"Teklif_{teklif_no}.pdf".replace("/", "-").replace(" ", "_")
                attachment.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{filename}"'
                )
                msg.attach(attachment)

            # SMTP gönder
            with smtplib.SMTP(self.config.host, self.config.port) as server:
                if self.config.use_tls:
                    server.starttls()
                if self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)
                server.send_message(msg, to_addrs=[to_email])

            logger.info(f"E-posta gönderildi: {to_email} — {teklif_no}")
            return True, f"E-posta başarıyla gönderildi: {to_email}"

        except smtplib.SMTPAuthenticationError:
            msg = "SMTP kimlik doğrulama hatası. Kullanıcı adı/şifre kontrol edin."
            logger.error(msg)
            return False, msg
        except smtplib.SMTPConnectError:
            msg = f"SMTP sunucusuna bağlanılamadı: {self.config.host}:{self.config.port}"
            logger.error(msg)
            return False, msg
        except Exception as e:
            logger.error(f"E-posta gönderilemedi: {e}")
            return False, str(e)

    def test_connection(self) -> tuple[bool, str]:
        """SMTP bağlantısını test et."""
        try:
            with smtplib.SMTP(self.config.host, self.config.port, timeout=10) as server:
                if self.config.use_tls:
                    server.starttls()
                if self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)
            return True, "SMTP bağlantısı başarılı."
        except Exception as e:
            return False, str(e)
