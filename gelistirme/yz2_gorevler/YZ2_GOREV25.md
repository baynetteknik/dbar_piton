# YZ 2 — Görev 25: Küçük diyalog tablolarını standart gride taşı

> **Dosyalar (yalnızca bunlar, birer birer):** `src/desktop/ui/widgets/gdrive_folder_dialog.py`, `stok_hareket_dialog.py`,
> `backup_disks_dialog.py`, `dev_item_dialog.py`; ilgili test dosyaları (`tests/test_gdrive_folder_dialog.py`, `tests/test_backup_*.py`,
> stok hareket testleri, `tests/test_gorev_ve_dev_tracker.py`).
> **Kural:** Commit yapma. Önce `gelistirme/00_mimari/GRID_STANDARDI.md` oku. Bir dosyayı bitirip testini çalıştırmadan diğerine geçme.
> Bir dosyada beklenmedik karmaşıklık (özel sütun editörü, çok sayıda AppGrid'e özel çağrı) görürsen o dosyayı ATLA ve nedenini yaz.

## Sorun
Bu diyaloglardaki tablolar `AppGrid` (eski, mavi başlıklı). Standart: `FilterableTableView`.

## Yapılacak (her dosya için)
1. `AppGrid(...)` → `standart_grid(profile_key, [(anahtar, başlık), ...])` (`entry_table_view.py`); `self.grid = g.table_view`, `layout.addWidget(g)`.
   `profile_key` sabit ve benzersiz olsun (ör. `dlg_gdrive_klasor`). Sütun anahtarları sonradan DEĞİŞMEZ.
2. `QTableWidgetItem` → `QStandardItem`; `setData(rol, değer)` çağrılarında argüman sırası TERSİNE döner: `setData(değer, rol)`.
3. `cellDoubleClicked`, `currentRow()`, `rowCount()`, `setRowCount(0)`, `insertRow`, `item(r, c)` aynen çalışır (EntryTableView sağlar).
4. Salt okunur tablolarda hücre bayrağı: `Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable`.
5. `enable_layout_persistence(...)` çağrısını kaldır (profil sistemi bunu karşılar); `grid_presets`/`register_preset` artık gerekmiyorsa kaldır.
6. Tutar hücreleri: `money_edit.bicimle(değer, 2)`; sağa hizalı.

## Testler
Değiştirdiğin her dosyanın testini çalıştır (`.venv\Scripts\python.exe -m pytest <test dosyası> -q -p no:cacheprovider`). Eski AppGrid API'sine bağlı
test satırlarını yeni API'ye uyarla (ör. `horizontalHeaderItem(i).text()` → `grid.model().headerData(i, Qt.Orientation.Horizontal)`).
`tests/conftest.py` kullanıcı ayarlarını yalıtır; bozma.

## Bitince
Dosyanın altına `## Yapıldı` ekle: taşınan / atlanan dosyalar (neden), test sonuçları.

## Yapıldı

24.09.2026 — Dört dosya sırayla taşındı; her dosyanın testi bitmeden sonraki dosya değiştirilmedi. **Atlanan dosya yok.** Commit yapılmadı.

| Dosya | Değişiklik | Tekil aşama doğrulaması |
|---|---|---|
| `gdrive_folder_dialog.py` | `standart_grid`, `QStandardItem`; seçim bildirimi `selectionModel().selectionChanged` üzerinden bağlandı. Klasör gezinme/seçme akışı korundu. | `test_gdrive_folder_dialog.py`: 9 geçti |
| `stok_hareket_dialog.py` | `standart_grid`, kalıcı alan anahtarları, `QStandardItem`; hizalama, etki renkleri ve çift tıkla fiş açma korundu. | `test_stok_fis_ui.py` + `test_stok_fis_service.py`: 27 geçti |
| `backup_disks_dialog.py` | `standart_grid`, kalıcı alan anahtarları ve salt okunur hücreler; disk işlemleri korundu. | `test_backup_disks_notify.py`: 15 geçti |
| `dev_item_dialog.py` | Geçmiş tablosu standart grid, salt okunur/seçilebilir hücreler; 170px üst yükseklik kapsayıcıya taşındı. | `test_gorev_ve_dev_tracker.py` + gerçek diyalog testi: 13 geçti |

Mevcut `PRESET_ID` değerleri profil kimliği olarak korundu; AppGrid/preset importları ve eski layout persistence çağrıları kaldırıldı. `setData` kullanan hücre olmadığı için argüman sırası değişikliği gerekmedi. AppGrid, FisKalemGrid ve conftest değiştirilmedi. Bu görevde test dosyası değiştirilmedi.

Komutlar:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_gdrive_folder_dialog.py -q -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -m pytest tests/test_stok_fis_ui.py tests/test_stok_fis_service.py -q -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -m pytest tests/test_backup_disks_notify.py -q -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -m pytest tests/test_gorev_ve_dev_tracker.py tests/test_gorev_ekranlari.py::test_gelistirme_kaydi_penceresi_ve_gecmis -q -p no:cacheprovider --tb=short
```

Son birleşik doğrulama (Görev 24 dahil): **102 test geçti**, çıkış kodu 0.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_cari_hareket_screen.py tests/test_finans_fis.py tests/test_stok_fis_ui.py tests/test_gdrive_folder_dialog.py tests/test_backup_disks_notify.py tests/test_gorev_ve_dev_tracker.py tests/test_gorev_ekranlari.py::test_gelistirme_kaydi_penceresi_ve_gecmis -q -p no:cacheprovider --tb=short
.venv/Scripts/python.exe -m ruff check src/desktop/ui/widgets/cari_fis_toplam_widget.py src/desktop/ui/widgets/stok_fis_toplam_widget.py src/desktop/ui/widgets/gdrive_folder_dialog.py src/desktop/ui/widgets/stok_hareket_dialog.py src/desktop/ui/widgets/backup_disks_dialog.py src/desktop/ui/widgets/dev_item_dialog.py
```

Ruff import düzenini düzeltti; `zip(..., strict=True)` ile sütun anahtarı/başlık sayısı uyumu açık hale getirildi. Son kontrol temiz. Ek stok servis testleri de geçti; 102 sayısına ayrıca eklenmemiştir.
