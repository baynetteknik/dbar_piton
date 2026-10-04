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

## ☁ Google Drive geliştirmeleri (klasör gezgini, servis hesabı, bulutta saklama)

Referans: `C:\xampp\htdocs\toya` (PHP `GoogleDriveDriver`, `gdrive-explorer.php`) — OAuth + servis hesabı, klasör listele/oluştur/seç.

- **Klasör gezgini** (`GoogleDriveFolderDialog`): Drive klasörlerini Windows Gezgini gibi gezme (çift tıkla gir, Yukarı, Drive'ım / Benimle Paylaşılanlar, Yeni Klasör, Yenile); seçilen klasörün kimliği ve görünen yolu hedefte saklanır (`folder_id`, `folder_path`). Ağ çağrıları arka planda.
- **Tam Drive erişimi** seçeneği: mevcut klasörleri görmek için (`drive` kapsamı). Varsayılan kapsam yalnız TOYA'nın oluşturduğu dosyalardır (`drive.file`).
- **Servis hesabı** (JSON anahtarı, RS256 JWT): paylaşılan sürücüler / Workspace için. Anahtar yalnızca Windows Kimlik Bilgisi Yöneticisi'nde saklanır.
- **Paylaşılan sürücüler** (`supportsAllDrives`) tüm çağrılarda açık.
- **Saklama kuralı buluta da uygulanır**: yükleme başarılıysa eski kümeler (tam yedek + artımlılar) uzak hedeften de silinir; yalnızca bu işin dosyalarına dokunulur (`file_job.retention_victims`, yerel ve bulutta ortak kural). Önceden yalnızca yerel klasör temizleniyordu, Drive sürekli doluyordu.
- **Harici disk kopyası** (Yedekleme Merkezi → sağ tık): seçili işin aynı kaynak/seçeneklerle, disk takılınca çalışan kopyası (`{disk}\TOYA_Yedek\<iş>`); asıl iş (ör. günlük, Drive'a, artımlı) değişmez.

### Açık maddeler
- [ ] TOYA (veritabanı) işlerinde artımlı mod yok: veritabanı her zaman tam yedek alınır (artımlı yalnızca dosya/klasör işlerinde).
- [ ] Drive'a klasör aynası (yalnız değişen dosyaları ağaç yapısıyla yükleme) — şu an arşiv (zip/tar) yüklenir.
- [ ] Drive'dan geri yükleme penceresinde dosya listesi (indirme altyapısı hazır: `GoogleDriveProvider.download`).
- [ ] Gerçek Google hesabıyla canlı deneme (testler sahte HTTP ile yapıldı).

## Yedek diskleri, JSON içe aktarma, bildirim seçenekleri, pano

- **Yedek Diskleri** (Yedekleme Merkezi › ⋯ menüsü): harici disk Windows birim seri numarasıyla kaydedilir (`backup.disks` ayarı, `disk_registry.py`). Sürücü harfi/etiket değişse de disk tanınır. İş hedefi `{disk:KIMLIK}\TOYA_Yedek` (işte "💽 Diskten…"), zamanlama "disk takılınca" kayıtlı diskle eşleşir; disk yoksa hedef atlanır ve not düşülür. Silme yalnız listeden gizler.
- **Google JSON içe aktarma** (hedef penceresi): OAuth istemci JSON'u (`installed`) client_id/secret'ı doldurur; `service_account` JSON'u kimlik bilgisi olarak saklanır.
- **Bildirim**: olaylar (başarılı, uyarı, hata, değişiklik yok) ve kanallar (e-posta, uygulama içi) çoklu seçilir; eski `mode` alanı geriye dönük türetilir.
- **Yedekleme Panosu** (merkezin altı, açılır/kapanır, durumu hatırlanır): tarih aralığı (24 sa/7 gün/1 ay/özel) ve iş filtresi, KPI kartları, zaman çizelgesi çubuk grafiği (tam=mavi kalın, artımlı=yeşil ince, hata=kırmızı "!"; üzerine gelince ayrıntı, tıklayınca log penceresi), hedef disk halka grafiği (dilim tıklayınca en büyük yedek dosyaları), süre/hız çizgi grafiği ve "Son Yedekleme İşlemleri" tablosu (Logları İncele). Veri kaynağı: DataTransferLog kayıtları (`history.py`).

## Bağlı kullanıcı, durum popup'ı, geri yükleme, hedef sonuçları

- **Bağlı kullanıcı kontrolü** (`presence.py`): her TOYA oturumu 30 sn'de bir `presence.<oturum>` ayarına zaman damgası yazar. Yedek başlamadan önce son 90 sn'de işaret veren başka oturum varsa yedek **bekler** (kuyrukta durur, dakikalık denetimde yeniden denenir, herkes çıkınca başlar). Ayar: `backup.wait_if_users` (varsayılan açık). "Şimdi Çalıştır" bağlı kullanıcıları gösterip onay ister.
- **Durum popup'ı** (`backup_status_popup.py`): ana pencerenin sağ altında aşama + ilerleme; yedek sürerken kullanıcı klavye/fare kullanırsa "işlem yapmayın" uyarısı; bekleyen yedek de burada duyurulur.
- **Hedef sonuçları**: her çalışmada klasör/disk + her dış hedef (Drive, FTP…) ayrı kaydedilir (`last_targets`); iş listesi "HEDEFLER" sütunu ve sağlık satırı ✔/✘ ile gösterir. Bir hedefe yazılamadıysa iş "uyarı" olur. "Değişiklik yok" sonucu artık başarılı denetim sayılır; iş düzenleme durumu (son çalışma) eski kopyayla ezmez.
- **Geri yükleme**: ana düğmeler arasında "↩ Geri Yükle…" ve "✔ Doğrula". TOYA yedeği yeniden başlatınca uygulanır; dosya yedeği seçilen klasöre çıkarılır. Tüm hazırlama/çıkarma/iptal işlemleri günlüğe yazılır, ⚙ Diğer › "Geri yükleme geçmişi".
- **Pano**: merkezde kompakt (kartlar + işlem tablosu); "⛶ Tam ekran" grafikli tam pencereyi açar. İş listesi standart AppGrid'dir.
