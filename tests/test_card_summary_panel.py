"""CardSummaryPanel — KPI, satırlar ve resim alanı."""

from src.desktop.ui.widgets.card_summary_panel import CardSummaryPanel


def test_kpi_and_rows(qapp):
    p = CardSummaryPanel(title="Özet Bilgi")
    p.set_kpi("Toplam Stok Miktarı", 100)
    assert p.lbl_kpi_label.text() == "Toplam Stok Miktarı"
    assert p.lbl_kpi_value.text() == "100"

    p.set_rows([("Son Alış Tarihi", "—"), ("Son Satış Fiyatı", "1.489,31")])
    assert p._rows_grid.count() == 4          # 2 satır × (etiket + değer)

    p.set_rows([("Tek", "1")])               # yeniden çizim
    assert p._rows_grid.count() == 2


def test_image_slot_roundtrip(qapp):
    p = CardSummaryPanel(image_key="image_path")
    assert p.image_field is not None
    assert p.image_value() is None


def test_no_image_slot_when_key_absent(qapp):
    p = CardSummaryPanel()
    assert p.image_field is None


def test_updater_invoked(qapp):
    p = CardSummaryPanel()
    seen = {}
    p.set_updater(lambda d: seen.update(d))
    p.update_from({"stock": 7})
    assert seen == {"stock": 7}
