# Belge Zinciri Tasarımı: Teklif → Sipariş → İrsaliye → Fatura (stok, cari ve rezerv bağlantısı)

Durum: **tasarım onaylandı (2026-09-21), uygulama sırası aşağıda.** Kararlar kullanıcıdan alındı; "Açık sorular" bölümü uygulamadan önce netleşecek.

## 0. Mevcut durum (kodda ne var)
- `Quotation` + `QuotationLine` tek tabloda teklif ve siparişi tutuyor (`quotation_type` = Quotation | Order). `InvoicesWidget` "Invoice" tipine bakıyor ama `DocumentDetailScreen` sekiz belge türünü (teklif, sipariş, irsaliye, fatura; alış/satış) yalnızca **Quotation / Order** olarak kaydediyor → irsaliye ve fatura ayrı bir kayıt türü değil.
- Hiçbir belge stok ya da cari hareketi üretmiyor. Stok (`StokFisService`), cari (`CariHareketService`) ve kasa/banka (`FinansFisService`) hareket altyapıları hazır.

## 1. Kararlar (kullanıcı)
1. **Stok düşümü hem irsaliyede hem faturada olabilir; irsaliyeli faturada TEKRAR düşmez.** Fatura oluştururken bir (veya birden çok) irsaliyeye bağlanır ya da irsaliye içinden "Fatura oluştur" denir.
2. **Cari etkisi:** fatura cariyi borçlandırır (satış) / alacaklandırır (alış). İrsaliyenin cari etkisi yoktur.
3. **Geri dönüş:** resmi bildirim (GİB) yapılmadan önce belge geri alınabilir/iade edilebilir; hareketler ters kayıtla düzeltilir, hiçbir şey silinmez. Bildirimden sonra düzeltme iade faturasıyla yapılır.
4. **Birleştirme:** birçok irsaliye tek faturada birleştirilebilir (irsaliye satırı ↔ fatura satırı bağı, kısmi faturalama dahil).
5. **Sipariş stok rezervi:** isteğe bağlı; **süreli** ya da **müşteri dönüş yapana kadar süresiz**.
6. **Cari borcuna yansıma:** faturanın **genel toplamı** yansır (KDV/iskonto ayrı ayrı yansımaz); müşteri "KDV ödemeyeceğim" gibi bir seçim yapamaz.

## 2. Belge türleri ve hareket kuralları

| Belge | Stok | Cari | Rezerv | Notlar |
| --- | --- | --- | --- | --- |
| Teklif (satış/alış) | — | — | — | Sipariş/irsaliye/faturaya dönüşebilir |
| Sipariş (alınan) | — | — | isteğe bağlı | Rezerv: süreli veya süresiz |
| Sipariş (verilen) | — | — | — | Alış tarafı; gelen mal için beklenen miktar |
| Sevk irsaliyesi | **çıkış** | — | rezervi "kullanıldı" yapar | Faturalanmamış miktar takip edilir |
| Alış irsaliyesi | **giriş** | — | — | |
| Satış faturası | irsaliyesizse **çıkış** | **borç (genel toplam)** | — | İrsaliyeye bağlıysa stok tekrar düşmez |
| Alış faturası | irsaliyesizse **giriş** | **alacak (genel toplam)** | — | |
| Satış/Alış iade faturası | ters yönde (bağlı belgeye göre) | ters yönde | — | Orijinal belgeye bağlanır |

**Stok çift sayım kuralı:** her belge satırının `stok_etkisi` alanı vardır (`kendi` | `kaynaktan`). Faturanın bir satırı irsaliye satırına bağlıysa `kaynaktan`: stok hareketi üretmez. Bir ürünün bir sevkiyat için toplam stok etkisi = irsaliyeler + irsaliyesiz fatura satırları, asla ikisi birden.

## 3. Veri modeli (eklenecek)
- `Quotation.belge_turu` (teklif|siparis|irsaliye|fatura|iade_fatura) + `yon` (satis|alis); mevcut `quotation_type` geriye uyumlu kalır.
- `Quotation.durum` akışı: taslak → onaylı/kesin → (resmi bildirim: elle veya e-fatura entegrasyonuyla) → iptal/iade. `resmi_bildirim_tarihi` boşken geri alma serbest.
- `belge_bag` (kaynak_satir_id, hedef_satir_id, miktar): irsaliye satırı → fatura satırı (kısmi/çoklu). Belge düzeyi: `Quotation.kaynak_belge_idleri` görüntü için bağ tablosundan türetilir.
- `QuotationLine.faturalanan_miktar`, `sevk_edilen_miktar` (bağ toplamlarından hesaplanır, önbellek).
- `stok_rezerv` (siparis_satir_id, product_id, depo_id, miktar, bitis NULL=süresiz, musteri_donus_bekle, durum: aktif|kullanildi|serbest|suresi_doldu). Kullanılabilir stok = eldeki − aktif rezerv.
- Hareketlere kaynak bağı: `StokHareket.belge_id/belge_satir_id`, `CariHareket.belge_id` (belgeden doğan hareketi bulmak/ters çevirmek için).

## 4. Servis: `BelgeHareketService`
- Belge kaydedilir/değişir/iptal edilirken hareketleri **atomik** üretir, günceller, ters çevirir (kasa fişindeki cari karşılığı yaklaşımı).
- `irsaliyeden_fatura(irsaliye_idleri, ...)`: seçilen irsaliyelerin faturalanmamış miktarlarını toplu faturaya çevirir (çoklu birleştirme).
- `iade(belge_id, satirlar)`: bağlı belgeye göre ters stok/cari hareketi + iade belgesi.
- `rezerv_olustur/serbest_birak/suresi_dolanlari_kapat`.
- Resmi bildirim öncesi geri alma: hareketlerin ters kaydı + belge durumu; sonrası engellenir ("iade faturası kesin").

## 5. Uygulama sırası
1. **Model + geçiş:** belge türü/yön/durum alanları, `belge_bag`, `stok_rezerv`, hareket kaynak bağları; DocumentDetailScreen'in irsaliye/faturayı gerçek türle kaydetmesi.
2. **BelgeHareketService + testler:** stok/cari üretimi, çift sayım koruması, geri alma/iade, çoklu irsaliye → tek fatura, rezerv.
3. **Arayüz:** irsaliye içinden "Fatura oluştur", fatura ekranında "İrsaliye seç (çoklu)", iade, rezerv seçenekleri (süreli/süresiz), kullanılabilir stok göstergesi.
4. **Kasa/Banka bağlantısı:** peşin ödeme (fatura → tahsilat fişi), tahsilatın faturaya bağlanması, cari fişindeki Araç=Kasa/Banka satırlarının otomatik `FinansHareket` olması.
5. **Denetim günlüğü ve geri alma** (ayrı iş; belge hareketleri buna uygun tasarlanır: her hareket kaynağını taşır).

## 6. Alınan kararlar (2. tur, 2026-09-22)
1. **Tevkifat: ertelendi.** Kullanıcı muhasebe kuralını araştıracak. O zamana dek cari borcu tevkifatsız faturanın genel toplamıdır; tevkifat alanları belgede saklanabilir ama cari hesabı değiştirmez. Karar gelince `BelgeHareketService` içinde tek noktadan değişir.
2. **Resmi bildirim: elle işaret.** Fatura bizde oluşturulur; e-Devlet'e (GİB) gönderim online yapıldığından belgede **"e-Devlete gönderildi"** işareti ve tarihi elle girilir. İşaret yokken belge geri alınabilir/iade edilebilir; işaretlendikten sonra geri alma kapanır, düzeltme iade faturasıyla yapılır. Ayrıca e-fatura entegrasyonu yazıldığında bu işaret otomatik dolar.
3. **Negatif stok: Genel Ayarlar › Stok bölümünde 3 seçenekli parametre:** *İzin ver* · *Uyarı ver, devam et* · *Uyarı ver, durdur*. Eldeki − aktif rezerv miktarı esas alınır; irsaliye, fatura ve stok çıkış/transfer fişlerinin hepsi aynı ayarı kullanır (`StokFisService` dahil).
4. **Depo: ikisi de.** Belge başlığında varsayılan depo seçilir; her satırda ayrıca değiştirilebilir (satırın deposu belirleyici).
5. **Bakiye etkisiz belgeler cari hareketlerinde görünür:** teklif, talep, sipariş ve irsaliye cari **borç/alacak ve bakiyeyi etkilemez**, ama cari alt panelinde ve ekstrede **"bilgi" satırı** olarak görünür (belge türü, no, tarih, tutar; borç/alacak sütunları boş, bakiyeye katılmaz). Ayrı hareket kaydı üretilmez; satırlar belgelerden okunarak listeye eklenir (bakiye hesabı ve mevcut hareketler bozulmaz). Aynı ilke stokta: sipariş rezervi "rezerv" satırı olarak görünür, teklif/talep stok hareketinde görünmez.

## 7. Faz 1 — TAMAMLANDI (2026-09-22)
- `src/core/belge_turleri.py`: belge türü/yön eşlemesi (`cozumle`, `ekran_metni`, `quotation_type_of`), `geriye_doldur` (eski kayıtları bir kez doldurur, idempotent), hangi türün stok/cari etkileyeceği tablosu (`STOK_ETKILI`, `CARI_ETKILI`).
- Şema: `Quotation` (`belge_turu`, `yon`, `depo_id`, `kaynak_belge_id`, `hareket_durumu`, `resmi_gonderildi`, `resmi_tarih`), `QuotationLine` (`depo_id`, `stok_etkisi`, `sevk_edilen`, `faturalanan`), yeni tablolar `belge_bag` ve `stok_rezerv`, hareketlerde kaynak bağı (`StokHareket.belge_id/belge_satir_id`, `CariHareket.belge_id`). Eski veritabanları açılışta otomatik genişler ve `belge_turu` doldurulur.
- Belge ekranı kaydı artık gerçek türü yazar (irsaliye ve fatura önceden "teklif" olarak kaydediliyordu); yükleme aynı tür metnini geri verir. Teklif → sipariş dönüşümü `kaynak_belge_id` ile bağlanır ve `quotation_type` kanonik `Order` olur (eski uzun metin bırakıldı).
- Liste ekranları `belge_turu`'na bakar; alanı boş eski kayıtlar için eski kural geçerlidir. (İrsaliye listesi/menüsü faz 3.)
- Testler: `tests/test_belge_turleri.py` (26).

## 8. Faz 2 — TAMAMLANDI (2026-09-22)
- `src/desktop/services/stok_negatif_politika.py`: negatif stok politikası (İzin ver | Uyarı ver-devam et | Uyarı ver-durdur), `SystemSetting` üzerinde saklanır (anahtar `stok.negatif_stok_politikasi`, varsayılan `uyari_dur`), saf `degerlendir()` fonksiyonu. **Not:** şimdilik yalnız `BelgeHareketService` kullanıyor; `StokFisService`'e entegrasyonu ve Genel Ayarlar › Stok ekranı ayrı, bekleyen bir iş.
- `src/desktop/services/belge_hareket_service.py` (`BelgeHareketService`):
  - `isle(belge_id)`: irsaliye/faturanın stok (`stok_etkisi='kendi'` satırlar) ve fatura ise cari (genel toplam, `CariHareketService._hazirla` ile) hareketlerini üretir; `kaynaktan` ve hizmet (üründen bağımsız) satırlar stok üretmez (çift sayım koruması). Teklif/talep/sipariş reddedilir. Carisiz fatura reddedilir. Hareketler `belge_id`/`belge_satir_id` ile bağlanır.
  - `geri_al(belge_id)`: yalnız `resmi_gonderildi=False` iken; orijinal satırları SİLMEDEN/DEĞİŞTİRMEDEN ters işaretli yeni `StokHareket`/`CariHareket` satırları ekler (tam denetim izi), `hareket_durumu='geri_alindi'`.
  - `resmi_isaretle(belge_id, gonderildi)`: "e-Devlete gönderildi" elle işareti + tarih; yalnız işlenmiş belgede.
  - `irsaliyeden_fatura(irsaliye_idleri, miktarlar=None)`: birden çok irsaliyeyi (aynı cari + yön) tek faturada birleştirir, kısmi faturalama (`miktarlar` ile), `belge_bag` + `faturalanan` önbelleği; fatura satırları `stok_etkisi='kaynaktan'`.
  - `siparisden_irsaliye(siparis_id, miktarlar=None)`: siparişten (kısmi) irsaliye üretir, sevk edilen miktar kadar aktif `StokRezerv`'i FIFO düşürür/kapatır (`sevk_edilen` önbelleği).
  - `iade(belge_id, satirlar=None)`: fatura/irsaliyeye bağlı iade taslağı (tüm ya da seçilen satırlar); `isle()` ile ters yönde işlenir.
  - `rezerv_olustur/serbest_birak/suresi_dolanlari_kapat`, modül düzeyi `kullanilabilir_stok(db, product_id, depo_id=None)` (eldeki − aktif rezervler; depo bazlı `StokFisService.depo_stok` ile tutarlı).
- Testler: `tests/test_belge_hareket_service.py` (20).

## 9. Sıradaki: Faz 3 — Arayüz
İrsaliyeden fatura / siparişten irsaliye ekran akışı, çoklu irsaliye seçimi, iade ekranı, rezerv (süreli/süresiz) girişi, kullanılabilir stok göstergesi, "e-Devlete gönderildi" işareti. Ardından Faz 4 (kasa/banka bağlantısı). Genel Ayarlar › Stok negatif stok ekranı ayrı bir iştir.

### Faz 3 durumu (tamamlandı)
- `BelgeZinciriBolumu` (sipariş/irsaliye/fatura listelerinin sol panelinde "BELGE ZİNCİRİ"): siparişten irsaliye (kısmi miktar), irsaliyeden fatura (çoklu irsaliye → tek fatura), iade, hareketleri işle / geri al, e-Devlet işareti (işaretliyken geri alma kapalı), rezerv.
- `KalemMiktarDialog`, `RezervDialog` (süreli/süresiz, müşteri dönüşü bekleyen, kullanılabilir stok = eldeki − aktif rezerv).
- İrsaliye Yönetimi ekranı + menü/yetki (`irsaliye.view`); "Yeni" listenin kendi belge türüyle açılır.
- Testler: `tests/test_belge_zinciri_ui.py` (8).
- Belge kalem gridinde seçili satırın stok durumu (eldeki · rezerv · kullanılabilir): `KullanilabilirStokEtiketi`.

### Faz 4 durumu (tamamlandı)
- **Peşin/kısmi tahsilat ve ödeme:** `BelgeHareketService.tahsilat_ekle / tahsilat_kaldir / tahsilatlar / odenen / kalan_tutar`; satış faturası → tahsilat (kasa/banka'ya giriş), alış faturası → ödeme (çıkış). Yalnız işlenmiş faturada, kalan tutarı aşmadan. Fatura sol panelinde "💰 Tahsilat / Ödeme…" (`TahsilatDialog`).
- **Faturaya bağlama:** `CariHareket.tahsilat_belge_id` (fatura kaynaklı borç için kullanılan `belge_id`'den ayrı; geri alma yalnız `belge_id` satırlarını ters çevirir). Bağlı tahsilat varken fatura geri alınamaz; önce tahsilat kaldırılır (gizlenir).
- **Cari fişindeki Araç=Kasa/Banka:** ayrı `FinansHareket` üretilmez — cari satır `fin_hesap_id` ile hesap hareketi olarak zaten okunur (`hesap_hareketleri`); ikinci kayıt çift sayım yaratırdı. Tahsilat da aynı yolu kullanır.
- Testler: `test_belge_hareket_service.py` (+3), `test_belge_zinciri_ui.py` (+2).

### Faz 5 (2026-09-29) — Satır bazlı cari hareket + karışık para birimi
Kullanıcı isteği: "her fiş satırının ödeme sistemine bağlanması ... ödeme sistemi sadece fişte bir not gibi
değil, yaşayan ve işlem gerçekleştiren bir yapı olsun ... her satırda farklı para birimiyle işlem yapılıp
borç/alacaklar kendi cinsinden işlensin." Araştırma: tahsilat zaten CANLI bir mekanizmaydı (gerçekten
`CariHareket` yazıyordu) ama yalnız BELGENİN TAMAMINA bağlıydı; satır bazlı döviz zaten `QuotationLine.doviz/kur`
ile vardı (Kasa/Banka `FinansHareket` tarafında zaten satır-satır ayrı `CariHareket` üretme deseni kanıtlıydı) —
eksik olan bu deseni fatura/teklif zincirine taşımaktı.

Yapılanlar:
- `CariHareket.belge_satir_id` eklendi (→ `quotation_items.id`, `StokHareket.belge_satir_id` ile AYNI desen).
- `_cari_yaz(belge)` artık `belge.lines`'ı gezip HER SATIR için kendi `doviz`/`kur`'uyla, KDV dahil kendi
  tutarıyla AYRI bir `CariHareket` üretiyor (`belge_satir_id` ile bağlı); `list[CariHareket]` döner (eskiden tek).
  Satır kendi dövizini belirtmemişse belgenin para birimine, o da yoksa yerel paraya düşer.
- `geri_al()` zaten satır satır DÖNGÜ ile çalıştığından (çoklu kayıt desteği) değişmedi; yalnız ters kayda da
  `belge_satir_id` taşınması eklendi (denetim izinde hangi satırın tersi olduğu kaybolmasın diye).
- `_borc_kuru()`: artık birden çok (potansiyel olarak farklı dövizli) satır kaydı olabileceğinden, önce
  BELGENİN kendi `currency`'sine ait bir kaydı arıyor (çoğunluk durumu — tüm satırlar aynı dövizde — tam doğru);
  KARIŞIK dövizli bir faturada bu yalnızca yaklaşık bir referanstır — **tahsilat/kur farkı hâlâ belge (fatura)
  düzeyinde TEK bir para biriminde çalışıyor**, bunu da satır/döviz bazlı yapmak ayrı, sonraki bir aşama
  (bilinen, kasıtlı bırakılmış sınırlama).
- `belge.grand_total` (bkz. `_toplamlari_hesapla`) hâlâ TEK özet bir rakam — bu değiştirilmedi, yalnız artık
  "bilgilendirici özet", asıl borç/alacak kaydı satır satır kendi cinsinden işleniyor.
- Testler: `test_belge_hareket_service.py` (+4: çoklu satır → çoklu CariHareket, karışık para birimi kendi
  cinsinden ayrı işleniyor + `dovizli_bakiye` doğrulaması, çoklu satırlı geri alma), `test_belge_zinciri_ui.py`
  (yardımcı `_belge()` artık satırlara `doviz`/`kur` de veriyor — gerçekçi senaryo).

### Faz A (2026-09-29) — Kur farkı: seçmeli gerçek fatura
Kullanıcı kararı: kur farkı hem "sadece cari hareket" (gayri resmi, hızlı) hem "gerçek fatura" (KDVK Md. 24) olarak
işlenebilsin, kullanıcı her seferinde seçsin. Not: Türk vergi mevzuatında ayrı bir "kur farkı faturası" belge TÜRÜ
yoktur (GİB e-Fatura sisteminde özel bir senaryo taşımaz) — bu, tek satırı kur farkı tutarı olan SIRADAN bir
satış/alış faturasıdır. `BelgeHareketService.kur_farki_faturasi_olustur(kur_farki_hareket_id)` eklendi: var olan
bir `tur="kur_farki"` `CariHareket`'ten taslak bir `Quotation` (belge_turu="fatura", kaynak_belge_id=orijinal,
KDV oranı orijinal faturadan taşınır) üretir; taslak döner, kullanıcı düzenleyip `isle()` ile resmileştirir.
Yinelenen çağrı aynı taslağı döner (notes'taki `[kur_farki:ID]` işaretiyle kontrol edilir). `TahsilatDialog`'da
kur farkı çıkınca artık 3 seçenekli bir soru var (`dialog_style.secenek_sor`, yeni genel amaçlı düğme-düğme seçim
yardımcısı). Testler: `test_belge_hareket_service.py` (+1), `test_belge_zinciri_ui.py` (+1).

### Faz B (2026-09-29) — Cariye Genel Tahsilat (FIFO, çoklu para birimi)
Kullanıcı senaryosu: "1.000 USD + 500 EUR + 2.000 TL borcu var, müşteri sadece 15.000 TL ödüyor; önce USD sonra
EUR borcunu o günkü kurdan kapatsın." Kullanıcı kararı (Seçenek 1 + Hibrit, detaylı analiz sonrası): hesap/cari
para birimi kısıtı ikiye ayrıldı —

- **`CariHareketService._finans_hesabi_yaz`**: kısıt artık yalnız hesabın KENDİ para birimi YEREL (TL) DEĞİLSE
  sıkı kalıyor (`hesap_para != para and hesap_para != yerel` koşulu). TL hesap artık HERHANGİ bir dövizdeki cari
  hareketi kapatabiliyor (fiziksel para TL girer, kapanan borç USD/EUR olabilir — `tutar`/`tutar_tl` ikilisi
  zaten bunu taşıyordu). Yabancı para hesaplar (USD kasaya EUR girilmesi gibi) hâlâ reddediliyor — "kasiyer
  yanlış tuşa bastı" koruması korunuyor.
- **`BelgeHareketService.acik_faturalar(customer_id)`**: müşterinin kalan tutarı > 0, işlenmiş faturaları belge
  tarihine göre (FIFO — TOYA'da henüz ayrı bir vade tarihi alanı yok, `payment_plan` yalnız metin; bu bilinen,
  kasıtlı bir sınırlama) sıralar.
- **`BelgeHareketService._tahsilat_plani`** (paylaşılan, kayıt YAZMAYAN saf hesaplama) + **`tahsilat_dagit_onizle`**
  (önizleme) + **`tahsilat_dagit`** (gerçek uygulama): tek bir TL tutarını açık faturalara FIFO dağıtır, her
  faturayı KENDİ para biriminde, ödeme tarihinin kuruyla (kısmi ya da tam) kapatır; mevcut, test edilmiş
  `tahsilat_ekle`'yi ardışık çağırır (yeni bir motor yazılmadı, DRY). `kur_farki_modu`: "cari" / "fatura" (Faz
  A'daki `kur_farki_faturasi_olustur` her kapanan fatura için tek tek çağrılır) / "yok" — TEK bir üst seçim,
  dağıtımdaki TÜM faturalara aynı şekilde uygulanır (her fatura için ayrı ayrı sormak yerine).
- **UI**: `GenelTahsilatDialog` (`belge_zinciri_dialogs.py`) — önce "Dağılımı Göster" (salt önizleme, hiçbir
  kayıt yazmaz), sonra "Onayla ve Uygula". Cari Hareketleri ekranı → DİĞER İŞLEMLER → "💰 Cariye Genel Tahsilat
  (FIFO)" düğmesinden açılıyor.
- Testler: `test_cari_hareket_service.py` (+1, hibrit kısıt), `test_belge_hareket_service.py` (+5: FIFO aynı
  döviz, TL→USD kapatma+kur farkı, kur_farki_modu=fatura, önizleme=gerçek uygulama, açık fatura yok), UI
  ekran görüntüsüyle doğrulandı, `test_cari_hareket_screen.py` (+2, düğme testleri).

**Araştırılan ama henüz yapılmayan (sonraki aşama adayları):**
- Tahsilat/ödeme'yi de satır/döviz bazlı hale getirmek (şu an hâlâ fatura'nın TEK `belge.currency`'sinde çalışıyor;
  karışık dövizli bir faturaya tek bir tahsilatla nasıl ödeme yapılacağı — hangi para biriminin kapatılacağı —
  ayrıca tasarlanmalı).
- Eski `quotation_service.py` yolundaki KUR ÇEVİRMEDEN yapılan ham toplama (satır dövizini hiç dikkate almıyor,
  hâlâ kullanımdaysa gerçek bir hata riski) netleştirilip düzeltilmeli/kaldırılmalı.
- Fiş toplamının (`grand_total`) şirketin yerel parası yerine belgenin KENDİ seçili `currency`'sine göre
  toplanması (`belge_hesap.belge_toplami` hedef parametresi) — araştırıldı, henüz uygulanmadı.

## 10. Kilit ve numara ilkeleri (kullanıcı kararı, 2026-09-25)
**Genel ilke: esnek, kuralcı olmayan.** Bağlantı kuralları varsayılan olarak *uyarır ve devam ettirir*; bloklama yalnız mevzuatın gerektirdiği yerde. Her kuralın sertliği ayarlanabilir olmalı (engelle / uyar / serbest) ve bağı koparma, kilit aşma, silme gibi her işlem **loglanır**; müşteri itiraz ederse loglar gösterilir. Sistem kullanıcıyı bir yola zorlamaz; "yanlışsa düzelt" yolu her zaman açıktır.
- **İrsaliye ↔ fatura:** irsaliye "alt makam" kalır. Fatura silinirken "bağlı irsaliyeler de silinsin mi?" sorulur; hayır denirse irsaliyeler serbest kalır (yeniden faturalanabilir). Bağ koparıp faturayı bırakmak mümkündür ama cari mutabakatta karşı taraf kayıtlarıyla uyuşmazlık riski uyarısı gösterilir. Faturaya bağlı irsaliye başka faturaya bağlanamaz; çözüm: faturayı sil (irsaliyeler serbest) → yeni faturada birden çok irsaliyeyi seç.
- **Logo tarzı (fatura kesilince arka planda otomatik irsaliye) uygulanmaz**; Akınsoft gibi irsaliye modülü isteğe bağlı: irsaliyesiz fatura serbest, irsaliye yazdırmak için faturadan "irsaliye baskısı" formu.
- **Teklif → sipariş:** bir teklif başka bir siparişe bağlanamaz ama satırları kopyalanabilir. Teklifin tamamı siparişe dönüşünce teklif kilitlenir; bağ koparılarak açılabilir (uyarılı, loglu).
- **Mevzuat uyarısı (engel değil):** irsaliye, düzenlendiği ayın sonunu geçmeden (mali müşavirle doğrulanacak: VUK 231/5 — teslimden itibaren 7 gün / toplu faturada ay sonu) faturalanmalıdır. Süre aşılırsa fatura kaydında uyarı verilir.
- **Numara:** `numara_servisi` (bkz. §11). Silinen SON numara geri verilir; e-Devlet işaretli belgenin numarası asla.

## 11. Numara servisi (uygulandı)
- Şablonlu numara: `{YYYY} {YY} {MM} {#####}`; sıra dönemi şablondan türer (aylık/yıllık/sürekli). Varsayılanlar: fatura `FAT{YYYY}{#########}` (GİB biçimi), teklif `TEK-{YYYY}-{#####}`, fişler eski biçimde (`000001`, `K000001`, `B000001`); alış yönü ayrı seri (`AFT…`).
- `numara_servisi`: `belge_numarasi / belge_onizle / belge_kullanildi / belge_silindi`, `fis_onizle / fis_kullanildi / fis_silindi`. Sayaç (`numara_sayac`) ipucudur; çakışma denetimi numaranın kullanımda olmasına bakar (elle girilen/eski numaralar sistemi bozmaz). Belge numarası unique olduğundan silinen son belge `<no>~sil<id>` adını alır, numara serbest kalır.
- Bağlandı: belge kaydı (yeni ekran + eski diyalog), siparişe dönüştürme, hareket servisi (irsaliye/fatura/iade), QuotationService, cari/kasa-banka/stok fişleri, belge silme.
- Ayar bileşeni: `NumaraSablonlariWidget` (yz2 `settings.py` işini bitirince Genel Ayarlar'a panel olarak eklenecek).
- Sıradaki: kilit/bağ yönetimi (yukarıdaki ilkeler), yerel para birimi, fatura kaydında otomatik işleme.

## 12. Kilit / bağ yönetimi (uygulandı)
- `belge_kilit_servisi` (`BelgeKilitServisi`): kurallar `belge.kilit.<kural>` ile *engelle / uyar / serbest*; varsayılanlar: irsaliye-tek-fatura **engelle**, teklif-tek-sipariş **engelle**, resmi belge silme **engelle**, bağlı belge silme / dönüşmüş teklif düzenleme / irsaliye ay aşımı **uyar**. Kararlar `belge_islem_logu` tablosuna yazılır (kullanıcı, kural, karar, ayrıntı; değiştirilmez).
- Silme: fatura silinince kaynak irsaliyeler *serbest kalır* (faturalanan miktar geri gelir, yeniden faturalanabilir) ya da birlikte silinir; irsaliye silinirken bağlı fatura birlikte silinir ya da bağı kopar (işlenmiş faturanın stok bağı koparılamaz: stok kaybı olmasın). İşlenmiş belge silinirken hareketleri ters kayıtla geri alınır; son numara serbest bırakılır; sipariş silinince teklif yeniden serbest (`accepted`).
- `bag_kopar`: belge kalır, kaynak bağı kopar (fatura satırı stoğu artık kendisi etkiler). Belge zinciri bölümünde "🔗 Kaynak Bağını Kopar…".
- Teklif siparişe ikinci kez dönüşmez (kural), bağ koparılınca dönüşür. Dönüşmüş teklifi düzenlemeden önce uyarı. İrsaliye ay dışında faturalanırsa uyarı (engel değil).
- Ayar bileşeni: `BelgeKilitAyarlariWidget` (yz2 `settings.py` işi bitince Genel Ayarlar'a panel olarak eklenecek).
- Bilinen sınır: sipariş silinirken sevk için düşülmüş rezerv geri yüklenmez; "Talep → Teklif" dönüşümü henüz yok.

## 13. Yerel para birimi, döviz ve kur farkı (uygulandı, 2026-09-25)
- **Çalışma para birimi:** firma kartındaki "Çalışma Para Birimi" (`Company.default_currency`) Sistem Dövizleri'nden seçilir (tanımlı/aktif olmalı); cari/kasa-banka/işlenmiş belge hareketi girildikten sonra değiştirilemez. `money_service.yerel_para(db)`, `kur_bul(db, para, tarih)` (yerel para 1; USD şirketinde TL için TL/USD), `get_rate(db, kod, tarih)` (kur geçmişinden o günün/önceki günün kuru; yoksa güncel).
- **Kur kaynağı tek yerde:** cari/kasa-banka hareket servisleri, fiş gridleri (cari, kasa/banka), belge kalem gridi ve belge başlığındaki döviz bileşeni (belge tarihi değişince kur o günün kurundan yenilenir) hepsi `money_service`'i kullanır; sabit "TRY" varsayımları yerel paraya çevrildi (hareket ekranları başlık/etiketleri dahil).
- **Cari bakiye:** her para birimi ayrı bakiye (`CariHareketService.dovizli_bakiye`: borç/alacak/bakiye, hareket günü ve güncel kurla yerel karşılık, gerçekleşmemiş kur farkı); fiş ekranlarındaki Cari Durumu kutusunda gösterilir. 100 USD + 50 EUR + 1000 TL borç ayrı ayrı kapanır.
- **Kur farkı:** faturaya bağlı döviz tahsilatı/ödemesinde tahsilat kuru (tarihe göre, elle değişir) fatura borç kurundan farklıysa diyalog "kur farkı cariye işlensin mi?" diye sorar. Evet → yerel para cinsinden `kur_farki` cari hareketi (`tahsilat_belge_id` + `iliskili_hareket_id` ile bağlı; tahsilat kaldırılırsa birlikte gizlenir; ödenen/kalan hesabına katılmaz). Hayır → döviz bakiyesi kapanır, fark cari yerel bakiyede açık kalır ve "gerçekleşmemiş/kayıtsız kur farkı" olarak görünür. Bilinen sınır: serbest (faturasız) cari fişi tahsilatlarında açık borçlarla eşleştirme henüz yok.
- **Kasa kararı:** para birimi başına ayrı kasa/hesap kartı önerilir; yeni kartta para birimi = yerel para ve "Döviz Kısıtı" açık gelir (çok dövizli kasa isteğe bağlı).

## 14. Belge kaydında otomatik hareket işleme (uygulandı, 2026-09-26)
Belge ekranı başlığında, yalnız hareket üreten türlerde (irsaliye, fatura, iade faturası) "⚙️ Kaydedince Hareketleri İşle" işareti var (varsayılan işaretsiz).
İşaretliyse belge kaydedilince `BelgeZinciriBolumu.otomatik_isle()` çağrılır — "Hareketleri İşle" düğmesiyle birebir aynı işlemi (depo seçimi, yetersiz stok
onayı, stok + faturaysa cari) onay sormadan çalıştırır (işaret zaten onaydır). İşaretsizse belge yalnız taslak kaydedilir. Tek durum alanı (`hareket_durumu`)
korunur; stok/cari ayrı ayrı işaretlenmez (bkz. kullanıcı kararı: ayrı alanlar gerektirecek daha büyük bir model değişikliği yerine tek işaretli, bugünkü mimariyle
uyumlu çözüm seçildi). Testler: `test_document_detail_screen.py` (+3).
