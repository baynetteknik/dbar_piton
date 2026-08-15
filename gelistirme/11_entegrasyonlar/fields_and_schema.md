# 11 - ENTEGRASYONLAR & ERP KÖPRÜSÜ MODÜLÜ (`ENTEG001`)

## 🖥️ 1. EKRAN & FORM ALANLARI (FIELDS)

### A. Entegrasyon Yönetim Paneli
- **E-Ticaret & Pazaryeri Kartları:** WooCommerce, PrestaShop, Trendyol, Hepsiburada bağlantı ayarları (API Key, Secret, Webhook URL).
- **ERP Köprüsü Kartları:** Logo (MSSQL Host/User/Pass/DB), Akınsoft Wolvox (Firebird/MSSQL Ayarları), Dia (Web Servis Oturumu).
- **Dinamik XML Tedarikçi Eşleme:**
  - `supplier_name` (Tedarikçi Adı), `xml_url` (XML Linki), `update_interval_min` (Senkron Aralığı: 60 dk).
  - **Görsel Alan Eşleme Tablosu (Field Mapping):**
    - XML Tag: `<UrunAdi>` $\rightarrow$ TOYA: `name`
    - XML Tag: `<StokKodu>` $\rightarrow$ TOYA: `sku`
    - XML Tag: `<Barkod>` $\rightarrow$ TOYA: `barcode`
    - XML Tag: `<Fiyat>` $\rightarrow$ TOYA: `buy_price`
    - XML Tag: `<KDV>` $\rightarrow$ TOYA: `tax_rate`

---

# 🗄️ 2. VERİTABANI ŞEMASI (DATABASE)

### `integrations` & `integration_mappings` & `xml_suppliers`
| Tablo | Kolonlar |
| :--- | :--- |
| **`integrations`** | `id`, `tenant_id`, `platform_type` (WOOCOMMERCE / TRENDYOL / LOGO / AKINSOFT / XML), `title`, `config_data` (Şifrelenmiş JSON), `is_active`, `last_sync_at`, `sync_status`, `error_message`, `created_at` |
| **`integration_mappings`** | `id`, `tenant_id`, `integration_id`, `entity_type` (PRODUCT / CUSTOMER / ORDER), `local_id`, `remote_id`, `last_synced_at`, `status` |
| **`xml_suppliers`** | `id`, `tenant_id`, `name`, `url`, `field_mapping` (JSON), `auto_sync`, `interval_minutes`, `last_sync_at` |

---

# 📋 3. GÖREV LİSTESİ (TASKS)
- [x] **11.01** Entegrasyonlar ve Dinamik XML Eşleme motoru veri modeli tasarlandı
- [ ] **11.02** `BaseERPAdapter` ve `IntegrationMapping` modellerinin kodlanması
- [ ] **11.03** WooCommerce, Trendyol ve Dinamik XML Tedarikçi parser servislerinin kodlanması
- [ ] **11.04** Entegrasyonlar Yönetim Paneli (`ENTEG001`) UI ekranının bağlanması
