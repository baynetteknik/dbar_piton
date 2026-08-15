# 🛠️ TOYA ERP - GELİŞTİRİCİ ÇALIŞMA & MODÜL REHBERİ

Bu klasör (`C:\toya_erp\gelistirme\`), projenin tüm modüllerinin **ekran alanlarını (fields)**, **veritabanı şemalarını (database)** ve **geliştirici görev/durum takibini (tasks)** modül modül ayrıştırılmış olarak içerir.

Geliştirici ister doğrudan bu klasördeki `.md` dosyalarından, isterse programın içindeki **Geliştirici Modülü (`DEVTODO001`)** üzerinden ilerlemeyi takip edebilir.

---

## 📁 MODÜL DİZİN İNDEKSİ

| Modül Klasörü | Modül Adı | Kısakod | Durum |
| :--- | :--- | :--- | :--- |
| [`01_ayarlar/`](file:///C:/toya_erp/gelistirme/01_ayarlar/) | Firma, Kullanıcı, Döviz, Genel Tanımlar | `GENELAYR001`, `DOVIZKUR001` | 📝 Tasarım Aşamasında |
| [`02_cari/`](file:///C:/toya_erp/gelistirme/02_cari/) | Cari Kartları (Müşteri/Tedarikçi/Personel) | `CAKALST001`, `YNCARK001` | 📝 Tasarım Aşamasında |
| [`03_stok/`](file:///C:/toya_erp/gelistirme/03_stok/) | Stok/Hizmet, Fiyat Listesi, Ürün Ağacı (BOM) | `STKLIST001`, `URUNAGAC001` | 📝 Tasarım Aşamasında |
| [`04_odeme_planlari/`](file:///C:/toya_erp/gelistirme/04_odeme_planlari/) | Ödeme Planları, Vade & Taksit Şablonları | `ODMPLN001` | 📝 Tasarım Aşamasında |
| [`05_teklif_siparis/`](file:///C:/toya_erp/gelistirme/05_teklif_siparis/) | Teklif & Sipariş Yönetimi | `TEKLIST001`, `YNTEKF001` | 📝 Tasarım Aşamasında |
| [`06_fatura_irsaliye/`](file:///C:/toya_erp/gelistirme/06_fatura_irsaliye/) | Satış, Alış, İade Faturası & İrsaliye | `FATLIST001`, `YNSATFAT001` | 📝 Tasarım Aşamasında |
| [`07_kasa/`](file:///C:/toya_erp/gelistirme/07_kasa/) | Nakit Kasalar, Tahsilat, Tediye | `KASATAH001`, `KASATED001` | 📝 Tasarım Aşamasında |
| [`08_banka/`](file:///C:/toya_erp/gelistirme/08_banka/) | Banka Hesapları, POS, Havale, Virman | `VRMTRAN001` | 📝 Tasarım Aşamasında |
| [`09_cek_senet/`](file:///C:/toya_erp/gelistirme/09_cek_senet/) | Çek & Senet Portföy Yönetimi | `CEKLIST001` | 📝 Tasarım Aşamasında |
| [`10_gorevler_notlar/`](file:///C:/toya_erp/gelistirme/10_gorevler_notlar/) | Görev & İş Takibi, Geliştirici Günlüğü | `GOREVLST001`, `DEVTODO001` | 📝 Tasarım Aşamasında |
| [`11_entegrasyonlar/`](file:///C:/toya_erp/gelistirme/11_entegrasyonlar/) | WooCommerce, Trendyol, XML, Logo/Akınsoft | `ENTEG001` | 📝 Tasarım Aşamasında |

---

## 📄 HER MODÜL KLASÖRÜNÜN İÇERİĞİ

Her modül klasöründe standart 3 dosya yer alır:
1. **`fields.md` (Ekran ve Form Alanları):** 3-bölmeli liste sütunları, filtreleri, tam ekran form alanları, tipleri ve zorunlulukları.
2. **`database.md` (Veritabanı Şeması):** Tablo isimleri, kolon tipleri, index'ler, foreign key ilişkileri ve soft delete kuralları.
3. **`tasks.md` (Görevler & Durum):** O modül için atanmış görevler, tamamlananlar, bekleyenler ve geliştirici notları.
