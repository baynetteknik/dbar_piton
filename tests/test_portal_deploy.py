"""Portal paketini FTP ile gönderme — gerçek FTP protokolüyle (yerel pyftpdlib sunucusu)."""

from __future__ import annotations

import ftplib
import json
import threading

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from src.core.models import DataTransferLog
from src.desktop.services import portal_deploy as dep

USER, PASSWORD = "toya", "cok-gizli-ftp-parolasi"


@pytest.fixture
def keyring_store(monkeypatch):
    """`keyring`'i bellekte bir sözlükle değiştirir (gerçek Windows kimlik deposuna dokunmaz)."""
    import keyring

    d: dict = {}
    monkeypatch.setattr(keyring, "set_password", lambda s, n, v: d.__setitem__((s, n), v))
    monkeypatch.setattr(keyring, "get_password", lambda s, n: d.get((s, n)))
    monkeypatch.setattr(keyring, "delete_password", lambda s, n: d.pop((s, n), None))
    return d


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


# ---- uzak klasör tarama (FTP klasör seçici için) ----------------------------------------
def test_list_remote_dirs_lists_only_subfolders_of_given_path(ftp_server):
    root, port = ftp_server
    (root / "public_html").mkdir()
    (root / "public_html" / "portal").mkdir()
    (root / "public_html" / "diger_site").mkdir()
    (root / "public_html" / "not_a_dir.txt").write_text("x")
    ok, err, dirs = dep.list_remote_dirs(_profile(port), "/public_html")
    assert ok and err == "" and dirs == ["diger_site", "portal"]


def test_list_remote_dirs_reports_error_for_missing_path(ftp_server):
    _root, port = ftp_server
    ok, err, dirs = dep.list_remote_dirs(_profile(port), "/olmayan_klasor")
    assert not ok and dirs == [] and err != ""


def test_list_remote_dirs_requires_host_and_user():
    ok, err, dirs = dep.list_remote_dirs(dep.FtpProfile())
    assert not ok and dirs == [] and "girilmelidir" in err


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
    assert w._worker is not None
    w._worker.wait(20000)
    qapp.processEvents()
    assert w._worker is None and toasts == ["success"]
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


# ---- çoklu FTP profili (PortalFtpProfileStore) --------------------------------------------
def test_profile_store_save_list_get_and_password_in_keyring_not_settings(db_session, keyring_store):
    store = dep.PortalFtpProfileStore(db_session)
    meta = dep.PortalFtpProfile(title="Canlı Sunucu", host="ftp.canli.com", port=21, user="u1", remote_dir="public_html/portal")
    ok, msg = store.save(meta, password="gizli-parola-1")
    assert ok and "Canlı Sunucu" in msg
    assert [p.title for p in store.list()] == ["Canlı Sunucu"]
    got = store.get(meta.id)
    assert got is not None and got.host == "ftp.canli.com" and not hasattr(got, "password")
    assert store.password(meta.id) == "gizli-parola-1"
    # ayarlar tablosunda parola düz metin olarak GEÇMEMELİ
    from src.core.models import SystemSetting
    raw = db_session.query(SystemSetting).filter(SystemSetting.key == dep.KEY_PROFILES).one().value
    assert "gizli-parola-1" not in raw
    resolved = store.resolve(meta.id)
    assert resolved.host == "ftp.canli.com" and resolved.password == "gizli-parola-1" and resolved.is_complete()


def test_profile_store_rejects_duplicate_title_and_updates_existing_by_id(db_session, keyring_store):
    store = dep.PortalFtpProfileStore(db_session)
    a = dep.PortalFtpProfile(title="Sunucu A", host="a.com", user="ua")
    store.save(a, password="pa")
    b = dep.PortalFtpProfile(title="sunucu a", host="b.com", user="ub")  # büyük/küçük harf farkı önemsiz
    ok, msg = store.save(b, password="pb")
    assert not ok and "zaten var" in msg
    a.host = "a-yeni.com"
    ok2, _ = store.save(a, password=None)  # password=None: mevcut parola değişmez
    assert ok2 and store.get(a.id).host == "a-yeni.com" and store.password(a.id) == "pa"


def test_profile_store_hide_removes_from_list_and_deletes_secret(db_session, keyring_store):
    store = dep.PortalFtpProfileStore(db_session)
    a = dep.PortalFtpProfile(title="Geçici", host="x.com", user="u")
    store.save(a, password="parola")
    store.hide(a.id)
    assert store.list() == [] and store.get(a.id).hidden is True
    assert store.password(a.id) == ""  # kimlik deposundan da silindi


def test_profile_store_migrates_legacy_single_profile_once_and_clears_plaintext(db_session, keyring_store):
    legacy = dep.FtpProfile(host="eski.com", port=2121, user="eski_kullanici", password="eski-duz-metin-parola",
                            remote_dir="eski/yol", use_tls=False, verify_cert=False, passive=False)
    legacy.save(db_session)
    store = dep.PortalFtpProfileStore(db_session)
    profiles = store.list()
    assert len(profiles) == 1
    p = profiles[0]
    assert (p.title, p.host, p.port, p.user, p.remote_dir) == ("Varsayılan", "eski.com", 2121, "eski_kullanici", "eski/yol")
    assert (p.use_tls, p.verify_cert, p.passive) == (False, False, False)
    assert store.password(p.id) == "eski-duz-metin-parola"
    assert store.active_id() == p.id
    # eski düz metin ayar temizlendi
    assert dep.FtpProfile.load(db_session).password == ""
    # ikinci çağrı yinelenen profil üretmez (idempotent)
    assert [x.id for x in store.list()] == [p.id]


def test_profile_store_active_profile_persists(db_session, keyring_store):
    store = dep.PortalFtpProfileStore(db_session)
    assert store.active_id() is None
    a = dep.PortalFtpProfile(title="A", host="a.com", user="u")
    store.save(a, password="p")
    store.set_active(a.id)
    assert dep.PortalFtpProfileStore(db_session).active_id() == a.id


def test_deploy_without_explicit_profile_uses_active_stored_profile(db_session, keyring_store, ftp_server, tmp_path):
    root, port = ftp_server
    store = dep.PortalFtpProfileStore(db_session)
    meta = dep.PortalFtpProfile(title="Test", host="127.0.0.1", port=port, user=USER, remote_dir="public_html/portal", use_tls=False)
    store.save(meta, password=PASSWORD)
    store.set_active(meta.id)
    r = dep.deploy(db_session, _zip(tmp_path), profile=None)
    assert r.success, r.message


def test_cwd_or_make_tolerates_jailed_cpanel_root_when_not_creating(ftp_server):
    """create=False: 'public_html' segmenti kökten girilemiyorsa (jailed hesap taklidi) altındaki yolu dener."""
    root, port = ftp_server
    (root / "portal").mkdir()  # jailed hesapta FTP kökü zaten public_html İÇİdir: 'portal' doğrudan kökte
    profile = _profile(port)
    ftp = dep._connect(profile)
    try:
        dep._cwd_or_make(ftp, ["public_html", "portal"], create=False)
        assert ftp.pwd() == "/portal"
    finally:
        ftp.quit()


# ---- arayüzde çoklu profil (standart dbgrid) ---------------------------------------------
def test_widget_profile_grid_save_as_new_switch_and_delete(qapp, db_session, tmp_path, keyring_store):
    w = _widget(db_session, tmp_path)
    assert w.profil_model.rowCount() == 0 and w._current_profile_id is None
    w.txt_title.setText("Canlı Sunucu")
    _fill(w, 2121)
    w.save()
    assert w.profil_model.rowCount() == 1 and w.profil_model.item(0, 0).text() == "Canlı Sunucu"
    assert w.store.active_id() == w._current_profile_id

    # yeni bir profil daha ekle (new_profile() popup açar — burada yalnız seçim temizleme etkisini
    # test ediyoruz; popup'ın gerçekten açıldığı ayrı bir testte doğrulanıyor)
    w.tbl_profil.table_view.clearSelection()
    assert w.txt_host.text() == "" and w._current_profile_id is None
    w.txt_title.setText("Test Sunucusu")
    w.txt_host.setText("test.ornek.com")
    w.txt_user.setText("tu")
    w.txt_pass.setText("tp")
    w.save()
    assert w.profil_model.rowCount() == 2

    # ikinci widget (yeni "oturum"): son etkin profil ("Test Sunucusu") otomatik seçili gelir
    w2 = _widget(db_session, tmp_path)
    assert w2.txt_title.text() == "Test Sunucusu" and w2.txt_host.text() == "test.ornek.com" and w2.txt_pass.text() == "tp"

    # ilk profile geç, sil
    w2.tbl_profil.table_view.selectRow(0)
    secili = w2.txt_title.text()
    assert secili == "Canlı Sunucu"

    def onayla(*a, **k):
        from PyQt6.QtWidgets import QMessageBox
        return QMessageBox.StandardButton.Yes

    import PyQt6.QtWidgets as qtw
    orig = qtw.QMessageBox.question
    qtw.QMessageBox.question = staticmethod(onayla)
    try:
        w2._on_delete_profile()
    finally:
        qtw.QMessageBox.question = orig
    kalan = [w2.profil_model.item(r, 0).text() for r in range(w2.profil_model.rowCount())]
    assert w2.profil_model.rowCount() == 1 and secili not in kalan


# ---- güncelleme anahtarını elle (panodan) alma -----------------------------------------------
def test_set_secret_validates_length_and_placeholder_and_paste_button_uses_it(qapp, db_session, tmp_path):
    from src.desktop.services import portal_package

    with pytest.raises(ValueError, match="en az 32"):
        portal_package.set_secret(db_session, "kisa")
    with pytest.raises(ValueError, match="örnek"):
        portal_package.set_secret(db_session, "DEGISTIR-en-az-32-karakter-rastgele")
    gercek = "sunucu-kurulumunda-uretilen-gercek-anahtar-1234567890"
    assert portal_package.set_secret(db_session, gercek) == gercek
    assert portal_package.get_or_create_secret(db_session) == gercek  # yeniden üretmedi, mevcudu korudu

    w = _widget(db_session, tmp_path)
    from PyQt6.QtWidgets import QApplication
    QApplication.clipboard().setText("DEGISTIR-en-az-32-karakter-rastgele")
    w._on_paste_secret()
    assert "alınamadı" in w.lbl_status.text() and portal_package.get_or_create_secret(db_session) == gercek
    QApplication.clipboard().setText("baska-gecerli-anahtar-otuz-iki-karakterden-uzun")
    w._on_paste_secret()
    assert "kaydedildi" in w.lbl_status.text()
    assert portal_package.get_or_create_secret(db_session) == "baska-gecerli-anahtar-otuz-iki-karakterden-uzun"


# ---- popup detay diyaloğu (liste artık her zaman açık form barındırmıyor) ----------------------
def test_new_profile_and_double_click_open_the_detail_dialog_not_inline(qapp, db_session, tmp_path):
    w = _widget(db_session, tmp_path)
    opened = []
    w._detail_dialog.exec = lambda: opened.append(1) or 0
    w.new_profile()
    assert opened == [1] and w._detail_dialog.windowTitle() == "Yeni FTP Profili"

    w.txt_title.setText("Depo Sunucusu")
    _fill(w, 21)
    w.save()
    opened.clear()
    w.tbl_profil.table_view.doubleClicked.emit(w.profil_model.index(0, 0))
    assert opened == [1] and "Depo Sunucusu" in w._detail_dialog.windowTitle()


def test_double_click_without_selection_warns_instead_of_opening(qapp, db_session, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    w = _widget(db_session, tmp_path)
    opened = []
    w._detail_dialog.exec = lambda: opened.append(1) or 0
    warned = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: warned.append(1)))
    w.tbl_profil.table_view.doubleClicked.emit(w.profil_model.index(0, 0))
    assert opened == [] and warned == [1]


def test_save_button_in_dialog_saves_and_closes(qapp, db_session, tmp_path):
    w = _widget(db_session, tmp_path)
    closed = []
    w._detail_dialog.accept = lambda: closed.append(1)
    w.txt_title.setText("Yeni Profil")
    _fill(w, 21)
    w._on_save_in_dialog()
    assert closed == [1] and w.profil_model.rowCount() == 1


# ---- FTP klasör tarayıcı (Windows Gezgini gibi dolaşma) -----------------------------------------
def test_ftp_browser_lists_and_navigates_subfolders(qapp, ftp_server):
    import src.desktop.ui.widgets.portal_deploy_widget as pdw
    from PyQt6.QtCore import Qt

    root, port = ftp_server
    (root / "public_html" / "portal").mkdir(parents=True)
    profile = _profile(port)

    dlg = pdw._FtpBrowserDialog(profile, "/", None)
    dlg._worker.wait(5000)
    qapp.processEvents()
    names = [dlg.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(dlg.list.count())]
    assert names == ["public_html"]

    dlg._descend(dlg.list.item(0))
    dlg._worker.wait(5000)
    qapp.processEvents()
    assert dlg.path == "/public_html"
    names2 = [dlg.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(dlg.list.count())]
    assert names2 == ["portal"]

    dlg._go_up()
    dlg._worker.wait(5000)
    qapp.processEvents()
    assert dlg.path == "/"


def test_browse_remote_dir_button_requires_host_and_user_first(qapp, db_session, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    w = _widget(db_session, tmp_path)
    warned = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: warned.append(1)))
    w._on_browse_remote_dir()
    assert warned == [1]


# ---- yardım ve sürüm/gönderim geçmişi ------------------------------------------------------------
def test_show_help_opens_a_howto_dialog(qapp, db_session, tmp_path, monkeypatch):
    import src.desktop.ui.widgets.portal_deploy_widget as pdw

    w = _widget(db_session, tmp_path)
    shown = []
    monkeypatch.setattr(pdw.QDialog, "exec", lambda self: shown.append(self) or 0)
    w.show_help()
    assert shown


def test_show_history_lists_previous_deploys(qapp, db_session, tmp_path, ftp_server, monkeypatch):
    import src.desktop.ui.widgets.portal_deploy_widget as pdw

    root, port = ftp_server
    w = _widget(db_session, tmp_path)
    _fill(w, port)
    r = w._do_deploy()
    assert r.success

    shown = []
    monkeypatch.setattr(pdw.QDialog, "exec", lambda self: shown.append(self) or 0)
    w.show_history()
    assert shown and shown[0].list.count() >= 1


def test_show_history_with_no_deploys_says_so(qapp, db_session, tmp_path, monkeypatch):
    import src.desktop.ui.widgets.portal_deploy_widget as pdw

    w = _widget(db_session, tmp_path)
    shown = []
    monkeypatch.setattr(pdw.QDialog, "exec", lambda self: shown.append(self) or 0)
    w.show_history()
    assert shown[0].list.item(0).text() == "Henüz bir gönderim yapılmadı."


# ---- bağlantı testi artık asenkron (popup ilerleme/günlük) --------------------------------------
def test_on_test_runs_in_background_and_reports_result(qapp, tmp_path, db_session, ftp_server):
    root, port = ftp_server
    w = _widget(db_session, tmp_path)
    _fill(w, port)
    w._on_test()
    assert w._test_worker is not None
    w._test_worker.wait(20000)
    qapp.processEvents()
    assert w._test_worker is None
    assert w.lbl_status.text() != ""


# ---- gönderim sonrası otomatik kurulum tetikleme (Online Portal tanımlıysa) ---------------------
def test_send_without_online_portal_configured_still_succeeds_with_skip_note(qapp, tmp_path, db_session, ftp_server):
    root, port = ftp_server
    w = _widget(db_session, tmp_path)
    _fill(w, port)
    r = w._do_deploy()
    assert r.success and "atlandı" in r.message


def test_send_triggers_auto_apply_and_logs_it_when_online_portal_configured(qapp, tmp_path, db_session, ftp_server, mock_api):
    from src.desktop.services import portal_sync_service as psvc
    from src.desktop.services import sync_log_service
    from src.desktop.services.settings_store import set_setting

    root, port = ftp_server
    set_setting(db_session, psvc.KEY_BASE_URL, "https://ornek.example/portal")
    set_setting(db_session, psvc.KEY_API_KEY, "gizli-anahtar")
    mock_api.add(
        mock_api.POST, "https://ornek.example/portal/api/v1/update/apply", status=200,
        json={"ok": True, "from": "1.0.0", "to": "1.0.1", "files": 3},
    )

    w = _widget(db_session, tmp_path)
    _fill(w, port)
    r = w._do_deploy()
    assert r.success and "Kuruldu: 1.0.0" in r.message and "1.0.1" in r.message
    logs = sync_log_service.recent(db_session, source="portal")
    assert any(log.message.startswith("Kuruldu") for log in logs)
    sent = json.loads(mock_api.calls[0].request.body)
    assert sent["package"] == "toya-portal-1.0.1.zip"
