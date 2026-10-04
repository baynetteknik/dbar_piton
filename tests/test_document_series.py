"""Tests for multi-series, company-isolated, and GİB e-invoice document numbering system."""

from datetime import date

import pytest

from src.core.models import Company, Quotation
from src.desktop.services import numara_servisi as ns


def _create_company(db, code="FIRMA1", name="Test Firma A"):
    c = Company(code=code, short_name=name)
    db.add(c)
    db.flush()
    return c


def test_ensure_default_series_creates_standard_series(db_session):
    db = db_session
    c1 = _create_company(db, "C1", "Firma 1")
    series_list = ns.ensure_default_series(db, company_id=c1.id)
    assert len(series_list) > 0
    
    # Check that fatura has both e-fatura (FAT) and e-arsiv (EAR) series
    fat_series = ns.list_series(db, company_id=c1.id, belge_turu="fatura")
    codes = [s.seri_kodu for s in fat_series]
    assert "FAT" in codes
    assert "EAR" in codes
    
    # Ensure idempotency
    series_list_2 = ns.ensure_default_series(db, company_id=c1.id)
    assert len(series_list_2) == 0


def test_company_isolated_numbering_and_series(db_session):
    db = db_session
    c1 = _create_company(db, "COMP1", "Firma 1")
    c2 = _create_company(db, "COMP2", "Firma 2")

    # Custom series for Company 1
    ns.save_series(
        db,
        {
            "company_id": c1.id,
            "belge_turu": "fatura",
            "seri_kodu": "ABC",
            "sablon": "{SERI}{YYYY}{#########}",
            "is_default": True,
            "is_efatura": True,
            "gib_prefix": "ABC",
        },
    )

    # Custom series for Company 2
    ns.save_series(
        db,
        {
            "company_id": c2.id,
            "belge_turu": "fatura",
            "seri_kodu": "XYZ",
            "sablon": "{SERI}{YYYY}{#########}",
            "is_default": True,
            "is_efatura": True,
            "gib_prefix": "XYZ",
        },
    )

    t = date(2026, 10, 1)
    no_c1 = ns.belge_numarasi(db, "fatura", "satis", t, company_id=c1.id, seri_kodu="ABC")
    assert no_c1 == "ABC2026000000001"

    no_c2 = ns.belge_numarasi(db, "fatura", "satis", t, company_id=c2.id, seri_kodu="XYZ")
    assert no_c2 == "XYZ2026000000001"

    # Next number for C1 advances C1 counter only
    no_c1_2 = ns.belge_numarasi(db, "fatura", "satis", t, company_id=c1.id, seri_kodu="ABC")
    assert no_c1_2 == "ABC2026000000002"

    no_c2_2 = ns.belge_numarasi(db, "fatura", "satis", t, company_id=c2.id, seri_kodu="XYZ")
    assert no_c2_2 == "XYZ2026000000002"


def test_gib_einvoice_16_character_validation(db_session):
    db = db_session
    # Valid GİB format (3 chars + 4 year + 9 seq = 16)
    ok, _ = ns.validate_gib_format("EFA", "{SERI}{YYYY}{#########}")
    assert ok is True

    # Invalid prefix (not 3 chars)
    ok, err = ns.validate_gib_format("EF", "{SERI}{YYYY}{#########}")
    assert ok is False
    assert "3 alfanümerik" in err

    # Invalid length template
    ok, err = ns.validate_gib_format("EFA", "{SERI}-{YYYY}-{#####}")
    assert ok is False
    assert "16 karakter" in err

    # Save series rejection with invalid GIB format
    with pytest.raises(ns.SablonHatasi):
        ns.save_series(
            db,
            {
                "belge_turu": "fatura",
                "seri_kodu": "EFA",
                "sablon": "{SERI}-{YYYY}-{#####}",
                "is_efatura": True,
                "gib_prefix": "EFA",
            },
        )


def test_number_gaps_detection(db_session):
    db = db_session
    c = _create_company(db, "GAP1", "Gap Test Co")

    # Produce numbers 1, 2, 4 (simulating 3 is missing/skipped)
    q1 = Quotation(
        quotation_number="TEK-2026-00001",
        belge_turu="teklif",
        yon="satis",
        company_id=c.id,
        currency="TRY",
    )
    q2 = Quotation(
        quotation_number="TEK-2026-00002",
        belge_turu="teklif",
        yon="satis",
        company_id=c.id,
        currency="TRY",
    )
    q4 = Quotation(
        quotation_number="TEK-2026-00004",
        belge_turu="teklif",
        yon="satis",
        company_id=c.id,
        currency="TRY",
    )
    db.add_all([q1, q2, q4])
    db.flush()

    gaps = ns.find_number_gaps(db, "teklif", company_id=c.id, yil=2026)
    assert len(gaps) == 1
    assert gaps[0]["seq"] == 3
    assert gaps[0]["missing_number"] == "TEK-2026-00003"
