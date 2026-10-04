# YZ 2 — Görev 28: Kırık testlerden "ONAR" sınıfındakileri onar (yalnızca test dosyaları)

> **Girdi:** `gelistirme/00_mimari/kirik_testler.md` (Görev 26 raporu). **Yalnızca ONAR** işaretli 9 test. SİL ve YENİDEN YAZ işaretlilere DOKUNMA.
> **Kural:** Commit yapma. Üretim kodunu (`src/`) DEĞİŞTİRME; yalnızca test dosyalarını güncelle. Görev 27 (Genel Ayarlar) başka bir oturumda
> `src/desktop/ui/settings.py` üzerinde çalışıyor olabilir — o dosyaya dokunma; testler `settings.py` davranışına bağlıysa o anki güncel davranışa göre onar.
> Test onarırken bir özelliğin GERÇEKTEN kaybolduğunu görürsen (ör. sabitle/kapat düğmelerinin ipucu) testi gevşetip geçirme: teste `pytest.xfail`/atla EKLEME,
> raporuna "üretim kaybı olabilir" diye yaz ve testi olduğu gibi bırak.

## Onarılacak testler
```
tests/test_backup_ui.py::test_backup_widget_quick_search_and_popups              (odak: pencereyi göster + etkinleştir, ya da odak yerine search_box'ın var/etkin olduğunu doğrula)
tests/test_backup_ui.py::test_backup_column_profile_persistence_and_settings     (modül anahtarı: 'backup' → güncel ayardaki 'backup_tasks'/'restore_tasks')
tests/test_base_managed_list.py::test_view_settings_widget_module_switching      (aktif profil etiketi süslü: '⭐ Ad (Aktif)' — ham adı içerme kontrolü yap)
tests/test_customers_ui.py::test_edge_triggered_panel_pin_and_tooltips           (pin/kapat düğmesi ipucu — yukarıdaki üretim kaybı uyarısına bak)
tests/test_customers_ui.py::test_view_settings_widget_integration                (profil anahtarı ve modül: 'customers' için açılıyor mu, güncel combo indeksleri)
tests/test_gorev19.py::test_alt_iskonto_context_menu_methods                     (özel '_show_...' yerine gerçek metot adı: show_alt_iskonto_context_menu vb.)
tests/test_gorev20.py::test_toggle_info_panel_f7                                 (eski alan adı → güncel toggle header_tabs görünürlüğü)
tests/test_gorev21.py::test_doc_no_readonly_and_placeholder                      (yardım metni değişmiş; salt okunurluk kontrolü aynı kalsın, metin kontrolünü güncel metne bağla)
tests/test_view_settings_ui.py::test_view_settings_widget_module_change          (sabit indeks 1 yerine module_combo'da kimliği ('backup_tasks') arayarak seç)
```

## Yöntem
1. Her testi TEK TEK çalıştır: `.venv\Scripts\python.exe -m pytest <dosya>::<test> -q -p no:cacheprovider --tb=short`; hata gerçekten raporda yazılı kök nedenden mi geliyor doğrula.
2. Testin ÖLÇTÜĞÜ özelliği koru; yalnızca eskimiş ad/indeks/metin beklentisini güncel davranışa uyarla. Sabit indeks yerine anahtarla arama tercih et (`findData`).
3. Profil kullanan testlerde (`ProfileManager`) test sonunda temizle; `tests/conftest.py` kullanıcı ayarlarını yalıtır, bozma.
4. Bitince ilgili test dosyalarının TAMAMINI çalıştır, başka test kırmadığını doğrula:
   `.venv\Scripts\python.exe -m pytest tests/test_backup_ui.py tests/test_base_managed_list.py tests/test_customers_ui.py tests/test_gorev19.py tests/test_gorev20.py tests/test_gorev21.py tests/test_view_settings_ui.py -q -p no:cacheprovider`
   (`test_gorev20/21` içindeki YENİDEN YAZ/SİL işaretli testler hâlâ kırık kalır; bu beklenen.)

## Bitince
Bu dosyanın altına `## Yapıldı` ekle: onarılan test sayısı, her testte ne değişti (1 satır), "üretim kaybı olabilir" diye işaretlenenler, çalıştırdığın komutlar.

## Yapıldı

24.09.2026 — `feat/gorev-28-test-onarimi` dalında **8 test onarıldı, 1 test üretim kaybı olabileceği için aynen bırakıldı**. Commit yapılmadı.

Görev 27 okundu: Genel Ayarlar tabloları/görünümü ayrı kapsamdır. Bu çalışmada `src/` altında hiçbir dosya değiştirilmedi; `settings.py`, `tests/conftest.py` ve Görev 27 belgesi değiştirilmedi. Ortak `test_view_settings_ui.py` dosyasında yalnız Görev 28'in açıkça istediği `test_view_settings_widget_module_change` güncellendi. SİL/YENİDEN YAZ testleri korunmuştur.

### Test bazında değişiklikler

| Test | Sonuç / değişiklik |
|---|---|
| `test_backup_widget_quick_search_and_popups` | Onarıldı. Pencere gösterilip etkinleşmesi bekleniyor; hızlı arama sonrasında gerçek `hasFocus()` kontrolü ve popup kontrolleri korunuyor. |
| `test_backup_column_profile_persistence_and_settings` | Onarıldı. `backup_tasks` anahtarı, gerçek tablo modeli ve ProfileManager kaydet/yükle akışı kullanılıyor; aktif profil ve sütun genişliği doğrulanıyor. Ayarlarda modül kimlikle seçiliyor. |
| `test_view_settings_widget_module_switching` | Onarıldı. customers/sites kimlikleriyle seçim; süslü aktif profil etiketlerinde profil adının bulunması ve diğer modül profilinin bulunmaması doğrulanıyor. |
| `test_edge_triggered_panel_pin_and_tooltips` | **Değiştirilmedi — üretim kaybı olabilir.** `pin_btn.toolTip()` boş; kapat düğmesinde de tooltip ataması yok. Test gevşetilmedi ve xfail/skip eklenmedi. |
| `test_view_settings_widget_integration` | Onarıldı. customers açıkça seçiliyor; seçili profil kimliği, silme bildirimi ve kalıcı depodan kaldırılması kontrol ediliyor. |
| `test_alt_iskonto_context_menu_methods` | Onarıldı. Olmayan `_show_alt_iskonto_context_menu` beklentisi yerine mevcut `show_alt_iskonto_context_menu` ve `_sort_alt_iskonto` metotlarının çağrılabilirliği doğrulanıyor. |
| `test_toggle_info_panel_f7` | Onarıldı. Eski `info_panels_widget` yerine güncel `header_tabs` görünürlüğü; kapat/aç ve `_info_visible` kontrolleri korunuyor. |
| `test_doc_no_readonly_and_placeholder` | Onarıldı. Güncel `Kaydedilince atanır` metni doğrulanıyor; salt okunurluk ve boş başlangıç numarası kontrolleri korunuyor. |
| `test_view_settings_widget_module_change` | Onarıldı. Sabit indeks yerine `findData("backup_tasks")`; modülün varlığı ve doğru profil anahtarı doğrulanıyor. |

Profil oluşturan üç testte temizlik `finally` içinde; test profilleri siliniyor ve önceki aktif profil geri yükleniyor. Kullanıcı ayarlarının conftest yalıtımı korunmuştur.

### Doğrulama

- Önce 9 hedef test **tek tek** çalıştırıldı: 9'u da Görev 26 raporundaki nedenlerle başarısızdı.
- Uyarlamadan sonra hedefler yine tek tek çalıştırıldı. Profil testinin ilk denemesinde tablo modeli bulunmadığı için genişlik 0 çıkıyordu; gerçek `QStandardItemModel` kurularak tamamlandı ve test yeniden tekil çalıştırılıp geçti.
- Son durumda hedefler: **8 geçti, 1 korunan tooltip hatası**.
- İstenen yedi test dosyasının tamamı birlikte çalıştırıldı: **33 test, 26 geçti, 7 başarısız, 0 atlanan, 0 kurulum hatası**. Süre yaklaşık 21 saniye. Kalanlar aşağıda; ilave başarısız test yok.
- Başlangıç test kopyaları ile fonksiyon kaynakları karşılaştırıldı: yalnız yukarıdaki 8 onarılan test değişti. Tooltip testi ile SİL/YENİDEN YAZ testlerinin gövdeleri aynen kaldı.
- Ruff öncesi/sonrası karşılaştırmasında yeni bulgu yok. Önceden mevcut tek `I001`, `tests/test_view_settings_ui.py` içindeki kapsam dışı `test_view_settings_widget_reset_all_profiles` yerel import bloğunda (güncel satır 41); o teste dokunulmadı. `git diff --check` temiz.

Tam koşuda korunan başarısız testler:

```text
tests/test_customers_ui.py::test_edge_triggered_panel_pin_and_tooltips
tests/test_gorev20.py::test_transaction_dialog_widget_composition
tests/test_gorev20.py::test_transaction_dialog_property_proxies
tests/test_gorev20.py::test_calculate_totals_with_toplam_widget
tests/test_gorev20.py::test_get_current_teklif_data
tests/test_gorev21.py::test_new_quotation_clears_cari_and_belge
tests/test_gorev21.py::test_window_scoped_shortcuts
```

### Çalıştırılan komutlar

Aşağıdaki 9 kimliğin her biri için, önce ve onarımdan sonra ayrı süreçte:

```powershell
.venv/Scripts/python.exe -m pytest <dosya>::<test> -q -p no:cacheprovider --tb=short
```

```text
tests/test_backup_ui.py::test_backup_widget_quick_search_and_popups
tests/test_backup_ui.py::test_backup_column_profile_persistence_and_settings
tests/test_base_managed_list.py::test_view_settings_widget_module_switching
tests/test_customers_ui.py::test_edge_triggered_panel_pin_and_tooltips
tests/test_customers_ui.py::test_view_settings_widget_integration
tests/test_gorev19.py::test_alt_iskonto_context_menu_methods
tests/test_gorev20.py::test_toggle_info_panel_f7
tests/test_gorev21.py::test_doc_no_readonly_and_placeholder
tests/test_view_settings_ui.py::test_view_settings_widget_module_change
```

Tam dosya doğrulaması ve lint:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_backup_ui.py tests/test_base_managed_list.py tests/test_customers_ui.py tests/test_gorev19.py tests/test_gorev20.py tests/test_gorev21.py tests/test_view_settings_ui.py -q -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -m ruff check tests/test_backup_ui.py tests/test_base_managed_list.py tests/test_customers_ui.py tests/test_gorev19.py tests/test_gorev20.py tests/test_gorev21.py tests/test_view_settings_ui.py --output-format json
git diff --check -- tests/test_backup_ui.py tests/test_base_managed_list.py tests/test_customers_ui.py tests/test_gorev19.py tests/test_gorev20.py tests/test_gorev21.py tests/test_view_settings_ui.py
```

Ham başlangıç/sonuç ve Ruff JSON kayıtları ile tam koşunun JUnit XML'i geçici `C:/Users/alp/AppData/Local/Temp/toya_task28_ii9l6803/` dizininde tutuldu. Tam koşuda ayrıca `--junitxml=.../full.xml` kullanıldı; rapordaki sayılar bu XML ile doğrulandı.
