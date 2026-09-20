"""Unit tests for MainWindow 3-column vertical dashboard and footer navigation."""

import pytest
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.main_window import MainWindow


def test_main_window_tabs_and_dashboard(qapp, db_session):
    """Verify 3-column vertical Dashboard, footer menu navigation, and dynamic tabs."""
    window = MainWindow(db_session=db_session)
    window.show()

    # 1. Dashboard is permanent Tab 0
    assert window.tab_widget.count() == 1
    assert "Ana Panel" in window.tab_widget.tabText(0)
    assert window.tab_widget.currentIndex() == 0

    # 2. 3-Column Vertical Layout Verification
    assert hasattr(window, "fav_screens_frame")
    assert hasattr(window, "fav_reports_frame")
    assert hasattr(window, "main_icons_frame")

    # Left: Favori Ek İşlemler List
    assert window.fav_screens_list.count() > 0
    first_fav = window.fav_screens_list.item(0)
    assert any(icon in first_fav.text() for icon in ["📦", "💾", "📄", "👥", "⭐"])

    # Middle: Favori Raporlar List
    assert window.fav_reports_list.count() >= 3
    first_rep = window.fav_reports_list.item(0)
    assert "📊" in first_rep.text() or "Sipariş" in first_rep.text()

    # Right: Ana İkonlar Grid
    assert window.grid_layout.count() >= 7

    # 3. Footer Bar Navigation & Menu Buttons
    assert hasattr(window, "footer_bar")
    assert hasattr(window, "menu_buttons")
    assert len(window.menu_buttons) >= 5
    for btn in window.menu_buttons:
        # Verify no double emojis
        text = btn.text()
        assert not text.startswith("📊  📊")
        assert not text.startswith("👥  👥")
        assert not text.startswith("📦  📦")

    # 4. Test GridModuleButton click directly opens module
    first_grid_item = window.grid_layout.itemAt(0).widget()
    assert first_grid_item is not None
    initial_tabs = window.tab_widget.count()
    first_grid_item.click()
    assert window.tab_widget.count() == initial_tabs + 1

    # 5. Test Context Menu Styling Rule (Zemin Mavi #1e3a8a, Yazılar Beyaz #ffffff)
    styled_menu = window.create_styled_menu()
    assert "#1e3a8a" in styled_menu.styleSheet()
    assert "#ffffff" in styled_menu.styleSheet()

    # 6. Cannot close Tab 0
    window.close_tab(0)
    assert window.tab_widget.count() == initial_tabs + 1

    # 7. Open Teklif Yönetimi
    window.open_module_in_tab("Teklif Yönetimi")
    assert "Teklif Yönetimi" in window.tab_widget.tabText(window.tab_widget.currentIndex())

    # 8. Test Favorite Add / Remove
    initial_count = len(window.favoriler)
    window.favoriye_ekle("Fiyat Politikaları")
    assert len(window.favoriler) == initial_count + 1
    window.favoriden_cikar("Fiyat Politikaları")
    assert len(window.favoriler) == initial_count

    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_main_window_schedules_currency_autofetch_once(qapp, db_session, monkeypatch, mock_api):
    """Program açılışında (MainWindow oluşturulunca) seçili döviz kuru
    kaynağından bir kerelik otomatik çekim tetiklenmeli (bkz. `_schedule_currency_autofetch`
    -> `currency_rate_service.startup_autofetch`)."""
    from src.core.models import Currency
    from src.desktop.services import currency_rate_service

    db_session.add(Currency(code="USD", name="Amerikan Doları", symbol="$", rate=1.0, is_active=True))
    db_session.commit()
    currency_rate_service.set_source_config(db_session, currency_rate_service.SOURCE_TCMB)
    mock_api.add(
        mock_api.GET, currency_rate_service.TCMB_URL, status=200,
        body=(
            b'<Tarih_Date><Currency Kod="USD">'
            b"<ForexSelling>41.25</ForexSelling></Currency></Tarih_Date>"
        ),
    )

    # Yalnızca 800ms'lik döviz zamanlayıcısını hemen (senkron) tetikler. Diğer tüm
    # singleShot çağrıları (örn. FilterableTableView'ın ertelenmiş profil uygulaması)
    # gerçek davranışında kalmalı; global yama, tablo kurulmadan çalışıp yerel
    # çökmeye (access violation) yol açıyordu.
    from PyQt6.QtCore import QTimer

    _orig_single_shot = QTimer.singleShot

    def _fake_single_shot(ms, *args):
        if ms == 800 and len(args) == 1 and callable(args[0]):
            args[0]()
        else:
            _orig_single_shot(ms, *args)

    monkeypatch.setattr(QTimer, "singleShot", staticmethod(_fake_single_shot))
    # Bu test kasıtlı olarak gerçek tetiklemeyi doğruluyor; üretim kodu
    # normalde pytest altında (PYTEST_CURRENT_TEST) atlar — bkz. main_window.py.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    window = MainWindow(db_session=db_session)

    usd = db_session.query(Currency).filter_by(code="USD").one()
    assert usd.rate == 41.25

    window.close()
    window.deleteLater()
    qapp.processEvents()


