# 02 - CARİ HESAPLAR GÖREV TAKİBİ

## 📋 GÖREV LİSTESİ

- [x] **02.01** Cari kartı alanları, vergi/e-fatura ve adres alanları belirlendi (`fields.md`)
- [x] **02.02** Cari veritabanı şeması ve bakiye alanı modellendi (`database.md`)
- [x] **02.03** Kopyalama (`/copy`) ve hızlı ekleme gereksinimleri netleştirildi
- [ ] **02.04** `Customer` SQLAlchemy modelinin güncellenmesi (Ödeme planı, fiyat listesi ve bakiye eklenerek)
- [ ] **02.05** `CustomerService` (GenericService'ten türetilerek) entegrasyonu
- [ ] **02.06** 3-Bölmeli Cari Listesi (`CAKALST001`) DbGrid ve Tam Ekran Form (`YNCARK001`) UI entegrasyonu
- [ ] **02.07** Koşullu renklendirme kuralının (Borçlu=Kırmızı, Alacaklı=Yeşil) gridde test edilmesi

## 📝 GELİŞTİRİCİ NOTLARI
- Cari bakiye doğrudan faturadan, tahsilattan ve tediyeden tetiklenecek; `balance` alanı sürekli güncel tutulacak.
