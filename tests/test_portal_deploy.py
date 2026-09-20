"""Portal paketini FTP ile gönderme — gerçek FTP protokolüyle (yerel pyftpdlib sunucusu)."""

from __future__ import annotations

import ftplib
import threading

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from src.core.models import DataTransferLog
from src.desktop.services import portal_deploy as dep

USER, PASSWORD = "toya", "cok-gizli-ftp-parolasi"


@pytest.fixture
def ftp_server(tmp_path):
    root = tmp_path / "ftproot"
    root.mkdir()
    auth = DummyAuthorizer()
    auth.add_user(USER, PASSWORD, str(root), perm="elradfmwMT")
    handler = type("H", (FTPHandler,), {"authorizer": auth, "passive_ports": range(50000, 50100)})
    handler.banner = "test"
    server = FTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=lambda: server.serve_forever(timeout=0.2, handle_exit=False), daemon=True)
    t.start()
    yield root, server.address[1]
    server.close_all()
    t.join(timeout=5)


def _profile(port, **kw):
    base = dict(host="127.0.0.1", port=port, user=USER, password=PASSWORD, remote_dir="public_html/portal",
                use_tls=False)
    base.update(kw)
    return dep.FtpProfile(**base)


def _zip(tmp_path, name="toya-portal-1.2.3.zip", size=300_000):
    p = tmp_path / name
    p.write_bytes(b"PK\x03\x04" + bytes(range(256)) * (size // 256))
    return p


# ---- bağlantı --------------------------------------------------------------
def test_connection_ok_and_reports_missing_portal_folder(ftp_server):
    _root, port = ftp_server
    r = dep.test_connection(_profile(port))
    assert r.success and "bulunamadı" in r.message  # klasör henüz yok ama bağlantı tamam


def test_connection_detects_existing_portal_folder(ftp_server):
    root, port = ftp_server
    (root / "public_html" / "portal" / "src").mkdir(parents=True)
    r = dep.test_connection(_profile(port))
    assert r.success and "portal klasörü bulundu" in r.message


def test_wrong_password_gives_friendly_message_without_leaking_it(ftp_server):
    _root, port = ftp_server
    r = dep.test_connection(_profile(port, password="yanlis-parola-xyz"))
    assert not r.success and "reddedildi" in r.message and "yanlis-parola-xyz" not in r.message


def test_unreachable_server_and_bad_host(ftp_server):
    _root, port = ftp_server
    assert not dep.test_connection(_profile(1)).success  # kimse dinlemiyor
    r = dep.test_connection(_profile(port, host="bu-alan-adi-yok.invalid"))
    assert not r.success and "çözümlen" in r.message


def test_tls_against_plain_server_fails_cleanly(ftp_server):
    _root, port = ftp_server
    r = dep.test_connection(_profile(port, use_tls=True))
    assert not r.success and r.message


def test_incomplete_profile_and_dotdot_dir_rejected(ftp_server):
    _root, port = ftp_server
    assert not dep.test_connection(dep.FtpProfile()).success
    assert "'..'" in dep.test_connection(_profile(port, remote_dir="../disari")).message


# ---- yükleme ---------------------------------------------------------------
def test_upload_creates_folders_and_delivers_identical_file(ftp_server, tmp_path):
    root, port = ftp_server
    z = _zip(tmp_path)
    seen = []
    r = dep.upload_package(z, _profile(port), progress=lambda s, t: seen.append((s, t)))
    assert r.success and r.remote_path == "public_html/portal/update_inbox/toya-portal-1.2.3.zip"
    dest = root / "public_html" / "portal" / "update_inbox" / "toya-portal-1.2.3.zip"
    assert dest.read_bytes() == z.read_bytes()
    assert not list((root / "public_html" / "portal" / "update_inbox").glob("*.part"))
    assert seen and seen[-1] == (z.stat().st_size, z.stat().st_size)
    assert [s for s, _ in seen] == sorted(s for s, _ in seen)  # ilerleme artan


def test_upload_replaces_an_older_file_with_the_same_name(ftp_server, tmp_path):
    root, port = ftp_server
    z = _zip(tmp_path)
    dep.upload_package(z, _profile(port))
    z.write_bytes(b"PK" + b"yeni-icerik" * 1000)
    assert dep.upload_package(z, _profile(port)).success
    dest = root / "public_html" / "portal" / "update_inbox" / "toya-portal-1.2.3.zip"
    assert dest.read_bytes() == z.read_bytes()


def test_invalid_package_names_and_missing_file_rejected(ftp_server, tmp_path):
    _root, port = ftp_server
    assert not dep.upload_package(tmp_path / "yok.zip", _profile(port)).success
    bad = tmp_path / "shell.php"
    bad.write_bytes(b"x")
    assert "toya-portal-X.Y.Z.zip" in dep.upload_package(bad, _profile(port)).message
    evil = tmp_path / "toya-portal-1.2.3.zip.php"
    evil.write_bytes(b"x")
    assert not dep.upload_package(evil, _profile(port)).success


def test_failed_size_check_deletes_the_partial_file(ftp_server, tmp_path, monkeypatch):
    root, port = ftp_server
    monkeypatch.setattr(ftplib.FTP, "size", lambda self, name: 1)  # sunucu yanlış boyut bildirir
    r = dep.upload_package(_zip(tmp_path), _profile(port))
    inbox = root / "public_html" / "portal" / "update_inbox"
    assert not r.success and "doğrulanamadı" in r.message
    assert list(inbox.iterdir()) == []  # ne .part ne de paket kaldı


def test_failed_rename_never_leaves_a_valid_looking_package(ftp_server, tmp_path, monkeypatch):
    root, port = ftp_server

    def boom(self, a, b):
        raise ftplib.error_perm("550 rename yasak")

    monkeypatch.setattr(ftplib.FTP, "rename", boom)
    r = dep.upload_package(_zip(tmp_path), _profile(port))
    inbox = root / "public_html" / "portal" / "update_inbox"
    assert not r.success
    assert not (inbox / "toya-portal-1.2.3.zip").exists()  # yarım paket asıl adıyla görünmez


def test_broken_progress_callback_does_not_break_the_upload(ftp_server, tmp_path):
    root, port = ftp_server

    def bad(_s, _t):
        raise RuntimeError("arayüz hatası")

    assert dep.upload_package(_zip(tmp_path), _profile(port), progress=bad).success


# ---- profil ve günlük -----------------------------------------------------------
def test_profile_roundtrip_through_settings(db_session):
    p = dep.FtpProfile(host="ftp.ornek.com", port=2121, user="u", password="p", remote_dir="portal",
                       use_tls=False, verify_cert=False, passive=False)
    p.save(db_session)
    q = dep.FtpProfile.load(db_session)
    assert (q.host, q.port, q.user, q.password, q.remote_dir) == ("ftp.ornek.com", 2121, "u", "p", "portal")
    assert (q.use_tls, q.verify_cert, q.passive) == (False, False, False)
    assert q.is_complete()


def test_deploy_is_logged_without_leaking_the_password(ftp_server, tmp_path, db_session):
    _root, port = ftp_server
    z = _zip(tmp_path)
    assert dep.deploy(db_session, z, _profile(port)).success
    assert not dep.deploy(db_session, z, _profile(port, password="yanlis-parola-xyz")).success
    rows = db_session.query(DataTransferLog).order_by(DataTransferLog.id).all()
    assert [r.status for r in rows] == ["ok", "error"] and all(r.direction == "deploy_to_portal" for r in rows)
    assert all(PASSWORD not in (r.message or "") and "yanlis-parola-xyz" not in (r.message or "") for r in rows)
    assert "toya-portal-1.2.3.zip" in rows[0].counts_json


# ---- arayüz bileşeni ------------------------------------------------------------
def _fake_portal(tmp_path):
    portal = tmp_path / "portal_src"
    (portal / "src").mkdir(parents=True, exist_ok=True)
    (portal / "src" / "A.php").write_text("<?php // A", encoding="utf-8")
    (portal / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    return portal


def _widget(db_session, tmp_path):
    from src.desktop.ui.widgets.portal_deploy_widget import PortalDeployWidget

    return PortalDeployWidget(db_session, portal_dir=_fake_portal(tmp_path), output_dir=tmp_path / "out")


def _fill(w, port):
    w.txt_host.setText("127.0.0.1")
    w.spn_port.setValue(port)
    w.txt_user.setText(USER)
    w.txt_pass.setText(PASSWORD)
    w.txt_remote.setText("public_html/portal")
    w.chk_tls.setChecked(False)


def test_widget_suggests_next_version_and_saves_profile(qapp, db_session, tmp_path):
    w = _widget(db_session, tmp_path)
    assert w.txt_version.text() == "1.0.1"
    _fill(w, 2121)
    w.save()
    w2 = _widget(db_session, tmp_path)
    assert (w2.txt_host.text(), w2.spn_port.value(), w2.txt_user.text(), w2.txt_remote.text()) == (
        "127.0.0.1", 2121, USER, "public_html/portal")


def test_widget_copies_the_update_secret(qapp, db_session, tmp_path):
    from PyQt6.QtWidgets import QApplication

    from src.desktop.services import portal_package

    w = _widget(db_session, tmp_path)
    w._on_copy_secret()
    assert QApplication.clipboard().text() == portal_package.get_or_create_secret(db_session)


def test_widget_deploy_builds_signed_package_and_uploads_it(qapp, db_session, tmp_path, ftp_server):
    import zipfile

    from src.desktop.services import portal_package

    root, port = ftp_server
    w = _widget(db_session, tmp_path)
    _fill(w, port)
    seen = []
    r = w._do_deploy(lambda s, t: seen.append(s))
    assert r.success and seen
    dest = root / "public_html" / "portal" / "update_inbox" / "toya-portal-1.0.1.zip"
    with zipfile.ZipFile(dest) as z:
        assert "manifest.json" in z.namelist() and z.read("files/VERSION") == b"1.0.1\n"
    assert portal_package.suggest_next_version(db_session, w.portal_dir) == "1.0.2"  # sürüm ilerledi


def test_widget_builds_softaculous_package_locally_from_the_real_portal(qapp, db_session, tmp_path):
    from pathlib import Path

    from src.desktop.ui.widgets.portal_deploy_widget import PortalDeployWidget

    real = Path(__file__).resolve().parents[1] / "portal"
    w = PortalDeployWidget(db_session, portal_dir=real, output_dir=tmp_path / "out")
    path = w._on_softaculous()
    assert path is not None and path.is_file() and "softaculous" in path.name
    assert "hazır" in w.lbl_status.text() and "Softaculous yoksa" in w.lbl_status.text()


def test_widget_reports_softaculous_build_errors(qapp, db_session, tmp_path):
    w = _widget(db_session, tmp_path)  # sahte portalda softaculous/ betikleri yok
    assert w._on_softaculous() is None
    assert "üretilemedi" in w.lbl_status.text()


def test_widget_reports_package_build_errors(qapp, db_session, tmp_path):
    w = _widget(db_session, tmp_path)
    w.txt_version.setText("1.0")
    r = w._do_deploy()
    assert not r.success and "Paket üretilemedi" in r.message


def test_widget_send_runs_in_background_thread_and_reports_back(qapp, db_session, tmp_path, ftp_server):
    root, port = ftp_server
    w = _widget(db_session, tmp_path)
    _fill(w, port)
    toasts = []
    w.toast_requested.connect(lambda m, t: toasts.append(t))
    w._on_send()
    assert w._worker is not None and not w.btn_send.isEnabled()
    w._worker.wait(20000)
    qapp.processEvents()
    assert w._worker is None and w.btn_send.isEnabled() and toasts == ["success"]
    assert (root / "public_html" / "portal" / "update_inbox" / "toya-portal-1.0.1.zip").exists()
    assert w.txt_version.text() == "1.0.2"


def test_widget_send_with_incomplete_profile_does_nothing(qapp, db_session, tmp_path):
    w = _widget(db_session, tmp_path)
    w._on_send()
    assert w._worker is None


# ---- FTPS (TLS) — kendi imzalı sertifikalı gerçek TLS FTP sunucusu ------------------------
@pytest.fixture
def ftps_server(tmp_path):
    pytest.importorskip("OpenSSL")
    import datetime as dt

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from pyftpdlib.handlers import TLS_FTPHandler

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1))
            .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2))
            .sign(key, hashes.SHA256()))
    pem = tmp_path / "server.pem"
    pem.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                      serialization.NoEncryption()) + cert.public_bytes(serialization.Encoding.PEM))
    root = tmp_path / "ftps_root"
    root.mkdir()
    auth = DummyAuthorizer()
    auth.add_user(USER, PASSWORD, str(root), perm="elradfmwMT")
    handler = type("TH", (TLS_FTPHandler,), {"authorizer": auth, "certfile": str(pem), "keyfile": str(pem),
                                              "tls_control_required": True, "tls_data_required": True,
                                              "passive_ports": range(50100, 50200)})
    server = FTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=lambda: server.serve_forever(timeout=0.2, handle_exit=False), daemon=True)
    t.start()
    yield root, server.address[1]
    server.close_all()
    t.join(timeout=5)


def test_ftps_upload_works_when_certificate_check_is_disabled(ftps_server, tmp_path):
    root, port = ftps_server
    z = _zip(tmp_path)
    r = dep.upload_package(z, _profile(port, use_tls=True, verify_cert=False))
    assert r.success, r.message
    assert (root / "public_html" / "portal" / "update_inbox" / z.name).read_bytes() == z.read_bytes()
    assert dep.test_connection(_profile(port, use_tls=True, verify_cert=False)).success


def test_ftps_rejects_a_self_signed_certificate_by_default_with_a_clear_message(ftps_server, tmp_path):
    _root, port = ftps_server
    r = dep.upload_package(_zip(tmp_path), _profile(port, use_tls=True, verify_cert=True))
    assert not r.success and "sertifika" in r.message.lower()
