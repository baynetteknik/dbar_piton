# Grid envanteri — Görev 23

24.09.2026; Görev 24–25 değişikliklerinden **önceki** durum. UI kaynakları okunmuştur; kod değiştirilmemiştir. Bir satır bir dosyadır. Kalıtım ve standart widget çağrıları dahil edilmiştir. Eski ve standart tablo birlikteyse H yazılmıştır. Altyapının kendi Qt motorunu kullanması istisna olarak E gösterilir.

| Dosya | Ekran / bileşen | Kullanılan tablo bileşeni | Tür (liste / giriş / özet / diyalog) | Standart mı? (E/H) | Taşıma önceliği (1-3) | Not |
|---|---|---|---|---|---|---|
| `src/desktop/ui/backup.py` | BackupWidget, NewTaskDialog, TaskDetailPopupDialog | FilterableTableView, QTableWidget | liste | H | 2 |  |
| `src/desktop/ui/cari_hareket_screen.py` | CariHareketScreen | ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView |
| `src/desktop/ui/cari_list_screen.py` | CariListScreen | FilterableTableView, ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView |
| `src/desktop/ui/components/app_grid.py` | AppGrid | QTableWidget | liste | H | 2 | Altyapı bileşeni; doğrudan değiştirme talimatı değildir |
| `src/desktop/ui/components/base_list_screen.py` | BaseListScreen | AppGrid | liste | H | 2 | Altyapı bileşeni; doğrudan değiştirme talimatı değildir |
| `src/desktop/ui/components/base_managed_list.py` | BaseManagedListWidget | FilterableTableView | liste | E | 3 | ölü kod adayı: src/**/*.py AST import taramasında src.desktop.ui.components.base_managed_list yok; UI sembol araması da kullanım bulmadı; dinamik kullanım doğrulanmalı; Altyapı bileşeni; doğrudan değiştirme talimatı değildir |
| `src/desktop/ui/components/entry_table_view.py` | EntryTableView | FilterableTableView, QTableView | giriş | E | 2 | Altyapı bileşeni; doğrudan değiştirme talimatı değildir; EntryTableView ve standart_grid fabrikası burada tanımlanır |
| `src/desktop/ui/components/filterable_table.py` | _ModelAwareTableView | QTableView | liste | E | 2 | Altyapı bileşeni; doğrudan değiştirme talimatı değildir |
| `src/desktop/ui/components/filterable_table_sorunlu.py` | FilterableTableView | QTableView | liste | H | 3 | ölü kod adayı: rg -n ile src/**/*.py içinde tam modül adı bulunmadı; aynı sınıf adı başka dosyada da olduğundan sembol eşleşmesi kullanım kanıtı değildir |
| `src/desktop/ui/components/git_tracker_screen.py` | GitTrackerScreen | ThreePanelBaseWidget | liste | E | 2 | Liste motoru: FilterableTableView |
| `src/desktop/ui/components/git_tracker_widget.py` | GitTrackerWidget | ThreePanelBaseWidget | liste | E | 2 | Dolaylı: GitTrackerScreen; Liste motoru: FilterableTableView |
| `src/desktop/ui/components/three_panel_base.py` | ThreePanelBaseWidget | FilterableTableView | liste | E | 2 | Altyapı bileşeni; doğrudan değiştirme talimatı değildir |
| `src/desktop/ui/conflict_resolution.py` | ConflictResolutionWidget | QTableWidget | liste | H | 3 | ölü kod adayı: src/**/*.py AST import taramasında src.desktop.ui.conflict_resolution yok; UI sembol araması da kullanım bulmadı; dinamik kullanım doğrulanmalı |
| `src/desktop/ui/customers.py` | MusteriYonetimiWidget | FilterableTableView, ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView; Doğrudan modül importu yok; sembol referansı mevcut |
| `src/desktop/ui/demo_appgrid_screen.py` | AppGridCariDemoScreen | BaseListScreen | liste | H | 3 | Şema kabuğu AppGrid kullanıyor |
| `src/desktop/ui/dev_tracker_screen.py` | DevTrackerScreen | ThreePanelBaseWidget | liste | E | 2 | Liste motoru: FilterableTableView |
| `src/desktop/ui/dialogs/quotation_edit_dialog.py` | QuotationEditDialog | QTableWidget | diyalog | H | 3 | ölü kod adayı: src/**/*.py AST import taramasında src.desktop.ui.dialogs.quotation_edit_dialog yok; UI sembol araması da kullanım bulmadı; dinamik kullanım doğrulanmalı |
| `src/desktop/ui/dialogs/screen_definition_dialog.py` | ScreenDefinitionDetailDialog | AppGrid, QTableWidget | diyalog | H | 2 |  |
| `src/desktop/ui/dialogs/transaction_document_dialog.py` | TransactionDocumentDialog ve yardımcı seçim diyalogları | QTableWidget | diyalog | H | 1 | ; TOYA_OLD_DOC_DIALOG=1 geri dönüş yolu hâlâ çağırıyor |
| `src/desktop/ui/finans_hareket_screen.py` | FinansHareketScreen | ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView |
| `src/desktop/ui/finans_hesap_list_screen.py` | FinansHesapListScreen | ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView |
| `src/desktop/ui/gorevler_screen.py` | GorevlerScreen | ThreePanelBaseWidget | liste | E | 2 | Liste motoru: FilterableTableView |
| `src/desktop/ui/grid.py` | ManagedTableView | QTableView | liste | H | 3 | ölü kod adayı: src/**/*.py AST import taramasında src.desktop.ui.grid yok; UI sembol araması da kullanım bulmadı; dinamik kullanım doğrulanmalı |
| `src/desktop/ui/import_dialog.py` | ExcelImportDialog | QTableWidget | diyalog | H | 2 |  |
| `src/desktop/ui/main_window.py` | MainWindow | BaseListScreen, ThreePanelBaseWidget | liste | H | 2 | Dolaylı: AppGridCariDemoScreen, CariHareketScreen, CariListScreen, DevTrackerScreen, FinansHareketScreen, FinansHesapListScreen, GorevlerScreen, InvoicesWidget, OrdersWidget, QuotationsWidget, StokHareketScreen, StokListScreen; Liste motoru: FilterableTableView; Şema kabuğu AppGrid kullanıyor; Menü/sekme taşıyıcısı; tabloları alt ekranlardan açar |
| `src/desktop/ui/quotations.py` | BaseQuotationOrderWidget, QuotationsWidget, OrdersWidget, InvoicesWidget | FilterableTableView, ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView |
| `src/desktop/ui/resources.py` | ResourcesWidget | FilterableTableView, ThreePanelBaseWidget | liste | E | 2 | Liste motoru: FilterableTableView; Doğrudan modül importu yok; sembol referansı mevcut |
| `src/desktop/ui/screen_definitions_manager.py` | ScreenDefinitionsManagerWidget | BaseListScreen, FilterableTableView | liste | H | 2 | Şema kabuğu AppGrid kullanıyor |
| `src/desktop/ui/screens/definition_editor_screen.py` | DefinitionEditorScreen ve alan bileşenleri | FilterableTableView | liste | E | 2 |  |
| `src/desktop/ui/screens/document_detail_screen.py` | WidgetCatalogDialog, DocumentDetailScreen | DocumentLinesGrid, FilterableTableView | giriş | E | 1 |  |
| `src/desktop/ui/screens/firma_list_widget.py` | FirmaListWidget | ThreePanelBaseWidget | liste | E | 2 | Liste motoru: FilterableTableView |
| `src/desktop/ui/screens/kullanici_list_widget.py` | KullaniciListWidget | ThreePanelBaseWidget | liste | E | 2 | Liste motoru: FilterableTableView |
| `src/desktop/ui/screens/rol_list_widget.py` | RolListWidget | ThreePanelBaseWidget | liste | E | 2 | Liste motoru: FilterableTableView |
| `src/desktop/ui/settings.py` | GeneralSettingsScreen, ViewSettingsWidget, UserManagementWidget | AppGrid, FilterableTableView, ThreePanelBaseWidget | liste | H | 2 | Dolaylı: FirmaListWidget, KullaniciListWidget, RolListWidget; Liste motoru: FilterableTableView; Eski tanım tabloları AppGrid üzerinden gelir |
| `src/desktop/ui/sites.py` | TokenFetchDialog, SiteDialog, SitesWidget | FilterableTableView | liste | E | 2 |  |
| `src/desktop/ui/stok_hareket_screen.py` | StokHareketScreen | ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView |
| `src/desktop/ui/stok_list_screen.py` | StokListScreen | FilterableTableView, ThreePanelBaseWidget | liste | E | 1 | Liste motoru: FilterableTableView |
| `src/desktop/ui/widgets/backup_center_widget.py` | BackupCenterWidget | AppGrid | liste | H | 2 |  |
| `src/desktop/ui/widgets/backup_dashboard.py` | _Kart, RunDetailDialog, DiskFilesDialog, BackupDashboard | AppGrid | liste | H | 2 |  |
| `src/desktop/ui/widgets/backup_disks_dialog.py` | BackupDisksDialog | AppGrid | diyalog | H | 2 |  |
| `src/desktop/ui/widgets/backup_restore_history_dialog.py` | BackupRestoreHistoryDialog | AppGrid | diyalog | H | 2 |  |
| `src/desktop/ui/widgets/cari_ekstre_widget.py` | CariEkstreWidget | QTableWidget | liste | H | 1 |  |
| `src/desktop/ui/widgets/cari_fis_dialog.py` | CariFisDialog | FisKalemGrid, AppGrid | diyalog | H | 1 | Dolaylı: CariFisKalemleriWidget; Kalemler standart, toplam widget üzerinden AppGrid (Görev 24 öncesi) |
| `src/desktop/ui/widgets/cari_fis_kalemleri_widget.py` | CariFisKalemleriWidget | FisKalemGrid | giriş | E | 1 |  |
| `src/desktop/ui/widgets/cari_fis_toplam_widget.py` | CariFisToplamWidget | AppGrid | özet | H | 1 |  |
| `src/desktop/ui/widgets/cari_kunye_widget.py` | FieldWithButton, CariSecimDialog, CariKunyeWidget, HizliCariEkleDialog | QTableWidget | liste | H | 1 |  |
| `src/desktop/ui/widgets/currency_rate_report_widget.py` | CurrencyRateReportWidget | QTableWidget | liste | H | 2 |  |
| `src/desktop/ui/widgets/dev_item_dialog.py` | DevItemDialog | AppGrid | diyalog | H | 2 |  |
| `src/desktop/ui/widgets/document_expenses_grid.py` | _ComboDelegate, DocumentExpensesGrid | FilterableTableView | giriş | E | 1 |  |
| `src/desktop/ui/widgets/document_form/hareket_kalemleri_widget.py` | HareketKalemleriDbGridWidget | QTableWidget | giriş | H | 1 |  |
| `src/desktop/ui/widgets/document_lines_grid.py` | _LookupDelegate, _ComboDelegate, StokAramaDialog, DocumentLinesGrid | DocumentLinesGrid, FilterableTableView, QTableWidget, EntryTableView | giriş | H | 1 | ; Ana kalem motoru standart; H nedeni StokAramaDialog içindeki QTableWidget |
| `src/desktop/ui/widgets/finans_fis_dialog.py` | FinansFisDialog | FisKalemGrid, AppGrid | diyalog | H | 1 | Dolaylı: FinansFisKalemleriWidget; Kalemler standart, toplam widget üzerinden AppGrid (Görev 24 öncesi) |
| `src/desktop/ui/widgets/finans_fis_kalemleri_widget.py` | FinansFisKalemleriWidget | FisKalemGrid | giriş | E | 1 |  |
| `src/desktop/ui/widgets/finans_fis_toplam_widget.py` | FinansFisToplamWidget | AppGrid | özet | H | 1 | CariFisToplamWidget üzerinden miras; rg -n finans_fis_toplam_widget src çağrıyı doğruladı |
| `src/desktop/ui/widgets/finans_hesap_widgets.py` | FinansHesapSecimDialog, FinansHesapTanimWidget, FinansHesapTanimDialog | AppGrid | liste | H | 1 |  |
| `src/desktop/ui/widgets/fis_kalem_grid.py` | KolonTanimi, FisKalemGrid | FilterableTableView, EntryTableView | giriş | E | 1 | Altyapı bileşeni; doğrudan değiştirme talimatı değildir |
| `src/desktop/ui/widgets/gdrive_folder_dialog.py` | GoogleDriveFolderDialog | AppGrid | diyalog | H | 2 |  |
| `src/desktop/ui/widgets/git_report_dialog.py` | GitReportDialog | AppGrid | diyalog | H | 2 |  |
| `src/desktop/ui/widgets/gorev_kisayol_bolumu.py` | IlgiliGorevlerDialog, GorevKisayolBolumu | ThreePanelBaseWidget | liste | E | 2 | Dolaylı: GorevlerScreen; Liste motoru: FilterableTableView |
| `src/desktop/ui/widgets/hareket_alt_paneli.py` | PanelKolon, PanelVeri, HareketAltPaneli | AppGrid | özet | H | 1 |  |
| `src/desktop/ui/widgets/hareket_kalemleri_widget.py` | StokSecimDialog, HareketKalemleriWidget | QTableWidget | giriş | H | 1 |  |
| `src/desktop/ui/widgets/hareket_kalemleri_widget_yedek.py` | HareketKalemleriWidget | QTableWidget | giriş | H | 3 | ölü kod adayı: rg -n ile src/**/*.py içinde tam modül adı bulunmadı; aynı sınıf adı başka dosyada da olduğundan sembol eşleşmesi kullanım kanıtı değildir |
| `src/desktop/ui/widgets/kalem_aktar_dialog.py` | KalemAktarDialog | QTableWidget | diyalog | H | 2 |  |
| `src/desktop/ui/widgets/portal_backup_widget.py` | _BackupWorker, PortalBackupWidget | QTableWidget | liste | H | 2 |  |
| `src/desktop/ui/widgets/stok_fis_dialog.py` | StokFisDialog | FisKalemGrid, AppGrid | diyalog | H | 1 | Dolaylı: StokFisKalemleriWidget; Kalemler standart, toplam widget üzerinden AppGrid (Görev 24 öncesi) |
| `src/desktop/ui/widgets/stok_fis_kalemleri_widget.py` | StokFisKalemleriWidget | FisKalemGrid | giriş | E | 1 |  |
| `src/desktop/ui/widgets/stok_fis_toplam_widget.py` | StokFisToplamWidget | AppGrid | özet | H | 1 |  |
| `src/desktop/ui/widgets/stok_hareket_dialog.py` | StokHareketDialog | AppGrid | diyalog | H | 1 |  |

- Standart liste / kabuk: `FilterableTableView` 17 dosya, `ThreePanelBaseWidget` 19 dosya, `BaseManagedListWidget` 0 dosya
- Standart giriş / özet: `EntryTableView` 2 dosya, `standart_grid` 0 dosya, `FisKalemGrid` 6 dosya, `DocumentLinesGrid` 2 dosya
- Eski grid / kabuk: `AppGrid` 19 dosya, `BaseListScreen` 3 dosya
- Doğrudan Qt tabloları: `QTableWidget` 16 dosya, `QTableView` 4 dosya
- Kapsam: 68 dosya; sayılar örtüşür, toplanmaz.

## Yapıldı

- `rg -l "AppGrid\(|QTableWidget\(|QTableView\(|FilterableTableView\(|EntryTableView|standart_grid\(|DocumentLinesGrid\(|FisKalemGrid|ThreePanelBaseWidget" src/desktop/ui -g "*.py"`
- `.venv/Scripts/python.exe` ile AST çağrı/kalıtım analizi, `src/**/*.py` Import/ImportFrom taraması ve UI sembol referansı kontrolü.
- Ölü kod adayları statik kanıttır; dinamik import, string kayıt ve dış başlangıç betikleri nedeniyle kesin silme önerisi değildir.
- Öncelik işlevden çıkarılmıştır; gerçek kullanıcı kullanım sıklığı ölçülmemiştir.
- Motor dosyaları ekran değildir; envanter bütünlüğü için gösterilmiştir.
- Elle doğrulama: `rg -n EntryTableView src/desktop/ui/widgets/fis_kalem_grid.py src/desktop/ui/widgets/document_lines_grid.py`; factory argümanları eklendi. Finans toplam kalıtımı ve fişlerin toplam bileşenleri ayrıca incelendi.
- Sayılar tablo sütunundaki doğrudan/dolaylı kullanımlardır; yalnız tanımlanan sınıf/fonksiyon sayılmaz. Görev 24–25 sonunda altı üretim dosyası standart gride taşınmıştır; bu envanter başlangıç fotoğrafını korur.
