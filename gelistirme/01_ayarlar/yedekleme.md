# Yedekleme Merkezi (Genel Ayarlar → Sistem → Yedekleme Merkezi)

`C:\mail_yedek` (dosya/SQL işleri, bulut, zamanlayıcı, şifreleme, e-posta raporu, disk takılınca yedek) ve
aidat projesindeki (veritabanı yedeği + bulut) fikirlerden TOYA'ya taşındı. Mail arşivi ve VHDX (Hyper-V) taşınmadı.

## Katmanlar (`src/desktop/services/backup/`)
| Dosya | Görev |
|---|---|
| `models.py` | `BackupJob` + doğrulama + `JobStore` (ayarlarda JSON; silme = gizleme) |
| `archive.py` | zip/tar.gz + `manifest.json` (SHA-256), doğrulama, zip-slip korumalı açma |
| `crypto.py` | AES-256-GCM parça parça şifreleme (scrypt); yanlış parola/oynama/kesilme algılanır |
| `toya_backup.py` | SQLite çevrimiçi yedek + `integrity_check`; geri yükleme hazırlama / açılışta uygulama |
| `file_job.py` | filtreler, artımlı, mirror (silmez), saklama (artımlı zincirleri bölmez) |
| `providers.py`, `remote_providers.py` | Klasör/NAS, FTP/FTPS, Google Drive (OAuth+PKCE, `drive.file`), S3 (SigV4; MinIO/Wasabi/B2 uç noktası) + yeniden deneme |
| `secrets.py` | parola/anahtarlar Windows Kimlik Bilgisi Yöneticisi'nde (`keyring`); depo yoksa düz metne düşmez |
| `runner.py` | arşivle → doğrula → şifrele → şifreliyi doğrula → saklama → yükle; DB'ye dokunmaz |
| `service.py`, `lock.py` | bağlam hazırlama, kilitli çalıştırma (uygulama + ajan çifte çalışmaz), kayıt, rapor |
| `schedule.py` | zamanı gelen işler (telafi + 30 dk'da bir en çok 3 yeniden deneme), sağlık özeti |
| `notify.py`, `disk_watch.py` | e-posta raporu; harici disk takılınca tetikleme (`{disk}\Yedek`) |

Arayüz: `ui/widgets/backup_center_widget.py` (+ `backup_job_dialog.py`, `backup_target_dialog.py`, `backup_runner.py`).
Arka plan ajanı (TOYA kapalıyken): `python -m src.desktop.backup_agent --due` (Görev Zamanlayıcı'ya `--register`).

## Önemli kurallar
- Yedek **doğrulanmadan başarılı sayılmaz**; bulut yüklemesi başarısızsa sonuç "Uyarı" (dış kopya yok).
- Şifreleme parolası kaybolursa şifreli yedekler açılamaz (arayüz uyarır).
- Geri yükleme çalışan uygulamada yapılmaz: hazırlanır, **bir sonraki açılışta** (`main.py`, veritabanı açılmadan önce)
  uygulanır; mevcut veritabanı `data/restore_previous/` altına saklanır.
- Bilinen sınırlar: gerçek Google Drive/S3/FTPS sunucusu ve gerçek Görev Zamanlayıcı kaydı canlı denenmedi;
  OneDrive/SFTP yok; ajan varsayılan veritabanını (`data/app.db`) kullanır; SQLCipher yolu test edilmedi.
