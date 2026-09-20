<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

web_session();
$auth = web_auth();
if (!$auth->hasAnyUser()) {
    http_response_code(503);
    web_header('Giriş');
    echo '<div class="card" style="max-width:420px;margin:40px auto"><h1>Kullanıcı yok</h1>'
        . '<div class="err">Bu portalda hiç kullanıcı tanımlı değil. Kurulum eksik kalmış olabilir; sunucudaki '
        . '<code>storage/install.lock</code> dosyasını silip <code>install.php</code> ile kurulumu yeniden yapın.</div></div>';
    web_footer();
    exit;
}
if (web_user() !== null) {
    header('Location: index.php');
    exit;
}
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    web_check_csrf();
    $r = $auth->authenticate((string)($_POST['username'] ?? ''), (string)($_POST['password'] ?? ''));
    if ($r['ok']) {
        session_regenerate_id(true);
        $_SESSION['user'] = ['id' => (int)$r['user']['id'], 'username' => $r['user']['username'], 'role' => $r['user']['role']];
        $_SESSION['csrf'] = bin2hex(random_bytes(16));
        header('Location: index.php');
        exit;
    }
    $error = $r['error'] === 'locked'
        ? 'Çok fazla hatalı deneme. Hesap 15 dakika kilitlendi.'
        : 'Kullanıcı adı veya parola hatalı.';
}
web_header('Giriş');
?>
<div class="card" style="max-width:380px;margin:40px auto">
  <h1>Giriş</h1>
  <?php if ($error): ?><div class="err"><?= h($error) ?></div><?php endif; ?>
  <form method="post" autocomplete="on">
    <input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>">
    <label for="u">Kullanıcı adı</label><input id="u" name="username" required autofocus style="width:100%">
    <label for="p">Parola</label><input id="p" name="password" type="password" required style="width:100%">
    <p><button style="width:100%">Giriş yap</button></p>
  </form>
</div>
<?php web_footer();
