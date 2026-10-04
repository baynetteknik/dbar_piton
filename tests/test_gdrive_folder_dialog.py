"""Google Drive klasör gezgini penceresi ve yedek hedefi diyaloğundaki klasör seçimi (sahte sağlayıcıyla)."""

import json
import time

import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from src.desktop.services.backup.providers import ProviderError
from src.desktop.services.backup.remote_providers import ROOT, SHARED
from src.desktop.ui.widgets.backup_target_dialog import BackupTargetDialog
from src.desktop.ui.widgets.gdrive_folder_dialog import GoogleDriveFolderDialog

AGAC = {
    ROOT: [{"id": "A", "name": "Belgeler"}, {"id": "B", "name": "Yedekler"}],
    "B": [{"id": "B1", "name": "TOYA"}],
    "B1": [],
    SHARED: [{"id": "S1", "name": "Ortak Klasör"}],
    "S1": [],
}


class SahteDrive:
    def __init__(self, hata: Exception | None = None) -> None:
        self.hata, self.olusturulan, self.istekler = hata, [], []

    def list_folders(self, parent_id=ROOT):
        self.istekler.append(parent_id)
        if self.hata:
            raise self.hata
        return list(AGAC.get(parent_id, []))

    def create_folder(self, name, parent_id=ROOT):
        self.olusturulan.append((name, parent_id))
        yeni = {"id": "N-" + name, "name": name}
        AGAC[yeni["id"]] = []
        return yeni


@pytest.fixture
def dlg(qapp):
    d = GoogleDriveFolderDialog(SahteDrive(), senkron=True)
    yield d
    d.close()


def _adlar(d):
    return [d.grid.item(r, 0).text() for r in range(d.grid.rowCount())]


def _bekle(kosul, saniye=3.0):
    bit = time.time() + saniye
    while time.time() < bit:
        QApplication.processEvents()
        if kosul():
            return True
        time.sleep(0.02)
    return False


def test_kokte_klasorleri_listeler_cift_tikla_girer_yukari_cikar_ve_yolu_gosterir(dlg):
    assert _adlar(dlg) == ["📁  Belgeler", "📁  Yedekler"] and dlg.lbl_yol.text() == "Drive'ım" and not dlg.btn_yukari.isEnabled()
    dlg._gir(1)                                                       # Yedekler
    assert _adlar(dlg) == ["📁  TOYA"] and dlg.lbl_yol.text() == "Drive'ım  ›  Yedekler" and dlg.btn_yukari.isEnabled()
    dlg._gir(0)
    assert dlg.yol() == "Drive'ım / Yedekler / TOYA" and "alt klasör yok" in dlg.lbl_durum.text()
    dlg.yukari()
    dlg.yukari()
    assert dlg.gecerli[0] == ROOT and len(_adlar(dlg)) == 2


def test_gecerli_klasoru_ya_da_listeden_secilen_alt_klasoru_secer(dlg):
    dlg._gir(1)
    assert dlg.btn_sec.text() == "✔ Bu klasörü seç: Yedekler"
    dlg.sec()
    assert dlg.secilen == {"id": "B", "name": "Yedekler", "path": "Drive'ım / Yedekler"}
    d2 = GoogleDriveFolderDialog(SahteDrive(), senkron=True)
    d2.grid.selectRow(0)                                              # Belgeler'i vurgula (içine girmeden)
    assert d2.btn_sec.text() == "✔ Seç: Belgeler"
    d2.sec()
    assert d2.secilen == {"id": "A", "name": "Belgeler", "path": "Drive'ım / Belgeler"}
    d2.close()


def test_benimle_paylasilanlar_koku_klasor_degildir_secilemez_icine_girilince_secilir(dlg):
    dlg.kok(SHARED)
    assert _adlar(dlg) == ["📁  Ortak Klasör"] and not dlg.btn_sec.isEnabled()
    dlg.sec()
    assert dlg.secilen is None
    dlg._gir(0)
    assert dlg.btn_sec.isEnabled() and dlg.yol() == "Benimle Paylaşılanlar / Ortak Klasör"
    dlg.kok(ROOT)
    assert dlg.yol() == "Drive'ım"


def test_yeni_klasor_gecerli_klasorun_icinde_olusturulur_ve_icine_girilir(dlg, monkeypatch):
    dlg._gir(1)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Haftalık", True)))
    dlg.yeni_klasor()
    assert dlg.provider.olusturulan == [("Haftalık", "B")] and dlg.yol() == "Drive'ım / Yedekler / Haftalık"
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", True)))
    dlg.yeni_klasor()
    assert len(dlg.provider.olusturulan) == 1                          # boş ad: işlem yok
    dlg.kok(SHARED)
    dlg.yeni_klasor()
    assert "önce bir klasörün içine" in dlg.lbl_durum.text()


def test_hata_mesaji_gosterilir_liste_bosalir_uygulama_cokmez(qapp):
    d = GoogleDriveFolderDialog(SahteDrive(ProviderError("Klasörleri görmek için tam Drive erişimi gerekir")), senkron=True)
    assert d.grid.rowCount() == 0 and "tam Drive erişimi" in d.lbl_durum.text()
    d.close()
    d = GoogleDriveFolderDialog(SahteDrive(RuntimeError("ağ yok")), senkron=True)
    assert "Klasörler alınamadı: ağ yok" in d.lbl_durum.text()
    d.close()


def test_arka_planda_yukler_pencere_donmaz(qapp):
    d = GoogleDriveFolderDialog(SahteDrive())                          # senkron değil: iş parçacığı
    assert _bekle(lambda: d.grid.rowCount() == 2) and d.grid.isEnabled()
    d.close()


# ---------------------------------------------------------------- hedef diyaloğu
def test_hedef_diyalogu_klasor_secimi_kimlik_ve_yolu_kaydeder_temizler(qapp, monkeypatch):
    d = BackupTargetDialog({"type": "gdrive", "client_id": "cid"}, {"refresh_token": "RT", "client_secret": "CS"})
    monkeypatch.setattr(d, "build_provider", lambda: SahteDrive())

    class Sahte(GoogleDriveFolderDialog):
        def __init__(self, provider, parent=None):
            super().__init__(provider, parent, senkron=True)

        def exec(self):
            self._gir(1)
            self.sec()
            return 1

    import src.desktop.ui.widgets.gdrive_folder_dialog as mod
    monkeypatch.setattr(mod, "GoogleDriveFolderDialog", Sahte)
    d._pick_folder()
    cfg, secret = d.values()
    assert (cfg["folder_id"], cfg["folder_path"], cfg["folder"]) == ("B", "Drive'ım / Yedekler", "Yedekler")
    assert cfg["auth_mode"] == "oauth" and cfg["full_access"] is False and "sa_json" not in secret
    d._clear_folder()
    assert d.values()[0]["folder_id"] == "" and d.values()[0]["folder_path"] == ""


def test_hedef_diyalogu_baglanmadan_klasor_secilemez_servis_hesabi_modu_alanlari_degistirir(qapp, tmp_path, monkeypatch):
    d = BackupTargetDialog({"type": "gdrive", "client_id": "cid"})
    d.show()
    d._pick_folder()
    assert "önce 'Google ile Bağlan'" in d.lbl_status.text()
    d.fields["auth_mode"].setCurrentIndex(d.fields["auth_mode"].findData("service_account"))
    assert not d.btn_google.isVisibleTo(d) and d.btn_sa.isVisibleTo(d) and "yüklenmedi" in d.lbl_google.text()
    d._pick_folder()
    assert "servis hesabı JSON" in d.lbl_status.text()
    yol = tmp_path / "sa.json"
    yol.write_text(json.dumps({"client_email": "x@y.iam.gserviceaccount.com", "private_key": "-----BEGIN PRIVATE KEY-----\n"}), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(yol), "")))
    d._pick_sa_json()
    cfg, secret = d.values()
    assert cfg["auth_mode"] == "service_account" and json.loads(secret["sa_json"])["client_email"].startswith("x@") and "sa_json" not in str(cfg)
    assert "yüklü" in d.lbl_google.text()
    yol.write_text("{}", encoding="utf-8")
    d2 = BackupTargetDialog({"type": "gdrive", "auth_mode": "service_account"})
    d2._pick_sa_json()
    assert "Geçerli bir servis hesabı" in d2.lbl_status.text()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    d3 = BackupTargetDialog({"type": "gdrive", "auth_mode": "service_account"})
    d3._accept()
    assert d3.result() == 0                                             # anahtar yüklenmeden kaydedilemez
    d.close(); d2.close(); d3.close()


def test_hedef_diyalogu_tam_erisim_isareti_google_baglantisina_iletilir(qapp, monkeypatch):
    from src.desktop.services.backup import remote_providers as rp
    gorulen = {}
    monkeypatch.setattr(rp, "authorize_google_interactive", lambda cid, cs, **kw: gorulen.update(kw) or {"refresh_token": "RT"})
    d = BackupTargetDialog({"type": "gdrive", "client_id": "cid", "full_access": True})
    d.fields["client_secret"].setText("CS")
    d._connect_google()
    assert _bekle(lambda: "bağlandı" in d.lbl_status.text())
    assert gorulen == {"full_access": True} and "tam Drive erişimi" in d.lbl_status.text()
    d.close()
