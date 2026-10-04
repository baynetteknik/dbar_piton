"""Tests for DocumentNumberingWidget and SeriesEditDialog UI components."""

from src.core.models import Company
from src.desktop.services import numara_servisi as ns
from src.desktop.ui.widgets.document_numbering_widget import (
    DocumentNumberingWidget,
    SeriesEditDialog,
)


def test_document_numbering_widget_load_and_filter(qapp, db_session, monkeypatch):
    db = db_session
    c = Company(code="TESTC", short_name="Test Firma")
    db.add(c)
    db.flush()

    ns.ensure_default_series(db, company_id=c.id)

    w = DocumentNumberingWidget(db_session=db)
    assert w.grid.table_view.rowCount() > 0

    # Filter by search
    w.txt_search.setText("FAT")
    assert w.grid.table_view.rowCount() >= 1


def test_series_edit_dialog_validation_and_preview(qapp, db_session, monkeypatch):
    db = db_session
    dlg = SeriesEditDialog(db_session=db)

    dlg.txt_code.setText("EFA")
    dlg.grp_efatura.setChecked(True)
    dlg.txt_gib_prefix.setText("EFA")
    dlg.txt_sablon.setText("{SERI}{YYYY}{#########}")

    assert "EFA20" in dlg.lbl_preview.text()
    assert "Uygun" in dlg.lbl_gib_badge.text()


def test_settings_widget_numara_serileri_panel_switch(qapp, db_session):
    from src.desktop.ui.settings import SettingsWidget

    sw = SettingsWidget(db_session=db_session)
    sw.switch_panel("numara_serileri")
    assert sw.active_panel_id == "numara_serileri"
    assert sw.lbl_bottom_count.text().startswith("📊")
    assert sw._get_active_table() is not None
