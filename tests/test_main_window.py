"""Unit tests for MainWindow 3-column vertical dashboard and footer navigation."""

from PyQt6.QtWidgets import QApplication

from src.desktop.ui.main_window import MainWindow


def test_main_window_tabs_and_dashboard(qapp, db_session):
    """Verify 3-column vertical Dashboard, footer menu navigation, and dynamic tabs."""
    from src.desktop.services.company_service import CompanyService
    firma_svc = CompanyService(db_session)
    firma_id = firma_svc.save({**CompanyService.blank_company(), "code": "TST", "short_name": "Test A.Ş."}).company_id
    firma_svc.aktif_firma_sec(firma_id)  # 2026-09-30: modül gridindeki ilk öğe artık aktif firma gerektiriyor

    window = MainWindow(db_session=db_session)
    window.show()

    # 1. Dashboard is permanent Tab 0
    assert window.tab_widget.count() == 1
    assert "Ana Panel" in window.tab_widget.tabText(0)
    assert window.tab_widget.currentIndex() == 0

    # 2. 3-Panel Splitter Dashboard Layout Verification
    assert hasattr(window, "dash_splitter")
    assert window.dash_splitter.count() == 3
    assert hasattr(window, "fav_widget")
    assert hasattr(window, "bugun_gorevleri")
    assert hasattr(window, "bildirimler_karti")
    assert hasattr(window, "menu_grid_widget")

    # Left: Favori İşlemler & Kısayollar
    assert hasattr(window, "fav_screens_list")
    assert window.fav_screens_list.count() > 0
    first_fav = window.fav_screens_list.item(0)
    assert any(name in first_fav.text() for name in ["Ürün", "Görev", "Teklif", "Müşteri", "Cari"])

    # Middle: Bugünün Görevleri & Bildirimler Kartları
    assert window.bugun_gorevleri is not None
    assert window.bildirimler_karti is not None

    # Right: Ana Menüler Modül Gridi
    assert window.menu_grid_widget.grid_layout.count() >= 7

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

    # 4. Test MenuGridButton click directly opens module
    first_grid_item = window.menu_grid_widget.grid_layout.itemAt(0).widget()
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




def test_ilk_gosterimde_dash_splitter_bir_kez_yeniden_yerlestirilir(qapp, db_session):
    """Pencere ilk gösterildiğinde (showMaximized() henüz oturmadan) gösterge paneli dar kalabiliyordu;
    kullanıcı pencereyi elle büyütüp küçültene kadar düzelmiyordu. showEvent artık bir olay döngüsü turu
    sonra bölücüyü kendi güncel boyutuna göre yeniden dağıtıyor (tek seferlik, sonraki show()'larda tekrar etmez)."""
    window = MainWindow(db_session=db_session)
    assert window._ilk_gosterim_yapildi is False
    calls = []
    window.dash_splitter.setSizes = lambda sizes, orig=window.dash_splitter.setSizes: (calls.append(sizes), orig(sizes))[1]
    window.show()
    assert window._ilk_gosterim_yapildi is True
    assert not calls                                                            # henüz olay döngüsü işlemedi (QTimer.singleShot(0,...))
    QApplication.processEvents()
    assert calls                                                                # nudge tetiklendi
    onceki = len(calls)
    window.hide()
    window.show()
    QApplication.processEvents()
    assert len(calls) == onceki                                                 # yalnız ilk gösterimde; tekrar tetiklenmez
