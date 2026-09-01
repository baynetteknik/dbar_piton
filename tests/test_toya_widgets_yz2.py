"""
Unit tests for ToyaUI YZ2 widgets (PaginationWidget, ActionBarWidget, ExportWidget, FilterWidget).
"""

import pytest
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.widgets import (
    ActionBarWidget,
    ExportWidget,
    FilterWidget,
    PaginationWidget,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_pagination_widget(qapp):
    widget = PaginationWidget(page_sizes=[10, 20, 50])
    widget.set_total(45)

    assert widget.current_page() == 1
    assert widget.current_page_size() == 10
    assert widget._total_pages == 5

    page_history = []
    widget.page_changed.connect(page_history.append)

    widget.go_to_next_page()
    assert widget.current_page() == 2
    assert page_history[-1] == 2

    widget.go_to_last_page()
    assert widget.current_page() == 5
    assert page_history[-1] == 5

    widget.reset()
    assert widget.current_page() == 1
    assert page_history[-1] == 1


def test_action_bar_widget(qapp):
    bar = ActionBarWidget(
        group_title="TEST İŞLEMLERİ",
        convert_label="Faturaya Dönüştür",
        hide_buttons=["bulk_delete"],
        initial_open=True,
        panel_width=240,
    )

    signals_received = []
    bar.new_clicked.connect(lambda: signals_received.append("new"))
    bar.edit_clicked.connect(lambda: signals_received.append("edit"))
    bar.delete_clicked.connect(lambda: signals_received.append("delete"))
    bar.passive_clicked.connect(lambda: signals_received.append("passive"))
    bar.convert_clicked.connect(lambda: signals_received.append("convert"))
    bar.excel_clicked.connect(lambda: signals_received.append("excel"))
    bar.close_clicked.connect(lambda: signals_received.append("close"))

    bar.btn_new.click()
    bar.btn_edit.click()
    bar.btn_delete.click()
    bar.btn_passive.click()
    bar.btn_convert.click()
    bar.btn_excel.click()
    bar.btn_close.click()

    assert signals_received == ["new", "edit", "delete", "passive", "convert", "excel", "close"]
    assert bar.btn_bulk_delete.isHidden()
    assert bar.is_open() is True


def test_export_widget(qapp):
    widget = ExportWidget(
        group_title="DIŞA AKTAR",
        hide_buttons=["import_excel"],
        initial_open=True,
    )

    signals_received = []
    widget.export_excel_clicked.connect(lambda: signals_received.append("excel"))
    widget.export_pdf_clicked.connect(lambda: signals_received.append("pdf"))
    widget.print_clicked.connect(lambda: signals_received.append("print"))
    widget.report_clicked.connect(lambda: signals_received.append("report"))

    widget.btn_export_excel.click()
    widget.btn_export_pdf.click()
    widget.btn_print.click()
    widget.btn_report.click()

    assert signals_received == ["excel", "pdf", "print", "report"]
    assert widget.btn_import_excel.isHidden()
    assert widget.section.is_expanded is True


def test_filter_widget(qapp):
    widget = FilterWidget(
        status_options=["Tümü", "Aktif", "Pasif"],
        group_options=["Tümü", "A", "B"],
        initial_open=True,
    )
    widget.show()

    assert widget.is_open() is True

    captured_filters = []
    cleared_events = []
    widget.filter_changed.connect(captured_filters.append)
    widget.filters_cleared.connect(lambda: cleared_events.append(True))

    widget.search_box.setText("Test Cari")
    assert captured_filters[-1]["search"] == "Test Cari"
    assert not widget.lbl_counter.isHidden()
    assert "1 Filtre Aktif" in widget.lbl_counter.text()

    widget.cmb_status.setCurrentText("Aktif")
    assert captured_filters[-1]["status"] == "Aktif"
    assert "2 Filtre Aktif" in widget.lbl_counter.text()

    widget.date_from.setDate(QDate(2026, 8, 27))
    assert captured_filters[-1]["date_from"] == "2026-08-27"
    assert "3 Filtre Aktif" in widget.lbl_counter.text()

    widget.clear_filters()
    assert cleared_events == [True]
    assert captured_filters[-1] == {}
    assert widget.lbl_counter.isHidden()

