"""
TOYA ERP - Portal Paketini FTP ile Gönderme

TOYA masaüstünde üretilen imzalı portal güncelleme paketini (bkz. `portal_package`) cPanel sunucusundaki
portalın `update_inbox/` klasörüne FTP/FTPS ile yükler. Paket YALNIZCA teslim edilir; kurulum portaldaki
`update.php` (yönetici girişi) veya `bin/update.php` ile yapılır ve orada imza + dosya özetleri yeniden doğrulanır.

Yükleme güvenli yapılır: dosya önce `.part` adıyla yüklenir, boyutu doğrulanır, sonra son adına çevrilir —
böylece yarım yüklenmiş paket sunucuda geçerli paket gibi görünmez. Parola hata mesajlarına ve günlüğe yazılmaz.

Birden çok adlandırılmış FTP profili tutulabilir (`PortalFtpProfileStore`); profil BİLGİLERİ (sunucu, kullanıcı,
klasör, TLS/pasif seçenekleri) ayarlarda JSON olarak, PAROLA ise (`disk_registry.DiskStore` ile aynı desenle)
işletim sistemi kimlik deposunda (`backup.secrets`, `keyring`) saklanır — parola hiçbir zaman düz metin olarak
veritabanına yazılmaz. Eskiden tek bir profil düz metin parolayla ayarlarda tutuluyordu (`FtpProfile.load/save`);
`PortalFtpProfileStore` ilk kullanımda bunu bir kereye mahsus yeni depoya taşır ve düz metin parolayı siler."""

from __future__ import annotations

import ftplib
import json
import logging
import re
import socket
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.desktop.services import sync_log_service
from src.desktop.services.backup import secrets as ftp_secrets
from src.desktop.services.settings_store import get_bool, get_int, get_setting, set_setting

logger = logging.getLogger(__name__)

PACKAGE_NAME_RE = re.compile(r"^toya-portal-\d+\.\d+\.\d+\.zip$")
INBOX_DIR = "update_inbox"
BLOCK_SIZE = 64 * 1024
TIMEOUT = 30

#: ftplib.all_errors zaten bir demettir; OSError ile düz bir demette birleştirilir.
_ERRORS = tuple(ftplib.all_errors) + (OSError,)

_KEYS = {
    "host": "portal.ftp.host", "port": "portal.ftp.port", "user": "portal.ftp.user",
    "password": "portal.ftp.password", "remote_dir": "portal.ftp.remote_dir",
    "use_tls": "portal.ftp.use_tls", "verify_cert": "portal.ftp.verify_cert", "passive": "portal.ftp.passive",
}


@dataclass
class FtpProfile:
    host: str = ""
    port: int = 21
    user: str = ""
    password: str = ""
    #: FTP oturum köküne göre portal klasörü (örn. "public_html/portal"); `update_inbox/` bunun altındadır.
    remote_dir: str = ""
    use_tls: bool = True
    verify_cert: bool = True
    passive: bool = True

    @classmethod
    def load(cls, db) -> "FtpProfile":
        return cls(
            host=get_setting(db, _KEYS["host"], "") or "",
            port=get_int(db, _KEYS["port"], 21),
            user=get_setting(db, _KEYS["user"], "") or "",
            password=get_setting(db, _KEYS["password"], "") or "",
            remote_dir=get_setting(db, _KEYS["remote_dir"], "") or "",
            use_tls=get_bool(db, _KEYS["use_tls"], True),
            verify_cert=get_bool(db, _KEYS["verify_cert"], True),
            passive=get_bool(db, _KEYS["passive"], True),
        )

    def save(self, db) -> None:
        for key, value in (("host", self.host), ("port", self.port), ("user", self.user),
                           ("password", self.password), ("remote_dir", self.remote_dir)):
            set_setting(db, _KEYS[key], value, commit=False)
        for key, value in (("use_tls", self.use_tls), ("verify_cert", self.verify_cert), ("passive", self.passive)):
            set_setting(db, _KEYS[key], "1" if value else "0", commit=False)
        db.commit()

    def is_complete(self) -> bool:
        return bool(self.host and self.user and self.password)


KEY_PROFILES = "portal.ftp.profiles"
KEY_ACTIVE_PROFILE = "portal.ftp.active_profile_id"


@dataclass
class PortalFtpProfile:
    """Kayıtlı bir FTP profilinin PAROLASIZ bilgileri (parola `PortalFtpProfileStore` üzerinden kimlik deposunda)."""
    title: str
    host: str = ""
    port: int = 21
    user: str = ""
    remote_dir: str = ""
    use_tls: bool = True
    verify_cert: bool = True
    passive: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    hidden: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PortalFtpProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _secret_name(profile_id: str) -> str:
    return f"portal-ftp-{profile_id}"


class PortalFtpProfileStore:
    """Birden çok adlandırılmış FTP profili. Silme yalnızca gizler (`hidden`); profil adı benzersiz olmalıdır."""

    def __init__(self, db) -> None:
        self.db = db

    def _all(self) -> list[PortalFtpProfile]:
        try:
            raw = json.loads(get_setting(self.db, KEY_PROFILES, "[]") or "[]")
        except (TypeError, ValueError):
            raw = []
        return [PortalFtpProfile.from_dict(d) for d in raw if isinstance(d, dict) and d.get("title")]

    def _write(self, profiles: list[PortalFtpProfile]) -> None:
        set_setting(self.db, KEY_PROFILES, json.dumps([p.to_dict() for p in profiles], ensure_ascii=False))

    def list(self, include_hidden: bool = False) -> list[PortalFtpProfile]:
        profiles = self._all()
        if not profiles and (get_setting(self.db, _KEYS["host"], "") or get_setting(self.db, _KEYS["user"], "")):
            migrated = self._migrate_legacy()
            if migrated is not None:
                profiles = [migrated]
        return [p for p in profiles if include_hidden or not p.hidden]

    def get(self, profile_id: str) -> PortalFtpProfile | None:
        return next((p for p in self._all() if p.id == profile_id), None)

    def password(self, profile_id: str) -> str:
        return ftp_secrets.get_json(_secret_name(profile_id)).get("password", "")

    def save(self, meta: PortalFtpProfile, password: str | None = None) -> tuple[bool, str]:
        if not meta.title.strip():
            return False, "Profil adı boş olamaz."
        profiles = self._all()
        for p in profiles:
            if p.id != meta.id and not p.hidden and p.title.strip().lower() == meta.title.strip().lower():
                return False, "Bu adla kayıtlı bir profil zaten var."
        profiles = [p for p in profiles if p.id != meta.id] + [meta]
        self._write(sorted(profiles, key=lambda p: p.title.lower()))
        if password is not None:
            ftp_secrets.set_json(_secret_name(meta.id), {"password": password})
        return True, f"'{meta.title}' kaydedildi."

    def hide(self, profile_id: str) -> None:
        profiles = self._all()
        for p in profiles:
            if p.id == profile_id:
                p.hidden = True
        self._write(profiles)
        ftp_secrets.delete_secret(_secret_name(profile_id))

    def resolve(self, profile_id: str) -> "FtpProfile | None":
        """Kayıtlı profili, parolası kimlik deposundan okunmuş çalışma zamanı nesnesine çevirir."""
        meta = self.get(profile_id)
        if meta is None:
            return None
        return FtpProfile(host=meta.host, port=meta.port, user=meta.user, password=self.password(meta.id),
                          remote_dir=meta.remote_dir, use_tls=meta.use_tls, verify_cert=meta.verify_cert,
                          passive=meta.passive)

    def active_id(self) -> str | None:
        return get_setting(self.db, KEY_ACTIVE_PROFILE) or None

    def set_active(self, profile_id: str | None) -> None:
        set_setting(self.db, KEY_ACTIVE_PROFILE, profile_id or "")

    def _migrate_legacy(self) -> PortalFtpProfile | None:
        """Eski tekli, düz metin parolalı profili (`FtpProfile.load`) bir kereye mahsus yeni depoya taşır;
        parola kimlik deposuna geçer ve eski düz metin ayar silinir. İdempotenttir (ikinci çağrıda bir şey yapmaz)."""
        legacy = FtpProfile.load(self.db)
        if not legacy.host and not legacy.user:
            return None
        meta = PortalFtpProfile(title="Varsayılan", host=legacy.host, port=legacy.port, user=legacy.user,
                                remote_dir=legacy.remote_dir, use_tls=legacy.use_tls, verify_cert=legacy.verify_cert,
                                passive=legacy.passive)
        self._write([meta])
        self.set_active(meta.id)
        if legacy.password:
            ftp_secrets.set_json(_secret_name(meta.id), {"password": legacy.password})
        for key in _KEYS.values():          # eski düz metin ayarlar (parola dahil) silinir
            set_setting(self.db, key, "", commit=False)
        self.db.commit()
        return meta


@dataclass
class DeployResult:
    success: bool
    message: str = ""
    remote_path: str = ""


def _clean_remote_dir(remote_dir: str) -> list[str] | None:
    """Uzak klasörü güvenli parçalara böler; `..` içeriyorsa None."""
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." or ":" in p for p in parts):
        return None
    return parts


def _connect(profile: FtpProfile) -> ftplib.FTP:
    if profile.use_tls:
        import ssl

        ctx = ssl.create_default_context()
        if not profile.verify_cert:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        ftp: ftplib.FTP = ftplib.FTP_TLS(context=ctx)
    else:
        ftp = ftplib.FTP()
    ftp.connect(profile.host, profile.port, timeout=TIMEOUT)
    ftp.login(profile.user, profile.password)
    if profile.use_tls:
        ftp.prot_p()
    ftp.set_pasv(profile.passive)
    return ftp


def _friendly(exc: Exception, profile: FtpProfile) -> str:
    """Kullanıcıya gösterilecek, parola içermeyen hata metni."""
    text = str(exc)
    if profile.password:
        text = text.replace(profile.password, "***")
    if isinstance(exc, ftplib.error_perm) and text.startswith("530"):
        return "FTP girişi reddedildi (kullanıcı adı/parola hatalı)."
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "FTP sunucusu zaman aşımına uğradı."
    if isinstance(exc, socket.gaierror):
        return "FTP sunucu adı çözümlenemedi."
    if isinstance(exc, ConnectionRefusedError):
        return "FTP sunucusu bağlantıyı reddetti (adres/port?)."
    if "CERTIFICATE_VERIFY_FAILED" in text:
        return "Sunucu sertifikası doğrulanamadı (kendi imzalı sertifika ise 'sertifikayı doğrula' seçeneğini kapatın)."
    return f"FTP hatası: {text}"


#: cPanel FTP hesapları genelde `public_html/` içine "jailed" (kilitli) olur: oturum kökü zaten public_html'in
#: içidir, bu adı ayrıca bir alt klasör olarak oluşturmaya/girmeye çalışmak başarısız olur.
_JAILED_ROOT_NAMES = ("public_html", "www", "htdocs", "httpdocs")


def _cwd_or_make(ftp: ftplib.FTP, parts: list[str], create: bool) -> None:
    ftp.cwd("/")
    try:
        _walk(ftp, parts, create)
    except ftplib.error_perm:
        # İlk parça public_html vb. bir kök takma adıysa ve oturum zaten o kökteyse (jailed hesap),
        # o parçayı atlayıp devam etmeyi dene (yalnızca ilk denemenin tamamı başarısız olursa).
        if not (parts and parts[0].lower() in _JAILED_ROOT_NAMES):
            raise
        ftp.cwd("/")
        _walk(ftp, parts[1:], create)


def _walk(ftp: ftplib.FTP, parts: list[str], create: bool) -> None:
    for part in parts:
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            if not create:
                raise
            ftp.mkd(part)
            ftp.cwd(part)


def test_connection(profile: FtpProfile) -> DeployResult:
    if not profile.is_complete():
        return DeployResult(False, "FTP sunucu, kullanıcı ve parola girilmelidir.")
    parts = _clean_remote_dir(profile.remote_dir)
    if parts is None:
        return DeployResult(False, "Uzak klasör '..' içeremez.")
    try:
        ftp = _connect(profile)
    except _ERRORS as exc:
        return DeployResult(False, _friendly(exc, profile))
    try:
        try:
            _cwd_or_make(ftp, parts, create=False)
        except ftplib.error_perm:
            return DeployResult(True, "Bağlantı başarılı, ancak portal klasörü sunucuda bulunamadı "
                                      "(gönderimde oluşturulur).")
        names = set(ftp.nlst())
        has_portal = "src" in names or "update_inbox" in names or "public" in names
        return DeployResult(True, "Bağlantı başarılı; portal klasörü bulundu." if has_portal
                            else "Bağlantı başarılı; klasör var ama portal dosyaları henüz görünmüyor.")
    except _ERRORS as exc:
        return DeployResult(False, _friendly(exc, profile))
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()


def list_remote_dirs(profile: FtpProfile, path: str = "/") -> tuple[bool, str, list[str]]:
    """`path` altındaki alt klasörleri döner (ok, hata_mesajı, [klasör_adı, ...]) — Windows Gezgini gibi
    dolaşarak uzak klasör seçen `_FtpBrowserDialog` için. Parola gerektirmediği için `profile.password`
    boş olabilir (test bağlantısı ayrı; burada yalnızca listeleme yapılır, klasör oluşturulmaz)."""
    if not (profile.host and profile.user):
        return False, "FTP sunucu ve kullanıcı girilmelidir.", []
    try:
        ftp = _connect(profile)
    except _ERRORS as exc:
        return False, _friendly(exc, profile), []
    try:
        try:
            ftp.cwd(path or "/")
        except ftplib.error_perm as exc:
            return False, _friendly(exc, profile), []
        dirs: list[str] = []
        try:
            for name, facts in ftp.mlsd():
                if name not in (".", "..") and facts.get("type") == "dir":
                    dirs.append(name)
        except (ftplib.error_perm, AttributeError):
            # Sunucu MLSD desteklemiyor: klasik LIST çıktısını satır satır ayrıştır (yalnız 'd' ile başlayanlar).
            lines: list[str] = []
            ftp.retrlines("LIST", lines.append)
            for line in lines:
                cols = line.split(maxsplit=8)
                if len(cols) >= 9 and cols[0].startswith("d") and cols[8] not in (".", ".."):
                    dirs.append(cols[8])
        return True, "", sorted(set(dirs), key=str.lower)
    except _ERRORS as exc:
        return False, _friendly(exc, profile), []
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()


def upload_package(zip_path: Path, profile: FtpProfile,
                   progress: Callable[[int, int], None] | None = None) -> DeployResult:
    """Paketi `<remote_dir>/update_inbox/` altına yükler. `progress(gönderilen, toplam)` bayt cinsindendir."""
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        return DeployResult(False, "Paket dosyası bulunamadı.")
    if not PACKAGE_NAME_RE.match(zip_path.name):
        return DeployResult(False, "Dosya adı toya-portal-X.Y.Z.zip biçiminde olmalıdır.")
    if not profile.is_complete():
        return DeployResult(False, "FTP sunucu, kullanıcı ve parola girilmelidir.")
    parts = _clean_remote_dir(profile.remote_dir)
    if parts is None:
        return DeployResult(False, "Uzak klasör '..' içeremez.")

    total = zip_path.stat().st_size
    part_name = zip_path.name + ".part"
    remote_path = "/".join(parts + [INBOX_DIR, zip_path.name])
    try:
        ftp = _connect(profile)
    except _ERRORS as exc:
        return DeployResult(False, _friendly(exc, profile))
    try:
        _cwd_or_make(ftp, parts + [INBOX_DIR], create=True)
        sent = 0

        def _cb(block: bytes) -> None:
            nonlocal sent
            sent += len(block)
            if progress:
                try:
                    progress(sent, total)
                except Exception:  # noqa: BLE001 - arayüz geri çağrısı yüklemeyi bozmamalı
                    logger.exception("Yükleme ilerleme geri çağrısı hata verdi")

        with zip_path.open("rb") as fh:
            ftp.storbinary(f"STOR {part_name}", fh, blocksize=BLOCK_SIZE, callback=_cb)

        ftp.voidcmd("TYPE I")
        remote_size = ftp.size(part_name)
        if remote_size != total:
            try:
                ftp.delete(part_name)
            except ftplib.all_errors:
                pass
            return DeployResult(False, f"Yükleme doğrulanamadı: sunucudaki boyut {remote_size}, beklenen {total}.")

        try:  # aynı adlı eski paket varsa değiştirilir
            ftp.delete(zip_path.name)
        except ftplib.error_perm:
            pass
        ftp.rename(part_name, zip_path.name)
        return DeployResult(True, f"Paket gönderildi: {remote_path}", remote_path)
    except _ERRORS as exc:
        return DeployResult(False, _friendly(exc, profile))
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()


def deploy(db, zip_path: Path, profile: FtpProfile | None = None,
           progress: Callable[[int, int], None] | None = None) -> DeployResult:
    """Yükler ve sonucu aktarım günlüğüne yazar. `profile` verilmezse etkin (son seçilen) kayıtlı profil kullanılır."""
    if profile is None:
        store = PortalFtpProfileStore(db)
        active = store.active_id()
        profile = (store.resolve(active) if active else None) or FtpProfile.load(db)
    started = datetime.utcnow()
    result = upload_package(zip_path, profile, progress)
    sync_log_service.record(
        db, "portal", sync_log_service.DIR_DEPLOY, result.success, result.message,
        {"package": Path(zip_path).name}, started,
    )
    return result
