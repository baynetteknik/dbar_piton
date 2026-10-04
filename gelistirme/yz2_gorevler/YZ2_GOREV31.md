# YZ 2 — Görev 31: Genel Ayarlar karşılama panosunu Ana Panel'in Ana Menüleriyle GÖRSEL olarak birebir eşle

> **Girdi:** Kullanıcı: "yz2 ye Genel Ayarlar için görev verdim ve dizayn klasoru içindeki genel_ayarlar_ikon
> resmine göre yapmasını söyledim Ana Paneldeki Ana Menuler gibi olsun istiyorum ama Genel Ayarlara
> girdiğimde hala eski şekilde geliyor." Referans görsel: `dizayn/genel_ayarlar_ikon.jpg`.
> **Kural:** Commit yapma. Bu görev yalnızca GÖRSEL/STİL + varsayılan ekran akışı ile ilgili; veri modeline,
> servislere (`DonemService`, `SubeService`, `CompanyService` vb.) DOKUNMA.

## Önce oku: mevcut durum (ana oturum bu görev yazılırken az önce değiştirdi)

1. Genel Ayarlar'ın ikonlu "karşılama panosu" ZATEN VAR: `src/desktop/ui/widgets/settings_hub_widget.py`
   (`SettingsHubWidget`, `SettingsTileButton`). Beyaz kartlı, koyu lacivert yazılı, 3D gölgeli bir tasarım —
   Ana Panel'in mavi dolgu kartlarından (`MenuGridWidget`/`MenuGridButton`, aşağıda) GÖRSEL OLARAK FARKLI.
   Kullanıcının "hala eski şekilde geliyor" şikayetinin asıl sebebi muhtemelen BU görsel fark, artı madde 2.
2. Ana oturum az önce `GeneralSettingsScreen.__init__` içindeki varsayılan açılış panelini
   `switch_panel("firma_bilgileri")`'den `switch_panel("settings_hub")`'a çevirdi (`src/desktop/ui/settings.py`,
   `__init__` metodunun son satırı) — yani ekran artık DOĞRUDAN bu pano ile açılıyor, eskiden düz
   "Firma Bilgileri" listesiyle açılıyordu. **Bu satıra DOKUNMA, zaten doğru.**
3. Ana oturum ayrıca `MENU_STRUCTURE`'ı sadeleştirdi: "Şube Tanımları" / "Depo Tanımları" / "Çalışma Dönemi"
   artık Genel Ayarlar'da YOK (Firma Detayı ekranına taşındı), "Döviz & Kur" artık "FİNANS TANIMLARI"
   grubunda. `settings_hub_widget.py`'deki kart listesi (`_build_sections`) de buna göre güncellendi —
   bu üç kartı YENİDEN EKLEME, Döviz & Kur kartını "ŞİRKET TANIMLARI" bölümüne GERİ TAŞIMA.

## Asıl iş: görsel eşleme

### Referans (doğru davranan örnek): `src/desktop/ui/widgets/menu_grid_widget.py`
`MenuGridButton` — Ana Panel'deki büyük modül kartlarının gerçek kodu:
- Dolgu mavi arkaplan (`#2563eb`, hover `#1d4ed8`, pressed `#1e40af`), `border-radius: 12px`, `QFixedSize(130, 112)`.
- İkon: `TILE_ICONS` eşlemesi doluysa gerçek PNG (56x56 beyaz yuvarlak rozet içinde), boşsa 34pt emoji.
- Başlık: beyaz, kalın, 11px, `QLabel`, alt ortalanmış.
- Sağ tık desteği (`right_clicked` sinyali) — bu KISMI Genel Ayarlar kartlarına taşımana gerek yok, sadece
  görsel paleti (renk/boyut/gölge/tipografi) referans al.

`SettingsTileButton` (`settings_hub_widget.py`, şu an) bunun yerine beyaz kart + gri kenarlık kullanıyor.
Bunu `MenuGridButton` ile GÖRSEL OLARAK (renk paleti, boyut, köşe yarıçapı, gölge, başlık tipografisi) birebir
eşleşecek şekilde güncelle — iki seçenekten birini uygula (kendi takdirin):
  a) `SettingsTileButton`'ın `setStyleSheet`/font/boyut değerlerini `MenuGridButton` ile birebir aynı yap, VEYA
  b) `MenuGridButton`'ı import edip doğrudan kullan (varsa `target_module` yerine `panel_id` ile genişletilmiş
     bir kullanım; bu durumda `menu_grid_widget.py`'nin KENDİSİNİ bozmadan, geriye dönük uyumlu şekilde).
Alt başlık (`subtitle`, ör. "Firma & İletişim") Ana Panel'de yok — Genel Ayarlar'da kullanıcı onu istiyor mu
belirsiz; görsel referans `dizayn/genel_ayarlar_ikon.jpg`'de alt başlık YOK gibi duruyor, o yüzden ARA RENK/
boyut olarak MenuGridButton'a sadık kal, alt başlığı küçük/ikincil tut ya da kaldırmayı değerlendir — emin
değilsen alt başlığı KORU (bilgi kaybı olmasın) ama görsel ağırlığını azalt.

### Sol sidebar sadeleştirme (kullanıcının ikinci isteği)
Kullanıcı: "bu ana ikonlardan sonra solda sadece seçilen menu ile ilgili işlemler kalsın ama ilk menü de
istenir ise kullanılabilsin." Şu an `switch_panel("settings_hub")` zaten sol/sağ paneli KAPATIYOR
(`settings.py::switch_panel`, `panel_id == "settings_hub"` dalı) — panoda sidebar hiç görünmüyor, bu kısmı
muhtemelen hallediyor. Ama bir kart tıklanıp başka bir panele geçildiğinde (`hub_tab.navigate_requested` →
`switch_panel`) sol sidebar (`build_left_sidebar`) HÂLÂ TÜM `MENU_STRUCTURE` gruplarını (hepsi varsayılan
kapalı `CollapsibleSection`) gösteriyor — yalnızca seçilen kategoriye ait öğeleri göstermiyor. Kullanıcının
"soldaki menü kalabalıklaştı" şikayeti muhtemelen bunun devamı. Değerlendirip bir öneri uygula:
- Basit/düşük riskli seçenek: seçili panelin ait olduğu grup dışındaki `CollapsibleSection`'ları varsayılan
  gizli/`setVisible(False)` yap, yalnız aktif grup + "🏠 Ayarlar Panosu" düğmesi (zaten header'da var, her
  panelde görünür — geri dönüş yolu bu) görünür kalsın. `on_menu_clicked`/`switch_panel` içinde
  `self._group_sections` listesi (`(sec, title, code)` üçlüleri, `build_left_sidebar` içinde dolduruluyor)
  üzerinden hangi grup aktif paneli içeriyor tespit edilip diğerleri `setVisible(False)` yapılabilir.
- Bunu uygularsan `tests/test_settings_menu.py` içindeki sidebar/grup görünürlüğünü test eden testleri
  (ör. `_sistem(screen).is_expanded` gibi erişimler) ÇALIŞTIR, kırılırsa yeni davranışa göre ONAR (test
  silme, davranış hâlâ geçerliyse testi güncel gerçekliğe uydur).

## ÇAKIŞMA UYARISI — bu dosyalar ana oturumda AZ ÖNCE değişti, dikkatli ol
- `src/desktop/ui/settings.py`: `MENU_STRUCTURE`, `__init__`'teki `switch_panel("settings_hub")` satırı,
  `panel_builders`/`save_current_panel`/`_get_active_table`/`panel_table_map` içinden Şube/Depo/Dönem
  girişleri SİLİNDİ, `WarehouseDefinition` import'u kaldırıldı. Bu temizliği GERİ ALMA. Sol sidebar
  sadeleştirmesi için bu dosyayı düzenleyeceksen `build_left_sidebar`/`on_menu_clicked`/`switch_panel`
  metodlarına EKLEME yap, yukarıda silinen panel id'lerini GERİ EKLEME.
- `src/desktop/services/settings_menu.py`: `ITEM_CODES`'tan `sube_tanimlari`/`depo_tanimlari`/
  `calisma_donemi` silindi, `doviz_kur` kodu `sys.set.300` oldu (FİNANS TANIMLARI grubundaki yeni konumu).
  Bunlara dokunmana muhtemelen gerek yok; dokunursan `tests/test_settings_menu.py` içindeki
  `test_every_menu_has_a_unique_code_and_every_group_too` testini çalıştır.
- `src/desktop/ui/widgets/settings_hub_widget.py`: `_build_sections()` içindeki kart listesi güncellendi
  (Şube/Depo/Çalışma Dönemi kartları silindi, Döviz & Kur "BANKA & FİNANS TANIMLARI" bölümüne taşındı) —
  BU DOSYA senin asıl çalışma alanın, ama kart LİSTESİNİ (hangi panel_id'ler hangi grupta) değil, yalnızca
  GÖRSEL stili (`SettingsTileButton`) değiştir; grup/kart listesini tekrar eski haline getirme.
- `tests/test_settings_menu.py`: `test_calisma_donemi_yeni_donem_ekle_grid_e_bos_satir_degil_popup_acar`
  SİLİNDİ (artık var olmayan bir özelliği test ediyordu), `test_all_definition_tables_are_standard_entry_grids_with_theme_style`
  içindeki beklenen tablo kümesinden `tbl_sube`/`tbl_donem`/`tbl_depo` çıkarıldı.
- `tests/test_master_definitions.py::TestSettingsHubWidget`: `test_settings_hub_creation_and_search`
  `len(hub._buttons) >= 20` bekliyor (şu an 29 kart var) — stil değişikliğinde kart SAYISINI değiştirmiyorsan
  sorun yok, ama emin olmak için çalıştır.
- Bu görevle AYNI ANDA başka bir ekranda `showMaximized()` civarına dokunan bir değişiklik YOK şu an (önceki
  görevdeki o uyarı bu göreve konu değil) — yine de `settings.py`'de yalnızca yukarıda belirtilen alanlarla
  sınırlı kal, dosyanın geri kalanına (Döviz & Kur panel mantığı, Firma Bilgileri sekmesi vb.) dokunma.

## Yöntem
1. `dizayn/genel_ayarlar_ikon.jpg`'i aç, Ana Panel'in gerçek görünümüyle (`python -m src.desktop.main` ile
   giriş yapıp ana ekranı aç) karşılaştır — görsel bir AI taslağı, birebir piksel eşleşmesi beklenmiyor, ama
   renk paleti/kart boyutu/düzen (satır başına kart sayısı, gruplama) ondan ilham alınmalı.
2. `SettingsTileButton`'ı `MenuGridButton` ile görsel olarak eşle (yukarıdaki a/b seçeneklerinden biri).
3. Sol sidebar sadeleştirmesini değerlendir, düşük riskli yöntemi uygula.
4. Uygulamayı gerçekten aç, Genel Ayarlar'a gir (artık doğrudan pano ile açılmalı), ekran görüntüsü al.
5. `tests/test_master_definitions.py tests/test_settings_menu.py tests/test_general_settings_screen.py`
   tek tek çalıştır, kırılma varsa düzelt/ONAR.

## Bitince
Bu dosyanın altına `## Yapıldı` ekle: değiştirilen dosya listesi, her dosyada ne değişti, ekran görüntüsü
dosya yolu, çalıştırdığın testler ve sonuçları.
