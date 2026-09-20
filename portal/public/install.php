<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

use Toya\Portal\Installer;

$root = dirname(__DIR__);
$inst = new Installer($root);

// Kurulu portalda sihirbaz yok sayılır (kalıcı kilit).
if ($inst->isInstalled()) {
    http_response_code(404);
    echo 'Bulunamadı.';
    exit;
}
web_session();

if (!$inst->ensureToken()) {
    web_header('Kurulum');
    echo '<div class="card" style="max-width:560px;margin:40px auto"><h1>Kurulum başlatılamadı</h1>'
        . '<div class="err"><code>storage/</code> klasörü oluşturulamıyor veya yazılamıyor. Klasör izinlerini (yazılabilir) düzeltip sayfayı yenileyin.</div></div>';
    web_footer();
    exit;
}

$error = '';
$info = '';
$done = null;

// Anahtar doğrulaması: art arda hatalı denemeler oturumda sınırlanır.
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'token') {
    web_check_csrf();
    $_SESSION['token_fails'] = (int)($_SESSION['token_fails'] ?? 0);
    if ($_SESSION['token_fails'] >= 10) {
        $error = 'Çok fazla hatalı deneme. Tarayıcıyı kapatıp yeniden deneyin.';
    } elseif ($inst->verifyToken((string)($_POST['token'] ?? ''))) {
        $_SESSION['install_ok'] = true;
        $_SESSION['token_fails'] = 0;
    } else {
        $_SESSION['token_fails']++;
        $error = 'Kurulum anahtarı hatalı.';
    }
}
$authorized = !empty($_SESSION['install_ok']);

$in = [
    'host' => 'localhost', 'port' => '3306', 'name' => '', 'user' => '', 'base_url' => '',
    'admin' => '',
];
if ($authorized && $_SERVER['REQUEST_METHOD'] === 'POST' && in_array($_POST['action'] ?? '', ['test', 'install'], true)) {
    web_check_csrf();
    foreach (['host', 'port', 'name', 'user', 'base_url', 'admin'] as $k) {
        $in[$k] = trim((string)($_POST[$k] ?? $in[$k]));
    }
    $db = ['host' => $in['host'], 'port' => $in['port'], 'name' => $in['name'], 'user' => $in['user'], 'pass' => (string)($_POST['pass'] ?? '')];
    if ($_POST['action'] === 'test') {
        $c = $inst->connect($db);
        $c['ok'] ? $info = 'Veritabanı bağlantısı başarılı.' : $error = $c['error'];
    } else {
        $r = $inst->install([
            'db' => $db, 'base_url' => $in['base_url'],
            'admin' => ['username' => $in['admin'], 'password' => (string)($_POST['password'] ?? ''), 'password2' => (string)($_POST['password2'] ?? '')],
        ]);
        if ($r['ok']) {
            $_SESSION = [];
            $done = $r;
        } else {
            $error = $r['error'];
        }
    }
}

if ($in['base_url'] === '') {
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off');
    $in['base_url'] = ($https ? 'https' : 'http') . '://' . ($_SERVER['HTTP_HOST'] ?? 'localhost')
        . rtrim(str_replace('\\', '/', dirname((string)($_SERVER['SCRIPT_NAME'] ?? '/'))), '/');
}

web_header('Kurulum');
echo '<div class="card" style="max-width:640px;margin:24px auto">';

if ($done !== null) { ?>
  <h1>Kurulum tamamlandı ✅</h1>
  <div class="okm">Yönetici hesabı oluşturuldu ve sihirbaz kilitlendi. <a href="login.php">Giriş sayfasına gidin</a>.</div>
  <p><strong>Bu iki anahtarı şimdi TOYA masaüstündeki ayarlara kaydedin</strong> (bu sayfa bir daha gösterilmez; aynı değerler sunucudaki
  <code>config.local.php</code> dosyasında da durur):</p>
  <label>Ajan API anahtarı (Genel Ayarlar → Online Portal → API anahtarı)</label>
  <input readonly value="<?= h($done['keys']['agent_api_key']) ?>" style="width:100%" onclick="this.select()">
  <label>Güncelleme anahtarı (TOYA'daki "Güncelleme Anahtarını Kopyala" ile AYNI olmalı)</label>
  <input readonly value="<?= h($done['keys']['update_secret']) ?>" style="width:100%" onclick="this.select()">
  <p class="mut">Güncelleme anahtarı TOYA'da farklıysa, TOYA'daki "Portal Yayın" panelinden gönderilen paketler imza hatasıyla reddedilir.
  Portal adresi: <code><?= h($done['base_url']) ?></code></p>
<?php } elseif (!$authorized) { ?>
  <h1>Portal kurulumu</h1>
  <p class="mut">Güvenlik için kurulum anahtarı gerekir. Anahtar sunucudaki <code>storage/install_token.txt</code> dosyasındadır;
  FTP veya cPanel Dosya Yöneticisi ile açıp içindeki metni buraya yapıştırın. Kurulum bitince dosya silinir.</p>
  <?php if ($error): ?><div class="err"><?= h($error) ?></div><?php endif; ?>
  <form method="post"><input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>"><input type="hidden" name="action" value="token">
    <label>Kurulum anahtarı</label><input name="token" required autofocus style="width:100%" autocomplete="off">
    <p><button>Devam</button></p></form>
<?php } else { ?>
  <h1>Portal kurulumu</h1>
  <?php if ($error): ?><div class="err"><?= h($error) ?></div><?php endif; ?>
  <?php if ($info): ?><div class="okm"><?= h($info) ?></div><?php endif; ?>
  <table>
    <?php foreach ($inst->requirements() as $r): ?>
      <tr><td><?= $r['ok'] ? '✅' : '❌' ?></td><td><?= h($r['name']) ?> <span class="mut"><?= h($r['detail']) ?></span></td></tr>
    <?php endforeach; ?>
  </table>
  <form method="post"><input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>">
    <h1 style="margin-top:16px">Veritabanı (MySQL)</h1>
    <p class="mut">cPanel → MySQL Veritabanları'ndan önce bir veritabanı ve kullanıcı oluşturup kullanıcıya tüm yetkileri verin.</p>
    <div class="row">
      <div><label>Sunucu</label><input name="host" value="<?= h($in['host']) ?>" required></div>
      <div><label>Port</label><input name="port" value="<?= h($in['port']) ?>" size="6" required></div>
    </div>
    <label>Veritabanı adı</label><input name="name" value="<?= h($in['name']) ?>" required style="width:100%">
    <label>Kullanıcı</label><input name="user" value="<?= h($in['user']) ?>" required style="width:100%">
    <label>Parola</label><input name="pass" type="password" style="width:100%" autocomplete="off">
    <p><button name="action" value="test" class="sec" formnovalidate>Bağlantıyı test et</button></p>

    <h1 style="margin-top:16px">Yönetici hesabı</h1>
    <label>Kullanıcı adı</label><input name="admin" value="<?= h($in['admin']) ?>" required style="width:100%">
    <label>Parola (en az <?= (int)\Toya\Portal\AuthService::MIN_PASSWORD_LENGTH ?> karakter)</label><input name="password" type="password" required style="width:100%" autocomplete="new-password">
    <label>Parola (tekrar)</label><input name="password2" type="password" required style="width:100%" autocomplete="new-password">

    <h1 style="margin-top:16px">Adres</h1>
    <label>Portalın internet adresi (public klasörünün adresi)</label><input name="base_url" value="<?= h($in['base_url']) ?>" style="width:100%">
    <p><button name="action" value="install"<?= $inst->requirementsMet() ? '' : ' disabled' ?>>Kurulumu tamamla</button></p>
  </form>
<?php }
echo '</div>';
web_footer();
