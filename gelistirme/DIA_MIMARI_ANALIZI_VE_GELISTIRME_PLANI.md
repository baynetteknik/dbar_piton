# DIA Mimari Analizi ve Toya ERP Geliştirme Planı

Bu belge, `C:\Users\alp\AppData\Local\DIAApp3-x64` ve `C:\Users\alp\.DIAApp3\baynet` dizinlerinde yer alan DIA ERP masaüstü istemcisi mimari incelemesi, DBGrid mekanizması ve Toya ERP ekran geliştirme yol haritasını içermektedir.

---

## 1. DIA İstemci Mimarisi Özeti

DIA istemcisi PyQt / PySide tabanlı, hafif istemci (thin-client) mimarisiyle çalışan ve form tanımlarını dinamik modüller halinde sunucudan yükleyen bir yapıya sahiptir.

### Temel Modül ve Kütüphane Dağılımı:

| Arşiv / Modül | Dosya Adı | Kapsam ve Yetenekler |
| :--- | :--- | :--- |
| **Çekirdek Widget Seti** | `sis_widgets.shr` | `lqTable` (DBGrid), `lqTableView`, `lqTableFilter`, `lqMemorySource`, `lqMemorySourceDelegate`, `lqLookUp`, `lqListScreen`, `lqNumberEdit`, `lqDateEdit`, `lqMultiComboBox`, `lqDinamikAlanContainer` |
| **Master Evrak Giriş Formu** | `scf2201.gui` | Fatura / İrsaliye / Sipariş / Teklif formu, hareket kalemleri gridi, seri-lot yönetimi, miktar pencereleri, hızlı satır girişi (`scf2201_hizli`) |
| **Stok Kartları** | `scf1100.gui` & `scf1110.gui` | Stok Kartları Listesi ve Detay Kart Formu (barkod, birimler, fiyat listeleri) |
| **Cari Hesaplar** | `scf1301.gui` & `scf2101.gui` | Cari Kart Detayı ve Cari Hareket Ekranı |
| **Satış Teklifleri** | `scf2800.gui` & `scf2801.gui` | Teklif Yönetimi ve Teklif Giriş Formu |
| **Sistem & Temalar** | `sis2100.gui` | Sistem ana menüsü, form yöneticisi ve `dia_styles` (QSS stilleri) |
| **İkonlar** | `sis_icons.shr` | DIA'nın tüm arayüz ikon kaynakları |

---

## 2. DBGrid (`lqTable`) Mimarisi ve Sağlanacak Geliştirmeler

DIA'nın `lqTable` bileşeni şu 5 temel fonksiyonel katmandan oluşmaktadır:

```
┌────────────────────────────────────────────────────────┐
│  lqTableFilter (Kolon Bazlı Hızlı Filtre Satırı)       │
├────────────────────────────────────────────────────────┤
│  lqTableView (Sanal Satırlar, Klavye Gezintisi)        │
├────────────────────────────────────────────────────────┤
│  lqMemorySource (Hafıza Veri Kaynağı & Meta Veri)      │
├────────────────────────────────────────────────────────┤
│  lqMemorySourceDelegate (Inline Editörler & LookUp)    │
├────────────────────────────────────────────────────────┤
│  Column Design Manager (Kolon Genişlik/Gizlilik/Sıra)  │
└────────────────────────────────────────────────────────┘
```

### Toya ERP'ye Kazandırılacak Özellikler:

1. **Entegre Sütun Filtre Satırı (`lqTableFilter`):**
   - Tablo başlığının hemen altına bağlanan, sütun genişlikleriyle otomatik senkronize olan filtre satırı.
   - Sol üst köşe göstergesinde filtre durumunun renkli bildirilmesi (`_set_topLeftWidget_backgroundColor`).
2. **Excel / Pano Entegrasyonu (`copyToTable`):**
   - Excel'den kopyalanan hücrelerin ve çoklu satırların doğrudan gride yapıştırılması (`setAllowPasteFromExcel`, `copyToTable_setCell`).
   - Tek tıkla açık formattaki Excel dışa aktarımı (`exportToExcel`).
3. **Akıllı Hücre Odaklama ve Hızlı Veri Girişi:**
   - Enter tuşuna basıldığında sonraki düzenlenebilir hücreye otomatik geçiş (`mayFocusNextResult`).
   - Fiyat, iskonto, miktar alanlarında otomatik hesaplama tetiklenmesi.
4. **Kullanıcı Kolon Tasarım Profilleri (`colDesign`):**
   - Sütun sıralaması, görünürlüğü ve genişliklerinin kullanıcı bazında profil olarak kaydedilmesi ve geri yüklenmesi.

---

## 3. Ekran Geliştirme Yol Haritası

1. **Aşama 1: Hareket Kalemleri & DBGrid Güçlendirmesi**
   - `HareketKalemleriWidget` ve `DataGrid` üzerine hızlı sütun filtresi eklenmesi.
   - Pano / Excel'den satır yapıştırma yeteneğinin kazandırılması.
2. **Aşama 2: Master Evrak & Fiş Formlarının Standardizasyonu**
   - `scf2201.gui` referans alınarak fatura, irsaliye, sipariş ve teklif ekranlarının ortak alt yapı üzerinden birleştirilmesi.
   - Dinamik alan ve ek masraf/iskonto sekme yapısının güçlendirilmesi.
3. **Aşama 3: Kart ve Liste Ekranları (`scf1100`, `scf1301`)**
   - Stok kartı ve Cari kart detay formlarının sekme ve alan yapısının DIA standartlarına uygun olarak zenginleştirilmesi.
4. **Aşama 4: DIA Çift Yönlü Sync Optimizasyonu**
   - `lqscf`, `lqmuh`, `lqefa` şemaları üzerinden DIA API alan eşleştirmelerinin doğrulanması.
