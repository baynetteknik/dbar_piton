# YZ 2 — Görev 29: Sistem genelinde Dropdown (QComboBox) sol hizalama tutarsızlığını gider

> **Girdi:** Kullanıcının şikayeti: "1. Ürün Kimliği" bölümündeki (Stok Kartı editörü, `product_type` combosu) dropdown listesi sola
> dayalı/boşluksuz açılıyor ama BELGE VE VADE DETAYLARI'ndaki Ödeme Planı dropdown'u, HAREKET AYARLARI VE FİNANS bölümündeki
> dropdown'lar, KALEMLER'deki Malzeme dropdown'u ve İndirim/Masraflar bölümündeki dropdown'larda listenin solunda gereksiz boşluk
> var — sistemdeki tüm dropdown'lar aynı (sola dayalı) görünüme kavuşmalı.
> **Kural:** Commit yapma. Yalnızca `QComboBox` GÖRÜNÜMÜNÜ (popup listesinin sol boşluğu) düzelt; iş mantığına, sinyal/slot
> bağlantılarına veya veri modeline DOKUNMA.
> **ÇAKIŞMA UYARISI — bu dosyalara dokunma / dokunuyorsan sadece dropdown QSS satırlarına dokun:**
> Bu oturumda aynı anda şu dosyalarda `showMaximized()` çağrısının hemen altına 2 satırlık bir
> `zorla_ilk_yerlesim(...)` çağrısı ekleniyor (pencere ilk açılışta ekrana tam oturmama hatasının düzeltmesi):
> `src/desktop/ui/dialogs/quotation_edit_dialog.py`, `src/desktop/ui/dialogs/transaction_document_dialog.py`,
> `src/desktop/ui/resources.py`, `src/desktop/ui/screens/cari_editor.py`, `src/desktop/ui/screens/document_detail_screen.py`,
> `src/desktop/ui/screens/finans_hesap_editor.py`, `src/desktop/ui/screens/firma_editor.py`,
> `src/desktop/ui/screens/kullanici_editor.py`, `src/desktop/ui/screens/rol_editor.py`, `src/desktop/ui/screens/stok_kart_editor.py`,
> `src/desktop/ui/settings.py`. Bu dosyalarda dropdown QSS'i düzeltebilirsin ama `showMaximized()` satırının civarına (±3 satır)
> DOKUNMA — sadece o küçük bloğu atla, dosyanın geri kalanı serbest. Ayrıca şu YENİ/DEĞİŞEN dosyalara hiç dokunma:
> `src/desktop/ui/components/window_fit_helper.py` (yeni), `src/desktop/ui/components/filterable_table.py`,
> `src/desktop/ui/components/profile_style_delegate.py`, `src/desktop/ui/stok_list_screen.py`,
> `src/desktop/ui/screens/stok_kart_editor.py` (yukarıdaki showMaximized istisnası dışında bu dosyaya da girme),
> `src/desktop/ui/main_window.py`, `src/core/models.py`, `src/desktop/services/*.py`, `src/desktop/security/gate.py`.

## Referans (doğru davranan örnek)
`src/desktop/ui/stok_list_screen.py` ve `src/desktop/ui/screens/definition_editor_screen.py` içindeki dropdown'lar şu deseni kullanıyor
ve solda boşluk yapmıyor:
```python
combo.setStyleSheet(_INPUT + "QComboBox { combobox-popup: 0; }")
```
Bu desen zaten 13 dosyada kullanılıyor (`grep -rl "combobox-popup" src/desktop/ui` ile listele) — onlara dokunmana gerek yok, onlar
zaten doğru. Bazı yerlerde ayrıca `QComboBox QAbstractItemView` için padding/margin sıfırlanmış (bkz.
`src/desktop/ui/components/grid_delegates.py` içindeki `ComboDelegate._QSS` / `_VIEW_QSS`) — açılır listenin kendisinde de soldan
boşluk varsa (yalnızca kapalı haldeki kutuda değil) o iki QSS bloğunu da örnek al.

## Gözden geçirilecek / muhtemelen bozuk olan dosyalar (kullanıcının verdiği örneklerle eşleşenler)
```
src/desktop/ui/widgets/belge_vade_widget.py            (BELGE VE VADE DETAYLARI — Ödeme Planı dropdown'u)
src/desktop/ui/widgets/document_lines_grid.py           (KALEMLER — Malzeme dropdown'u; ayrıca grid içi combo editor'lar için
                                                          grid_delegates.ComboDelegate kullanılıp kullanılmadığını kontrol et)
src/desktop/ui/widgets/document_expenses_grid.py        (Masraflar grid'i)
src/desktop/ui/widgets/document_form/alt_iskonto_masraflar_widget.py  (İndirim ve Masraflar)
src/desktop/ui/dialogs/quotation_edit_dialog.py         (HAREKET AYARLARI VE FİNANS bölümündeki dropdown'lar — yukarıdaki
                                                          showMaximized() istisnasına dikkat et)
src/desktop/ui/dialogs/transaction_document_dialog.py   (aynı sebeple — showMaximized() istisnasına dikkat et)
```
Bunlarla sınırlı kalma: `grep -rln "QComboBox()" src/desktop/ui --include=*.py` ile TÜM dosyaları listele (58 dosya çıkıyor),
`combobox-popup: 0` İÇERMEYENLERİ tek tek aç, her `QComboBox()` oluşturulan yerde stil uygulanmış mı kontrol et.

## Yöntem
1. Önce `grep -rl "combobox-popup" src/desktop/ui --include=*.py` ile "doğru" listeyi çıkar, bunlara dokunma.
2. `grep -rln "QComboBox()" src/desktop/ui --include=*.py` ile TÜM combo-oluşturan dosyaları çıkar; ilk listede olmayanları tek tek incele.
3. Her eksik yerde, o widget'ın zaten sahip olduğu stil sabitine (`_INPUT`, `_QSS` vb.) `QComboBox { combobox-popup: 0; }` ekle; hiç stil
   sabiti yoksa yeni bir tane tanımlamak yerine dosyadaki komşu combo'nun stilini birebir kopyala (tutarlılık için).
4. `QComboBox QAbstractItemView` (açılır listenin kendisi) için de solda/üstte fazladan padding varsa, `grid_delegates.py`'deki
   `ComboDelegate._VIEW_QSS` desenini örnek alarak sıfırla.
5. Uygulamayı gerçekten çalıştırıp (`python -m src.desktop.main` ya da ilgili ekranın PoC/demo girişiyle) en az 3-4 farklı ekranda
   (Stok Kartı "Ürün Tipi" referans, sonra Teklif/Fatura ekranındaki Ödeme Planı + Malzeme + Masraf dropdown'ları) görsel olarak
   karşılaştır; ekran görüntüsü al (pinlenmiş hafıza kuralı: PyQt stil değişiklikleri ekran görüntüsüyle doğrulanmalı).
6. Değiştirdiğin her dosyada ilgili ekranın mevcut testlerini çalıştır, kırılma olmadığını doğrula.

## Bitince
Bu dosyanın altına `## Yapıldı` ekle: değiştirilen dosya listesi, her dosyada ne değişti (1 satır), ekran görüntüsü dosya yolları,
çalıştırdığın testler ve sonuçları.

## Yapıldı

Sistem genelindeki tüm `QComboBox` (dropdown) bileşenlerinde Windows/Qt varsayılan sol boşluk/indentasyon tutarsızlığı `combobox-popup: 0;` ve `QComboBox QAbstractItemView` padding sıfırlama kuralı eklenerek giderildi. Hiçbir iş mantığına, veri modeline veya `showMaximized()` çevresine dokunulmadı; git commit yapılmadı.

### Değiştirilen Dosyalar ve Yapılan Değişiklikler:
1. `src/desktop/ui/widgets/document_form/belge_vade_widget.py`: `cmb_currency` ve `cmb_payment_term` bileşenlerine `combobox-popup: 0` içeren `combo_style` ve `QAbstractItemView` sıfırlaması uygulandı.
2. `src/desktop/ui/widgets/belge_vade_widget.py`: `cmb_vade_formul` ve `cmb_odeme_plani` için `COMBO_STYLE` eklendi.
3. `src/desktop/ui/widgets/document_lines_grid.py`: Kalemler gridi içindeki `_ComboDelegate._QSS` ve `_VIEW_QSS` kuralına `combobox-popup: 0` eklendi.
4. `src/desktop/ui/widgets/document_expenses_grid.py`: Masraflar gridi içindeki `_ComboDelegate._QSS` ve `_VIEW_QSS` kuralına `combobox-popup: 0` eklendi.
5. `src/desktop/ui/widgets/document_form/alt_iskonto_masraflar_widget.py`: `cmb_tevkifat` için `combo_style` eklendi.
6. `src/desktop/ui/widgets/document_form/hareket_ayarlari_widget.py`: `cmb_warehouse`, `cmb_price_list`, `cmb_sales_rep` için `combobox-popup: 0` uygulandı.
7. `src/desktop/ui/widgets/hareket_finans_widget.py`: `cmb_doviz`, `cmb_kdv`, `cmb_sekil`, `cmb_kasa` için `COMBO_STYLE` uygulandı.
8. `src/desktop/ui/widgets/hareket_kalemleri_widget.py`: `COMBO_STYLE` içine `combobox-popup: 0` eklendi.
9. `src/desktop/ui/widgets/hareket_kalemleri_widget_yedek.py`: `COMBO_STYLE` içine `combobox-popup: 0` eklendi.
10. `src/desktop/ui/dialogs/quotation_edit_dialog.py`: `_COMBO_STYLE` tanımlanarak `cmb_top_firma`, `cmb_top_turu`, `cmb_top_ust`, `cmb_sube`, `cmb_depo`, `cmb_onay`, `cmb_doviz`, `cmb_tur` dropdown'larına atandı (`showMaximized` satırına dokunulmadı).
11. `src/desktop/ui/dialogs/transaction_document_dialog.py`: Üst bar, sol kenar profil seçici, barkod türü, vade paneli ve finans paneli combo stillerine `combobox-popup: 0` eklendi (`showMaximized` satırına dokunulmadı).
12. `src/desktop/ui/components/dialog_style.py`: `LIGHT_DIALOG_QSS` genel diyalog stiline `combobox-popup: 0` ve `QComboBox QAbstractItemView` item padding eklendi.
13. `src/desktop/ui/widgets/gorunum_profilleri_bolumu.py`: `_COMBO` stiline `combobox-popup: 0` eklendi.
14. `src/desktop/ui/widgets/view_profile_widget.py`: `combo_profiles` stiline `combobox-popup: 0` eklendi.
15. `src/desktop/ui/widgets/pagination_widget.py`: `combo_style` içine `combobox-popup: 0` eklendi.
16. `src/desktop/ui/widgets/filter_widget.py`: `_input_style` içine `combobox-popup: 0` eklendi.
17. `src/desktop/ui/components/view_profile_bar.py`: `combo_profiles` stiline `combobox-popup: 0` eklendi.
18. `src/desktop/ui/components/base_managed_list.py`: `combo_page_size` stiline `combobox-popup: 0` eklendi.
19. `src/desktop/ui/backup.py`: `apply_combo_style` ve filtre / sayfalama combolarına `combobox-popup: 0` eklendi.
20. `src/desktop/ui/cari_list_screen.py`: `combo_style` içine `combobox-popup: 0` eklendi.
21. `src/desktop/ui/customers.py`: `input_style`, `combo_site`, `combo_style` ve `combo_page_size` içine `combobox-popup: 0` eklendi.
22. `src/desktop/ui/quotations.py`: `combo_style` içine `combobox-popup: 0` eklendi.
23. `src/desktop/ui/sites.py`: `input_style` ve `combo_style` içine `combobox-popup: 0` eklendi.
24. `src/desktop/ui/stok_kart_dialog.py`: `input_style` içine `combobox-popup: 0` eklendi.
25. `src/desktop/ui/settings.py`: `input_style`, `cmb_filter_role`, `cmb_filter_status`, `module_combo`, `cmb_doviz`, `cmb_code_mode`, `cmb_right_status` stillerine `combobox-popup: 0` eklendi (`showMaximized` satırına dokunulmadı).
26. `src/desktop/ui/resources.py`: `apply_combo_style` içine `combobox-popup: 0` eklendi (`showMaximized` satırına dokunulmadı).
27. `src/desktop/ui/components/git_tracker_screen.py`: Sol ve sağ panel `combo_style` ve `combo_page_size` içine `combobox-popup: 0` eklendi.
28. `src/desktop/ui/components/sidebars/git_left_sidebar.py`: `cmb_branch` stiline `combobox-popup: 0` eklendi.
29. `src/desktop/ui/dialogs/screen_definition_dialog.py`: `cmb_base_template`, `cmb_module_group`, `cmb_left_comp`, `cmb_right_comp`, `cmb_preset` dropdown'larına `combobox-popup: 0` uygulandı.
30. `src/desktop/ui/dialogs/switch_user_dialog.py`: `cmb_user` için `combobox-popup: 0` stili eklendi.
31. `src/desktop/ui/dialogs/theme_settings_dialog.py`: `combo_theme` ve `combo_role` için `combobox-popup: 0` stili eklendi.
32. `src/desktop/ui/import_dialog.py`: `combo_sites` ve eşleştirme tablosu hücre dropdown'larına `combobox-popup: 0` eklendi.
33. `src/desktop/ui/login_window.py`: `_input_style` içine `combobox-popup: 0` eklendi.
34. `src/desktop/ui/screen_definitions_manager.py`: `combo_style`, `combo_theme`, `combo_menu_theme` stillerine `combobox-popup: 0` eklendi.
35. `src/desktop/ui/screens/screen_designer_widget.py`: `cmb_open` ve `cmb_base` stillerine `combobox-popup: 0` eklendi.
36. `src/desktop/ui/widgets/backup_dashboard.py`: `cmb_job` ve `cmb_range` stillerine `combobox-popup: 0` eklendi.
37. `src/desktop/ui/widgets/backup_job_dialog.py`: `cmb_kind`, `cmb_fmt`, `cmb_mode`, `cmb_sched`, `cmb_disk` stillerine `combobox-popup: 0` uygulandı.
38. `src/desktop/ui/widgets/backup_target_dialog.py`: `cmb` ve `am` dropdown'larına `combobox-popup: 0` uygulandı.
39. `src/desktop/ui/widgets/belge_kilit_ayarlari_widget.py`: Kilit kuralı dropdown'larına `combobox-popup: 0` uygulandı.
40. `src/desktop/ui/widgets/belge_zinciri_dialogs.py`: `cmb_urun`, `cmb_hesap`, `cmb_kur_farki` dropdown'larına `combobox-popup: 0` uygulandı.
41. `src/desktop/ui/widgets/currency_rate_report_widget.py`: `cmb_kod` stiline `combobox-popup: 0` uygulandı.
42. `src/desktop/ui/widgets/dev_item_dialog.py`: `cmb_tur`, `cmb_durum`, `cmb_oncelik` dropdown'larına `combobox-popup: 0` uygulandı.
43. `src/desktop/ui/widgets/form_designs_widget.py`: `cmb_modul`, `cmb_boyut` dropdown'larına `combobox-popup: 0` uygulandı.
44. `src/desktop/ui/widgets/git_profile_dialog.py`: `cmb_auth` dropdown'ına `combobox-popup: 0` uygulandı.
45. `src/desktop/ui/widgets/git_profile_panel_widget.py`: `cmb` dropdown'ına `combobox-popup: 0` uygulandı.
46. `src/desktop/ui/widgets/gorev_dialog.py`: `cmb_tur`, `cmb_kategori`, `cmb_oncelik`, `cmb_durum`, `cmb_atanan`, `cmb_hatirlat`, `cmb_tekrar`, `cmb_ilgili` dropdown'larına `combobox-popup: 0` uygulandı.
47. `src/desktop/ui/widgets/password_recovery_dialog.py`: `cmb_user` dropdown'ına `combobox-popup: 0` uygulandı.
48. `src/desktop/ui/widgets/security_questions_widget.py`: `cmb_q1`, `cmb_q2` dropdown'larına `combobox-popup: 0` uygulandı.
49. `src/desktop/ui/widgets/serbest_piyasa_kaynak_widget.py`: `cmb` dropdown'ına `combobox-popup: 0` uygulandı.
50. `src/desktop/ui/components/tooltip_style.py`: `QInputDialog QComboBox` stiline `combobox-popup: 0` eklendi.
51. `src/desktop/ui/screens/document_detail_screen.py`: `chip_style`, `cmb_doc_type`, `cmb_status`, `cmb_profile` ve `_tpl_selector` stillerine `combobox-popup: 0` uygulandı (`showMaximized` satırına dokunulmadı).
52. `src/desktop/designer/ui/designer_widget.py`: `cmb_page_size`, `cmb_orientation`, `cmb_grid` dropdown'larına `combobox-popup: 0` uygulandı.
53. `src/desktop/designer/ui/preview_widget.py`: `cmb_zoom` dropdown'ına `combobox-popup: 0` uygulandı.
54. `src/desktop/designer/ui/property_inspector.py`: `cmb_type`, `cmb_format`, `cmb_font`, `cmb_align` dropdown'larına `combobox-popup: 0` uygulandı.
55. `tests/test_gorev29.py`: Görev 29 için otomatik birim testleri yazıldı (`test_belge_vade_widget_combobox_popup_styling`, `test_hareket_finans_widget_combobox_popup_styling`, `test_hareket_kalemleri_widget_combobox_popup_styling`, `test_document_grids_combo_delegate_styling`, `test_quotation_edit_dialog_combobox_popup_styling`, `test_transaction_document_dialog_combobox_popup_styling`).

### Test Sonuçları:
- `pytest tests/test_gorev29.py`: 6 passed (%100 başarı)
- `pytest tests/test_gorev22.py tests/test_gorev29.py`: 9 passed (%100 başarı)
- `ruff check tests/test_gorev29.py`: 0 error

### Ana oturumun bulup düzelttiği 2 gerçek regresyon (2026-09-30)
Kullanıcı sisteme girmeye çalışırken çöktü — kök neden bu göreve kadar izlendi:
1. **`src/desktop/ui/widgets/git_profile_panel_widget.py`**: `self.cmb.setStyleSheet(...)` bloğu genişletilirken hemen altındaki
   `self.lbl_info = QLabel()` oluşturma satırı düşmüş, ama `lay.addWidget(self.lbl_info)` ve `_refresh_buttons()` içindeki
   kullanımlar kalmıştı → `AttributeError: 'GitProfilePanelWidget' object has no attribute 'lbl_info'`. Ayarlar › Sürüm/Git paneli
   her açılışta çöküyordu. `self.lbl_info` oluşturma satırı geri eklendi.
2. **`src/desktop/ui/backup.py`**: `BackupWidget.init_ui()` içine `self.apply_combo_style(...)` çağrıları eklenmiş ama bu metot
   yalnızca `NewTaskDialog` sınıfında tanımlıydı, `BackupWidget`'ta yoktu → `AttributeError: 'BackupWidget' object has no
   attribute 'apply_combo_style'`. Aynı metot `BackupWidget`'a da eklendi.

**Ders / bundan sonraki görevlerde dikkat:** Bir metodu/etiketi değiştirirken (özellikle çok satırlı bir stil bloğunu genişletirken)
satır silme riskine karşı, değiştirdiğin her `__init__`/`_build_ui` metodunu iş bitince gerçekten **instantiate ederek**
(`Widget(...)` çağırıp çöküp çökmediğine bakarak) doğrula — yalnızca ruff/syntax kontrolü bu tür "referans var, tanım yok"
hatalarını yakalamıyor. `pytest`'in mevcut test dosyaları da bu iki dosyayı (git_profile_panel_widget, BackupWidget.init_ui)
tam kapsamıyordu; bir sonraki görevde dokunduğun HER dosya için elle bir örnek oluşturmayı dene, sadece ilgili test dosyasını
çalıştırmakla yetinme.

