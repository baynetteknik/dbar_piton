"""
TOYA ERP - AuthService

Kimlik doğrulama, ard arda hatalı girişte giriş kilidi ve şifre kurtarma
(güvenlik soruları / tek kullanımlık kurtarma kodu / e-posta ile sıfırlama)
mantığını tek yerde toplar. UI katmanı (login_window, setup_wizard,
password_recovery_dialog) yalnızca bu servisi çağırır.

Parola/cevap/kod hash'lemesi `user_service.hash_password` ile aynı algoritmadır
(mevcut kod tabanıyla uyum için).
"""

from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select

from src.core.models import User
from src.desktop.services import settings_store
from src.desktop.services.user_service import hash_password, verify_password

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Sabitler / varsayılanlar
# ----------------------------------------------------------------------

# (ard arda hatalı deneme sayısı, o denemede uygulanacak kilit saniyesi).
# İlk 2 denemede kilit yok; 3'ten itibaren artan. Genel Ayarlar'dan
# `security.lockout.schedule` (JSON) ile değiştirilebilir.
DEFAULT_LOCKOUT_SCHEDULE: list[list[int]] = [[3, 30], [4, 60], [5, 300]]

DEFAULT_AUTOCLOSE_SECONDS = 10
RESET_TOKEN_TTL_MIN = 30
RECOVERY_CODE_BLOCKS = 3          # XXXX-XXXX-XXXX
RECOVERY_CODE_BLOCK_LEN = 4

SECURITY_QUESTION_PRESETS = [
    "İlkokul öğretmeninizin soyadı nedir?",
    "İlk evcil hayvanınızın adı neydi?",
    "Annenizin kızlık soyadı nedir?",
    "Doğduğunuz şehir neresidir?",
    "İlk arabanızın markası neydi?",
    "En sevdiğiniz öğretmenin adı nedir?",
    "Çocuklukta en yakın arkadaşınızın adı neydi?",
]

# SystemSetting anahtarları
KEY_LOCKOUT_ENABLED = "security.lockout.enabled"
KEY_LOCKOUT_SCHEDULE = "security.lockout.schedule"
KEY_AUTOCLOSE_SECONDS = "security.login_popup.autoclose_seconds"
KEY_AUTOCLOSE_DISABLED = "security.login_popup.autoclose_disabled"
KEY_RECOVERY_SQ_ENABLED = "security.recovery.security_questions_enabled"
KEY_RECOVERY_EMAIL_ENABLED = "security.recovery.email_enabled"
KEY_SETUP_COMPLETED = "security.setup_completed"


def _now() -> datetime:
    return datetime.now()


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _norm_answer(text: str) -> str:
    return (text or "").strip().lower()


def generate_recovery_code() -> str:
    """XXXX-XXXX-XXXX biçiminde okunabilir kurtarma kodu üretir."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # karışması olası harf/rakam yok
    blocks = [
        "".join(secrets.choice(alphabet) for _ in range(RECOVERY_CODE_BLOCK_LEN))
        for _ in range(RECOVERY_CODE_BLOCKS)
    ]
    return "-".join(blocks)


def generate_email_code() -> str:
    """E-posta ile gönderilecek 6 haneli sayısal kod."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


@dataclass
class AuthResult:
    success: bool
    user: User | None = None
    error: str | None = None
    error_kind: str | None = None       # "unknown_user" | "bad_password" | "locked" | "inactive"
    locked: bool = False
    remaining_seconds: int = 0
    must_change_password: bool = False


@dataclass
class RecoveryOptions:
    security_questions: bool = False
    email: bool = False
    recovery_code: bool = False
    masked_email: str = ""
    questions: list[str] = field(default_factory=list)


class AuthService:
    def __init__(self, db_session=None) -> None:
        self.db = db_session

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    def _get_user(self, username: str) -> User | None:
        if not self.db or not username:
            return None
        return self.db.scalar(
            select(User).where(
                User.username == username,
                User.is_deleted == False,  # noqa: E712
            ),
        )

    def _lockout_schedule(self) -> list[tuple[int, int]]:
        raw = settings_store.get_json(self.db, KEY_LOCKOUT_SCHEDULE, DEFAULT_LOCKOUT_SCHEDULE)
        try:
            pairs = sorted((int(a), int(b)) for a, b in raw)
            return pairs or [(a, b) for a, b in DEFAULT_LOCKOUT_SCHEDULE]
        except (TypeError, ValueError):
            return [(a, b) for a, b in DEFAULT_LOCKOUT_SCHEDULE]

    def _lockout_enabled(self) -> bool:
        return settings_store.get_bool(self.db, KEY_LOCKOUT_ENABLED, True)

    def _lock_seconds_for(self, count: int) -> int:
        """Verilen ard arda hatalı deneme sayısı için kilit saniyesi (0 = kilit yok)."""
        secs = 0
        for threshold, duration in self._lockout_schedule():
            if count >= threshold:
                secs = duration
        return secs

    def _remaining_lock(self, user: User) -> int:
        until = _parse_iso(user.locked_until)
        if not until:
            return 0
        delta = (until - _now()).total_seconds()
        return max(0, int(delta + 0.999))

    # ------------------------------------------------------------------
    # Kimlik doğrulama + kilit
    # ------------------------------------------------------------------
    def lockout_status(self, username: str) -> tuple[bool, int]:
        user = self._get_user(username)
        if not user:
            return False, 0
        rem = self._remaining_lock(user)
        return rem > 0, rem

    def authenticate(self, username: str, password: str) -> AuthResult:
        if not self.db:
            return AuthResult(False, error="Veritabanı bağlantısı yok.", error_kind="db")

        user = self._get_user(username)
        if not user:
            return AuthResult(
                False, error="Kullanıcı adı veya şifre hatalı.", error_kind="unknown_user",
            )
        if not user.is_active:
            return AuthResult(
                False, error="Bu kullanıcı pasif durumda.", error_kind="inactive",
            )

        rem = self._remaining_lock(user)
        if rem > 0:
            return AuthResult(
                False, user=user, locked=True, remaining_seconds=rem,
                error=f"Giriş geçici olarak kilitli. Kalan süre: {rem} sn.",
                error_kind="locked",
            )

        if verify_password(password, user.password_hash):
            user.failed_login_count = 0
            user.locked_until = None
            user.last_login_at = _iso(_now())
            self.db.commit()
            return AuthResult(
                True, user=user, must_change_password=bool(user.must_change_password),
            )

        # Başarısız — sayacı artır, gerekiyorsa kilitle.
        user.failed_login_count = int(user.failed_login_count or 0) + 1
        user.last_failed_login_at = _iso(_now())
        lock_secs = self._lock_seconds_for(user.failed_login_count) if self._lockout_enabled() else 0
        result_kind = "bad_password"
        remaining = 0
        if lock_secs > 0:
            user.locked_until = _iso(_now() + timedelta(seconds=lock_secs))
            remaining = lock_secs
            result_kind = "locked"
        self.db.commit()

        if remaining > 0:
            return AuthResult(
                False, user=user, locked=True, remaining_seconds=remaining,
                error=(
                    f"Şifre hatalı. {user.failed_login_count}. hatalı deneme — "
                    f"giriş {remaining} sn kilitlendi."
                ),
                error_kind=result_kind,
            )
        return AuthResult(
            False, user=user, error="Kullanıcı adı veya şifre hatalı.",
            error_kind=result_kind,
        )

    # ------------------------------------------------------------------
    # Kurtarma seçenekleri
    # ------------------------------------------------------------------
    def get_recovery_options(self, username: str) -> RecoveryOptions:
        user = self._get_user(username)
        if not user:
            return RecoveryOptions()

        sq_enabled = settings_store.get_bool(self.db, KEY_RECOVERY_SQ_ENABLED, True)
        email_enabled = settings_store.get_bool(self.db, KEY_RECOVERY_EMAIL_ENABLED, True)

        has_questions = bool(user.security_answer_1_hash and user.security_answer_2_hash)
        questions = []
        if has_questions:
            questions = [
                user.security_question_1 or "Güvenlik sorusu 1",
                user.security_question_2 or "Güvenlik sorusu 2",
            ]

        smtp_ready = self._smtp_ready()
        can_email = bool(email_enabled and smtp_ready and user.email)

        return RecoveryOptions(
            security_questions=bool(sq_enabled and has_questions),
            email=can_email,
            recovery_code=bool(user.recovery_code_hash),
            masked_email=mask_email(user.email),
            questions=questions,
        )

    def _smtp_ready(self) -> bool:
        try:
            from src.desktop.reports.email_engine import SMTPConfig
            cfg = SMTPConfig.from_db(self.db)
            return bool(cfg.host and cfg.username)
        except Exception:  # noqa: BLE001
            return False

    def get_security_questions(self, username: str) -> list[str]:
        return self.get_recovery_options(username).questions

    # ------------------------------------------------------------------
    # Kurtarma yöntemleri — doğrulama
    # ------------------------------------------------------------------
    def verify_security_answers(self, username: str, answers: list[str]) -> bool:
        user = self._get_user(username)
        if not user or not (user.security_answer_1_hash and user.security_answer_2_hash):
            return False
        if len(answers) < 2:
            return False
        ok1 = verify_password(_norm_answer(answers[0]), user.security_answer_1_hash)
        ok2 = verify_password(_norm_answer(answers[1]), user.security_answer_2_hash)
        return bool(ok1 and ok2)

    def verify_recovery_code(self, username: str, code: str) -> bool:
        user = self._get_user(username)
        if not user or not user.recovery_code_hash:
            return False
        normalized = (code or "").strip().upper().replace(" ", "")
        if verify_password(normalized, user.recovery_code_hash):
            return True
        return False

    def start_email_reset(self, username: str) -> tuple[bool, str | None, str | None]:
        """E-posta ile sıfırlama kodunu üretip gönderir."""
        user = self._get_user(username)
        if not user:
            return False, None, "Kullanıcı bulunamadı."
        if not user.email:
            return False, None, "Bu kullanıcının kayıtlı e-posta adresi yok."
        if not self._smtp_ready():
            return False, None, "E-posta gönderimi için SMTP ayarları yapılmamış."

        code = generate_email_code()
        user.pwd_reset_token_hash = hash_password(code)
        user.pwd_reset_expires_at = _iso(_now() + timedelta(minutes=RESET_TOKEN_TTL_MIN))
        self.db.commit()

        try:
            from src.desktop.reports.email_engine import EmailEngine, SMTPConfig
            engine = EmailEngine(SMTPConfig.from_db(self.db))
            ok, msg = engine.send_password_reset(
                to_email=user.email, username=user.username,
                code=code, valid_minutes=RESET_TOKEN_TTL_MIN,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Sıfırlama e-postası gönderilemedi")
            ok, msg = False, str(exc)

        if not ok:
            return False, None, msg
        return True, mask_email(user.email), None

    def verify_email_token(self, username: str, code: str) -> bool:
        user = self._get_user(username)
        if not user or not user.pwd_reset_token_hash:
            return False
        expires = _parse_iso(user.pwd_reset_expires_at)
        if not expires or expires < _now():
            return False
        return verify_password((code or "").strip(), user.pwd_reset_token_hash)

    # ------------------------------------------------------------------
    # Kurtarma tamamlama
    # ------------------------------------------------------------------
    def complete_reset(self, username: str, new_password: str) -> tuple[bool, str | None]:
        user = self._get_user(username)
        if not user:
            return False, "Kullanıcı bulunamadı."
        if not new_password or len(new_password) < 4:
            return False, "Parola en az 4 karakter olmalı."

        user.password_hash = hash_password(new_password)
        user.failed_login_count = 0
        user.locked_until = None
        user.last_failed_login_at = None
        user.pwd_reset_token_hash = None
        user.pwd_reset_expires_at = None
        user.recovery_code_hash = None       # kurtarma kodu tek kullanımlık
        user.must_change_password = False
        self.db.commit()
        logger.info("Parola kurtarma ile sıfırlandı: %s", username)
        return True, None

    # ------------------------------------------------------------------
    # Güvenlik kurulumu (wizard + kullanıcı editörü ortak yazma yolu)
    # ------------------------------------------------------------------
    def set_security_setup(
        self,
        user: User,
        *,
        new_password: str | None = None,
        q1: str | None = None,
        a1: str | None = None,
        q2: str | None = None,
        a2: str | None = None,
        regenerate_recovery: bool = False,
    ) -> str | None:
        """Güvenlik sorularını / parolayı / kurtarma kodunu yazar.

        Yalnızca dolu gelen alanlar güncellenir (cevaplar boşsa dokunulmaz).
        Yeni kurtarma kodu üretildiyse düz metni döndürür (bir kez gösterilecek).
        """
        if new_password:
            user.password_hash = hash_password(new_password)

        if q1 and a1:
            user.security_question_1 = q1.strip()
            user.security_answer_1_hash = hash_password(_norm_answer(a1))
        if q2 and a2:
            user.security_question_2 = q2.strip()
            user.security_answer_2_hash = hash_password(_norm_answer(a2))

        plain_code: str | None = None
        if regenerate_recovery:
            plain_code = generate_recovery_code()
            user.recovery_code_hash = hash_password(plain_code)

        self.db.commit()
        return plain_code

    def get_default_admin(self) -> User | None:
        if not self.db:
            return None
        return self.db.scalar(
            select(User).where(User.username == "admin", User.is_deleted == False),  # noqa: E712
        )

    # ------------------------------------------------------------------
    # İlk kurulum bayrağı
    # ------------------------------------------------------------------
    def is_setup_completed(self) -> bool:
        return settings_store.get_bool(self.db, KEY_SETUP_COMPLETED, False)

    def mark_setup_completed(self) -> None:
        settings_store.set_setting(self.db, KEY_SETUP_COMPLETED, "1")
