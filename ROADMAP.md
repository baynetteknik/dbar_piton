# Multi-CMS Manager - Geliştirme Yol Haritası

**DIAApp3 referans alınarak yapılacak geliştirmeler**

---

## Genel Bakış

Bu yol haritası, Multi-CMS Manager uygulamasının DIAApp3 benzeri modern bir desktop uygulamasına dönüştürülmesi için planlanan çalışmaları içerir.

---

## Aşama 1: UI/UX İyileştirmeleri (Hafta 1)

### 1.1 Toast Notification Sistemi
**Durum:** Yapılacak
**Dosya:** `src/desktop/ui/main_window.py`
**Tahmini Süre:** 2-3 saat

- DIAApp3'teki gibi animasyonlu bildirim sistemi
- QPropertyAnimation ile slide-in efekti
- Otomatik kaybolma (3 saniye)
- Bildirim türleri: success, warning, error, info
- Footer bar'a network durum göstergesi ekleme

```python
# Örnek kullanım
self.show_toast("Senkronizasyon tamamlandı", "success")
self.show_toast("İnternet bağlantısı yok", "warning")
```

### 1.2 Frameless Window
**Durum:** Yapılacak
**Dosya:** `src/desktop/ui/main_window.py`
**Tahmini Süre:** 4-6 saat

- PySideSix-Frameless-Window entegrasyonu
- Özel title bar (minimize, maximize, close butonları)
- Custom hover efektleri
- Pencere boyutu kaydetme/geri yükleme

### 1.3 Multi-dil Desteği (i18n)
**Durum:** Yapılacak
**Dosya:** `src/desktop/i18n/` (yeni dizin)
**Tahmini Süre:** 1 gün

- `self.tr()` kullanımı genişletilecek
- Türkçe, İngilizce, Almanca, Rusça, Fransızca, Ukraynaca
- Diller arası geçiş (ayarlardan)
- Translation dosyaları: `translations_tr.json`, `translations_en.json`

### 1.4 Splash Screen
**Durum:** Yapılacak
**Dosya:** `src/desktop/main.py`
**Tahmini Süre:** 2-3 saat

- Uygulama başlatılırken splash screen
- Logo ve versiyon bilgisi
- İlerleme göstergesi

---

## Aşama 2: Network & Performance (Hafta 2)

### 2.1 MessagePack + Zstandard Serializasyonu
**Durum:** Yapılacak
**Dosya:** `src/core/serializer.py` (yeni dosya)
**Tahmini Süre:** 1 gün

- JSON yerine MessagePack (2-5x daha hızlı)
- Zstandard ile sıkıştırma (%60-70 küçülme)
- Base64 encoding ile ASCII uyumluluk
- Legacy JSON fallback desteği

```python
# Performans karşılaştırması
# JSON: ~100KB, ~50ms serialize
# MsgPack+Zstd: ~30KB, ~10ms serialize
```

### 2.2 Asenkron Network Katmanı
**Durum:** Yapılacak
**Dosya:** `src/core/network.py` (yeni dosya)
**Tahmini Süre:** 3 gün

- `asyncio + qasync` entegrasyonu
- Mevcut `requests` isteklerini `aiohttp` ile değiştirme
- Connection pooling
- Timeout yönetimi
- Retry mekanizması (mevcut tenacity korunacak)

### 2.3 Delta Sync (Incremental Pull)
**Durum:** Yapılacak
**Dosya:** `src/core/sync/pull_engine.py`
**Tahmini Süre:** 2 gün

- `modified_after` parametresinin aktif kullanımı
- Son senkronizasyon zaman damgası takibi
- Yeni model: `SyncState` tablosu
- Sadece değişen kayıtları çekme

```sql
CREATE TABLE sync_states (
    id INTEGER PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id),
    entity_type VARCHAR(50),
    last_sync_at DATETIME,
    records_synced INTEGER DEFAULT 0,
    UNIQUE(site_id, entity_type)
);
```

### 2.4 Cache Sistemi
**Durum:** Yapılacak
**Dosya:** `src/core/cache.py` (yeni dosya)
**Tahmini Süre:** 1 gün

- MD5 tabanlı cache key
- TTL (Time-To-Live) desteği
- Manuel cache temizleme
- Cache istatistikleri

---

## Aşama 3: Data Layer İyileştirmeleri (Hafta 3)

### 3.1 Conflict Resolution İyileştirmesi
**Durum:** Yapılacak
**Dosya:** `src/core/sync/conflict_resolver.py` (yeni dosya)
**Tahmini Süre:** 2 gün

- Field-level merge desteği
- Vector clock entegrasyonu
- Conflict log kaydı
- UI'dan manuel çakışma çözümü

### 3.2 Offline Queue Persistence
**Durum:** Yapılacak
**Dosya:** `src/core/sync/queue_manager.py` (yeni dosya)
**Tahmini Süre:** 2 gün

- Mevcut `SyncQueue` tablosunun geliştirilmesi
- Öncelik sıralaması
- Otomatik temizleme (işlenmiş kayıtlar)
- UI'dan kuyruk durumu izleme

### 3.3 Network Connectivity Monitor
**Durum:** Yapılacak
**Dosya:** `src/core/network_monitor.py` (yeni dosya)
**Tahmini Süre:** 1 gün

- Periyodik bağlantı kontrolü
- State makinası: ONLINE, OFFLINE, DEGRADED
- UI bildirimleri
- Offline modda otomatik kuyruğa alma

### 3.4 Enhanced Change Tracking
**Durum:** Yapılacak
**Dosya:** `src/core/models.py`
**Tahmini Süre:** 1 gün

- Customer entity için event listener ekleme
- `after_insert`, `after_update` tetikleyicileri
- Tutarlı ChangeLog oluşturma

---

## Aşama 4: Auto-Update & Paketleme (Hafta 4)

### 4.1 PyInstaller Paketleme
**Durum:** Yapılacak
**Dosya:** `build.spec` (yeni dosya)
**Tahmini Süre:** 1 gün

- Tek dosya executable oluşturma
- İkon ve version bilgisi
- Resource dosyaları dahil etme
- 32-bit ve 64-bit desteği

### 4.2 WinSparkle Auto-Update
**Durum:** Yapılacak
**Dosya:** `src/core/updater.py` (yeni dosya)
**Tahmini Süre:** 2 gün

- Appcast XML hosting
- Otomatik güncelleme kontrolü
- Sessiz güncelleme modu
- Kullanıcı bildirimi

### 4.3 Configuration Management
**Durum:** Yapılacak
**Dosya:** `src/core/config.py`
**Tahmini Süre:** 1 gün

- config.json desteği
- Ortam değişkenleri
- Öncelik sıralaması: env > .env > config.json > varsayılan
- Encryption key yönetimi

---

## Aşama 5: Advanced Features (Hafta 5-6)

### 5.1 QR Kod Desteği
**Durum:** Yapılacak
**Dosya:** `src/core/qrcode_gen.py` (yeni dosya)
**Tahmini Süre:** 1 gün

- qrcode + pypng ile QR kod üretimi
- Müşteri kartları için QR kod
- Ürün etiketleri için QR kod

### 5.2 E-Fatura Entegrasyonu
**Durum:** Yapılacak
**Dosya:** `src/adapters/efatura/` (yeni dizin)
**Tahmini Süre:** 3-5 gün

- E-Fatura API entegrasyonu
- Fatura oluşturma/gönderme
- XML/UBL format desteği

### 5.3 Raporlama Motoru
**Durum:** Yapılacak
**Dosya:** `src/core/reporting.py` (yeni dosya)
**Tahmini Süre:** 3 gün

- matplotlib ile grafik oluşturma
- Excel/CSV rapor dışa aktarma
- PDF rapor oluşturma
- Zamanlanmış raporlar

### 5.4 Logging & Audit Trail
**Durum:** Yapılacak
**Dosya:** `src/core/audit.py` (yeni dosya)
**Tahmini Süre:** 1 gün

- Detaylı işlem logları
- Kullanıcı aktivite takibi
- Audit trail raporları
- Log rotasyonu

---

## Öncelik Matrisi

| Özellik | Öncelik | Maliyet | Fayda | Durum |
|---------|---------|---------|-------|-------|
| Toast Notification | P0 | 2 saat | Yüksek | Yapılacak |
| Multi-dil (i18n) | P0 | 1 gün | Yüksek | Yapılacak |
| Delta Sync | P0 | 2 gün | Çok Yüksek | Yapılacak |
| MessagePack + Zstd | P1 | 1 gün | Yüksek | Yapılacak |
| Cache Manager | P1 | 1 gün | Yüksek | Yapılacak |
| Network Monitor | P1 | 1 gün | Yüksek | Yapılacak |
| Frameless Window | P2 | 4 saat | Orta | Yapılacak |
| Async Network | P2 | 3 gün | Yüksek | Yapılacak |
| Conflict Resolver | P2 | 2 gün | Yüksek | Yapılacak |
| Offline Queue | P2 | 2 gün | Yüksek | Yapılacak |
| PyInstaller | P3 | 1 gün | Orta | Yapılacak |
| Auto-Update | P3 | 2 gün | Orta | Yapılacak |
| QR Kod | P4 | 1 gün | Düşük | Yapılacak |
| E-Fatura | P4 | 5 gün | Yüksek | Yapılacak |
| Raporlama | P5 | 3 gün | Orta | Yapılacak |
| Audit Trail | P5 | 1 gün | Orta | Yapılacak |

---

## Dosya Yapısı (Hedef)

```
src/
├── core/
│   ├── __init__.py
│   ├── config.py              # Ayar yönetimi (geliştirilecek)
│   ├── models.py              # Veritabanı modelleri (geliştirilecek)
│   ├── database.py            # DB yönetimi
│   ├── serializer.py          # YENİ: MsgPack + Zstd
│   ├── network.py             # YENİ: Async network
│   ├── network_monitor.py     # YENİ: Bağlantı izleme
│   ├── cache.py               # YENİ: Cache sistemi
│   ├── audit.py               # YENİ: Audit trail
│   ├── reporting.py           # YENİ: Raporlama
│   ├── qrcode_gen.py          # YENİ: QR kod
│   ├── importer.py            # Excel/ODS import
│   ├── logger.py              # Structured logging
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── pull_engine.py     # Geliştirilecek
│   │   ├── push_engine.py     # Geliştirilecek
│   │   ├── customer_sync.py   # Geliştirilecek
│   │   ├── conflict_resolver.py  # YENİ
│   │   └── queue_manager.py   # YENİ
│   ├── backup/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── db_backup.py
│   │   ├── file_backup.py
│   │   ├── migration.py
│   │   ├── parsers.py
│   │   ├── scheduler.py
│   │   └── exceptions.py
│   └── security/
│       ├── __init__.py
│       └── keyring_store.py
├── adapters/
│   ├── __init__.py
│   ├── base.py
│   ├── mappers.py
│   ├── dolibarr/
│   │   ├── __init__.py
│   │   ├── dolibarr_client.py
│   │   └── dolibarr_adapter.py
│   ├── woocommerce/
│   │   ├── __init__.py
│   │   ├── woocommerce_client.py
│   │   └── woocommerce_adapter.py
│   └── efatura/               # YENİ
│       ├── __init__.py
│       └── efatura_client.py
├── desktop/
│   ├── __init__.py
│   ├── main.py
│   ├── i18n/                  # YENİ
│   │   ├── __init__.py
│   │   ├── translations_tr.json
│   │   ├── translations_en.json
│   │   └── ...
│   ├── core/
│   │   ├── __init__.py
│   │   └── workers.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py     # Geliştirilecek
│       ├── toast.py           # YENİ
│       ├── sites.py
│       ├── resources.py
│       ├── customers.py
│       ├── backup.py
│       ├── dashboard.py
│       ├── import_dialog.py
│       └── column_manager.py
└── cli/
    ├── __init__.py
    └── sync.py

# Ek dosyalar
build.spec                    # YENİ: PyInstaller spec
config.json                   # YENİ: Ayarlar
data/
├── app.db
├── cache/                    # YENİ
├── backups/
├── images/
└── view_settings.json
```

---

## Bağımlılık Güncellemeleri

### Yeni Bağımlılıklar

```toml
# pyproject.toml'a eklenecekler
dependencies = [
    # Mevcutler...
    "msgpack>=1.0.0",           # MessagePack serializasyon
    "zstandard>=0.20.0",        # Zstandard sıkıştırma
    "aiohttp>=3.9.0",           # Asenkron HTTP
    "qasync>=0.27.0",           # Qt + asyncio köprüsü
    "qrcode>=7.0",              # QR kod üretimi
    "pypng>=0.2000",            # PNG desteği
    "PySideSix-Frameless-Window>=0.3.0",  # Frameless pencere
    "winsparkle>=0.1.0",        # Auto-update (opsiyonel)
]

[project.optional-dependencies]
efatura = [
    "zeep>=4.0.0",              # SOAP client
    "lxml>=5.0.0",              # XML işleme
]
```

---

## Test Stratejisi

### Unit Test Öncelikleri

1. `tests/test_serializer.py` - MsgPack + Zstd testleri
2. `tests/test_cache.py` - Cache sistemi testleri
3. `tests/test_network_monitor.py` - Network durum testleri
4. `tests/test_conflict_resolver.py` - Çakışma çözümü testleri
5. `tests/test_queue_manager.py` - Kuyruk yönetimi testleri

### Integration Test Öncelikleri

1. Pull/Push senkronizasyon testleri
2. Offline → Online geçiş testleri
3. Multi-dil testleri

---

## Başlangıç Noktası

**İlk yapılacak iş:** Toast Notification Sistemi (Aşama 1.1)

Bu özellik hem hızlıca uygulanabilir hem de mevcut UI'ya büyük katkı sağlar. Diğer özellikler için temel oluşturur.

---

## Notlar

- Tüm değişiklikler `main` branch'ine yapılacaktır
- Her özellik için ayrı branch açılacaktır (feat/toast-notification, feat/delta-sync vb.)
- Commit mesajları Türkçe olacaktır
- Kod yorumları İngilizce olacaktır
- PR review sonrası merge işlemi yapılacaktır

---

*Son güncelleme: 18 Ocak 2026*
*Hazırlayan: Multi-CMS Manager Development Team*
