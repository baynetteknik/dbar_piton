# YZ 2 — Görev 27: Genel Ayarlar (Sistem Ayarları) ekranını standart hale getir

> **Dosyalar:** `src/desktop/ui/settings.py` (asıl iş), ilgili testler: `tests/test_settings_menu.py`, `tests/test_general_settings_screen.py`, `tests/test_view_settings_ui.py`.
> **Kural:** Commit yapma. Önce `gelistirme/00_mimari/GRID_STANDARDI.md` oku. `filterable_table.py`, `entry_table_view.py`, `fis_kalem_grid.py`,
> `document_lines_grid.py` dosyalarına DOKUNMA (ana geliştirici üzerinde çalışıyor). Davranışı DEĞİŞTİRME: yalnızca görünüm/bileşen standardı.
> `settings.py` çok büyük (~4900 satır) ve içinde yakın zamanda yapılmış değişiklikler var (`btn_style` merkezi dosyaya bağlandı, `ViewSettingsWidget.showEvent`,
> `build_sayi_bicimi_panel`); dosyayı baştan okuyup üzerine yaz, eski bir kopyaya dönme.

## Amaç
Genel Ayarlar'ın tanım panellerindeki tablolar hâlâ eski `AppGrid`. Sistemin geri kalanı standart grid (`FilterableTableView`) kullanıyor.
Ayrıca panellerin başlık/açıklama/düğme görünümü panelden panele farklı olabilir; tek standarda çek.

## A) Tanım tablolarını standart gride taşı (panel panel)
`GeneralSettingsScreen._new_grid(name, labels, stretch, editable)` (~satır 3001) tüm `tbl_*` tablolarını (`tbl_sube, tbl_donem, tbl_odeme, tbl_fiyat,
tbl_kategori, tbl_marka, tbl_birim, tbl_depo, tbl_cari_grup, tbl_kdv, tbl_yetkiler, tbl_lockout` ve özel alan tabloları) `AppGrid` olarak üretiyor.

1. `_new_grid` içinde `AppGrid`/`register_preset` yerine `standart_grid` kullan (`from src.desktop.ui.components.entry_table_view import standart_grid`):
   - `profile_key` = mevcut `pid` (`f"dbgrid_ayar_{name}"`) — DEĞİŞTİRME (kullanıcı profilleri buna bağlı).
   - Sütun anahtarları `c0..cN` olsun (başlıklar `self._tr_upper(label)` ile aynı BÜYÜK harf).
   - Dönen değer `EntryTableView` (tablo) olsun; ekleme için kapsayıcıyı `tablo.container = <FilterableTableView>` niteliğiyle taşı.
   - Panel kodunda `lyt.addWidget(self.tbl_x)` yerine `lyt.addWidget(self.tbl_x.container)` yaz (her panelde).
   - `stretch` sütunu: ilk gösterimde oranlı genişlik (`FisKalemGrid._oranli_genislik`/`showEvent` desenine bak); kullanıcı elle boyutlarsa oran devreye girmesin.
   - `editable=False` ise hücreleri salt okunur (`ItemIsEnabled | ItemIsSelectable`) yap; `True` ise düzenlenebilir bırak.
   - `context_actions_provider = self._panel_context_actions` davranışı korunmalı: sağ tık menüsünde panel eylemleri görünsün
     (`FisKalemGrid._baglam_menusu` desenine bak: eylemler + ayırıcı + `entry.add_column_actions_to_menu(menu)`).
2. Hücre öğeleri `QTableWidgetItem` → `QStandardItem`. `setData` kullanılan yerde argüman sırası tersine döner: `setData(değer, rol)`.
3. `_load_generic_table`, ekle/sil/kaydet fonksiyonları ve testler eski API'ye (ör. `horizontalHeaderItem(i).text()`) bağlıysa yeni API'ye uyarla:
   başlık = `tablo.model().headerData(i, Qt.Orientation.Horizontal)`.
4. Yetki matrisi (`tbl_yetkiler`) sütunları dinamik; `profile_key` sabit kalsın, sütun sayısı değişiminde `set_columns` yeniden çağrılabilir olmalı.

## B) Panel görünüm standardı
- Her panelin başlığı aynı biçimde: `QLabel("<emoji> Başlık")` stili `font-size:14px; font-weight:800; color:#1e3a8a;` ve altında gri açıklama `color:#64748b; font-size:11px;` (bugün panelden panele sapmalar var: aynı stile getir; yeni ortak yardımcı yazmak yerine `settings.py` içinde tek küçük fonksiyon `_panel_baslik(ikon_baslik, aciklama)` yeterli).
- Panellerdeki tüm düğmeler `btn_style(...)` (`src/desktop/ui/components/button_style.py`) kullansın: birincil (Kaydet/Ekle) `btn_style("#2563eb", "#ffffff")`, tehlike (Sil) `btn_style("#fee2e2", "#991b1b")`, diğerleri `btn_style()`. Elle yazılmış `QPushButton{...}` stillerini bu çağrılarla değiştir.
- Form satırlarında etiket/alan hizası ve iç boşluklar (`setContentsMargins(12,12,12,12)`, `setSpacing(8)`) tüm panellerde aynı olsun.
- Menü yapısı (`MENU_STRUCTURE`), panel kimlikleri ve metinleri DEĞİŞMEZ.

## Testler
Her panel grubunu bitirdikçe çalıştır:
```
.venv\Scripts\python.exe -m pytest tests/test_settings_menu.py tests/test_general_settings_screen.py tests/test_view_settings_ui.py -q -p no:cacheprovider
```
Bilinen kırık test (senin değişikliğinle ilgisiz, bozma/onarma): `tests/test_view_settings_ui.py::test_view_settings_widget_module_change`. Diğer hepsi geçmeli.
`tests/conftest.py` kullanıcı ayarlarını yalıtır; bozma. Test eklerken profil kullanıyorsan sonunda temizle (`ProfileManager(...).delete_profile(...)`).
Görsel kontrol: `GeneralSettingsScreen(db_session=db)` aç, birkaç paneli (`switch_panel("birim_tanimlari")`, `"kdv_oranlari"`, `"depo"` vb.) sırayla gösterip `grab().save(...)` ile ekran görüntüsü al; başlıkların açık renkli standart grid başlığı olduğunu ve düğmelerin derinlikli standart düğme olduğunu doğrula. Qt material teması için `apply_stylesheet(app, theme='light_teal.xml')` uygula (gerçek görünüm için şart).

## Bitince
Dosyanın altına `## Yapıldı` ekle: taşınan tablolar/paneller, atlananlar (neden), test sonuçları, ekran görüntüsü yolları.

## Yapıldı (2026-09-27, Claude devraldı — "evet devral")

**A) Tanım tabloları → standart grid.** `_new_grid` artık `standart_grid()` kullanıyor (`AppGrid`/`register_preset`/`GRID_PRESETS` tamamen kaldırıldı).
Taşınan 12 tablo: `tbl_sube, tbl_donem, tbl_odeme, tbl_fiyat, tbl_kategori, tbl_marka, tbl_birim, tbl_depo, tbl_cari_grup, tbl_kdv, tbl_yetkiler, tbl_lockout`.
- Dönüş değeri `EntryTableView`; ekleme için `.container` (`FilterableTableView`) niteliği — 12 `lyt.addWidget(...)` çağrısı güncellendi.
- Sütun anahtarları `c0..cN`, başlıklar `_tr_upper` ile BÜYÜK harf (profile_key `dbgrid_ayar_<name>` DEĞİŞMEDİ — kullanıcı profilleri korunuyor).
- `context_actions_provider = self._panel_context_actions` korunuyor; sağ tık menüsü `_ayar_grid_menu` ile eylemler + ayırıcı + `entry.add_column_actions_to_menu(menu)` (`FisKalemGrid._baglam_menusu` deseni).
- `stretch` sütunu ilk gösterimde oranlı genişliyor, kullanıcı elle boyutlandırınca kalıcı olarak durur (`_oranli_kur`/`_oranli_yenile`, `switch_panel`'den `QTimer.singleShot(0,...)` ile tetiklenir — `FisKalemGrid._oranli_genislik`/`showEvent` deseninin dışarıdan, `EntryGridBase`'e bağlanmadan uygulanmış hali).
- `editable=False` (yalnız `tbl_yetkiler`) hücre bazında `ItemIsEnabled|ItemIsSelectable` ile salt okunur yapılıyor.
- 28 `QTableWidgetItem` → `QStandardItem`; `_load_generic_table`/`_save_generic_table`/`_add_table_row`/`_delete_table_row`/DB yükleme-kaydetme fonksiyonları (birim/depo/ödeme/kategori) değişmeden çalışıyor (EntryTableView'in QTableWidget-benzeri yüzeyi sayesinde).
- Yardımcı genel fonksiyonlar (`filter_active_table(_status)`, `export_active_to_excel`, `import_active_from_excel`, `_generate_table_html`, `_update_bottom_count`) `isinstance(QTableWidget)` varsayımına göre kırılıyordu (arama/filtre, Excel'den içe aktarma, kayıt sayacı sessizce çalışmaz olurdu) — `_tablo_boyut`/`_tablo_metin` ile model-farkında hale getirildi; davranış korundu.
- `tests/test_settings_menu.py`: `test_all_definition_tables_are_standard_appgrids_with_theme_style` → `test_all_definition_tables_are_standard_entry_grids_with_theme_style` (AppGrid/`horizontalHeaderItem`/`editTriggers()` yerine `EntryTableView`/`model().headerData()`/item `ItemIsEditable` bayrağı); `test_kdv_panel_is_a_standard_editable_grid_that_persists` aynı şekilde güncellendi (tam kayıt/yükle/sil round-trip'i hâlâ geçiyor).

**B) Panel görünüm standardı.** `_panel_baslik(lyt, ikon_baslik, aciklama)` ortak yardımcısı eklendi; 13 panelin (yukarıdaki 12 + `yetkiler`, `guvenlik`, `sayi_bicimi`) tekrarlanan başlık+açıklama kodu buna taşındı (görsel/davranış DEĞİŞMEDİ — zaten hepsi aynı stildeydi, sadece DRY). Manuel `QPushButton{...}` stilleri (Güvenlik panelindeki Kaydet + Satır/Sil düğmeleri, Sayı Biçimi panelindeki Kaydet) `self.btn_style(...)`'a taşındı. `build_doviz_panel` kasıtlı olarak başlıksız (açıklama üst çubuktaki ℹ️ ipucunda) — dokunulmadı. Sol menü düğmesi stili (`menu_btn_style`) kapsam dışı bırakıldı (farklı bir UI kavramı: gezinme, panel eylemi değil).

**Atlanan/kapsam dışı:** `build_ozel_alan_panel` bir grid değil (düz form alanları) — dokunulmadı. `doviz_grid` zaten `FilterableTableView` tabanlıydı, taşınmadı (zaten standart). `firma_bilgileri/cms_baglantilari/kullanicilar/roller/gorunum_profilleri/ekran_grid/surum_git/eposta_smtp/online_portal/portal_yayin/yedek_merkezi/portal_yedek` panelleri ayrı dosyalardaki gömülü widget'lar (`FirmaListWidget`, `SitesWidget`, `SmtpSettingsWidget`, ...) — bu görev `settings.py`'ın kendi panellerini kapsıyor, o dosyalara dokunulmadı.

**Testler:** `tests/test_settings_menu.py` (38), `tests/test_general_settings_screen.py` (19), `tests/test_view_settings_ui.py` (4) — üçü de ayrı ayrı tam geçti (61/61). Not: üçü BİRLİKTE tek pytest çağrısında bu ortamda zaman aşımına/yavaşlığa uğruyor (dokümanın kendi notu: "tam paket... dosyaları tek tek/gruplarla çalıştır" — bilinen ortam sorunu, kod sorunu değil).
**Ekran görüntüleri:** Birim/KDV/Yetki Matrisi/Depo/Güvenlik panelleri qt_material `light_teal` temasıyla görsel olarak doğrulandı (standart grid başlığı, alternatif satır rengi, derinlikli standart düğmeler).
