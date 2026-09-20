"""Uzak yedek hedefleri: FTP (gerçek sunucu), S3 (SigV4 + sahte HTTP), Google Drive (sahte HTTP), kimlik deposu."""

from __future__ import annotations

import datetime as dt
import threading
import urllib.parse

import pytest
import requests
import responses
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from src.desktop.services.backup import remote_providers as rp
from src.desktop.services.backup import secrets as sec
from src.desktop.services.backup.providers import ProviderError, with_retry

USER, PASSWORD = "yedek", "cok-gizli-ftp-parolasi"


# ---------------------------------------------------------------- FTP
@pytest.fixture
def ftp_server(tmp_path):
    root = tmp_path / "ftproot"
    root.mkdir()
    auth = DummyAuthorizer()
    auth.add_user(USER, PASSWORD, str(root), perm="elradfmwMT")
    handler = type("H", (FTPHandler,), {"authorizer": auth, "passive_ports": range(50200, 50300)})
    server = FTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=lambda: server.serve_forever(timeout=0.2, handle_exit=False), daemon=True)
    t.start()
    yield root, server.address[1]
    server.close_all()
    t.join(timeout=5)


def test_ftp_upload_list_download_delete_and_size(ftp_server, tmp_path):
    root, port = ftp_server
    p = rp.FtpProvider("127.0.0.1", USER, PASSWORD, "yedekler/toya", port)
    assert p.test() == (True, "FTP bağlantısı başarılı.")
    f = tmp_path / "toya-full-20260101-000000.zip"
    f.write_bytes(bytes(range(256)) * 5000)
    seen = []
    p.upload(f, f.name, lambda d, t: seen.append(d))
    assert seen and seen[-1] == f.stat().st_size
    assert (root / "yedekler" / "toya" / f.name).read_bytes() == f.read_bytes()      # alt klasörler oluşturuldu
    assert not list((root / "yedekler" / "toya").glob("*.part"))                       # geçici dosya kalmadı
    assert p.size(f.name) == f.stat().st_size and p.size("yok.zip") is None
    assert p.list() == [{"name": f.name, "size": f.stat().st_size}]
    p.upload(f, f.name)                                                                # aynı adla üzerine yazma
    out = tmp_path / "indirilen.zip"
    p.download(f.name, out)
    assert out.read_bytes() == f.read_bytes()
    p.delete(f.name)
    assert p.list() == []
    for bad in ("../x", "a/b"):
        with pytest.raises(ProviderError):
            p.upload(f, bad)


def test_ftp_wrong_password_is_permanent_and_never_leaks_it(ftp_server, tmp_path):
    _root, port = ftp_server
    p = rp.FtpProvider("127.0.0.1", USER, "yanlis-parola-xyz", "", port)
    ok, msg = p.test()
    assert not ok and "yanlis-parola-xyz" not in msg
    f = tmp_path / "a.zip"
    f.write_bytes(b"1")
    calls = []
    with pytest.raises(ProviderError) as e:
        with_retry(lambda: (calls.append(1), p.upload(f, "a.zip"))[1], attempts=4, sleep=lambda s: None)
    assert getattr(e.value, "permanent", False) and len(calls) == 1 and "yanlis-parola-xyz" not in str(e.value)
    dead = rp.FtpProvider("127.0.0.1", USER, PASSWORD, "", 1)
    assert dead.test()[0] is False


# ---------------------------------------------------------------- S3 / SigV4
def test_sigv4_matches_the_aws_documentation_vector():
    """AWS 'GET Object' örneği (s3 SigV4 başlık imzası) — belgelenmiş beklenen imza."""
    h = rp.sigv4_headers(
        "GET", "examplebucket.s3.amazonaws.com", "/test.txt", {}, {"range": "bytes=0-9"},
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1", "20130524T000000Z")
    assert h["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


def _s3(**kw) -> rp.S3Provider:
    return rp.S3Provider("yedek-kovasi", "AKIATEST", "gizli-anahtar-xyz", now=lambda: dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc), **kw)


@responses.activate
def test_s3_small_upload_signs_and_verifies_size(tmp_path):
    f = tmp_path / "x.zip"
    f.write_bytes(b"A" * 1000)
    url = "https://yedek-kovasi.s3.us-east-1.amazonaws.com/toya/x.zip"
    responses.add(responses.PUT, url, status=200)
    responses.add(responses.HEAD, url, status=200, headers={"Content-Length": "1000"})
    p = _s3(prefix="toya")
    p.upload(f, "x.zip")
    req = responses.calls[0].request
    assert req.body == b"A" * 1000 and req.headers["x-amz-date"] == "20260102T030405Z"
    assert req.headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIATEST/20260102/us-east-1/s3/aws4_request")
    assert "gizli-anahtar-xyz" not in str(req.headers)                               # gizli anahtar hiçbir yere gitmez
    assert p.size("x.zip") == 1000


@responses.activate
def test_s3_multipart_upload_completes_and_aborts_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(rp.S3Provider, "PART", 1000)
    f = tmp_path / "b.zip"
    f.write_bytes(b"B" * 2500)
    url = "https://yedek-kovasi.s3.us-east-1.amazonaws.com/b.zip"
    responses.add(responses.POST, url, body="<r><UploadId>UP1</UploadId></r>", status=200,
                  match=[responses.matchers.query_param_matcher({"uploads": ""})])
    for n in (1, 2, 3):
        responses.add(responses.PUT, url, status=200, headers={"ETag": f'"e{n}"'},
                      match=[responses.matchers.query_param_matcher({"partNumber": str(n), "uploadId": "UP1"})])
    responses.add(responses.POST, url, body="<Complete/>", status=200,
                  match=[responses.matchers.query_param_matcher({"uploadId": "UP1"})])
    _s3().upload(f, "b.zip")
    body = responses.calls[-1].request.body.decode()
    assert body.count("<Part>") == 3 and '"e1"' in body and "<PartNumber>3</PartNumber>" in body

    responses.reset()
    responses.add(responses.POST, url, body="<r><UploadId>UP2</UploadId></r>", status=200,
                  match=[responses.matchers.query_param_matcher({"uploads": ""})])
    responses.add(responses.PUT, url, status=500)
    responses.add(responses.DELETE, url, status=204)
    with pytest.raises(ProviderError):
        _s3().upload(f, "b.zip")
    assert responses.calls[-1].request.method == "DELETE"                            # yarım yükleme temizlendi


@responses.activate
def test_s3_denied_is_permanent_and_list_and_custom_endpoint(tmp_path):
    f = tmp_path / "x.zip"
    f.write_bytes(b"1")
    responses.add(responses.PUT, "https://yedek-kovasi.s3.us-east-1.amazonaws.com/x.zip", status=403)
    with pytest.raises(ProviderError) as e:
        _s3().upload(f, "x.zip")
    assert e.value.permanent
    responses.add(responses.GET, "https://minio.local:9000/yedek-kovasi/", status=200, body=(
        "<ListBucketResult><Contents><Key>toya/a.zip</Key><LastModified>x</LastModified><Size>10</Size></Contents>"
        "<Contents><Key>toya/alt/b.zip</Key><Size>5</Size></Contents></ListBucketResult>"))
    p = rp.S3Provider("yedek-kovasi", "ak", "sk", endpoint="https://minio.local:9000", prefix="toya")
    assert p.list() == [{"name": "a.zip", "size": 10}]
    assert responses.calls[-1].request.url.startswith("https://minio.local:9000/yedek-kovasi/?")
    for bad in ("A", "bu_gecersiz", "-x-", "ab"):
        with pytest.raises(ProviderError):
            rp.S3Provider(bad, "a", "b")


# ---------------------------------------------------------------- Google Drive
def _drive() -> rp.GoogleDriveProvider:
    return rp.GoogleDriveProvider("cid", "csecret", "refresh-xyz", "TOYA Yedek")


def _token_ok():
    responses.add(responses.POST, rp.GDRIVE_TOKEN, json={"access_token": "AT1"}, status=200)


@responses.activate
def test_drive_creates_folder_uploads_in_chunks_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "GDRIVE_CHUNK", 262144)
    f = tmp_path / "toya.zip"
    f.write_bytes(b"D" * 600000)
    _token_ok()
    responses.add(responses.GET, f"{rp.GDRIVE_API}/files", json={"files": []}, status=200)      # klasör yok, dosya yok
    responses.add(responses.POST, f"{rp.GDRIVE_API}/files", json={"id": "FOLDER1"}, status=200)
    responses.add(responses.POST, rp.GDRIVE_UPLOAD, status=200, headers={"Location": "https://upload.example/session1"})
    responses.add(responses.PUT, "https://upload.example/session1", status=308)
    responses.add(responses.PUT, "https://upload.example/session1", status=308)
    responses.add(responses.PUT, "https://upload.example/session1", status=200, json={"id": "F1"})
    prog = []
    _drive().upload(f, "toya.zip", lambda d, t: prog.append(d))
    puts = [c.request for c in responses.calls if c.request.method == "PUT"]
    assert [r.headers["Content-Range"] for r in puts] == ["bytes 0-262143/600000", "bytes 262144-524287/600000", "bytes 524288-599999/600000"]
    assert prog[-1] == 600000
    init = [c.request for c in responses.calls if c.request.url.startswith(rp.GDRIVE_UPLOAD)][0]
    assert b"FOLDER1" in init.body and init.headers["Authorization"] == "Bearer AT1"


@responses.activate
def test_drive_refreshes_expired_token_and_reports_revoked_access_as_permanent(tmp_path):
    responses.add(responses.POST, rp.GDRIVE_TOKEN, json={"access_token": "OLD"}, status=200)
    responses.add(responses.POST, rp.GDRIVE_TOKEN, json={"access_token": "NEW"}, status=200)
    responses.add(responses.GET, f"{rp.GDRIVE_API}/files", status=401)
    responses.add(responses.GET, f"{rp.GDRIVE_API}/files", json={"files": [{"id": "FOLDER1"}]}, status=200)
    ok, msg = _drive().test()
    assert ok and responses.calls[-1].request.headers["Authorization"] == "Bearer NEW"
    responses.reset()
    responses.add(responses.POST, rp.GDRIVE_TOKEN, json={"error": "invalid_grant"}, status=400)
    with pytest.raises(ProviderError) as e:
        _drive()._auth()
    assert e.value.permanent and "refresh-xyz" not in str(e.value)
    assert _drive().test()[0] is False


@responses.activate
def test_drive_quota_and_server_errors(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"1")
    _token_ok()
    responses.add(responses.GET, f"{rp.GDRIVE_API}/files", json={"files": [{"id": "FOLDER1"}]}, status=200)
    responses.add(responses.GET, f"{rp.GDRIVE_API}/files", json={"files": []}, status=200)
    responses.add(responses.POST, rp.GDRIVE_UPLOAD, status=403, body="storageQuotaExceeded quota")
    with pytest.raises(ProviderError) as e:
        _drive().upload(f, "a.zip")
    assert e.value.permanent and "dolu" in str(e.value)


@responses.activate
def test_drive_interactive_authorization_uses_pkce_state_and_returns_only_refresh_token():
    responses.add_passthru("http://127.0.0.1")
    responses.add(responses.POST, rp.GDRIVE_TOKEN, json={"refresh_token": "RT-YENI", "access_token": "x"}, status=200)
    seen = {}

    def fake_browser(url: str) -> None:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        seen.update({k: v[0] for k, v in q.items()})
        threading.Thread(target=lambda: requests.get(f"{q['redirect_uri'][0]}/?code=KOD123&state={q['state'][0]}"), daemon=True).start()

    out = rp.authorize_google_interactive("cid", "csecret", timeout=10, open_browser=fake_browser)
    assert out == {"refresh_token": "RT-YENI"}
    assert seen["scope"] == rp.GDRIVE_SCOPE and seen["code_challenge_method"] == "S256" and seen["access_type"] == "offline"
    post = [c.request for c in responses.calls if c.request.url == rp.GDRIVE_TOKEN][0]
    body = urllib.parse.parse_qs(post.body)
    assert body["code"] == ["KOD123"] and body["code_verifier"][0] and body["redirect_uri"][0].startswith("http://127.0.0.1:")


@responses.activate
def test_drive_authorization_rejects_wrong_state_and_denied_consent():
    responses.add_passthru("http://127.0.0.1")

    def evil_browser(url: str) -> None:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        threading.Thread(target=lambda: requests.get(f"{q['redirect_uri'][0]}/?code=X&state=BASKA"), daemon=True).start()

    with pytest.raises(ProviderError):
        rp.authorize_google_interactive("cid", "cs", timeout=10, open_browser=evil_browser)

    def deny(url: str) -> None:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        threading.Thread(target=lambda: requests.get(f"{q['redirect_uri'][0]}/?error=access_denied&state={q['state'][0]}"), daemon=True).start()

    with pytest.raises(ProviderError, match="access_denied"):
        rp.authorize_google_interactive("cid", "cs", timeout=10, open_browser=deny)


# ---------------------------------------------------------------- kimlik deposu + fabrika
class _FakeKeyring:
    def __init__(self):
        self.d = {}

    def set_password(self, s, n, v):
        self.d[(s, n)] = v

    def get_password(self, s, n):
        return self.d.get((s, n))

    def delete_password(self, s, n):
        self.d.pop((s, n), None)


def test_secrets_use_the_keyring_only_and_fail_closed(monkeypatch, tmp_path):
    import keyring

    fake = _FakeKeyring()
    for name in ("set_password", "get_password", "delete_password"):
        monkeypatch.setattr(keyring, name, getattr(fake, name))
    sec.set_secret(sec.KEY_ENCRYPTION, "cok-gizli")
    assert sec.encryption_password() == "cok-gizli" and fake.d
    sec.set_json("hedef-1-a", {"password": "p"})
    assert sec.get_json("hedef-1-a") == {"password": "p"} and sec.get_json("yok") == {}
    sec.delete_secret(sec.KEY_ENCRYPTION)
    assert sec.encryption_password() is None

    def boom(*a):
        raise RuntimeError("depo kilitli")

    monkeypatch.setattr(keyring, "set_password", boom)
    with pytest.raises(sec.SecretStoreError):
        sec.set_secret("x", "y")                                                     # düz metne düşmez
    monkeypatch.setattr(keyring, "get_password", boom)
    assert sec.get_secret("x") is None


def test_build_provider_merges_public_config_with_secrets_and_rejects_unknown(tmp_path):
    p = rp.build_provider({"type": "ftp", "host": "h", "user": "u", "remote_dir": "a/b", "port": 2121, "tls": True}, {"password": "pw"})
    assert isinstance(p, rp.FtpProvider) and p.password == "pw" and p.port == 2121 and p.tls
    g = rp.build_provider({"type": "gdrive", "client_id": "c"}, {"client_secret": "s", "refresh_token": "r"})
    assert isinstance(g, rp.GoogleDriveProvider) and g.refresh == "r"
    s = rp.build_provider({"type": "s3", "bucket": "abc-kova", "access_key": "ak"}, {"secret_key": "sk"})
    assert isinstance(s, rp.S3Provider) and s.sk == "sk"
    assert rp.build_provider({"type": "local", "path": str(tmp_path)}, {}).test()[0]
    with pytest.raises(ProviderError):
        rp.build_provider({"type": "dropbox"}, {})
