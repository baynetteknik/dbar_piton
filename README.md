# Multi-CMS Manager 📝

Python tabanlı, çevrimdışı/çevrimiçi hibrit çalışan, Dolibarr ve WooCommerce'i tek noktadan yöneten masaüstü uygulaması.

## Özellikler
- **Çift Yönlü Akıllı Senkronizasyon**: Dolibarr ve WooCommerce arasında veri senkronizasyonu.
- **Yedekleme ve Taşıma Motoru**: Veritabanı ve dosya yedekleme/taşıma.
- **Güvenli API Saklama**: Keyring ile işletim sisteminin güvenli kasasında API anahtarları.
- **Dirençli Mimari**: Çöken API'ler için Circuit Breaker (pybreaker) ve Yeniden Deneme (tenacity).
- **Yerel Şifreli Veritabanı**: SQLCipher ile şifrelenmiş SQLite veritabanı.

## Kurulum

1. Sanal ortamı oluşturun ve aktifleştirin:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Bağımlılıkları yükleyin:
   ```bash
   pip install --upgrade pip
   pip install -e .[dev]
   ```

3. Geliştirici yol haritasını Excel olarak üretin:
   ```bash
   python scripts/generate_roadmap.py
   ```

## Testlerin Çalıştırılması
```bash
pytest
```
