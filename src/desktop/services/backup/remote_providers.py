"""
TOYA ERP - Uzak Yedek Hedefleri: FTP/FTPS, Google Drive, S3 (ve S3 uyumlu servisler)

Hepsi `providers.Provider` arayüzünü uygular. Hata mesajları gizli bilgi (parola/anahtar/token) İÇERMEZ.
Google Drive yalnızca `drive.file` kapsamını ister: uygulama sadece kendi oluşturduğu dosyaları görür.
"""

from __future__ import annotations

import datetime as _dt
import ftplib
import hashlib
import hmac
import http.server
import json
import re
import secrets as _secrets
import ssl
import threading
import urllib.parse
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from src.desktop.services.backup.providers import LocalFolderProvider, ProviderError, Provider, _valid_name

Progress = Callable[[int, int], None]
TIMEOUT = 60


def _perm(msg: str) -> ProviderError:
    e = ProviderError(msg)
    e.permanent = True  # type: ignore[attr-defined]
    return e


# =====================================================================  FTP / FTPS
class FtpProvider:
    def __init__(self, host: str, user: str, password: str, remote_dir: str = "", port: int = 21, tls: bool = False,
                 verify_cert: bool = True, label: str = "FTP") -> None:
        self.host, self.user, self.password, self.port = host, user, password, port
        self.remote_dir, self.tls, self.verify, self.label = remote_dir.strip("/"), tls, verify_cert, label

    def _connect(self) -> ftplib.FTP:
        try:
            if self.tls:
                ctx = ssl.create_default_context()
                if not self.verify:
                    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
                ftp: ftplib.FTP = ftplib.FTP_TLS(context=ctx)
            else:
                ftp = ftplib.FTP()
            ftp.connect(self.host, self.port, timeout=TIMEOUT)
            ftp.login(self.user, self.password)
            if self.tls:
                ftp.prot_p()  # type: ignore[attr-defined]
            ftp.set_pasv(True)
            for part in [p for p in self.remote_dir.split("/") if p]:
                try:
                    ftp.cwd(part)
                except ftplib.error_perm:
                    ftp.mkd(part)
                    ftp.cwd(part)
            return ftp
        except ftplib.error_perm as exc:
            raise _perm("FTP kullanıcı adı/parolası ya da klasör yetkisi hatalı.") from exc
        except ssl.SSLError as exc:
            raise ProviderError("FTPS sertifikası doğrulanamadı (sunucu sertifikasını doğrulamayı kapatabilirsiniz).") from exc

    def test(self) -> tuple[bool, str]:
        try:
            ftp = self._connect()
            ftp.quit()
            return True, "FTP bağlantısı başarılı."
        except (ProviderError, OSError, ftplib.Error) as exc:
            return False, f"FTP bağlantısı kurulamadı: {exc.__class__.__name__}: {str(exc)[:120]}" if not isinstance(exc, ProviderError) else str(exc)

    def upload(self, local: Path, remote_name: str, progress: Progress | None = None) -> None:
        if not _valid_name(remote_name):
            raise ProviderError("Geçersiz dosya adı.")
        total, done = Path(local).stat().st_size, [0]

        def cb(block: bytes) -> None:
            done[0] += len(block)
            if progress:
                progress(done[0], total)

        ftp = self._connect()
        try:
            part = remote_name + ".part"
            with open(local, "rb") as fh:
                ftp.storbinary(f"STOR {part}", fh, callback=cb)
            try:
                ftp.delete(remote_name)
            except ftplib.error_perm:
                pass
            ftp.rename(part, remote_name)
        finally:
            try:
                ftp.quit()
            except Exception:  # noqa: BLE001
                ftp.close()

    def size(self, remote_name: str) -> int | None:
        ftp = self._connect()
        try:
            ftp.voidcmd("TYPE I")
            return ftp.size(remote_name)
        except ftplib.error_perm:
            return None
        finally:
            ftp.close()

    def list(self) -> list[dict[str, Any]]:
        ftp = self._connect()
        try:
            out = []
            for name, facts in ftp.mlsd(facts=["size", "type"]):
                if facts.get("type") == "file" and not name.endswith(".part"):
                    out.append({"name": name, "size": int(facts.get("size", 0))})
            return sorted(out, key=lambda x: x["name"])
        finally:
            ftp.close()

    def download(self, remote_name: str, local: Path) -> None:
        if not _valid_name(remote_name):
            raise ProviderError("Geçersiz dosya adı.")
        ftp = self._connect()
        try:
            with open(local, "wb") as fh:
                ftp.retrbinary(f"RETR {remote_name}", fh.write)
        finally:
            ftp.close()

    def delete(self, remote_name: str) -> None:
        if _valid_name(remote_name):
            ftp = self._connect()
            try:
                ftp.delete(remote_name)
            finally:
                ftp.close()


# =====================================================================  Google Drive
GDRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
GDRIVE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GDRIVE_TOKEN = "https://oauth2.googleapis.com/token"
GDRIVE_API = "https://www.googleapis.com/drive/v3"
GDRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
GDRIVE_CHUNK = 8 * 1024 * 1024  # 256 KB'ın katı olmalı


def authorize_google_interactive(client_id: str, client_secret: str, timeout: int = 180,
                                 open_browser: Callable[[str], Any] = webbrowser.open) -> dict[str, str]:
    """Kurulu uygulama (loopback) akışı: tarayıcı açılır, kullanıcı Google hesabıyla izin verir, refresh_token döner."""
    state = _secrets.token_urlsafe(16)
    verifier = _secrets.token_urlsafe(48)
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    got: dict[str, str] = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                got["code"] = q["code"][0]
            elif "error" in q:
                got["error"] = q["error"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<html><body style='font-family:sans-serif'><h3>TOYA ERP</h3>"
                             "İzin alındı; bu pencereyi kapatıp TOYA'ya dönebilirsiniz.</body></html>".encode())
            done.set()

        def log_message(self, *a):  # noqa: D401
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = GDRIVE_AUTH + "?" + urllib.parse.urlencode({
            "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": GDRIVE_SCOPE,
            "access_type": "offline", "prompt": "consent", "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256"})
        open_browser(url)
        if not done.wait(timeout):
            raise ProviderError("Google izni zaman aşımına uğradı.")
    finally:
        srv.shutdown()
        srv.server_close()
    if "code" not in got:
        raise ProviderError("Google izni verilmedi: " + got.get("error", "bilinmeyen"))
    r = requests.post(GDRIVE_TOKEN, data={"code": got["code"], "client_id": client_id, "client_secret": client_secret,
                                          "redirect_uri": redirect, "grant_type": "authorization_code",
                                          "code_verifier": verifier}, timeout=TIMEOUT)
    if r.status_code != 200 or "refresh_token" not in r.json():
        raise ProviderError("Google belirteç alınamadı (İstemci kimliği/gizli anahtarı doğru mu?).")
    return {"refresh_token": r.json()["refresh_token"]}


def _b64(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class GoogleDriveProvider:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, folder_name: str = "TOYA Yedek",
                 label: str = "Google Drive") -> None:
        self.cid, self.secret, self.refresh = client_id, client_secret, refresh_token
        self.folder_name, self.label = folder_name, label
        self._token = ""
        self._folder = ""

    def _auth(self) -> dict[str, str]:
        if not self._token:
            r = requests.post(GDRIVE_TOKEN, data={"client_id": self.cid, "client_secret": self.secret,
                                                  "refresh_token": self.refresh, "grant_type": "refresh_token"}, timeout=TIMEOUT)
            if r.status_code in (400, 401):
                raise _perm("Google yetkisi geçersiz/iptal edilmiş; 'Google ile Bağlan'ı yeniden yapın.")
            if r.status_code != 200:
                raise ProviderError(f"Google oturumu açılamadı (HTTP {r.status_code}).")
            self._token = r.json()["access_token"]
        return {"Authorization": "Bearer " + self._token}

    def _req(self, method: str, url: str, **kw) -> requests.Response:
        kw.setdefault("timeout", TIMEOUT)
        extra = kw.pop("headers", {})
        r = requests.request(method, url, headers={**self._auth(), **extra}, **kw)
        if r.status_code == 401:
            self._token = ""
            r = requests.request(method, url, headers={**self._auth(), **extra}, **kw)
        if r.status_code == 403 and "quota" in r.text.lower():
            raise _perm("Google Drive alanı dolu.")
        if r.status_code >= 500 or r.status_code == 429:
            raise ProviderError(f"Google Drive geçici hata (HTTP {r.status_code}).")
        return r

    def _folder_id(self) -> str:
        if self._folder:
            return self._folder
        q = f"name = '{self.folder_name.replace(chr(39), chr(92) + chr(39))}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        r = self._req("GET", f"{GDRIVE_API}/files", params={"q": q, "fields": "files(id)", "spaces": "drive"})
        if r.status_code != 200:
            raise ProviderError(f"Drive klasörü sorgulanamadı (HTTP {r.status_code}).")
        files = r.json().get("files", [])
        if files:
            self._folder = files[0]["id"]
        else:
            c = self._req("POST", f"{GDRIVE_API}/files", json={"name": self.folder_name, "mimeType": "application/vnd.google-apps.folder"})
            if c.status_code not in (200, 201):
                raise ProviderError(f"Drive klasörü oluşturulamadı (HTTP {c.status_code}).")
            self._folder = c.json()["id"]
        return self._folder

    def _find(self, name: str) -> dict[str, Any] | None:
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name = '{safe}' and '{self._folder_id()}' in parents and trashed = false"
        r = self._req("GET", f"{GDRIVE_API}/files", params={"q": q, "fields": "files(id,size)"})
        files = r.json().get("files", []) if r.status_code == 200 else []
        return files[0] if files else None

    def test(self) -> tuple[bool, str]:
        try:
            self._folder_id()
            return True, f"Google Drive bağlantısı başarılı (klasör: {self.folder_name})."
        except (ProviderError, requests.RequestException) as exc:
            return False, str(exc) if isinstance(exc, ProviderError) else "Google Drive'a erişilemedi."

    def upload(self, local: Path, remote_name: str, progress: Progress | None = None) -> None:
        if not _valid_name(remote_name):
            raise ProviderError("Geçersiz dosya adı.")
        existing = self._find(remote_name)
        total = Path(local).stat().st_size
        meta: dict[str, Any] = {"name": remote_name}
        if existing:
            init = self._req("PATCH", f"{GDRIVE_UPLOAD}/{existing['id']}", params={"uploadType": "resumable"}, json=meta,
                             headers={"X-Upload-Content-Length": str(total)})
        else:
            meta["parents"] = [self._folder_id()]
            init = self._req("POST", GDRIVE_UPLOAD, params={"uploadType": "resumable"}, json=meta,
                             headers={"X-Upload-Content-Length": str(total)})
        if init.status_code != 200 or "Location" not in init.headers:
            raise ProviderError(f"Drive yükleme oturumu açılamadı (HTTP {init.status_code}).")
        session = init.headers["Location"]
        sent = 0
        with open(local, "rb") as fh:
            while True:
                chunk = fh.read(GDRIVE_CHUNK)
                end = sent + len(chunk)
                hdr = {"Content-Range": f"bytes {sent}-{end - 1}/{total}" if chunk else f"bytes */{total}"}
                r = requests.put(session, data=chunk, headers=hdr, timeout=TIMEOUT * 5)
                if r.status_code in (200, 201):
                    sent = end
                    break
                if r.status_code != 308:
                    raise ProviderError(f"Drive yükleme hatası (HTTP {r.status_code}).")
                sent = end
                if progress:
                    progress(sent, total)
        if progress:
            progress(total, total)

    def size(self, remote_name: str) -> int | None:
        f = self._find(remote_name)
        return int(f["size"]) if f and f.get("size") is not None else None

    def list(self) -> list[dict[str, Any]]:
        r = self._req("GET", f"{GDRIVE_API}/files", params={"q": f"'{self._folder_id()}' in parents and trashed = false",
                                                            "fields": "files(id,name,size)", "pageSize": 1000})
        return sorted(({"name": f["name"], "size": int(f.get("size", 0)), "id": f["id"]} for f in r.json().get("files", [])),
                      key=lambda x: x["name"])

    def download(self, remote_name: str, local: Path) -> None:
        f = self._find(remote_name)
        if not f:
            raise ProviderError("Dosya Drive'da bulunamadı.")
        r = self._req("GET", f"{GDRIVE_API}/files/{f['id']}", params={"alt": "media"}, stream=True)
        if r.status_code != 200:
            raise ProviderError(f"Drive indirme hatası (HTTP {r.status_code}).")
        with open(local, "wb") as fh:
            for block in r.iter_content(1024 * 1024):
                fh.write(block)

    def delete(self, remote_name: str) -> None:
        f = self._find(remote_name)
        if f:
            self._req("DELETE", f"{GDRIVE_API}/files/{f['id']}")


# =====================================================================  S3 (SigV4)
def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def sigv4_headers(method: str, host: str, path: str, query: dict[str, str], headers: dict[str, str], payload_hash: str,
                  access_key: str, secret_key: str, region: str, amz_date: str, service: str = "s3") -> dict[str, str]:
    """AWS Signature V4 üstbilgileri. `headers` imzalanacak ek üstbilgilerdir (küçük harfli anahtar)."""
    date = amz_date[:8]
    all_h = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    all_h.update({k.lower(): v.strip() for k, v in headers.items()})
    signed = ";".join(sorted(all_h))
    canon_h = "".join(f"{k}:{all_h[k]}\n" for k in sorted(all_h))
    canon_q = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}" for k, v in sorted(query.items()))
    canonical = "\n".join([method, urllib.parse.quote(path, safe="/-_.~"), canon_q, canon_h, signed, payload_hash])
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(_sign(_sign(_sign(("AWS4" + secret_key).encode(), date), region), service), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    out = {k: v for k, v in all_h.items() if k != "host"}
    out["Authorization"] = f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed}, Signature={sig}"
    return out


class S3Provider:
    PART = 16 * 1024 * 1024

    def __init__(self, bucket: str, access_key: str, secret_key: str, region: str = "us-east-1", endpoint: str = "",
                 prefix: str = "", label: str = "S3", now: Callable[[], _dt.datetime] | None = None) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]", bucket or ""):
            raise ProviderError("Bucket adı geçersiz.")
        self.bucket, self.ak, self.sk, self.region, self.label = bucket, access_key, secret_key, region, label
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        self.endpoint = endpoint.rstrip("/")
        self._now = now or (lambda: _dt.datetime.now(_dt.timezone.utc))

    def _target(self, key: str) -> tuple[str, str, str]:
        """(url, host, path)"""
        if self.endpoint:
            u = urllib.parse.urlparse(self.endpoint)
            path = f"{u.path.rstrip('/')}/{self.bucket}/{key}"
            return f"{u.scheme}://{u.netloc}{urllib.parse.quote(path, safe='/-_.~')}", u.netloc, path
        host = f"{self.bucket}.s3.{self.region}.amazonaws.com"
        return f"https://{host}{urllib.parse.quote('/' + key, safe='/-_.~')}", host, "/" + key

    def _call(self, method: str, key: str, query: dict[str, str] | None = None, body: bytes = b"", extra: dict[str, str] | None = None,
              stream: bool = False) -> requests.Response:
        query = query or {}
        url, host, path = self._target(key)
        h = sigv4_headers(method, host, path, query, extra or {}, hashlib.sha256(body).hexdigest(), self.ak, self.sk, self.region,
                          self._now().strftime("%Y%m%dT%H%M%SZ"))
        r = requests.request(method, url, params=query, data=body, headers=h, timeout=TIMEOUT * 5, stream=stream)
        if r.status_code in (403, 401):
            raise _perm("S3 erişim reddedildi (anahtarlar/yetki/bölge kontrol edin).")
        if r.status_code >= 500 or r.status_code == 429:
            raise ProviderError(f"S3 geçici hata (HTTP {r.status_code}).")
        return r

    def test(self) -> tuple[bool, str]:
        try:
            r = self._call("GET", "", {"list-type": "2", "max-keys": "1"})
            return (True, "S3 bağlantısı başarılı.") if r.status_code == 200 else (False, f"S3 yanıtı beklenmedik (HTTP {r.status_code}).")
        except (ProviderError, requests.RequestException) as exc:
            return False, str(exc) if isinstance(exc, ProviderError) else "S3'e erişilemedi."

    def upload(self, local: Path, remote_name: str, progress: Progress | None = None) -> None:
        if not _valid_name(remote_name):
            raise ProviderError("Geçersiz dosya adı.")
        key, total = self.prefix + remote_name, Path(local).stat().st_size
        if total <= self.PART:
            r = self._call("PUT", key, body=Path(local).read_bytes())
            if r.status_code != 200:
                raise ProviderError(f"S3 yükleme hatası (HTTP {r.status_code}).")
            if progress:
                progress(total, total)
            return
        r = self._call("POST", key, {"uploads": ""})
        m = re.search(r"<UploadId>([^<]+)</UploadId>", r.text)
        if r.status_code != 200 or not m:
            raise ProviderError(f"S3 çok parçalı yükleme başlatılamadı (HTTP {r.status_code}).")
        uid, etags, sent = m.group(1), [], 0
        try:
            with open(local, "rb") as fh:
                n = 1
                for chunk in iter(lambda: fh.read(self.PART), b""):
                    pr = self._call("PUT", key, {"partNumber": str(n), "uploadId": uid}, chunk)
                    if pr.status_code != 200 or "ETag" not in pr.headers:
                        raise ProviderError(f"S3 parça {n} yüklenemedi (HTTP {pr.status_code}).")
                    etags.append((n, pr.headers["ETag"]))
                    sent += len(chunk)
                    n += 1
                    if progress:
                        progress(sent, total)
            xml = "<CompleteMultipartUpload>" + "".join(f"<Part><PartNumber>{i}</PartNumber><ETag>{e}</ETag></Part>" for i, e in etags) + "</CompleteMultipartUpload>"
            cr = self._call("POST", key, {"uploadId": uid}, xml.encode())
            if cr.status_code != 200 or "<Error>" in cr.text:
                raise ProviderError("S3 çok parçalı yükleme tamamlanamadı.")
        except BaseException:
            try:
                self._call("DELETE", key, {"uploadId": uid})
            except Exception:  # noqa: BLE001
                pass
            raise

    def size(self, remote_name: str) -> int | None:
        r = self._call("HEAD", self.prefix + remote_name)
        return int(r.headers["Content-Length"]) if r.status_code == 200 and "Content-Length" in r.headers else None

    def list(self) -> list[dict[str, Any]]:
        r = self._call("GET", "", {"list-type": "2", "prefix": self.prefix})
        out = []
        for m in re.finditer(r"<Contents>.*?<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>.*?</Contents>", r.text, re.S):
            name = m.group(1)[len(self.prefix):]
            if name and "/" not in name:
                out.append({"name": name, "size": int(m.group(2))})
        return sorted(out, key=lambda x: x["name"])

    def download(self, remote_name: str, local: Path) -> None:
        r = self._call("GET", self.prefix + remote_name, stream=True)
        if r.status_code != 200:
            raise ProviderError(f"S3 indirme hatası (HTTP {r.status_code}).")
        with open(local, "wb") as fh:
            for block in r.iter_content(1024 * 1024):
                fh.write(block)

    def delete(self, remote_name: str) -> None:
        self._call("DELETE", self.prefix + remote_name)


# =====================================================================  fabrika
def build_provider(cfg: dict[str, Any], secret: dict[str, Any]) -> Provider:
    """İş kaydındaki gizli olmayan ayarlar (`cfg`) + kimlik deposundaki gizli bilgiler (`secret`)."""
    t, label = cfg.get("type"), cfg.get("label") or cfg.get("type", "")
    if t == "local":
        return LocalFolderProvider(cfg.get("path", ""), label or "Klasör")
    if t == "ftp":
        return FtpProvider(cfg.get("host", ""), cfg.get("user", ""), secret.get("password", ""), cfg.get("remote_dir", ""),
                           int(cfg.get("port", 21)), bool(cfg.get("tls")), bool(cfg.get("verify_cert", True)), label or "FTP")
    if t == "gdrive":
        return GoogleDriveProvider(cfg.get("client_id", ""), secret.get("client_secret", ""), secret.get("refresh_token", ""),
                                   cfg.get("folder", "TOYA Yedek"), label or "Google Drive")
    if t == "s3":
        return S3Provider(cfg.get("bucket", ""), cfg.get("access_key", ""), secret.get("secret_key", ""), cfg.get("region", "us-east-1"),
                          cfg.get("endpoint", ""), cfg.get("prefix", ""), label or "S3")
    raise ProviderError(f"Bilinmeyen hedef türü: {t}")


def secret_name(job_id: str, target_id: str) -> str:
    return f"hedef-{job_id}-{target_id}"
