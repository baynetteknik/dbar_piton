# 01 - AYARLAR & TANIMLAR GÖREV TAKİBİ

## 📋 GÖREV LİSTESİ

- [x] **01.01** Firma/Şube alanları ve veri tipleri belirlendi (`fields.md`)
- [x] **01.02** Kullanıcı ve Rol alanları belirlendi (`fields.md`)
- [x] **01.03** Merkezi Döviz Motoru alanları ve TCMB entegrasyon kuralı belirlendi
- [x] **01.04** Dinamik Kısakod (`screen_shortcuts`) mimarisi ve tablosu tasarlandı
- [x] **01.05** Kullanıcı Grid & Renk Tercihleri (`user_grid_settings`) tablosu tasarlandı
- [ ] **01.06** `tenants`, `users`, `currencies`, `screen_shortcuts`, `user_grid_settings` SQLAlchemy modellerinin kodlanması
- [ ] **01.07** `MoneyService` (TCMB Kur Çekici & Çapraz Kur Hesaplayıcı) servisinin kodlanması
- [ ] **01.08** Genel Ayarlar & Kısakod Yönetim Ekranı UI (`GENELAYR001`) tasarımının bağlanması

## 📝 GELİŞTİRİCİ NOTLARI
- Döviz kurları TCMB üzerinden çekilirken `aiosonic` veya `httpx` kullanılacak.
- Kısakod arama çubuğu (`Ctrl+K`), `screen_shortcuts` tablosunu yerel bellekte (cache) tutarak sıfır gecikmeyle sonuç döndürecek.
