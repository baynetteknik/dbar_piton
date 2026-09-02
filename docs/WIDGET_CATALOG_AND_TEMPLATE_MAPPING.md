# 📑 TOYA ERP - Widget Kataloğu & Ekran Şablonları Haritası (Master Inventory)

Bu doküman, TOYA ERP sistemindeki tüm kullanıcı arayüzü (UI) bileşenlerini, yerleşim bölgelerini, teknik kodlarını, görsel rapor tasarımcısı araç paletini ve işlevlerini listeleyen ana envanterdir.

---

## 📑 1. ŞABLON 1: Ana Ekran / Dashboard Şablonu (`tpl.dash.001`)

| Şablon Adı | Bölge (Zone) | Alt Konum | Widget / Bileşen Adı | Teknik Kod / ID | Sınıf (Class) | Ne İşe Yarar? (İşlev Açıklaması) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Ana Ekran** | `zone.header` | Sol | Firma Logosu & Başlık | `pan.nav.logo` | `QLabel` | Kurumsal firma logosunu ve ERP sistem başlığını gösterir. |
| **Ana Ekran** | `zone.header` | Orta-Sağ | Global Arama Çubuğu | `cmp.top.search` | `QLineEdit` | Modüller, menüler ve kayıtlar arasında hızlı arama yapar (`Ctrl+K`). |
| **Ana Ekran** | `zone.header` | Sağ | Kullanıcı Bilgisi | `sys.usr.001` | `QLabel` | Aktif oturum açan kullanıcının e-posta, rol ve profil bilgilerini gösterir. |
| **Ana Ekran** | `zone.header` | Sağ | Şirket / Şube Seçici | `tan.cmp.001` | `QComboBox` | Çoklu şirket ve şubeler arasında anında geçiş yapılmasını sağlar. |
| **Ana Ekran** | `zone.header` | Sağ | Mimari Kodlar Butonu | `sys.cfg.hints` | `QPushButton` | Ekrandaki teknik buton/panel kodlarını (`act.*`, `cmp.*`) açıp kapatır. |
| **Ana Ekran** | `zone.header` | Sağ | Grid & Tema Ayarları | `cmp.top.theme` | `QPushButton` | Tablo satır yükseklikleri, font boyutu ve renk temasını ayarlar. |
| **Ana Ekran** | `zone.header` | En Sağ | Yardım Butonu | `cmp.top.help` | `QPushButton` | Kullanıcı kılavuzu ve yardım dökümantasyonunu açar. |
| **Ana Ekran** | `zone.body` | Sol Sütun | Favori İşlemler | `widget_favorite_actions`| `FavoriteActionsWidget` | Kullanıcının sık kullandığı ekranları ve hızlı kısayol butonlarını listeler. |
| **Ana Ekran** | `zone.body` | Sol Sütun | Hızlı Kısayol Kartları | `cmp.quick_actions` | `QuickActionCard` | "Yeni Teklif", "Cari Ekle", "Stok Sayımı" gibi tek tıkla işlem butonları. |
| **Ana Ekran** | `zone.body` | Sağ Sütun | Ana Menü Modül Gridi | `widget_menu_grid` | `MenuGridWidget` | Büyük kurumsal ikonlu modül kartları (Cari, Stok, Teklif, Fatura) gösterir. |
| **Ana Ekran** | `zone.body` | Sağ Sütun | İşlem Günlüğü Erişimi | `act.sys.logs` | `QPushButton` | Son yapılan işlemleri ve sistem işlem günlüklerini sekmede açar. |
| **Ana Ekran** | `zone.footer` | Footer Üstü | Hızlı Erişim & Durum Bandı| `widget_quick_tiles` | `QuickTilesBarWidget` | Açılır/kapanır mini durum kartları (Açık Teklifler, Kritik Stok vb.). |
| **Ana Ekran** | `zone.footer` | Ana Footer | Açılır Kategori Menüleri| `pan.nav.footer` | `FooterMenuButton` | Hover/tıklama ile yukarı açılan zengin alt menü butonları. |
| **Ana Ekran** | `zone.footer` | Sağ Footer | Sistem Durum Bilgisi | `lbl_status_info` | `QLabel` | DB bağlantı durumu, aktif şirket ve yanıt süresini gösterir. |

---

## 📑 2. ŞABLON 2: Modül Liste & Yönetim Şablonu (`tpl.list.001`)

*Örnek Ekranlar: Teklif Listesi (`scr_quotations`), Cari Listesi (`scr_cari_list`), Stok Listesi (`scr_stok_list`), Fatura Listesi (`scr_fis_list`)*

| Şablon Adı | Bölge (Zone) | Alt Konum | Widget / Bileşen Adı | Teknik Kod / ID | Sınıf (Class) | Ne İşe Yarar? (İşlev Açıklaması) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Liste Şablonu** | `zone.header` | Üst Bar | Global Kurumsal Header | `pan.nav.header` | `QWidget` | Ana Panel ile birebir aynı üst arama, kullanıcı ve şube barı. |
| **Liste Şablonu** | `zone.sidebar.left` | 1. Grup (Üst)| CRUD Eylem Butonları | `widget_crud_actions` | `ActionBarWidget` | Yeni Ekle (`F2`), Düzenle (`F3`), Sil (`F5`), Kopyala, Dönüştür, Yenile. |
| **Liste Şablonu** | `zone.sidebar.left` | 2. Grup (Alt)| Görünüm Profilleri | `widget_view_profiles`| `ViewProfileWidget` | Kullanıcıya özel tablo sütun dizilimlerini kaydetme ve geri yükleme. |
| **Liste Şablonu** | `zone.body` | Üst/Orta | Akıllı Filtrelenebilir Tablo| `cmp.table_view` | `FilterableTableView` | Sütun başlığı filtreleri, sıralama, çoklu seçim kutusu ve veri gridi. |
| **Liste Şablonu** | `zone.body` | Alt | Bağımsız Sayfalama Barı| `cmp.pagination` | `PaginationWidget` | Sayfa başına kayıt adedi (25, 50, 100) ve sayfa geçiş butonları. |
| **Liste Şablonu** | `zone.sidebar.right`| 1. Grup (Üst)| Arama ve Durum Filtreleri| `sec.filters` | `FilterWidget` | Metin araması, tarih aralıkları ve Durum (Taslak, Onaylı vb.) filtreleri. |
| **Liste Şablonu** | `zone.sidebar.right`| 2. Grup (Alt)| Dışa Aktarım & Baskı | `widget_export_actions`| `ExportWidget` | Excel (`F9`), PDF, CSV aktarımı ve doğrudan yazdırma butonları. |
| **Liste Şablonu** | `zone.footer` | Alt Bar | Hızlı Alt Menü & Durum | `pan.nav.footer` | `QFrame` | Ana ekranla senkron durum ve kısayol navigasyonu. |

---

## 📑 3. ŞABLON 3: Fiş / Evrak Detay Form Şablonu (`tpl.trans.001`)

*Örnek Ekranlar: Teklif Girişi, Sipariş Girişi, Fatura Girişi, İrsaliye Formu*

| Şablon Adı | Bölge (Zone) | Alt Konum | Widget / Bileşen Adı | Teknik Kod / ID | Sınıf (Class) | Ne İşe Yarar? (İşlev Açıklaması) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Evrak Detay** | `zone.form.top` | Sol Blok | Cari Hesap Künyesi Kartı | `widget_cari_kunyesi` | `CariHesapKunyesiWidget` | Cari kodu, ünvanı, vergi no/dairesi, bakiye ve iletişim bilgileri. |
| **Evrak Detay** | `zone.form.top` | Orta Blok | Belge & Vade Parametreleri| `widget_belge_vade` | `BelgeVadeDetaylariWidget` | Belge No, Tarih, Vade Tarihi, Döviz Cinsi, Kur ve Ödeme Şartları. |
| **Evrak Detay** | `zone.form.top` | Sağ Blok | Hareket & Fiyat Ayarları | `widget_hareket_ayarlari`| `HareketAyarlariWidget` | Fiyat listesi, KDV Dahil/Hariç, İskonto Tipi ve Plasiyer seçimi. |
| **Evrak Detay** | `zone.body` | Tam Genişlik| Satır Kalemleri Gridi | `widget_hareket_kalemleri`| `HareketKalemleriDbGridWidget`| Stok/Hizmet seçimi, miktar, birim fiyat, satır iskontosu, KDV ve tutar gridi. |
| **Evrak Detay** | `zone.form.bottom` | Sol Blok | Alt İskonto & Masraflar | `widget_alt_iskonto_masraflar`| `AltIskontoMasraflarWidget`| Genel dip iskontoları (1/2/3), masraf/navlun ve tevkifat oranları. |
| **Evrak Detay** | `zone.form.bottom` | Orta Blok | Belge Notları & IBAN | `widget_belge_notlari` | `BelgeNotlariWidget` | Evrak dip açıklamaları, banka IBAN bilgisi ve teslimat koşulları. |
| **Evrak Detay** | `zone.form.bottom` | Sağ Blok | Finans & Dip Toplam Kartı| `widget_finans` | `FinansWidget` | Ara Toplam, İskonto Tutarı, KDV Matrahı ve Vurgulu Genel Toplam. |
| **Evrak Detay** | `zone.actions` | Eylem Barı | Form Aksiyon Butonları | `act.doc.group` | `QHBoxLayout` | Kaydet (`F2`), Vazgeç (`Esc`), Satır Ekle (`Ins`), Satır Sil (`Del`), Yazdır (`F9`). |

---

## 📑 4. ŞABLON 4: Tanım & Kart Form Şablonu (`tpl.card.001`)

*Örnek Ekranlar: Cari Hesap Kartı (`tan.car.001`), Stok Kartı (`tan.stk.001`), Depo Tanımı, Banka Hesabı Tanımı*

| Şablon Adı | Bölge (Zone) | Alt Konum | Widget / Bileşen Adı | Teknik Kod / ID | Sınıf (Class) | Ne İşe Yarar? (İşlev Açıklaması) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tanım Kartı** | `zone.header` | Üst Bar | Kart Başlık & Durum Kartı| `pan.card.header` | `QFrame` | Kart Kodu, Ünvan/Ad ve Aktif/Pasif rozetini vurgulu gösterir. |
| **Tanım Kartı** | `zone.body` | Sol Üst | Profil & Görsel Paneli | `pan.card.avatar` | `QLabel` | Cari logosu, personel vesikalığı veya ürün fotoğrafı yükleme alanı. |
| **Tanım Kartı** | `zone.body` | Merkez | Çoklu Sekme Yöneticisi | `tabs.card.main` | `QTabWidget` | Genel Bilgiler, İletişim, Finans/Risk, Muhasebe sekmelerini barındırır. |
| **Tanım Kartı** | `zone.tab.1` | Form Bloğu 1| Temel Kimlik Bilgileri | `grp.card.identity` | `QGroupBox` | Kod, Ticari Ünvan, Kısa Ad, Grup/Kategori hiyerarşik seçimi. |
| **Tanım Kartı** | `zone.tab.1` | Form Bloğu 2| Vergi & Resmi Bilgiler | `grp.card.tax` | `QGroupBox` | Vergi Dairesi, Vergi/TCKN No, Mersis No, Ticaret Sicil No. |
| **Tanım Kartı** | `zone.tab.2` | Form Bloğu | İletişim & Adres Detay | `grp.card.contact` | `QGroupBox` | İl, İlçe, Açık Adres, Telefon, E-posta, Web ve Yetkili Kişiler. |
| **Tanım Kartı** | `zone.tab.3` | Form Bloğu | Finans, Risk & Vade | `grp.card.finance` | `QGroupBox` | Risk Limiti, Açık Hesap Limiti, Varsayılan Vade Günü, Fiyat Listesi. |
| **Tanım Kartı** | `zone.tab.4` | Form Bloğu | Muhasebe & Kod Bağlantıları| `grp.card.gl_codes` | `QGroupBox` | Muhasebe Entegrasyon Hesap Kodları (Alıcılar, Satıcılar, İskonto). |
| **Tanım Kartı** | `zone.footer` | Sol Blok | Hızlı Ekstre & Hareketler | `act.card.extra` | `QPushButton` | Kartla ilişkili ekstre veya geçmiş hareket pencerelerini doğrudan açar. |
| **Tanım Kartı** | `zone.footer` | Sağ Blok | Kaydet & Vazgeç Butonları | `act.card.save_group` | `QHBoxLayout` | Kaydet (`F2`), Vazgeç (`Esc`), Yeni Tanım Aç (`Ctrl+N`). |

---

## 📑 5. ŞABLON 5: Raporlama & Analiz Şablonu (`tpl.report.001`)

*Örnek Ekranlar: Cari Bakiye & Yaşlandırma Raporu, Karlılık Analizi, KDV İcmali, Depo Stok Durum Raporu*

| Şablon Adı | Bölge (Zone) | Alt Konum | Widget / Bileşen Adı | Teknik Kod / ID | Sınıf (Class) | Ne İşe Yarar? (İşlev Açıklaması) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Rapor Ekranı**| `zone.sidebar.left`| Üst Blok | Rapor Kriter Filtreleri | `sec.report_filters`| `CollapsibleSection` | Başlangıç/Bitiş Tarihi, Cari/Stok Seçimi, Depo/Şube Çoklu Seçim. |
| **Rapor Ekranı**| `zone.sidebar.left`| Alt Blok | Rapor Görünüm Ayarları | `sec.report_views` | `CollapsibleSection` | Gruplama Kriteri (Aylık/Haftalık), Kırılımlar, Sıfır Bakiyeleri Gizle. |
| **Rapor Ekranı**| `zone.sidebar.left`| Dip | Filtrele / Yenile Butonu | `act.report.execute`| `QPushButton` | Belirlenen kriterlere göre rapor sorgusunu arka planda çalıştırır (`F5`). |
| **Rapor Ekranı**| `zone.body` | Üst Blok | Özet KPI & Grafik Paneli | `cmp.report.chart` | `QChartWidget` | Rapor sonucunun trend eğrisini, pasta dağılımını veya KPI kutularını çizer. |
| **Rapor Ekranı**| `zone.body` | Orta/Alt | Detay Veri & Pivot Gridi | `cmp.report.grid` | `FilterableTableView` | Gruplanabilir, ara toplamlı, tıklanabilir detay veri gridi. |
| **Rapor Ekranı**| `zone.footer` | Sol | Genel Dip Toplam Özeti | `lbl.report.summary` | `QLabel` | Toplam Kayıt Adedi, Genel Ciro, Net Bakiye, KDV Toplamı özet göstergesi. |
| **Rapor Ekranı**| `zone.footer` | Sağ | Dışa Aktar & Yazdır | `act.report.export` | `QHBoxLayout` | Excel (`XLSX`), Vektörel PDF, Form Tasarımcısı ile Baskı (`F9`). |

---

## 📑 6. ŞABLON 6: Baskı & Rapor Form Şablonu (`tpl.print.001`) - Bant Tabanlı Belge Tasarımcısı

*Örnek Çıktılar: Fatura Baskısı, Teklif Mektubu, İrsaliye, Kasa Tahsilat Makbuzu, Stok Sayım Fişi, Barkod Etiketi*

### 6.1. Bant (Band) Mimarisi ve Baskı Davranışları

| Şablon Adı | Bölge (Bant / Band) | Tip | Sürükle-Bırak Öğeleri | Veri Bağlama Örnekleri (Data-Binding) | Baskı Davranışı |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baskı Formu** | `band_overlay` | Arka Plan Filigran | Matbu Evrak Şablonu, Taslak/İptal Filigranı | `{sistem.filigran_metni}` | Sayfanın arkasında sabit durur; akışı etkilemez. |
| **Baskı Formu** | `band_report_title` | Rapor Başlığı | Kurumsal Kapak Başlığı, Şirket Künyesi | `{sirket.unvan}`, `{belge.baslik}` | Yalnızca 1. sayfanın en üstünde tek sefer basılır. |
| **Baskı Formu** | `band_page_header` | Sayfa Üst Bilgisi | Logo, Belge No, Belge Tarihi | `{sirket.logo}`, `{belge.no}`, `{belge.tarih}` | Her sayfanın en üstünde tekrarlanır. |
| **Baskı Formu** | `band_header_group` | Müşteri Künyesi | Sn. Alıcı Ünvanı, Adres, Vergi Dairesi, Vergi No | `{cari.unvan}`, `{cari.adres}`, `{cari.vergi_no}` | İlk sayfa veya grup başında basılır. |
| **Baskı Formu** | `band_group_header` | Grup Başlığı | Grup / KDV / Depo Adı | `{kalem.kdv_orani}`, `{kalem.depo_adi}` | Belirlenen alan değiştikçe grup başında basılır. |
| **Baskı Formu** | `band_column_header`| Kolon Başlığı | Sıra, Stok Kodu, Açıklama, Miktar, Fiyat, KDV, Tutar | Sabit Başlık Metinleri (`[T]`) | Tablo kalemlerinin üzerinde tekrarlanır. |
| **Baskı Formu** | `band_detail_data` | Veri / Satır Bandı | Kalem Satırları (Kod, Açıklama, Miktar, Fiyat, Tutar) | `{kalem.stok_adi}`, `{kalem.miktar}`, `{kalem.birim_fiyat}`, `{kalem.satir_tutari}` | Satır adedi kadar basılır; sayfa bitiminde sonraki sayfaya taşar. |
| **Baskı Formu** | `band_child` | Alt / Bağlı Bant | Ürün Açıklaması, Seri No/Lot Listesi, Teknik Notlar | `{kalem.aciklama}`, `{kalem.seri_no_listesi}` | Satıra ek veri varsa detay altına dinamik açılır (`can_shrink`). |
| **Baskı Formu** | `band_group_footer` | Grup / Ara Toplam | KDV Grubu Bazlı Ara Toplamlar, Grup İskontosu | `[SUM(kalem.satir_tutari)]`, `{grup.kdv_tutari}` | Grup bitiminde ara toplam basar. |
| **Baskı Formu** | `band_column_footer`| Nakli Yekûn | Sayfadan Sayfaya Devreden Ara Toplam | `[SUM_PAGE(kalem.satir_tutari)]` | Sayfa sonlarında devreden toplam basar. |
| **Baskı Formu** | `band_report_summary`| Rapor / Belge Özeti | Ara Toplam, KDV Tutarı, Genel Toplam, Yazıyla Tutar, IBAN | `{finans.ara_toplam}`, `{finans.genel_toplam}`, `[YAZIYLA(finans.genel_toplam, 'TL')]` | Belgenin en son sayfasında tablo bitimine basılır (`keep_together`). |
| **Baskı Formu** | `band_page_footer` | Sayfa Altı | Kaşe / İmza Kutuları, Belge Dip Notu, Sayfa No | `[Page#] / [TotalPages#]`, `{belge.notlar}` | Her sayfanın en dip kenarında basılır. |

### 6.2. Görsel Tasarımcı Araç Kutusu (Toolbox Bileşenleri)

Görsel tasarımcının sol panelindeki araç kutusundan sürüklenip bantlara bırakılan nesneler:

| Araç Kodu | Görsel Nesne Adı | Sınıf (Class) | Nitelikler & Parametreler | Ne İşe Yarar? |
| :--- | :--- | :--- | :--- | :--- |
| `cmp.rpt.label` | Sabit Metin Kutusu | `ReportLabelItem` | `text`, font, renk, border | Değişmeyen başlık, sabit etiket veya uyarı metni yazar. |
| `cmp.rpt.field` | Dinamik Veri Alanı | `ReportFieldItem` | `field`, format (`currency`, `date`), `can_grow` | Veritabanından gelen canlı veriyi formatlayarak basar. |
| `cmp.rpt.image` | Resim & Logo | `ReportImageItem` | `field`, `file_path`, `aspect_ratio` | Şirket logosu, kaşe, yetkili imzası veya ürün resmi basar. |
| `cmp.rpt.barcode` | 1D/2D Barkod & QR | `ReportBarcodeItem`| `format` (`qrcode`, `code128`, `ean13`), `field` | GİB e-Belge karekodunu veya ürün/belge barkodunu üretir. |
| `cmp.rpt.line` | Çizgi & Ayırıcı | `ReportLineItem` | `orientation`, `thickness`, `style`, `color` | Tablolar arasına yatay/dikey ayırıcı çizgi çeker. |
| `cmp.rpt.box` | Kutu & Çerçeve | `ReportBoxItem` | `border_color`, `fill_color`, `corner_radius` | İmza kutusu, vurgulu dip toplam alanı veya çerçeve çizer. |
| `cmp.rpt.richtext`| Zengin Metin (HTML) | `ReportRichTextItem`| `html_content`, `can_grow: true` | Teklif sözleşme maddeleri ve kalın/renkli uzun metinleri basar. |
| `cmp.rpt.subreport`| Alt Rapor Bloğu | `ReportSubReportItem`| `template_ref`, `dataset_ref` | Fatura altında bağımsız ikinci bir tablo/icmal basar. |
| `cmp.rpt.system` | Sistem Değişkeni | `ReportSystemVarItem`| `var_type` (`page_no`, `print_date`, `user`) | Sayfa numarası, baskı saati ve kullanıcı bilgisini basar. |

---

## 📑 7. Ekran Tasarım Modu İçin UI Bileşen Kataloğu (UI Screen Designer Palette)

ERP masaüstü ekranı tasarlanırken sol panelden sürüklenip forma eklenen standart PyQt bileşenleri:

| Bileşen Kodu | Bileşen Adı | Sınıf (Class) | Ne İşe Yarar? |
| :--- | :--- | :--- | :--- |
| `cmp.form.lookup` | Akıllı Arama & Seçici | `DbLookupComboBox` | Cari veya Stok seçimi için filtreli açılır kutu (`F10` destekli). |
| `cmp.form.currency`| Para & Tutar Girişi | `CurrencyLineEdit` | Döviz simgeli, otomatik binlik noktalı milimetrik sayı giriş alanı. |
| `cmp.form.date_range`| Tarih Aralığı Seçici | `DateRangePicker` | Başlangıç ve Bitiş tarihlerini takvim üzerinden tek tıkla seçtirir. |
| `cmp.form.badge` | Durum Rozeti | `StatusBadgeWidget` | Taslak (Mavi), Onaylı (Yeşil), İptal (Kırmızı) gibi durum rozeti. |
| `cmp.form.tabs` | Sekmeli Panel | `QTabWidget` | Büyük formları alt sekmelere bölerek dikey alanı verimli yönetir. |
| `cmp.form.section`| Açılır/Kapanır Akordiyon| `CollapsibleSection` | Yan panellerde dikey açılıp kapanabilir akordiyon grubu oluşturur. |
| `cmp.form.grid` | Veri & Kalem Gridi | `HareketKalemleriDbGridWidget`| Excel tarzı klavye navigasyonlu satır hareket gridi. |
