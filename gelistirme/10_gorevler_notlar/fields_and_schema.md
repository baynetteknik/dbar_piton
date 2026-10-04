# 10 - GÖREVLER, NOTLAR & GELİŞTİRİCİ GÜNLÜĞÜ MODÜLÜ (`GOREVLST001`, `DEVTODO001`, `YNGOREV001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Görevler Ekranı (Data Grid + Kanban Pano Seçeneği)
- `title` (Görev Başlığı), `category` (Geliştirici / Bug, Tahsilat Takibi, Müşteri Ziyareti, Sevkiyat, Genel), `priority` (Düşük, Normal, Yüksek, Acil/Kritik), `status` (Yapılacak, Devam Eden, Tamamlanan), `assigned_user` (Atanan Kişi), `related_entity` (İlişkili Kart: Cari / Fatura / Teklif / Stok), `due_date` (Bitiş Tarihi).

### B. Form Alanları
- `title` (Text, Zorunlu, Max: 255) -> Başlık
- `category` (Select: GELİSTİRİCİ, TAHSİLAT, SATIŞ, SEVKİYAT, GENEL)
- `is_developer_only` (Boolean, Default: False) -> Sadece Geliştirici/Admin Görsün
- `priority` (Select: 1-Düşük, 2-Normal, 3-Yüksek, 4-Acil)
- `status` (Select: TODO, IN_PROGRESS, REVIEW, DONE, CANCELLED)
- `assigned_to` (ForeignKey -> users.id)
- `related_type` (Select: Cari, Fatura, Teklif, Stok, Yok)
- `related_id` (Integer -> İlgili Kart No)
- `due_date` (DateTime) -> Son Teslim / Vade
- `description` (Markdown / Rich Textarea) -> Detaylı Notlar & Kod Açıklamaları

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `tasks` & `notes`
| Tablo | Kolonlar |
| :--- | :--- |
| **`tasks`** | `id`, `tenant_id`, `title`, `category`, `is_developer_only`, `priority`, `status`, `assigned_to`, `created_by`, `related_type`, `related_id`, `start_date`, `due_date`, `completed_at`, `description`, `is_deleted`, `created_at` |
| **`notes`** | `id`, `tenant_id`, `user_id`, `title`, `content`, `color`, `is_pinned`, `is_developer_only`, `is_deleted`, `created_at` |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **10.01** Görevler, Notlar ve Geliştirici To-Do alanları modellendi
- [ ] **10.02** `Task` ve `Note` SQLAlchemy modellerinin kodlanması
- [ ] **10.03** `TaskService` (Görev CRUD, Kanban durum güncelleme ve ilişkili kart yönlendirme)
- [ ] **10.04** Görevler Gridi & Kanban Panosu (`GOREVLST001`) ve Geliştirici Konsolu (`DEVTODO001`) UI entegrasyonu

## ✅ UYGULANAN (2026-09-21)
- **Görevler (müşteri veritabanı, tablo `gorevler`):** görev / randevu / hatırlatma; durum (yapılacak, devam, incelemede, tamamlandı, iptal), öncelik, kategori, atanan, başlangıç/bitiş, tüm gün, hatırlatma (dk önce), tekrar + tekrar bitişi, ilişkili kayıt (`ilgili_tur/id/ad`). Eski `tasks` tablosu yedekleme zamanlaması içindir, ayrıdır.
- `gorev_service.py`: kayıt/doğrulama, durum değiştirme (yinelenen görev tamamlanınca sonraki tekrar açılır), filtre/özet, `takvim()` (yinelenenleri açar), `hatirlatmalar()`, `iliskili_olustur()` / `ilgili_gorevler()` (diğer modüller için).
- Ekranlar: `GorevlerScreen` (3 panelli; Liste / Pano / Takvim), `GorevDialog`, `GorevKanbanWidget`, `GorevTakvimWidget`. Ana menü: GÖREVLER › Görevler, Takvim (yetki `gorev.*`).
- Hatırlatma: ana pencere dakikada bir `hatirlatmalar()` çağırıp toast gösterir.
- **Geliştirme takibi:** `dev_tracker_store.py` → ayrı `dev_tracker.db` (git'e girmez; `*.db` yoksayılır). `dev_items` + `dev_gecmis` (alan bazlı değişiklik geçmişi). Ekran `DevTrackerScreen` (menü: GÖREVLER › Geliştirme). `git_tracker.db` görevlerini içe alma, `SURUM_NOTLARI.md` otomatik bölümünü yazma.
- **Paketleme (exe):** `gelistirme_acik()` kaynak koddan çalışırken True, PyInstaller `frozen` iken False (`TOYA_DEV_BUILD=1` ile zorlanır). Menüde "Geliştirme" görünmez ve ekran açılmaz. `dev_tracker.db` ve `git_tracker.db` pakete DAHİL EDİLMEMELİ (spec dosyasında `datas` listesine eklemeyin).
- [x] Ana panelde "Bugünün Görevleri" kartı; cari ve stok listelerinde "Görev Ekle" kısayolu (`GorevKisayolBolumu`).
- [ ] Fatura/teklif/sipariş ekranlarına aynı kısayol; e-posta ile hatırlatma.

## ✅ MASRAF TANIMLARI ENTEGRASYONU (2026-09-30)
- `ILGILI_TURLERI`'ne `"masraf": "Masraf"`, `KATEGORILER`'e `"finans": "Finans / Masraf"` eklendi.
- `ProductService._senkron_masraf_hatirlatma()`: `product_type="Masraf"` ve `is_recurring_expense=True` işaretli bir kart her
  kaydedildiğinde `ilgili_tur="masraf", tur="hatirlatma", tekrar="aylik"` bir `Gorev` açar/günceller (idempotent — tekrar kayıt yeni
  görev üretmez); bayrak kapatılınca açık hatırlatma gizlenir (silme=gizleme). Vade günü (`recurring_due_day`) ve kaç gün önce
  hatırlatılacağı (`recurring_reminder_days_before`) Masraf kartının "8. Masraf Tekrarı" bölümünden girilir.
- Bilinen sınır: Ana Panel'deki "Bugünün Görevleri" kartı yalnızca `baslangic`/`bitis` tarihi bugüne düşen ya da gecikmiş görevleri
  gösterir (tasarım gereği) — tarihsiz eklenen bir görev orada hiç görünmez, yalnızca tam Görevler ekranında listelenir.
