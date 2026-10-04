# TOYA ERP — Sürüm Notları

Yapılan geliştirmelerin tarih sırasıyla (yeniden eskiye) kaydı. Her madde: ne yapıldı, hangi commit'e girdi, ayrıntı/test nerede.
Commit hash'i `bekliyor` ise geliştirme çalışma dizininde yapılmış ama henüz commit edilmemiştir; commit atılınca hash buraya işlenir.
Modül ayrıntıları `gelistirme/<modül>/` klasöründedir.

---

## 2026-09-22 (commit bekliyor — son commit `c431996` sonrası)

### Belge zinciri: Teklif → Sipariş → İrsaliye → Fatura (Faz 1 + Faz 2)
- **Faz 1 (model + geçiş):** `Quotation`'a gerçek belge türü/yön (`belge_turu`, `yon`) — irsaliye ve fatura artık "teklif" olarak değil kendi türüyle kaydediliyor. `belge_bag` (irsaliye↔fatura, sipariş↔irsaliye bağı) ve `stok_rezerv` tabloları, hareketlerde belgeye kaynak bağı. Eski veritabanları açılışta otomatik geçiyor.
- **Faz 2 (`BelgeHareketService`):** irsaliye/fatura hareket üretimi (stok + fatura ise cari, genel toplam üzerinden), çift sayım koruması (irsaliyeden gelen fatura satırı stok yazmaz), geri alma (ters kayıtla, hiçbir şey silinmeden), "e-Devlete gönderildi" elle işareti, çoklu irsaliye → tek fatura (kısmi faturalama dahil), sipariş → irsaliye + rezerv düşümü, kısmi iade. Negatif stok politikası (İzin ver / Uyarı ver-devam et / Uyarı ver-durdur) ayrı, paylaşılan bir modül.
- Arayüze henüz bağlanmadı (Faz 3, ayrı bir iş).
- Ayrıntı: `gelistirme/06_fatura_irsaliye/belge_zinciri_tasarim.md` · Testler: `tests/test_belge_turleri.py`, `tests/test_belge_hareket_service.py`

### Online Teklif Portalı: tür düzeltmesi
- "ONLİNE TEKLİF (PORTAL)" bölümü artık yalnız "Verilen Satış Teklifi" belgesinde görünüyor; önceden sipariş/irsaliye/fatura da dahil her belge türü yanlışlıkla portala yayınlanabiliyordu.
- Kod tarafı (yayınlama, müşteri kararı çekme, kurulum/dağıtım araçları) zaten tamamdı; aktivasyon için kalan tek adım gerçek bir cPanel barındırma sağlanması.
- Ayrıntı: `gelistirme/11_entegrasyonlar/portal_kaldigimiz_yer.md`

---

## 2026-09-21 (commit bekliyor — son commit `c431996` sonrası)

### Görevler, Takvim ve Geliştirme takibi
- **Görevler modülü** (herkese açık): görev / randevu / hatırlatma; Liste, Pano (Kanban, sürükle-bırak) ve Takvim (aylık) görünümleri; öncelik, kategori, atanan, tekrar (günlük/haftalık/aylık), hatırlatma (bildirim), ilişkili kayıt (cari, stok, fatura, teklif, servis…). Başka modül `GorevlerScreen(ilgili=("servis", 42, "…"))` ile gömüp kendi görevlerini gösterebilir. Ana menüde GÖREVLER grubu (eski "Görevler = yedekleme" ekranının yerine).
- **Geliştirme takibi:** `dev_tracker.db` (ayrı dosya, git'e girmez, müşteri verisine karışmaz). Öneri / yapılacak / hata kayıtları, durum akışı, değişiklik geçmişi. Ekran yalnız kaynak koddan çalışırken görünür; paketlenen exe'de gizlidir (`TOYA_DEV_BUILD`). Tamamlananlar aşağıdaki otomatik bölüme yazılır.
- **Ana panel:** "Bugünün Görevleri" kartı (gecikmiş + bugün, yinelenenler dahil; çift tıkla aç, ✔ Tamamla, ➕ Görev, Tümü ›). Varsayılan: giriş yapan kullanıcıya atanmış + kimseye atanmamış olanlar.
- **Cari ve Stok listeleri:** yan panelde GÖREVLER bölümü (✅ Görev Ekle, 📋 Görevleri (N)) ve sağ tık › Görev Ekle; görev seçili karta bağlanır.
- Ayrıntı: `gelistirme/10_gorevler_notlar` · Testler: `tests/test_gorev_ve_dev_tracker.py`, `tests/test_gorev_ekranlari.py`, `tests/test_gorev_kisayollari.py`

### Kasa & Banka hareketleri
- Kasa Tahsilat / Tediye / Açılış / Virman ve Banka Gelen-Giden Havale / EFT / Virman / Açılış fişleri (ortak `FinansFis` + `FinansHareket`).
- Kasa Hareketleri ve Banka Hareketleri ekranları (3 panelli), Kasa/Banka Kartları listelerinde "Hareket Girişi" paneli.
- Carili satır, cari defterinde otomatik karşılık üretir; hesap bakiyesi cari fişi + kasa/banka fişlerinden birleşik hesaplanır.
- Ayrıntı: `gelistirme/07_kasa`, `gelistirme/08_banka` · Test: `tests/test_finans_fis.py`

### Yedekleme Merkezi
- Yedek diskleri seri numarasıyla tanınır (sürücü harfi değişse de); Google Drive JSON içe aktarma; bildirimde çoklu olay/kanal seçimi.
- Yedekleme Panosu (kartlar, zaman çizelgesi, disk halkası, süre/hız grafiği, işlem tablosu; kompakt + tam ekran).
- Bağlı kullanıcı varken yedek başlamaz; ana pencerede yedek durum popup'ı ve kullanıcı uyarısı.
- Hedef sonuçları (klasör/disk + Drive ayrı ayrı), geri yükleme düğmesi, dosya yedeğini klasöre çıkarma, geri yükleme geçmişi.
- Ayrıntı: `gelistirme/01_ayarlar/yedekleme.md` · Testler: `tests/test_backup_*.py`, `tests/test_gdrive_folder_dialog.py`

### Bilinen açık noktalar
- `tests/test_main_window.py::test_main_window_tabs_and_dashboard` (`fav_screens_frame`) — önceden beri kırık, bu geliştirmelerden bağımsız.
- Cari fişindeki "Araç=Kasa/Banka" satırlarının otomatik kasa/banka hareketine dönüşmesi (şimdilik okuma tarafında birleşiyor).
- Değişiklik denetim günlüğü / geri alma (ertelendi).

---

## 2026-09-20 — `fce72aa`, `ca4e21f`, `ad2a89b`
- Döviz kurları ve döviz işlemleri, "parolamı unuttum" akışı (Ayarlar).
- Git bağlantı/gönderme ayarları ve Git Takip geliştirmeleri.
- Yedekleme sistemi (TOYA veritabanı + dosya/klasör işleri, zamanlama, şifreleme, dış hedefler); portal işlemlerine başlandı.

## 2026-09-21 — `c431996`
- Kasa ve Banka & POS kartları (açılış bakiyesi kartta yok, isteğe bağlı döviz kısıtı, alt hareket paneli).

## 2026-09-08 — `ea46715` ve öncesi
- Görsel tasarımcı Aşama 3 (gömülebilir tasarımcı, canlı baskı önizleme, fatura/irsaliye/80mm fiş şablonları, masaüstü ekran tasarımcısı modu).
- Bant tabanlı evrak detay ekranı (`DocumentDetailScreen`), Cari ve Stok kart editörleri.
- Cari Hareketleri: cari fişi (tahsilat, tediye, borç/alacak, virman, açılış), MoneyEdit widget'ı, ortak fiş iskeleti (`FisDialogBase` + `FisKalemGrid`), Stok Hareket Fişi ve Stok Hareketleri ekranı.

---

<!-- DEV-TRACKER:BEGIN -->
## Geliştirme Takibi (otomatik)
_Kaynak: dev_tracker.db — tamamlanan kayıtlar._

## [v1.0.0] — 2026-09-30 — Release 1
### 🛠️ Geliştirmeler & Yeni Özellikler
- 2026-10-01 · **Kasa:** Kasa fişi — `a1b2c3d`
### 🐞 Düzeltilen Hatalar
- 2026-10-01 · **Banka:** Hata düzeltmesi
### 💡 Tamamlanan İyileştirmeler & Öneriler
- 2026-10-01 · **UI:** İyileştirme
<!-- DEV-TRACKER:END -->
