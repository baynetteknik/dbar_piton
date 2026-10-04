# YZ 2 — Görev 24: Fiş "Toplamlar" tablolarını standart gride taşı

> **Dosyalar (yalnızca bunlar):** `src/desktop/ui/widgets/cari_fis_toplam_widget.py`, `src/desktop/ui/widgets/stok_fis_toplam_widget.py`,
> gerekirse `tests/test_cari_hareket_screen.py`, `tests/test_finans_fis.py`, `tests/test_stok_fis_ui.py` (yalnızca AppGrid'e özel test satırları).
> `finans_fis_toplam_widget.py` cari widget'ının alt sınıfıdır, değişmesi gerekmez.
> **Kural:** Commit yapma. Önce `gelistirme/00_mimari/GRID_STANDARDI.md` oku. `AppGrid`'in kendisine ve `fis_kalem_grid.py`'ye dokunma.

## Sorun
Kasa/cari/stok fişinin altındaki "TOPLAMLAR" tabloları hâlâ eski `AppGrid` (mavi başlık). Fiş kalem gridi ve teklif gridi ise standart
`FilterableTableView`. Aynı ekranda iki farklı tablo görünümü var.

## Yapılacak
1. `AppGrid(PRESET_ID)` + `register_preset(...)` + `enable_layout_persistence(...)` yerine `standart_grid` kullan
   (`from src.desktop.ui.components.entry_table_view import standart_grid`):
   ```python
   self.entry = standart_grid(self.PRESET_ID, [(f"c{i}", e) for i, e in enumerate(self.ETIKETLER)])
   self.grid = self.entry.table_view          # EntryTableView (QTableWidget benzeri yüzey)
   v.addWidget(self.entry, 1)
   ```
   Cari widget'ta `ETIKETLER` alt sınıflarca değiştirilebiliyor (finans) — sütun anahtarları `c0..cN` kalsın; başlıklar `ETIKETLER`'den gelsin.
2. `_row` içinde `QTableWidgetItem` → `QStandardItem`; `g.setRowHeight(r, g.effective_row_height)` aynı kalır. Hücreler salt okunur olmalı:
   `it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)`. Hizalama, kalın yazı ve B/A renkleri aynen korunur.
3. `update_totals` / `clear` içindeki `g.setRowCount(0)` aynen çalışır (EntryTableView'da var).
4. Sütun genişlikleri: `_WIDTHS` oranlarını, widget ilk gösterildiğinde/yeniden boyutlanınca `setColumnWidth` ile uygula
   (`FisKalemGrid._oranli_genislik`/`showEvent`/`resizeEvent` desenine bak; kullanıcı elle genişlik verince oran devreye girmez).
5. Aynısını `stok_fis_toplam_widget.py` için yap (`_WIDTHS` oranları orada).
6. `PRESET_ID`/`PRESET_AD` ve `grid_presets` içe aktarmaları artık gerekmiyorsa kaldır.

## Testler
Çalıştır (her biri geçmeli; eski AppGrid API'sine bağlı satırları yeni API'ye uyarla — ör. `t.grid._save_layout()` çağıran
"toplam widget sütunları kaydedilir" testi artık profil tabanlı: `t.entry.save_column_profile("Ad")` → yeni widget → `QTest.qWait(80)` → doğrula →
`ProfileManager(profile_key=...).delete_profile("Ad")` + `set_active_profile_name("Varsayılan")`):
```
.venv\Scripts\python.exe -m pytest tests/test_cari_hareket_screen.py tests/test_finans_fis.py tests/test_stok_fis_ui.py -q -p no:cacheprovider
```
`tests/conftest.py` kullanıcı ayarlarını yalıtır; bunu bozma. Görsel kontrol: `d = FinansFisDialog(db, grup="kasa", tur="tahsilat"); d.show(); d.grab().save("x.png")` ile ekran görüntüsü al, toplam tablosunun başlığı kalem gridiyle aynı (açık başlık) olmalı.

## Bitince
Bu dosyanın altına `## Yapıldı` ekle: değişen dosyalar, çalıştırdığın testlerin sonucu, ekran görüntüsü yolu.

## Yapıldı

24.09.2026 — `feat/gorev-23-26-grid-standardizasyonu` dalında, commit yapılmadan tamamlandı.

- Değişen üretim dosyaları: `cari_fis_toplam_widget.py`, `stok_fis_toplam_widget.py`. AppGrid/preset kaydı yerine `standart_grid` + `EntryTableView`, salt okunur ve seçilebilir `QStandardItem` hücreler kullanılıyor.
- `finans_fis_toplam_widget.py` değiştirilmedi; cari alt sınıfı üzerinden standart gride geçti. Döviz başlıkları, B/A ve G/Ç renkleri, kalın toplam satırı ve tutar biçimleri korundu.
- Mevcut profil kimlikleri korundu; sütun anahtarları `c0..cN`. Oranlı ilk genişlikler gösterme/resize sırasında uygulanıyor, kullanıcı veya profil genişliği uygulandığında yeniden ezilmiyor.
- Test uyarlaması: yalnız `tests/test_cari_hareket_screen.py::test_toplam_widget_sutunlari_da_kaydedilir`. Eski `_save_layout()` yerine profil kaydet/yükle; sıra, gizleme, genişlik ve resize sonrasında genişliğin korunması doğrulanıyor. Test profili finally ile temizleniyor. `tests/conftest.py` değiştirilmedi.
- İlk üç-dosya koşusunda 64 test geçti, uyarlanan testte eksik QTest importu bulundu; düzeltildikten sonra tekil test geçti. Son birleşik koşuda bu üç dosyanın **65 testi de geçti** (Görev 25 ile toplam 102 test başarılı).

Komutlar:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_cari_hareket_screen.py tests/test_finans_fis.py tests/test_stok_fis_ui.py -q -p no:cacheprovider
.venv/Scripts/python.exe -m pytest tests/test_cari_hareket_screen.py::test_toplam_widget_sutunlari_da_kaydedilir -q -p no:cacheprovider --tb=short
```

Görsel kontrol: `tests.conftest` ile yalıtılmış QSettings ve bellek içi SQLite kullanılarak `FinansFisDialog(grup="kasa", tur="tahsilat")` açıldı; TRY/USD örnek toplamlarıyla `grab()` görüntüsü alındı ve incelendi. Başlıklar kalem gridiyle aynı açık renkte, miktarlar sağa hizalı, toplam satırı kalın ve giriş yönü yeşil.

Ekran görüntüsü: [scratch/gorev24_finans_toplam.png](../../scratch/gorev24_finans_toplam.png).

Ruff kontrolü değişen üretim dosyalarında temiz. Önceden var olan SQLAlchemy `datetime.utcnow()` uyarıları sürüyor; kapsam dışı dosyalara müdahale edilmedi.
