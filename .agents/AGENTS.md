# Proje Kuralları (Multi-CMS Manager)

## Genel Kurallar
- **Dil**: Tüm projede kullanıcı ile iletişim dili Türkçe olacaktır.
- **İşlem Onayları**: Proje genelinde yapılacak teknik işlemler, dosya yazmaları/güncellemeleri ve plan uygulamaları için kullanıcıdan her adımda onay alınması gerekmez; doğrudan eyleme geçilebilir.

## Geliştirme Standartları
- **Branch**: Tüm değişiklikler için ayrı branch açılacaktır (feat/ozellik-adi)
- **Commit**: Commit mesajları Türkçe olacaktır
- **Kod Yorumları**: Kod yorumları İngilizce olacaktır
- **Test**: Her yeni özellik için test yazılacaktır
- **Lint**: ruff ile kod kalitesi kontrolü yapılacaktır

## Yol Haritası
- Detaylı yol haritası: `ROADMAP.md`
- Mevcut durum: Aşama 1 (UI/UX İyileştirmeleri) başlangıç aşamasında
- Öncelikli işler: Toast Notification, Multi-dil, Delta Sync

## Kodlama Standartları
- Python 3.10+ syntax kullanımı
- Type hint kullanımı zorunlu
- docstring: Google style
- Maksimum satır uzunluğu: 88 karakter (ruff config)
