"""YardimWidget: Genel Ayarlar > Yardım paneli — arama ve açılır/kapanır konu bölümleri."""

from src.desktop.ui.widgets.yardim_widget import YardimWidget


def test_tum_konular_varsayilan_kapali_gelir(qapp):
    w = YardimWidget()
    assert len(w._bolumler) >= 6   # bugüne kadarki bölümler (bu sayı yeni konu eklendikçe büyür)
    assert all(not sec.is_expanded for sec, *_ in w._bolumler)


def test_arama_eslesen_bolumu_gosterip_acar_eslesmeyeni_gizler(qapp):
    # Not: widget hiç `show()` edilmediği için Qt'nin top-level'a bağlı `isVisible()`'ı her zaman False
    # döner — `isHidden()` (yalnızca kendi/ebeveyn `setVisible(False)` bayrağını yansıtır) kullanılır.
    w = YardimWidget()
    w.txt_ara.setText("BSMV")
    gorunur = [baslik for sec, baslik, _html in w._bolumler if not sec.isHidden()]
    assert gorunur == ["🏦 Banka Ödeme Planları"]
    acik = next(sec for sec, baslik, _h in w._bolumler if baslik == "🏦 Banka Ödeme Planları")
    assert acik.is_expanded


def test_arama_turkce_harf_duyarsiz_ve_icerikte_de_arar(qapp):
    """`sm.matches` Türkçe büyük/küçük harf duyarsız ve hem başlıkta hem içerikte arar (ör. "pos" hem
    başlıkta hem gövdede geçiyor olabilir — en azından ilgili konular bulunmalı)."""
    w = YardimWidget()
    w.txt_ara.setText("formül")
    gorunur = [baslik for sec, baslik, _html in w._bolumler if not sec.isHidden()]
    assert "📑 Çok Türlü Ödeme Planları (Satırlar)" in gorunur


def test_arama_temizlenince_hepsi_tekrar_gorunur_ve_kapanir(qapp):
    w = YardimWidget()
    w.txt_ara.setText("POS")
    w.txt_ara.setText("")
    assert all(not sec.isHidden() for sec, *_ in w._bolumler)
    assert all(not sec.is_expanded for sec, *_ in w._bolumler)
