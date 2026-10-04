"""Unit tests for DevTracker versioning, release management, and milestones."""

from __future__ import annotations

import pytest

from src.desktop.services.dev_tracker_store import DevTracker, DevTrackerError
from src.desktop.ui.widgets.dev_version_dialog import _parse_semver


@pytest.fixture
def dev(tmp_path):
    return DevTracker(tmp_path / "dev_tracker.db")


def test_semver_parser():
    assert _parse_semver("v1.2.3") == (1, 2, 3)
    assert _parse_semver("1.0.0") == (1, 0, 0)
    assert _parse_semver("v2.5") == (2, 5, 0)
    assert _parse_semver("invalid") == (1, 0, 0)


def test_surum_crud_and_validation(dev):
    # Validation tests
    with pytest.raises(DevTrackerError, match="Sürüm kodu boş olamaz"):
        dev.surum_ekle("", "Başlık")
    with pytest.raises(DevTrackerError, match="Sürüm başlığı boş olamaz"):
        dev.surum_ekle("v1.0.0", "")
    with pytest.raises(DevTrackerError, match="Geçersiz sürüm durumu"):
        dev.surum_ekle("v1.0.0", "Başlık", status="invalid_status")

    # Add version
    vid = dev.surum_ekle(
        version_code="v1.0.0",
        title="Temel Modüller",
        description="Kasa, Banka ve Cari geliştirmeleri",
        target_date="2026-10-15",
        status="gelistirmede",
    )
    assert vid > 0

    # Duplicate code error
    with pytest.raises(DevTrackerError, match="zaten mevcut"):
        dev.surum_ekle("v1.0.0", "İkinci Deneme")

    # Get version
    v = dev.surum_getir(vid)
    assert v["version_code"] == "v1.0.0"
    assert v["title"] == "Temel Modüller"
    assert v["status"] == "gelistirmede"

    # Update version
    dev.surum_guncelle(vid, title="Temel Modüller & Fatura", status="testte")
    v_up = dev.surum_getir(vid)
    assert v_up["title"] == "Temel Modüller & Fatura"
    assert v_up["status"] == "testte"

    # Delete (hide) version
    dev.surum_sil(vid)
    assert dev.surum_liste() == []


def test_surum_gorev_atama_ve_istatistikler(dev):
    dev.surum_ekle("v1.0.0", "İlk Sürüm", target_date="2026-10-01", status="gelistirmede")
    dev.surum_ekle("v1.1.0", "İkinci Sürüm", target_date="2026-11-01", status="planli")

    # Add items
    dev.ekle("Kasa Fişleri", modul="Kasa", surum="v1.0.0", durum="tamam")
    dev.ekle("Banka Fişleri", modul="Banka", surum="v1.0.0", durum="devam")
    dev.ekle("Cari Fişleri", modul="Cari", surum="v1.0.0", durum="test")
    i4 = dev.ekle("Fatura İrsaliye", modul="Fatura", surum="v1.1.0", durum="planli")
    i5 = dev.ekle("Sürümsüz Görev", modul="Sistem")

    # Check surum_liste with progress calculations
    s_list = dev.surum_liste()
    assert len(s_list) == 2
    v1_stat = next(x for x in s_list if x["version_code"] == "v1.0.0")
    assert v1_stat["total_items"] == 3
    assert v1_stat["completed_items"] == 1
    assert v1_stat["in_progress_items"] == 1
    assert v1_stat["test_items"] == 1
    assert v1_stat["progress_percent"] == 33  # 1/3 = 33%

    v2_stat = next(x for x in s_list if x["version_code"] == "v1.1.0")
    assert v2_stat["total_items"] == 1
    assert v2_stat["completed_items"] == 0
    assert v2_stat["progress_percent"] == 0

    # Test batch assignment: assign i5 and reassign i4 to v1.0.0
    dev.surume_gorevleri_ata([i4, i5], "v1.0.0", kim="tester")
    assert dev.getir(i4)["surum"] == "v1.0.0"
    assert dev.getir(i5)["surum"] == "v1.0.0"

    # Test filtering by version in liste()
    v1_items = dev.liste(surum="v1.0.0")
    assert len(v1_items) == 5

    # Unassign i5
    dev.surume_gorevleri_ata([i5], None, kim="tester")
    assert dev.getir(i5)["surum"] is None
    atanmamis = dev.liste(surum="atanmamis")
    assert len(atanmamis) == 1
    assert atanmamis[0]["baslik"] == "Sürümsüz Görev"


def test_surum_kapat_ve_yayinla(dev, tmp_path):
    vid = dev.surum_ekle("v1.0.0", "Release 1", target_date="2026-10-01", status="gelistirmede")
    dev.ekle("Kasa fişi", modul="Kasa", surum="v1.0.0", durum="tamam", commit_hash="a1b2c3d4e5f6")
    dev.ekle("Hata düzeltmesi", tur="hata", modul="Banka", surum="v1.0.0", durum="tamam")
    dev.ekle("İyileştirme", tur="oneri", modul="UI", surum="v1.0.0", durum="tamam")

    md_file = tmp_path / "SURUM_NOTLARI.md"
    md_file.write_text("# Sürüm Notları\n", encoding="utf-8")

    # Release version
    res = dev.surum_kapat_ve_yayinla("v1.0.0", release_date="2026-09-30", git_tag=False)
    assert res["version_code"] == "v1.0.0"
    assert res["release_date"] == "2026-09-30"

    v_after = dev.surum_getir(vid)
    assert v_after["status"] == "yayinlandi"
    assert v_after["release_date"] == "2026-09-30"

    # Generate and verify markdown output
    dev.surum_notlarina_yaz(md_file)
    content = md_file.read_text(encoding="utf-8")
    assert "## [v1.0.0] — 2026-09-30 — Release 1" in content
    assert "### 🛠️ Geliştirmeler & Yeni Özellikler" in content
    assert "**Kasa:** Kasa fişi — `a1b2c3d`" in content
    assert "### 🐞 Düzeltilen Hatalar" in content
    assert "**Banka:** Hata düzeltmesi" in content
    assert "### 💡 Tamamlanan İyileştirmeler & Öneriler" in content
    assert "**UI:** İyileştirme" in content
