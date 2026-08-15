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
