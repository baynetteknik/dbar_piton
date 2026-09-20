<?php
// Bu dosyayı config.local.php olarak kopyalayıp doldurun (config.local.php repoya girmez).
return [
    'db_dsn'        => 'mysql:host=localhost;dbname=CPANEL_KULLANICI_toyaportal;charset=utf8mb4',
    'db_user'       => 'CPANEL_KULLANICI_toya',
    'db_pass'       => 'DEGISTIR',
    // Masaüstü ajanının X-API-Key başlığında göndereceği uzun rastgele anahtar
    'agent_api_key' => 'DEGISTIR-en-az-40-karakter-rastgele',
    'token_days'    => 30,
    // Portal kullanıcı hesabı üst sınırı (kullanıcı girişi adımında uygulanacak). Daha fazlası için
    // paylaşımlı hosting yerine kiralık sunucu (VPS) önerilir.
    'max_users'     => 5,
    // Güncelleme paketlerinin imzasını doğrulayan gizli anahtar. TOYA masaüstündeki 'portal.update_secret'
    // ile AYNI olmalı; en az 32 rastgele karakter. Boşsa güncelleme kapalıdır.
    'update_secret' => 'DEGISTIR-en-az-32-karakter-rastgele',
    // Sunucuda saklanacak en yeni veritabanı yedeği sayısı (bin/backup.php create ve web'den alınan yedekler).
    'backup_keep'   => 14,
    'base_url'      => 'https://ORNEK.com/portal',
];
