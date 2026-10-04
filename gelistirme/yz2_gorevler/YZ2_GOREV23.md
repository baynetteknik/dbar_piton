# YZ 2 — Görev 23: Grid Envanteri (yalnızca okuma + belge)

> **Yazacağın tek dosya:** `gelistirme/00_mimari/grid_envanteri.md`
> **Kural:** Kod dosyalarına DOKUNMA. Commit yapma. Önce `gelistirme/00_mimari/GRID_STANDARDI.md` dosyasını oku.

## Amaç
Sistemde hangi ekranın hangi tablo bileşenini kullandığını çıkarmak; taşıma önceliğini belirlemek.

## Yöntem
`C:\toya_erp` içinde şu aramaları yap (Grep aracı ya da `rg`), sonuçları dosya bazında birleştir:

```
AppGrid(            QTableWidget(       QTableView(         FilterableTableView(
EntryTableView      standart_grid(      DocumentLinesGrid(  FisKalemGrid        ThreePanelBaseWidget
```
Kapsam: `src/desktop/ui/**` (test ve `__pycache__` hariç).

## Çıktı biçimi (`grid_envanteri.md`)
Tek tablo, satır başına bir DOSYA:

| Dosya | Ekran / bileşen | Kullanılan tablo bileşeni | Tür (liste / giriş / özet / diyalog) | Standart mı? (E/H) | Taşıma önceliği (1-3) | Not |

- "Standart mı?" = `FilterableTableView` (liste), `FisKalemGrid`/`DocumentLinesGrid`/`standart_grid` (giriş/özet) ise **E**, aksi halde **H**.
- Öncelik: 1 = kullanıcının sık kullandığı ana ekran (cari/stok/kasa/banka/teklif akışı), 2 = ayar/yönetim ekranı, 3 = nadir kullanılan ya da ölü kod adayı.
- Dosya kullanılmıyorsa (başka yerden import edilmiyor) Not sütununa "ölü kod adayı" yaz ve nasıl doğruladığını belirt (hangi arama).
- Tablonun altına: her bileşenden kaç dosyada kullanıldığını gösteren 5 satırlık özet.

## Bitince
Dosyanın en altına `## Yapıldı` başlığı ekle: hangi komutları çalıştırdığını ve emin olmadığın satırları yaz.
