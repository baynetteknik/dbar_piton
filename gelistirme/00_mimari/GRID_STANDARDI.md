# TOYA ERP — Grid (Tablo) Standardı

> Durum: 2026-09-24. Karar: **tüm tablolar tek standart grid bileşenini kullanır.** Bu belge, o standardın tüm sistemde
> uygulanması için gerekli notlardır. Yeni ekran/tablo yazan herkes (insan ya da YZ) önce bunu okur.

## 1. Karar

Standart grid = **`FilterableTableView`** (`src/desktop/ui/components/filterable_table.py`; model/görünüm tabanlı, `QTableView` içerir).
Gerekçe: liste ekranları, belge kalemleri ve `docs/UI_PAGE_AND_COMPONENT_STANDARDS.md` zaten bunu standart sayıyor; görünüm
profilleri (sütun sırası/görünürlük/genişlik/renk kuralları), iki sütunlu aramalı sütun menüsü, sayfalama ve filtre satırı burada.

İki kullanım biçimi:

| Kullanım | Nasıl kurulur | Nerede kullanılır |
|---|---|---|
| **Liste** (salt okunur, filtre satırı, sıralama, sayfalama) | `FilterableTableView(headers, profile_key)` (varsayılan `mode="list"`); genelde `ThreePanelBaseWidget` içinde | Cari/Stok/Teklif listeleri, Kasa/Banka/Cari/Stok hareketleri, Görevler |
| **Giriş** (hücre içi düzenleme, kalem satırları) | `FilterableTableView(..., mode="entry", table_view_class=EntryTableView)` | Fiş kalemleri (cari/kasa/banka/stok), belge kalemleri (teklif…fatura) |
| **Küçük tablo** (özet, diyalog listesi) | `standart_grid(profile_key, [(anahtar, başlık), ...])` (`entry_table_view.py`) | Fiş Toplamlar tabloları, küçük diyalog listeleri |

## 2. Bileşen haritası

| Bileşen | Dosya | Görev |
|---|---|---|
| `FilterableTableView` | `ui/components/filterable_table.py` | Standart grid: başlık, filtre satırı, sütun menüsü, görünüm profilleri |
| `EntryTableView` | `ui/components/entry_table_view.py` | Giriş modunun tablo motoru: QTableWidget benzeri yüzey (`item/setItem/insertRow/removeRow/setRowCount/currentRow/currentColumn/setCurrentCell/editItem/cellDoubleClicked/itemChanged/currentCellChanged`), Enter/Tab gezinme, son satırı aşınca `row_append_requested`, `commit_editor()`, `suspend/resume_navigation()` |
| `standart_grid()` | `entry_table_view.py` | Küçük tabloyu tek çağrıda kurar |
| `EntryGridBase` | `ui/widgets/entry_grid_base.py` | **Tek taban sınıf** (belge + fiş kalemleri): `KolonTanimi` ile sütun tanımı (tip: text/para/tarih/combo/lookup/readonly/secim; `oran`+`min_px` genişlik), standart grid kurulumu (`self.entry` = `FilterableTableView`, `self.tv` = `EntryTableView`, `self.model`), tipine göre editör, Enter/Tab gezinme, sağ tık menüsü, oranlı genişlik, hücre erişimi (`text/set_text/item/kimlik/set_kimlik`), satır işlemleri (`secili_satirlar`, `satirlari_sil`, `satiri_tasi`, `aktif_satir`) |
| `FisKalemGrid` | `ui/widgets/fis_kalem_grid.py` | `EntryGridBase` alt sınıfı — fiş satırı: sıra no (`sn`), sonda hep boş satır, boş satır kuralı; kancalar `hucre_degisti`, `satir_bayraklari`, `bos_mu`, `varsayilan_degerler`, `lookup_delegate`, `combo_secenekleri`. Alt sınıflar: cari/finans/stok kalem widget'ları |
| `DocumentLinesGrid` | `ui/widgets/document_lines_grid.py` | `EntryGridBase` alt sınıfı — belge kalemi (teklif…fatura): stok arama, satır dövizi/kur, KDV, iskonto, toplam sinyali (`totals_changed(dict)`). Geriye uyum: burada `grid` = `FilterableTableView` (fiş gridlerinde `grid` = tablo) |
| `NavDelegate` / `MoneyDelegate` / `ComboDelegate` / `DateDelegate` | `ui/components/grid_delegates.py` | Hücre editörleri (para = `MoneyEdit`) |
| `ProfileStyleDelegate` | `ui/components/profile_style_delegate.py` | Renk kuralları + (giriş modunda) Enter/Tab gezinmesi |
| `TooltipManager` | `ui/components/tooltip_manager.py` | Tüm ipuçları (hücre/başlık dahil) okunur pencerede |
| `veri_bus` | `services/veri_bus.py` | Kayıt sonrası açık ekranların canlı yenilenmesi (`BUS_KONULARI`) |
| `sayi_bicimi` | `services/sayi_bicimi.py` | Kur / fiyat / miktar / tutar hane sayıları (Ayarlar › Kuruş Hanesi) |

## 3. Yeni tablo yazma kuralları

1. **Yeni ekran/tabloda `AppGrid`, `QTableWidget`, `QTableView`'i doğrudan KULLANMA.** Yukarıdaki üç kullanımdan birini seç.
2. **Sütun anahtarı (field adı) kalıcıdır.** Görünüm profilleri anahtara bağlıdır; anahtarı değiştirme/yeniden adlandırma. Başlık metni serbesttir.
3. **`profile_key` kararlı ve benzersiz olmalı** (ör. `finans_hareket_kasa`, `dbgrid_cari_fis_kalem`). Profil anahtarı değişirse kullanıcının kayıtlı profilleri kaybolur.
4. **Hücre öğesi `QStandardItem`'dır.** DİKKAT: `QStandardItem.setData(değer, rol)` — `QTableWidgetItem.setData(rol, değer)`'in TERSİ.
5. **Tutar biçimi:** `money_edit.bicimle(değer, sayi_bicimi.hane("tutar"))` (Türkçe `1.250,00`), sağa hizalı; para birimi ayrı sütun. Elle `f"{x:,.2f}"` yazma.
6. **Parasal giriş hücresi `MoneyDelegate`** (kur/fiyat/miktar/tutar için `sayi_bicimi.hane(...)`).
7. **Liste ekranı `ThreePanelBaseWidget` alt sınıfıdır;** kayıt sonrası canlı yenileme için `BUS_KONULARI = ("cari",)` gibi konu belirt.
8. **Kalem/hesaplama mantığı grid'de olmaz** (uzun vadeli kural; bugün belge gridinde hâlâ var): hesap servise gider, grid sonucu gösterir.
9. **Silme = gizleme** (soft delete); toplu işlemler servis üzerinden.
10. **UI doğrudan `commit` çalıştırmaz;** kayıt servis katmanındadır.
11. **İpucu için** widget'a `setToolTip(...)` yeter; stil ekleme (TooltipManager sabit stille gösterir).

## 4. Testler için kritik notlar

- `tests/conftest.py` `QSettings(org, app)` çağrılarını geçici INI dosyasına yönlendirir. **Kullanıcının gerçek kayıt defteri ayarlarına (görünüm profilleri!) dokunma.** Bu yalıtımı bozma. (Geçmişte test paketi kullanıcı profillerini siliyordu.)
- Profil testinde: `k.entry.save_column_profile("Ad")` → yeni widget → `QTest.qWait(80)` (aktif profil ertelenmiş uygulanır) → doğrula → `ProfileManager(profile_key=...).delete_profile("Ad")` + `set_active_profile_name("Varsayılan")` ile temizle.
- Giriş gridi testlerinde hücre: `k.grid.item(r, c).setText(...)`; başlık: `k.grid.model().headerData(i, Qt.Orientation.Horizontal)`.
- Tam paket çalışırken bir grup dosyada süreç çıkışında Windows/Qt çökmesi görülebilir (bilinen ortam sorunu); dosyaları tek tek/gruplarla çalıştır.

## 5. Geçiş durumu (2026-09-24)

**Tamam (standart gride taşındı):** cari/kasa/banka/stok fiş kalem gridleri (`FisKalemGrid`) ve belge kalemleri (`DocumentLinesGrid`) TEK tabandan (`EntryGridBase`) türüyor: aynı giriş motoru (`EntryTableView`), Enter/Tab akışı, son satırda yeni satır, sağ tık menüsü, sütun/profil menüsü; teklif liste tutar biçimi; standart düğme stili (`button_style.py`); Fiş Toplamlar tabloları ve 4 diyalog (YZ2 24–25).

**Standart grid'de zaten olanlar:** Cari Listesi (`cari_list_screen`), Stok Listesi, Teklif/Sipariş/Fatura listesi, Kasa/Banka/Cari/Stok hareketleri,
Görevler listesi, belge kalemleri (`DocumentLinesGrid`), müşteri/kaynak/kullanıcı/firma yönetim listeleri.

**Hâlâ `AppGrid` kullananlar** (taşınacak; sıra önerisi): 
1. Fiş "Toplamlar" tabloları: `cari_fis_toplam_widget.py`, `finans_fis_toplam_widget.py` (alt sınıf), `stok_fis_toplam_widget.py` → **YZ2 Görev 24**
2. Küçük diyaloglar: `gdrive_folder_dialog.py`, `stok_hareket_dialog.py`, `backup_disks_dialog.py`, `dev_item_dialog.py`, `finans_hesap_widgets.py`, `git_report_dialog.py`, `backup_restore_history_dialog.py` → **YZ2 Görev 25**
3. Yedekleme merkezi/pano tabloları: `backup_center_widget.py`, `backup_dashboard.py`
4. ~~Ayarlar tanım tabloları: `settings.py`~~ **Tamam (2026-09-27, Görev 27).** `base_list_screen.py` `AppGrid` kullanımı ayrı, bu maddeye dahil değildi.
5. Diğer: `hareket_alt_paneli.py`, `screen_definition_dialog.py`; eski `hareket_kalemleri_widget*.py` + `TransactionDocumentDialog` (eski belge penceresi; testleri kırık — silinecek/emekli edilecek)

## 6. Sıradaki mimari adımlar (ana geliştirici)

1. ~~`DocumentLinesGrid` + `FisKalemGrid` → tek taban sınıf~~ **Tamam (2026-09-24, `EntryGridBase`).** Kalan tekrar: `DocumentLinesGrid` kendi `add_row/get_lines/_emit_totals` mantığını taşıyor (belge veri modeli); `FisKalemGrid.rows()` benzeri alt sınıf kodları fiş servislerine bağlı.
2. Teklif listesi ile Kasa hareketleri listesinin çevre bileşenleri (paneller, düğme çubuğu, filtre/export alanı) tek liste iskeletinde birleşir.
3. Hesaplamanın (satır/toplam/döviz) griden servise taşınması; Dip toplam yalnızca sonucu gösterir. (`DocumentLinesGrid._row_values/_emit_totals` şu an hesap yapıyor.)
4. ~~Genel Ayarlar tanım tabloları (`settings.py`, `_new_grid` → AppGrid)~~ **Tamam (2026-09-27, Görev 27: `gelistirme/yz2_gorevler/YZ2_GOREV27.md` "Yapıldı").**
5. Ayrıntı: `gelistirme/00_mimari/` altındaki envanter (`grid_envanteri.md`, YZ2 Görev 23) ve kırık test raporu (`kirik_testler.md`, YZ2 Görev 26).
