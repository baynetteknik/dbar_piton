# 🏭 TOYA ERP & ÖN MUHASEBE VE ENTEGRASYON SİSTEMİ
## MASTER SİSTEM PROMPTU & MİMARİ ŞARTNAME (GÜNCEL)

---

## 📌 0. HAZIRLIK AŞAMASI (Tasarım & Şablonların Belirlenmesi)
> **KURAL:** Bu aşamada kod yazılmaz. Tüm veri modelleri, CRUD sözleşmeleri, UI tasarımları ve entegrasyon şablonları dokümante edilip netleştirilir. Çıktılar doküman olarak saklanır ve kullanıcı onayı alınır.

### 0.1. Veritabanı Şema Tasarımı
- **Tüm Tablolar İçin Ortak Alanlar:** `id` (int/UUID), `tenant_id` (int/UUID), `is_deleted` (bool - Soft Delete), `version_id` (int - Optimistic Lock), `created_at` (datetime), `updated_at` (datetime).
- **Modül Alan Listeleri & İlişkiler:**
  - *Firma / Şube:* Künye, vergi no, e-fatura entegrasyon ayarları, varsayılan para birimi, çalışma dönemi.
  - *Kullanıcı:* Giriş, profil, firma bağı, rol, kişiselleştirilmiş grid ve renk ayarları.
  - *Merkezi Döviz:* TRY, USD, EUR para birimleri, TCMB günlük kurları, kur geçmişi.
  - *Dinamik Kısakodlar (`screen_shortcuts`):* Sistemdeki tüm ekranların anlamlı kısakodları (Yöneticinin değiştirebileceği dinamik yapı).
  - *Kullanıcı Grid Ayarları (`user_grid_settings`):* Sütun genişlikleri, gizle/gösterme, sıra ve koşullu renklendirme kuralları.
  - *Görevler & Notlar (`tasks`, `notes`):* Geliştirici yapılacaklar listesi, kullanıcı iş/görev takibi, ilişkili cari/fatura bağı, öncelik, durum, hatırlatıcılar.
  - *Ödeme Planları (`payment_plans`, `payment_plan_terms`):* Vade günleri, peşinat oranı, taksit sayısı ve vadeleri.
  - *Gelişmiş Fiyat Listeleri (`price_lists`, `price_list_items`):* Cari/Grup bazlı fiyat matrisi, dövizli fiyatlar.
  - *Ürün Ağacı / Reçete (`product_bom`, `product_bom_items`):* Set/Paket ürünler, mamul-hammadde reçeteleri, fire oranları.
  - *Cari Kartları:* Ünvan, kod, vergi/TCKN, e-fatura kutusu, çoklu adres/telefon, bakiye, risk limiti, varsayılan ödeme planı.
  - *Stok Kartları:* SKU, barkod, ad, kategori, marka, birim, KDV oranları, alış/satış fiyatı, kritik stok, ürün ağacı bağı.
  - *Teklif & Fatura:* Başlık, kalemler, iskonto, KDV, tevkifat, ödeme planı taksitleri, stok/cari/kasa otomatik hareketleri.
  - *Kasa & Banka:* Kasa/Banka/POS hesapları, tahsilat, tediye, virman (transfer), çek/senet portföyü.

### 0.2. Generic CRUD Şablonu (Backend Sözleşmeleri - DRY Prensibi)
- **`BaseModel` (SQLAlchemy 2.0 Async):** Ortak alanlar ve tenant filtreleme mantığı.
- **`BaseSchema` (Pydantic v2):** Ortak `id`, `created_at`, `updated_at`, `is_deleted` şemaları.
- **`GenericRepository[T]`:** `get_by_id`, `get_all` (filtreleme, sütun bazlı arama, sayfalama, sıralama), `create`, `update`, `delete_soft`, `copy`.
- **`GenericService[T]`:** İş mantığı soyutlaması, transaction yönetimi (`commit`/`rollback`).
- **`GenericRouter[T]`:** Standart CRUD endpoint'lerini tek satırla otomatik üreten fabrika fonksiyonu.
- **Merkezi Döviz Servisi (`MoneyService`):** Tüm modüllerde tek satırla kur ve çapraz kur çevirisi.
- **Görev & Bildirim Servisi (`TaskService`):** Geliştirici ve personel görevleri, vade hatırlatıcıları, ilişkili kart entegrasyonu.
- **Ödeme Planı Motoru (`PaymentPlanService`):** Fatura/Teklif tutarını taksit vadelerine ve cari hareketlerine bölen servis.
- **Ürün Ağacı Motoru (`BOMService`):** Set/Paket ürün satıldığında alt bileşenlerin stok hareketlerini yöneten servis.

### 0.3. Evrensel 3-Bölmeli Gelişmiş DbGrid Şablonu (Dia / ERP Master Layout)
- **Üst Bar (Navbar):** `Breadcrumb`, Global Hızlı Arama (`Ctrl+K` & Anlamlı Kısakod `CAKALST001`), Ana Menüye Dönüş, Aktif Firma/Kullanıcı, Hızlı Görevler/Notlar Paneli.
- **Sol Panel (İşlemler / Aksiyonlar):** `➕ Yeni Ekle`, `✏️ Düzenle`, `📋 Kopyala`, `❌ Sil / Pasife Al`, `🖨️ Yazdır`, `📤 Excel`, `📥 İçe Aktar`.
- **Orta Panel (Gelişmiş Data Grid & Kanban Seçeneği):**
  - *Sütun Bazlı Arama Satırı:* Senkronize genişlik ve kaydırma.
  - *Kullanıcı Bazlı Sütun Ayarları:* Sütun genişlikleri, gizleme ve sıra kaydı.
  - *Koşullu Renklendirme:* Borçlu kırmızı, alacaklı yeşil, kritik stok turuncu, acil görevler kırmızı.
  - *Görevler İçin Kanban Pano Modu:* (Yapılacak $\rightarrow$ Devam Ediyor $\rightarrow$ Tamamlandı).
- **Sağ Panel (Gelişmiş Filtreler & Ekstra İşlemler):** Durum, Gruplar, Tarih Aralığı, Mecra, Özel Kodlar ve filtre sıfırlama.
- **Tam Ekran Form Bileşeni:** Dikey kaydırmalı, 3-4 kolonlu ferah ızgara, `Kaydet`, `Vazgeç`, `Kopyala`.
- **Akıllı Hızlı Giriş & Serbest Kalem:** Hızlı cari/stok ekleme, serbest kalem yazabilme ve `[x] Kartlara da kaydet`.

### 0.4. Dinamik & Anlamlı Kısakod Sistemi (Command Palette - `Ctrl+K`)
| Varsayılan Kısakod | Ekran / Modül Adı | Açıklama |
| :--- | :--- | :--- |
| **`YNGOREV001`**| Yeni Görev / Yapılacak Ekle | Görev / To-Do ekleme formu |
| **`GOREVLST001`**| Görev & İş Takibi Listesi | Görevler gridi & Kanban panosu |
| **`YNNOT001`**   | Yeni Not Ekle | Hızlı not alma formu |
| **`NOTLIST001`** | Notlar Listesi | Not defteri ve sistem notları |
| **`DEVTODO001`** | Geliştirici Yapılacaklar Listesi | Geliştirici / Admin görev ve yama günlüğü |
| **`YNCARK001`** | Yeni Cari Kartı Ekle | Müşteri / Tedarikçi ekleme formu |
| **`CAKALST001`** | Cari Kart Listesi | Tüm carilerin data grid listesi |
| **`YNSTK001`** | Yeni Stok Kartı Ekle | Ürün / Hizmet ekleme formu |
| **`STKLIST001`** | Stok Kart Listesi | Ürün ve envanter grid listesi |
| **`YNTEKF001`** | Yeni Teklif Hazırla | Teklif oluşturma tam ekran formu |
| **`TEKLIST001`** | Teklif Listesi | Verilen/alınan teklifler gridi |
| **`YNSATFAT001`**| Yeni Satış Faturası | Satış faturası oluşturma formu |
| **`YNALFAT001`** | Yeni Alış Faturası | Alış faturası giriş formu |
| **`FATLIST001`** | Fatura Listesi | Tüm faturaların arşivi ve listesi |
| **`ODMPLN001`** | Ödeme Planları | Vade ve taksit planı tanımları |
| **`URUNAGAC001`**| Ürün Ağacı (Reçete / BOM)| Mamul, set ve paket ürün ağacı |
| **`FIYATLST001`**| Gelişmiş Fiyat Listeleri | Cari/Grup özel fiyat tanımları |
| **`KASATAH001`** | Kasa Tahsilat Fişi | Nakit para girişi fişi |
| **`KASATED001`** | Kasa Tediye Fişi | Nakit para çıkışı fişi |
| **`VRMTRAN001`** | Virman Transfer Fişi | Kasa $\leftrightarrow$ Banka transferi |
| **`DOVIZKUR001`**| Döviz & Kur Yönetimi | Para birimleri ve TCMB kurları |
| **`GENELAYR001`**| Genel Sistem Ayarları | Grid, renk, lisans ve kısakod yönetimi |

---

### 0.5. GÖREVLER, YAPILACAKLAR & NOTLAR MODÜLÜ (`GOREVLST001` & `DEVTODO001`)

Bu modül iki ana amaca hizmet eder:
1. **Geliştirici & Sistem Yöneticisi Modu (`DEVTODO001`):**
   - Kodlama sürecinde yapılacaklar, bug takibi, veritabanı yama notları ve versiyon değişiklik günlüğü (Changelog) tutulur.
   - Sadece Geliştirici/Süper Admin yetkisindeki kullanıcılara görünür.
2. **Kullanıcı & Ekip İş/Görev Takip Modu (`GOREVLST001`):**
   - Şirket içi iş ve görev dağılımı (Örn: "Ahmet Bey ABC Ltd. carisinden 15.000 TL tahsilatı alacak", "Kritik stoktaki ürün için tedarikçiden teklif istenecek").
   - **İlişkili Kart Bağlantısı:** Görev oluştururken doğrudan ilgili **Cari**, **Teklif**, **Fatura** veya **Stok** kartına link verilebilir.
   - **Öncelik Seviyeleri:** `Düşük`, `Normal`, `Yüksek`, `Acil / Kritik` (Renk kodlu).
   - **Durum:** `Beklemede`, `Devam Ediyor`, `İncelemede`, `Tamamlandı`, `İptal`.
   - **İki Farklı Görünüm:** Standart 3-bölmeli Data Grid veya Sürükle-Bırak **Kanban Panosu**.

---

## 🏗️ GELİŞTİRME FAZLARI (1 - 5)
- **Faz 1:** Çekirdek İskelet, Generic Katmanlar, Gelişmiş DbGrid (Senkronize Arama, Kullanıcı Grid Ayarları, Koşullu Renklendirme), Döviz & Dinamik Kısakod Motoru, Görevler & Notlar Modülü.
- **Faz 2:** Temel Kartlar (Cari, Stok, Ödeme Planları, Fiyat Listeleri, Ürün Ağacı, Teklif).
- **Faz 3:** Finans ve Fatura Modülleri (Kasa/Banka, Fatura/İrsaliye, Tekliften Dönüşüm, Taksit Takibi).
- **Faz 4:** Dashboard & Entegrasyon Katmanı (WooCommerce, Trendyol, Dinamik XML, Logo/Akınsoft DB Köprüsü).
- **Faz 5:** Masaüstü (.exe / PyWebView), Web Dağıtımı ve Testler.
