"""Kenar panelinin sabitle / kapat / şerit düğmelerinde ipucu bulunur; sabitleme durumuna göre değişir."""

from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel


def test_kenar_paneli_dugmelerinin_ipuclari_var_ve_sabitlemeyle_degisir(qapp):
    p = EdgeTriggeredPanel("left")
    assert p.close_btn.toolTip() and p.trigger_strip.toolTip()
    assert p.pin_btn.toolTip() == EdgeTriggeredPanel.PIN_ACIK_IPUCU
    p.toggle_pin()
    assert p.pin_btn.toolTip() == EdgeTriggeredPanel.PIN_KAPALI_IPUCU
    p.toggle_pin()
    assert p.pin_btn.toolTip() == EdgeTriggeredPanel.PIN_ACIK_IPUCU
