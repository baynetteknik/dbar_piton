# Kırık testlerin sınıflandırılması — Görev 26

24.09.2026, mevcut çalışma kopyası. Listedeki **17 test ayrı süreçlerde çalıştırıldı; 17'si de başarısız** (pytest çıkış kodu 1). Kod ve test dosyalarında bu görev kapsamında değişiklik yapılmadı. Bu, tüm test paketinin sonucu değildir.

## Bulgular

- `src/desktop/ui/quotations.py`: yeni `DocumentDetailScreen` varsayılan; `TOYA_OLD_DOC_DIALOG=1` eski `TransactionDocumentDialog` yolunu hâlâ açıyor (yeni/düzenle). Eski pencereyi test eden her testi otomatik olarak silmek doğru değildir.
- `src/desktop/ui/settings.py:1068`: varsayılan modül `quotations`; indeks 1 `customers`; yedek anahtarı `backup_tasks`. `backup` anahtarı ve indeks varsayımları eskimiş.
- `settings.py:1321`: aktif profil etiketi `⭐ {name} (Aktif)`. Görünen metnin ham profil adına eşit olması beklenmemeli. Modelde profil kimliği UserRole ile tutuluyor; ProfileManager üzerinden de doğrulanabilir.
- `src/desktop/ui/components/edge_panel.py`: sabitleme davranışı var, fakat pin/kapat düğmelerine beklenen tooltip atanmıyor. Bu yalnız test eskimesi değil, arayüz eksikliği adayıdır.
- Odak deneyi: gizli `BackupWidget` için `hasFocus=False`; aynı pencere gösterilip etkinleştirildikten ve olay döngüsü beklendikten sonra `isActiveWindow=True`, `hasFocus=True`. Sorun testin görünür/etkin pencere önkoşulunu sağlamaması; mevcut deneyde hızlı arama kodu çalışıyor. Başka pencere yöneticilerinde ayrıca ortam etkisi olabilir.
- Bazı pytest traceback'lerinde `C:\dbar_icin\tests\...` eski derleme yolu görünüyor. Komutların çalışma dizini `C:\toya_erp`; test kaynakları burada okundu. Bu raporda önbellek veya test dosyası silinmedi.

## Sınıflandırma

| Test | Hata mesajı (1 satır) | Kök neden | Test ne ölçüyor | Ölçtüğü özellik hâlâ var mı? | Öneri (ONAR / SİL / YENİDEN YAZ) | Gerekçe |
|---|---|---|---|---|---|---|
| `tests/test_backup_ui.py::test_backup_widget_quick_search_and_popups` | `assert widget.search_box.hasFocus()` → False | Widget gösterilmeden/etkinleştirilmeden işletim sistemi odağı bekleniyor. | Hızlı arama odağı ve detay popup'ı | Evet | **ONAR** | Pencereyi göster, etkinleşmesini ve odak koşulunu bekle. Arama ile popup senaryolarını ayır; popup bölümü ilk assert yüzünden hiç ölçülmüyor. Görünür pencere deneyinde odak doğrulandı. |
| `tests/test_backup_ui.py::test_backup_column_profile_persistence_and_settings` | `assert idx != -1` → -1 | Test `backup` arıyor; güncel ayarlarda `backup_tasks`/`restore_tasks` var. | Modüle bağlı profil saklama ve ayarlar eşleşmesi | Evet | **ONAR** | Sabit anahtarı güncel modülle eşle; doğrudan QSettings'e yazıp aynı değeri okumak yerine gerçek ProfileManager kaydet/yükle akışını doğrula. Görünen `Görevler` metnine bağımlı beklentiyi de güncelle. |
| `tests/test_base_managed_list.py::test_view_settings_widget_module_switching` | `'CustProfile' in ['Varsayılan', ..., '⭐ CustProfile (Aktif)']` başarısız | Ham profil adı, süslenmiş aktif profil etiketiyle karşılaştırılıyor. | İki modülün profillerinin birbirinden ayrılması | Evet | **ONAR** | Modül seçimini `findData` ile koru; profil kimliği/manager üzerinden doğrula; temizlemeyi finally ile güvenceye al. |
| `tests/test_customers_ui.py::test_edge_triggered_panel_pin_and_tooltips` | `'' == 'Paneli Sabitle'` başarısız | Güncel EdgeTriggeredPanel pin/close düğmelerine tooltip atamıyor. | Sabitleme, düğme ipuçları ve durum değişimi | Sabitleme var; ipuçları eksik | **ONAR** | Tooltip gereksinimi korunuyorsa üretim kodunda ipuçlarını geri getir ve testi koru. Hata veren beklentiyi sessizce kaldırma. Sabitleme davranışı ile renk/metin ayrıntılarını ayrı doğrula. |
| `tests/test_customers_ui.py::test_view_settings_widget_integration` | `any('SettingsTest' in item ...)` → False | Profil `customers` için kaydediliyor, ayar ekranı artık `quotations` ile açılıyor. | Profil listeleme ve silme | Evet | **ONAR** | `module_combo.findData('customers')` ile modülü açıkça seç; sonra listeleme/silme ve kalıcı depodan kaldırılmayı doğrula. |
| `tests/test_gorev19.py::test_alt_iskonto_context_menu_methods` | `hasattr(dlg, '_show_alt_iskonto_context_menu')` → False | `_show_...` adlı özel metot yok; `show_alt_iskonto_context_menu` ve `_sort_alt_iskonto` var. | Alt indirim menüsü ve sıralama | Eski pencerede var | **ONAR** | Hayalî metot beklentisini kaldır; geçerli menü eyleminin satırları gerçekten sıraladığını doğrula. Eski yol hâlâ çağrılıyor. |
| `tests/test_gorev20.py::test_transaction_dialog_widget_composition` | `hasattr(dlg, 'cari_widget')` → False | Eski pencerenin artık sahip olmadığı beş-widget bileşimi bekleniyor. | Modüler belge ekranı bileşimi | Yeni DocumentDetailScreen'de karşılıkları var | **YENİDEN YAZ** | Yeni ekranın `cari`, `belge_vade`, `finans`, `lines`, `toplam` bağlantılarını ve veri akışını ölç. Sadece eski nitelik adlarını yeni pencereye kopyalama. |
| `tests/test_gorev20.py::test_transaction_dialog_property_proxies` | `AttributeError: ... no attribute 'cari_widget'` | Mevcut sınıfta bulunmayan eski widget-proxy düzeni test ediliyor. | İç widget'lara erişen eski proxy alanları | Bu proxy sözleşmesi yok; cari/belge girişi var | **SİL** | Bu test özel olarak kaldırılmış iç uygulama yapısını ölçüyor. Cari/belge kayıt-yükleme kapsamı korunarak yalnız bu test kaldırılabilir; eski pencere veya bütün dosya silinmemeli. |
| `tests/test_gorev20.py::test_calculate_totals_with_toplam_widget` | `AttributeError: 'QFrame' object has no attribute 'get_data'` | Eski `toplam_widget` artık QFrame; test ToplamWidget veri API'sini varsayıyor. | 10 × 100, %10 indirim, %20 KDV → 1080 | Evet | **YENİDEN YAZ** | Aynı sayısal senaryoyu yeni ekran/hesaplama sözleşmesinde koru. `test_document_detail_screen.py::test_screen_totals_wiring` ile kapsamı karşılaştır; eski yol için sayısal kayıt testi de korunmalı. |
| `tests/test_gorev20.py::test_get_current_teklif_data` | `AttributeError: ... no attribute 'cari_widget'` | Veri hazırlama adımı eski widget set_data API'sine bağlı. | Cari bilgisinin baskı/teklif verisine aktarımı | Evet | **YENİDEN YAZ** | Yeni ekranın canlı form → baskı veri modelini test et; mevcut `test_build_print_data_maps_live_form` ile birleştirilebilir. |
| `tests/test_gorev20.py::test_toggle_info_panel_f7` | `AttributeError: ... no attribute 'info_panels_widget'` | Eski alan adı bekleniyor; güncel toggle `header_tabs` görünürlüğünü de yönetiyor. | Üst panelin kapanıp açılması | Evet | **ONAR** | Eski pencere için `header_tabs` görünürlüğünü doğrula; yeni ekranın `sec_ust_form` bölümü ayrı senaryo olmalı. |
| `tests/test_gorev21.py::test_new_quotation_clears_cari_and_belge` | `AttributeError: ... no attribute 'cari_widget'` | Eski bileşim beklentisi; test ayrıca temizlemeyi kendisi çağırarak gerçek Yeni akışını ölçmüyor. | Yeni fişte önceki cari/belge bilgisinin taşınmaması | Evet | **YENİDEN YAZ** | Gerçek Yeni veya Kaydet ve Yeni aksiyonunu tetikle; cari kimliği ve başlık/kalem durumunu kontrol et. `test_save_new_resets` mevcut kapsamıyla karşılaştır. |
| `tests/test_gorev21.py::test_doc_no_readonly_and_placeholder` | `'otomatik' in 'kaydedilince atanır'` başarısız | Yardım metni değişmiş; salt okunurluk kontrolü geçiyor. | Numaranın salt okunurluğu ve kayıtla atanacağı bilgisi | Evet | **ONAR** | Semantik davranışı ölç: salt okunur alan, yeni kayıtta boş numara, kayıttan sonra atanmış numara. Metin kontrolünü güncel ifadeyle ayrı tut. |
| `tests/test_gorev21.py::test_window_scoped_shortcuts` | `hasattr(dlg, '_sc_f6')` → False | F6/F7 `_shortcuts` sözlüğünde; test özel alanları varsayıyor. F5 için aynı nesne yapısı varsayılamaz. | Pencere kapsamlı kısayol ve panel davranışı | F6/F7 var; F5 olay işleyicisinde de ele alınıyor | **YENİDEN YAZ** | Pencereyi göster, bir alt alana odaklan, gerçek tuş olaylarıyla etkisini ölç. `activated.emit()` gerçek odak/kısayol çakışmasını sınamaz. |
| `tests/test_hareket_kalemleri_integration.py::test_hareket_kalemleri_widget_instance_and_init` | `hasattr(dialog, 'hareket_kalemleri')` → False | Eski widget sınıfı ve nitelik adı bekleniyor. | Kalem bileşeni entegrasyonu ve başlangıç satırı | Yeni ekranda DocumentLinesGrid ile var | **YENİDEN YAZ** | Yeni ekranda kalem ekle/düzenle → toplam → payload bağlantısını doğrula; eski sınıf kimliğine bağlı assert'i taşımayı hedefleme. |
| `tests/test_main_window.py::test_main_window_tabs_and_dashboard` | `hasattr(window, 'fav_screens_frame')` → False | Eski dashboard alanları kaldırılmış; güncel yapı `fav_widget`/`dash_splitter`. | Sabit ana sekme, favoriler, navigasyon ve ekran açma | Evet | **YENİDEN YAZ** | Güncel dashboard bileşenleri ve gözlenebilir navigasyonu test et. İlk üç ana sekme kontrolü geçiyor; tek eski alan hatası yüzünden kalan davranışlar ölçülmüyor. |
| `tests/test_view_settings_ui.py::test_view_settings_widget_module_change` | `'customers' == 'backup_tasks'` başarısız | Sabit indeks 1 artık customers. | Modül değişince doğru profil anahtarının yüklenmesi | Evet | **ONAR** | İndeks yerine `findData('backup_tasks')`; bulunabilirlik, seçim ve doğru profil kümesini doğrula. |

## Öncelik listesi

- **Hemen silinebilecek (1):** `test_transaction_dialog_property_proxies` — kaldırılmış iç proxy düzeni. Silme yalnız bu test için öneridir; cari giriş/kayıt davranışı kapsamını kaldırmaz. Bu görevde hiçbir test silinmedi.
- **Onarılacak (9):** hızlı arama/odak, yedek profil anahtarı, modüller arası profil geçişi, pin/tooltip, profil silme entegrasyonu, alt indirim menüsü, üst panel görünürlüğü, numara placeholder, ayarlar modül seçimi. Tooltip maddesi üretim davranışı kararı/düzeltmesi gerektirir; diğerlerinin çoğu küçük test uyarlamasıdır.
- **Yeniden yazılacak (7):** widget bileşimi, toplam hesaplama, baskı veri çıkarımı, yeni fiş sıfırlama, kısayollar, kalem entegrasyonu, dashboard. Öncelik veri kaybı ve hesaplama riskini ölçen toplam/sıfırlama/kalem senaryolarıdır.

## Yapıldı

Her satırdaki tam test kimliği için ayrı subprocess ile şu komut çalıştırıldı:

```powershell
.venv/Scripts/python.exe -m pytest <dosya>::<test> -q -p no:cacheprovider --tb=short
```

Çalıştırılan kimlikler:

```text
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

Ek okuma/kanıt komutları:

- `rg -n 'TransactionDocumentDialog|TOYA_OLD_DOC_DIALOG' src -g '*.py'`
- `rg -n 'module_combo.add|profile_list.add|Aktif' src/desktop/ui/settings.py`
- `rg -n 'fav_screens_frame|favori|dashboard' src/desktop/ui/main_window.py`
- `rg -n 'F6|F7|F5|QShortcut|toggle_info_panel' src/desktop/ui/dialogs/transaction_document_dialog.py src/desktop/ui/screens/document_detail_screen.py`
- `Get-Content` ile ilgili test gövdeleri, EdgeTriggeredPanel, ViewProfileBar ve yeni belge testleri okundu.
- `.venv/Scripts/python.exe -c ...`: `tests.conftest` içe aktarılarak QSettings yalıtıldı; bellek içi SQLite ve QApplication ile gizli/görünür BackupWidget odak deneyi yapıldı. Sonuç: `hidden_focus False`, `visible_active True focus True`.

Test çıktıları geçici dizindeki `toya_gorev26_results.json` dosyasında toplandı. İlk çıktı yazdırma sırasında Windows kod sayfası hatası oluştu; ilgili test ve kalan testler UTF-8 çıktıyla tamamlandı. Bu, test hatası olarak sınıflandırılmadı. Kullanıcının gerçek görünüm profilleri değiştirilmedi; `tests/conftest.py` yalıtımı korundu.
