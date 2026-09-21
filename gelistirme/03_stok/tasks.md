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
