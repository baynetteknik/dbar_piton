# YZ 2 — Görev 26: Kırık testlerin sınıflandırma raporu (yalnızca okuma + belge)

> **Yazacağın tek dosya:** `gelistirme/00_mimari/kirik_testler.md`
> **Kural:** Kod ve test dosyalarına DOKUNMA. Commit yapma. Amaç: hangi kırık test onarılmalı, hangisi silinmeli, karar için veri.

## Bilinen 17 kırık test
```
tests/test_backup_ui.py::test_backup_widget_quick_search_and_popups
tests/test_backup_ui.py::test_backup_column_profile_persistence_and_settings
tests/test_base_managed_list.py::test_view_settings_widget_module_switching
tests/test_customers_ui.py::test_edge_triggered_panel_pin_and_tooltips
tests/test_customers_ui.py::test_view_settings_widget_integration
tests/test_gorev19.py::test_alt_iskonto_context_menu_methods
tests/test_gorev20.py::test_transaction_dialog_widget_composition
tests/test_gorev20.py::test_transaction_dialog_property_proxies
tests/test_gorev20.py::test_calculate_totals_with_toplam_widget
tests/test_gorev20.py::test_get_current_teklif_data
tests/test_gorev20.py::test_toggle_info_panel_f7
tests/test_gorev21.py::test_new_quotation_clears_cari_and_belge
tests/test_gorev21.py::test_doc_no_readonly_and_placeholder
tests/test_gorev21.py::test_window_scoped_shortcuts
tests/test_hareket_kalemleri_integration.py::test_hareket_kalemleri_widget_instance_and_init
tests/test_main_window.py::test_main_window_tabs_and_dashboard
tests/test_view_settings_ui.py::test_view_settings_widget_module_change
```

## Her test için (tek tek çalıştır)
`.venv\Scripts\python.exe -m pytest <dosya>::<test> -q -p no:cacheprovider --tb=short`

Tabloya şu sütunlarla yaz: **Test | Hata mesajı (1 satır) | Kök neden | Test ne ölçüyor | Ölçtüğü özellik hâlâ var mı? | Öneri (ONAR / SİL / YENİDEN YAZ) | Gerekçe**

İpuçları:
- `test_gorev19/20/21` ve `test_hareket_kalemleri_integration` çoğunlukla eski `TransactionDocumentDialog` / `HareketKalemleriWidget`'ı test eder; yeni belge ekranı `DocumentDetailScreen`. Eski pencere hâlâ menüden/başka yerden çağrılıyor mu? (`grep`)
- Profil testleri (`view_settings`, `customers_ui`, `base_managed_list`): test beklentisi (ör. combo indeksi, "⭐ … (Aktif)" etiket biçimi) güncel arayüzle uyuşmuyor olabilir; güncel davranışı `src/desktop/ui/settings.py` ve `components/view_profile_bar.py` içinde doğrula.
- `test_backup_ui::…quick_search_and_popups` odak (`hasFocus`) bekler; pencere odağı ortama bağlı olabilir — ortama bağlı mı, koda bağlı mı, belirt.
- `test_main_window::…dashboard` `fav_screens_frame` niteliğini arıyor; güncel ana pencerede bu nitelik var mı?

## Bitince
Tablonun altına: "hemen silinebilecek", "onarılacak (kolay)", "yeniden yazılacak" olarak 3 madde listesi + `## Yapıldı` (çalıştırdığın komutlar).
