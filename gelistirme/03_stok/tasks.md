# 03 - STOK, FİYAT & ÜRÜN AĞACI GÖREV TAKİBİ

## 📋 GÖREV LİSTESİ

- [x] **03.01** Stok/Hizmet alanları, birimler, KDV ve fiyat alanları belirlendi (`fields.md`)
- [x] **03.02** Ürün Ağacı (BOM / Reçete) ve Fiyat Listeleri veri modelleri tasarlandı (`database.md`)
- [ ] **03.03** `Product`, `ProductBOM`, `PriceList` SQLAlchemy modellerinin kodlanması
- [ ] **03.04** `ProductService` ve `BOMService` (Reçete maliyet hesaplayıcı) servislerinin kodlanması
- [ ] **03.05** 3-Bölmeli Stok Listesi (`STKLIST001`) DbGrid ve Tam Ekran Form (`YNSTK001`) UI entegrasyonu
- [ ] **03.06** Ürün Ağacı tanımlama sekmesi ve Fiyat Listeleri yönetim ekranı (`FIYATLST001`)
- [ ] **03.07** Kritik stok seviyesi renklendirmesinin (Kritik Altı=Turuncu) gridde doğrulanması

## ✅ STOK HAREKET FİŞİ VE DEPO DEFTERİ (kapanış özeti)

- [x] **03.08** Ortak fiş iskeleti: `FisDialogBase` + `FisKalemGrid` (cari, stok; kasa/banka aynı iskeleti kullanacak)
- [x] **03.09** `StokFis` + `StokHareket` modelleri (depo bazlı defter, ondalıklı miktar, silme = gizleme)
- [x] **03.10** `StokFisService`: giriş / çıkış / depo transferi / sayım / açılış; düzenleme ve gizlemede stok etkisi geri alınır; yetersiz stok kontrolü
- [x] **03.11** Stok Fişi penceresi (stok kodu/barkod/ad arama, depo, hedef depo, birim bazında toplamlar, Yazdır/PDF/Excel)
- [x] **03.12** "Stok Hareketleri" liste ekranı (STOK menüsü, standart 3 panelli, sütun düzeni otomatik kaydedilir)
- [x] **03.13** Stok kartından elle stok değişince fark deftere yazılır (`kart_duzeltme`); yeni kartta açılış stoğu
- [x] **03.14** Stok kartı "Stok Hareketleri" penceresi + kart alt şeridi: yeni defter + eski `stock_movements` tek listede, depo dağılımı ve "depoya atanmamış" miktar

### Açık maddeler
- [ ] İçe aktarma (`importer`), pazaryeri eşitleme (`mappers`) ve `resources.py` toplam stoğu doğrudan yazıyor; deftere düzeltme kaydı yazmıyor (depo dağılımında "depoya atanmamış" olarak görünür)
- [ ] `Product.stock` alanı tam sayı tipinde (SQLite ondalığı saklıyor); Float'a geçiş temiz bir taşıma ile yapılmalı
- [ ] Negatif stok izni ayarı (şu an servis parametresi, ayarlara bağlı değil)
- [ ] Depo tanım ekranı (kart) — şu an `WarehouseDefinition` yalnızca ayarlarda; ilk fişte "MERKEZ" otomatik oluşur
- [ ] Yazdırma tasarımcı şablonları (şu an yalın ortak HTML/PDF)
- [ ] Faturadan / irsaliyeden doğan stok hareketleri (fatura adımı)

## ✅ HİZMET TANIMLARI (kapanış özeti, 2026-09-29)

- [x] **03.15** `Product` modeline hizmet alanları: `tracks_stock`, `sales_account_code`, `purchase_account_code`, `vat_withholding_rate`, `nondeductible_expense`, `invoice_description_template`
- [x] **03.16** Gerçek hata düzeltildi: fiş satır ızgarasındaki "Malzeme/Hizmet" seçici salt kozmetikti, `QuotationLine.stok_etkisi`'ni etkilemiyordu — katalogdan seçilen bir Hizmet kartı fatura/irsaliyede stok hareketi üretip depo isterdi. `BelgeHareketService.isle()` artık bağlı `Product.tracks_stock` alanını kontrol ediyor
- [x] **03.17** Stok Kartı ekranı: "3. Stok Takibi" bölümüne `tracks_stock` onay kutusu, "5. KDV" bölümüne `vat_withholding_rate` katalog alanı, yeni "7. Muhasebe & Hizmet" bölümü (hesap kodları, KKEG, fatura açıklama şablonu) eklendi
- [x] **03.18** İkinci gerçek hata düzeltildi: `ProductService.PRODUCT_FIELDS` elle tutulan bir liste — yeni alanlar buraya eklenmeden `to_dict()`/`save()` tarafından görünmüyordu (model ve UI doğru olsa da kayıt/yükleme sessizce çalışmıyordu). Liste ve `blank_product()` güncellendi
- [x] **03.19** Testler: `test_belge_hareket_service.py` (gerçek Hizmet kartına bağlı satır depo istemeden işleniyor), `test_cari_stok_editors.py` (6 yeni alanın tam kaydet/geri yükle turu) — ekran görüntüsüyle görsel doğrulama da yapıldı
- [x] **03.20** "Fiyat listeleri" ve "Raporlama faydaları" başlıkları ayrı ekran gerektirmiyor: mevcut Fiyat Listesi mekanizması ve genel raporlama zaten kapsıyor (kavramsal olarak ele alındı, kod değişikliği gerekmedi)

## ✅ MASRAF TANIMLARI + AYRI EKRANLAR + PENCERE SIĞDIRMA (kapanış özeti, 2026-09-30)

- [x] **03.21** `Product` modeline masraf tekrar alanları: `is_recurring_expense`, `recurring_due_day`, `recurring_reminder_days_before`; Stok Kartı'na "8. Masraf Tekrarı" bölümü (yalnız `kart_modu="masraf"`)
- [x] **03.22** `ProductService._senkron_masraf_hatirlatma()`: Görevler modülüyle entegrasyon — ayrıntı `gelistirme/10_gorevler_notlar/fields_and_schema.md`
- [x] **03.23** `StokListScreen`'e `kart_modu` ("stok"/"hizmet"/"masraf") eklendi: `product_type`'a göre filtreli liste, ayrı profil anahtarı (`hizmet_list`/`masraf_list`), "Ürün Kodu/Ürün Adı" başlıkları; `StokKartEditorDialog`'a aynı `kart_modu` eklendi (pencere başlığı, alan etiketleri, yeni kayıtta varsayılan `product_type`)
- [x] **03.24** STOK menüsüne "Hizmet Tanımları" ve "Masraf Tanımları" eklendi (`main_window.py` menu_structure + dispatch + yetki: `gate.py`'de `stok.view`'e bağlandı, `Ürün Yönetimi` ile aynı)
- [x] **03.25** Gerçek hata: bir grid sütunu (ör. Geliştirme ekranının "Başlık" sütunu, kullanıcının gerçek kayıtlı profilinde ölçüldü) herhangi bir sebeple binlerce piksele genişleyip profile kaydedilirse sağındaki tüm sütunları ekran dışına itiyordu — `FilterableTableView.MAX_COLUMN_WIDTH=900` ile hem kayıt hem uygulama noktasında sınırlandı (kendini onarır, elle müdahale gerekmez)
- [x] **03.26** Gerçek hata: çok sayıda maksimize pencere/diyalog (Stok/Cari/Firma/Kullanıcı/Rol/Finans Hesap kartları, Teklif-Sipariş-Fatura formu, Belge Detay, Kur Raporları) `showMaximized()` sonrası bazen ekrana tam oturmuyordu (kullanıcı elle küçültüp büyütene kadar) — paylaşılan `window_fit_helper.zorla_ilk_yerlesim()` 11 dosyaya eklendi
- [x] **03.27** Testler: `test_filterable_table_profiles.py` (sütun genişliği sınırlama), `test_stok_kart_dialog.py` (kart_modu filtreleme + menüden açılma), `test_cari_stok_editors.py` (masraf hatırlatma senkronu) — ekran görüntüleriyle görsel doğrulama yapıldı
