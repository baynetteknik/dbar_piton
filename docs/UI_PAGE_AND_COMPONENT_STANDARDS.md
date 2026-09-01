# 📐 TOYA ERP - UI Sayfa Şablonları & Bileşen İsimlendirme Standartları (Master Specification)

Bu doküman, **TOYA ERP** masaüstü arayüzünde kullanılan tüm ekranların, yan panellerin (sidebar), form alanlarının ve modüler bileşenlerin mimari standartlarını ve isimlendirme kurallarını belirler.

Gelecekte yeni bir ekran veya modül geliştirilirken bu standartlara uyulacak; kullanıcı asistana tek satırda şablon ve bileşen isimlerini belirterek sayfa ürettirebilecektir.

---

## 📑 İÇİNDEKİLER
1. [🏗️ Temel Mimari Prensipler](#1-temel-mimari-prensipler)
2. [🗺️ Ekran & Modül Kodlama Standardı (Module Code Taxonomy)](#2-ekran--modül-kodlama-standardı)
3. [📄 5 Ana Sayfa Şablonu (Master Page Templates)](#3-5-ana-sayfa-şablonu)
   - [3.1. `tpl.list.001` - Liste & Yönetim Sayfası (3-Panelli DIA Düzeni)](#31-tpllist001---liste--yönetim-sayfası)
   - [3.2. `tpl.trans.001` - İşlem / Belge & Evrak Detay Sayfası](#32-tpltrans001---işlem--belge--evrak-detay-sayfası)
   - [3.3. `tpl.card.001` - Tanım & Kart Form Sayfası](#33-tplcard001---tanım--kart-form-sayfası)
   - [3.4. `tpl.report.001` - Raporlama & Analiz Sayfası](#34-tplreport001---raporlama--analiz-sayfası)
   - [3.5. `tpl.dash.001` - Dashboard & Gösterge Paneli](#35-tpldash001---dashboard--gösterge-paneli)
4. [🧩 Ekran Bölgeleri İsimlendirmesi (Zone Taxonomy)](#4-ekran-bölgeleri-isimlendirmesi)
5. [📦 Modüler Sidebar Akordiyon Bileşenleri (Reusable Sidebar Sections)](#5-modüler-sidebar-akordiyon-bileşenleri)
6. [📋 Modül & Ekran Kod Tablosu (Registry)](#6-modül--ekran-kod-tablosu)
7. [💬 Yapay Zeka Hızlı İstek Formatı (AI Request DSL)](#7-yapay-zeka-hızlı-istek-formatı)

---

## 1. 🏗️ Temel Mimari Prensipler

1. **Dikey Alan Verimliliği:** Tüm çalışma sekmelerinde gereksiz şeritler ve hantal başlıklar kaldırılmış, üst modül menüsü sekmelerde otomatik gizlenerek maksimum dikey veri alanı sağlanmıştır.
2. **Edge-Triggered (3-Panel) Esnekliği:** Sol ve sağ paneller gerektiğinde açılıp kapanabilir (`EdgeTriggeredPanel`), iğnelenebilir (`📌 Sabitle`) veya daraltılabilir (`❌ Gizle`).
3. **Standart Akordiyon Düzeni (`CollapsibleSection`):** Yan paneller içindeki gruplar dikey akordiyon şeklinde açılır/kapanır.
   - **Sol Sidebar Kuralı:** En üstte **İşlemler (`sec.actions`)**, hemen altında **Görünüm Profilleri (`sec.profiles`)** yer alır.
   - **Sağ Sidebar Kuralı:** En üstte **Hızlı Filtreler (`sec.filters`)**, altında **Dosya & Aktarım (`sec.sync_export`)** yer alır.
4. **DbGrid Filtre Sıfırlama Kuralı:** Kolon arama satırının (Filter Row) en solundaki Seçim hücresinde tek tıkla tüm filtreleri temizleyen **`🗑️` butonu** bulunur.

---

## 2. 🗺️ Ekran & Modül Kodlama Standardı

Tüm ekran ve bileşenler standart 3 parçalı nokta notasyonu ile adlandırılır:

$$\text{Format: } \mathbf{[kategori].[modül].[sıra\_no]}$$

### Kategori Önekleri:
- `isl.` $\rightarrow$ **İşlem & Hareket Ekranları** (Teklif, Sipariş, Fatura, İrsaliye, Kasa/Banka Fişi)
- `tan.` $\rightarrow$ **Tanım & Kart Ekranları** (Cari Kart, Stok Kartı, Depo, Banka Hesabı, Masraf)
- `rep.` $\rightarrow$ $\mathbf{Raporlar}$ (Ekstre, Yaşlandırma, KDV İcmali, Karlılık Analizi)
- `set.` $\rightarrow$ **Ayarlar & Sistem** (Kullanıcılar, Şirket Ayarları, Döviz Kurları, Yedekleme)
- `tpl.` $\rightarrow$ **Sayfa Şablonları (Templates)**
- `cmp.` $\rightarrow$ **Yeniden Kullanılabilir UI Bileşenleri (Components)**
- `act.` $\rightarrow$ **Buton & İşlem Aksiyonları (Actions)**
- `sec.` $\rightarrow$ **Sidebar Akordiyon Bölümleri (Sections)**
- `zone.` $\rightarrow$ **Ekran Yerleşim Bölgeleri (Zones)**

---

## 3. 📄 5 Ana Sayfa Şablonu

---

### 3.1. `tpl.list.001` - Liste & Yönetim Sayfası (3-Panelli DIA Düzeni)

Veri kayıtlarının listelendiği, filtrelendiği, sıralandığı ve toplu yönetildiği ana ekran şablonudur.

```text
+-----------------------------------------------------------------------------------+
|  [zone.sidebar.left]  |         [zone.center / zone.body]         | [zone.sidebar.right]  |
|                       |                                           |                       |
| +-------------------+ | +---------------------------------------+ | +-------------------+ |
| | sec.actions       | | | [🗑️] [Kolon Filtresi 1] [Filtre 2]... | | | sec.filters       | |
| | - ➕ Yeni (F3)    | | +---------------------------------------+ | | - Arama Kutusu    | |
| | - ✏️ Değiştir (F4) | | | ID | Evrak No | Cari Adı | Tutar | Dur | | | - Durum Seçimi   | |
| | - 📋 Kopyala      | | |----+----------+----------+-------+-----| | | - Tarih Aralığı   | |
| | - ❌ Sil (Del)    | | | 1  | TK-2026-1| ABC Ltd. | 15000 | Onay| | | - 🗑️ Temizle      | |
| | - 🔄 Dönüştür     | | | 2  | TK-2026-2| XYZ A.Ş. | 32000 | Tasl| | +-------------------+ |
| | - 🖨️ Yazdır (F9)  | | |                                       | |                       |
| | - 🚪 Kapat        | | +---------------------------------------+ | +-------------------+ |
| +-------------------+ | | [zone.footer]                         | | | sec.sync_export   | |
|                       | | [⏮️] [⬅️] Sayfa 1/1 [➡️] [⏭️]   Adet:[25] | | | - 📤 Excel Dışa   | |
| +-------------------+ | +---------------------------------------+ | | - 📊 Detay Rapor  | |
| | sec.profiles      | |                                           | +-------------------+ |
| | - Aktif Profil    | |                                           |                       |
| | - 💾 Kaydet       | |                                           |                       |
| | - ⚙️ Sütunlar     | |                                           |                       |
| +-------------------+ |                                           |                       |
+-----------------------------------------------------------------------------------+
```

#### Bileşen Yerleşimi:
- **`zone.sidebar.left` (Sol Çekmece):**
  1. `sec.actions` (İşlem Butonları - **Üstte**)
  2. `sec.profiles` (Görünüm Profilleri & Sütun Yöneticisi - **Altta**)
- **`zone.center` (Orta Alan):**
  - `FilterableTableView` (Hızlı kolon arama + Sol baş `🗑️` filtre sıfırlama butonu)
- **`zone.footer` (Dip Alan):**
  - Sayfalama Barı (`⏮️`, `⬅️`, `Sayfa X/Y`, `➡️`, `⏭️`, `Sayfa Başı Kayıt Adedi`)
- **`zone.sidebar.right` (Sağ Çekmece):**
  1. `sec.filters` (Hızlı filtre kriterleri)
  2. `sec.sync_export` (Excel dışa aktarım & Raporlar)

---

### 3.2. `tpl.trans.001` - İşlem / Belge & Evrak Detay Sayfası

Teklif, Sipariş, İrsaliye, Satış/Alış Faturası, Cari Mahsup, Stok/Kasa/Banka Fişi gibi finansal/ticari hareket evraklarının giriş ve düzenleme şablonudur.

```text
+-----------------------------------------------------------------------------------+
| [zone.header]  📄 Belge No: [TK-2026-001]   Tarih: [22.08.2026]   Durum: [🔵 Taslak] |
|                Cari: [ABC TEKNOLOJİ LTD. ŞTİ.]   Depo: [Merkez]    Döviz: [USD / 36.50]|
+-----------------------------------------------------------------------------------+
| [zone.body] Satır Detayları & Kalemler Grid                                       |
| +----+---------+----------------------+-------+------+----------+--------+------+ |
| | No | Barkod  | Stok / Hizmet Adı    | Miktar| Birim| B. Fiyat | İsk %  | KDV% | |
| +----+---------+----------------------+-------+------+----------+--------+------+ |
| | 1  | 8690001 | 4K Güvenlik Kamerası | 8     | Adet | 150.00   | %10.00 | %20  | |
| | 2  | 8690002 | 16 Kanal NVR Kayıt   | 1     | Adet | 650.00   | %5.00  | %20  | |
| +----+---------+----------------------+-------+------+----------+--------+------+ |
| [+ Yeni Kalem Ekle (INS)]  [- Satır Sil (DEL)]  [📋 Seri/Lot]  [📝 Kalem Notu]    |
+-----------------------------------------------------------------------------------+
| [zone.footer / zone.summary] Evrak Dip Toplamları ve Butonlar                     |
| [📝 Fatura Notları & Banka IBAN]                Ara Toplam:      1,730.00 USD     |
| [🖨️ Yazdır / Önizleme]                          İskonto Tutarı:    152.50 USD     |
| [🔄 Siparişe/Faturaya Dönüştür]                 KDV Matrahı:     1,577.50 USD     |
|                                                 KDV Tutarı (%20):  315.50 USD     |
| [💾 KAYDET & ONAYLA (F2)]  [❌ VAZGEÇ (ESC)]    GENEL TOPLAM:    1,893.00 USD     |
+-----------------------------------------------------------------------------------+
```

#### Desteklenen Evrak Alt Türleri:
- `isl.quo.001` $\rightarrow$ Satış Teklifi / Alınan Teklif
- `isl.ord.001` $\rightarrow$ Alınan Sipariş / Verilen Sipariş
- `isl.way.001` $\rightarrow$ Satış İrsaliyesi / Alış İrsaliyesi
- `isl.inv.001` $\rightarrow$ Satış Faturası / Alış Faturası / İade / Tevkifatlı Fatura
- `isl.car.001` $\rightarrow$ Cari Virman / Mahsup Fişi / Borç-Alacak Dekontu
- `isl.stk.001` $\rightarrow$ Stok Giriş-Çıkış Fişi / Depolar Arası Transfer / Sayım Fişi
- `isl.bnk.001` $\rightarrow$ Banka Gelen/Giden Havale / EFT / POS Tahsilat
- `isl.chk.001` $\rightarrow$ Müşteri Çeki / Kendi Çekimiz / Senet Giriş-Çıkış
- `isl.csh.001` $\rightarrow$ Kasa Tahsilat / Kasa Tediye Fişi

---

### 3.3. `tpl.card.001` - Tanım & Kart Form Sayfası

Cari hesap, stok kartı, banka hesabı, kasa veya masraf merkezi gibi master veri tanım pencereleridir.

```text
+-----------------------------------------------------------------------------------+
| [zone.header]  👤 CARİ KART: [CR00012] AK İTHALAT İHRACAT A.Ş.   Durum: [🟢 Aktif] |
+-----------------------------------------------------------------------------------+
| [zone.body] Sekmeli Kart Gövdesi (QTabWidget)                                     |
| [ 1. Genel Bilgiler ] [ 2. İletişim & Adres ] [ 3. Finans & Risk ] [ 4. Muhasebe ] |
| +-------------------------------------------------------------------------------+ |
| | Ünvan:        [AK İTHALAT İHRACAT A.Ş.                                      ] | |
| | Kısa Ad / Kod:[AK ITHALAT            ]  Yetkili:   [Ahmet Yılmaz            ] | |
| | Grubu:        [ALICI / SATICI        ]  Ara Grubu: [TOPTAN                  ] | |
| | Vergi Dairesi:[Büyük Mükellefler     ]  Vergi No:  [1234567890              ] | |
| | Risk Limiti:  [150,000.00 TL         ]  Vade Günü: [45 Gün                  ] | |
| +-------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
| [zone.footer]                                                                     |
| [📊 Cari Hareketler] [📜 Ekstre Al]             [💾 Kaydet (F2)] [❌ Vazgeç (ESC)] |
+-----------------------------------------------------------------------------------+
```

---

### 3.4. `tpl.report.001` - Raporlama & Analiz Sayfası

Detaylı filtreleme kriterlerine göre tablo, pivot ve grafik formatında analiz sunan rapor ekranı şablonudur.

```text
+-----------------------------------------------------------------------------------+
| [zone.sidebar.left]  |              [zone.center / zone.body]                     |
| +------------------+ | +--------------------------------------------------------+ |
| | sec.filters      | | | 📈 ÖZET GRAFİK (Aylık Satış Trendi / Kategori Dağılımı)| |
| | - Başlangıç Tar. | | +--------------------------------------------------------+ |
| | - Bitiş Tarihi   | | | 📊 DETAY PİVOT TABLO                                   | |
| | - Cari / Grup    | | | Kategori | Kalem Sayısı | Brüt Satış | Net Kar | Marj%| |
| | - Depo / Şube    | | |----------+--------------+------------+---------+------| |
| | - Evrak Türü     | | | Güvenlik | 142 Adet     | 450,000 TL | 98,000  | %21.7| |
| | - [🔍 Filtrele]  | | | Donanım  | 88 Adet      | 310,000 TL | 62,000  | %20.0| |
| +------------------+ | +--------------------------------------------------------+ |
| | sec.sync_export  | | [zone.footer]                                            | |
| | - 📄 PDF Rapor   | | Toplam Kayıt: 230   Toplam Ciro: 760,000 TL              | |
| | - 📊 Excel Aktar | |                                                          | |
| +------------------+ +--------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

---

### 3.5. `tpl.dash.001` - Dashboard & Gösterge Paneli

Sistemin açılış ilk sekmesidir (`Tab 0`). Kalıcıdır ve kapatılamaz. KPI kartları, son işlemler ve modül kısayollarını sunar.

---

## 4. 🧩 Ekran Bölgeleri İsimlendirmesi (Zone Taxonomy)

Bir ekranda bileşenlerin yerleştiği 5 ana bölge:

| Bölge Kodu | Adı | Açıklama |
| :--- | :--- | :--- |
| `zone.header` | Üst Başlık & Evrak Bilgi Şeridi | Belge no, tarih, cari başlığı, durum rozeti |
| `zone.sidebar.left` | Sol Çekmece (Yan Panel) | `EdgeTriggeredPanel(side="left")` işlem butonları ve profiller |
| `zone.sidebar.right` | Sağ Çekmece (Yan Panel) | `EdgeTriggeredPanel(side="right")` arama filtreleri ve dışa aktarım |
| `zone.center` / `zone.body` | Orta Gövde / Tablo Alanı | `FilterableTableView`, satır kalemleri gridi veya form sekmeleri |
| `zone.footer` / `zone.summary` | Dip Barı & Toplamlar | Sayfalama, dip matrah ve toplam tutar kutuları, ana aksiyon butonları |

---

## 5. 📦 Modüler Sidebar Akordiyon Bileşenleri (Reusable Sections)

Yan panellere tek tek eklenebilen standart akordiyon (`CollapsibleSection`) blokları:

| Bileşen Kodu | Akordiyon Başlığı | İçerdiği Elemanlar | Standart Konum |
| :--- | :--- | :--- | :--- |
| `sec.actions` | `[MODÜL] İŞLEMLERİ` | ➕ Yeni (F3), ✏️ Değiştir (F4), 📋 Kopyala, ❌ Sil, 🔄 Dönüştür, 🖨️ Yazdır/Excel, 🚪 Kapat | `zone.sidebar.left` (1. Sıra - Üstte) |
| `sec.profiles` | `GÖRÜNÜM PROFİLLERİ` | Aktif Profil QComboBox, 💾 Kaydet, ⚙️ Sütunlar | `zone.sidebar.left` (2. Sıra - Altta) |
| `sec.filters` | `FİLTRELER` | QLineEdit Hızlı Ara, QComboBox Durum, QDateEdit Tarih, 🗑️ Filtreleri Temizle | `zone.sidebar.right` (1. Sıra) |
| `sec.sync_export` | `DOSYA & AKTARIM` | 📤 Excel Dışa Aktar, 📊 Rapor Al, 🔄 Entegrasyon Gönder | `zone.sidebar.right` (2. Sıra) |
| `sec.card_quickinfo` | `ÖZET BİLGİ KARTI` | Bakiye, Risk Limiti, Açık Sipariş Tutarı, Vadesi Geçen Tutar | `zone.sidebar.left` veya `right` |
| `sec.doc_summary` | `EVRAK TOPLAMLARI` | Ara Toplam, İskonto Tutarı, KDV Matrahları, Tevkifat, Genel Toplam | `zone.footer` |
| `sec.quick_product_select` | `HIZLI STOK SEÇİMİ` | Barkod okutma, Sık kullanılan ürünler listesi, Hızlı miktar girişi | `zone.sidebar.right` |

---

## 6. 📋 Modül & Ekran Kod Tablosu (Registry)

| Modül Kodu | Ekran / Menü Adı | Kullanılan Şablon | Sol Sidebar | Sağ Sidebar |
| :--- | :--- | :--- | :--- | :--- |
| `isl.quo.001` | **Teklif Yönetimi** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.ord.001` | **Sipariş Yönetimi** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.way.001` | **İrsaliye Yönetimi** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.inv.001` | **Fatura Yönetimi** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.car.001` | **Cari Fiş & Mahsup** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.stk.001` | **Stok Fişleri & Transfer** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.bnk.001` | **Banka Hareketleri** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.chk.001` | **Çek & Senet Bordroları** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `isl.csh.001` | **Kasa Hareketleri** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `tan.car.001` | **Müşteriler & Cariler** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `tan.stk.001` | **Stok & Hizmet Kartları** | `tpl.list.001` | `sec.actions` + `sec.profiles` | `sec.filters` + `sec.sync_export` |
| `rep.car.001` | **Cari Hesap Ekstresi** | `tpl.report.001` | `sec.filters` + `sec.sync_export` | - |
| `rep.sal.001` | **Satış & Karlılık Analizi** | `tpl.report.001` | `sec.filters` + `sec.sync_export` | - |

---

## 7. 💬 Yapay Zeka Hızlı İstek Formatı (AI Request DSL)

Yeni bir ekran, modül veya form eklemek istediğinizde bana aşağıdaki basit şablonlarla talimat verebilirsiniz:

### Örnek 1: Yeni Bir Liste Sayfası İsteği
> **Kullanıcı:**  
> *"Bana `[isl.inv.001]` kodlu **Fatura Yönetimi** sayfasını yap. Şablon: `tpl.list.001`. Sol sidebar: `sec.actions` (üstte), `sec.profiles` (altta). Sağ sidebar: `sec.filters`, `sec.sync_export`."*

### Örnek 2: Yeni Bir Evrak / Fiş Giriş Ekranı İsteği
> **Kullanıcı:**  
> *"Bana `[isl.way.001]` **İrsaliye Giriş Formu** yap. Şablon: `tpl.trans.001`. Sağ tarafa `sec.quick_product_select` koy, dip toplamda tevkifat ve iskonto alanları olsun."*

### Örnek 3: Yeni Bir Rapor Ekranı İsteği
> **Kullanıcı:**  
> *"Bana `[rep.stk.001]` **Depo Stok Durum Raporu** yap. Şablon: `tpl.report.001`. Sol panele depo ve kategori filtreleri, orta gövdeye pivot tablo ve stok trend grafiği koy."*

---

> **Son Güncelleme:** 22 Ağustos 2026  
> **Referans Standart Sürümü:** v2.1.0 (DIA + Akınsoft Hibrit Standardı)
