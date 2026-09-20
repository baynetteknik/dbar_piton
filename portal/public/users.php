<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$me = web_require_login('admin');
$auth = web_auth();
$rep = web_reports();
$msg = '';
$err = '';
$errs = [
    'invalid_username' => 'Kullanıcı adı 3-60 karakter; harf, rakam, . _ - kullanılabilir.',
    'weak_password' => 'Parola en az ' . \Toya\Portal\AuthService::MIN_PASSWORD_LENGTH . ' karakter olmalı.',
    'invalid_role' => 'Geçersiz rol.',
    'username_taken' => 'Bu kullanıcı adı zaten var.',
    'user_limit' => 'Kullanıcı sınırına ulaşıldı (' . $auth->maxUsers() . '). Daha fazlası için kiralık sunucuya geçilmelidir.',
    'last_admin' => 'Son yönetici pasifleştirilemez.',
    'not_found' => 'Kullanıcı bulunamadı.',
];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    web_check_csrf();
    $action = (string)($_POST['action'] ?? '');
    $id = (int)($_POST['id'] ?? 0);
    if ($action === 'create') {
        $r = $auth->createUser((string)($_POST['username'] ?? ''), (string)($_POST['password'] ?? ''), (string)($_POST['role'] ?? 'viewer'));
    } elseif ($action === 'toggle') {
        $u = $auth->getUser($id);
        if ($u !== null && (int)$u['id'] === (int)$me['id'] && (int)$u['active']) {
            $r = ['ok' => false, 'error' => 'not_found'];
            $err = 'Kendi hesabınızı pasifleştiremezsiniz.';
        } else {
            $r = $auth->setActive($id, !($u && (int)$u['active']));
        }
    } elseif ($action === 'password') {
        $r = $auth->setPassword($id, (string)($_POST['password'] ?? ''));
    } else {
        $r = ['ok' => false, 'error' => 'not_found'];
    }
    if ($r['ok']) {
        $msg = 'İşlem tamamlandı.';
    } elseif ($err === '') {
        $err = $errs[$r['error']] ?? 'İşlem başarısız.';
    }
}
web_header('Kullanıcılar', $me, null, $rep->sources());
$users = $auth->listUsers();
?>
<h1>Kullanıcılar <span class="mut">(<?= $auth->activeCount() ?> / <?= $auth->maxUsers() ?> aktif)</span></h1>
<?php if ($msg): ?><div class="okm"><?= h($msg) ?></div><?php endif; ?>
<?php if ($err): ?><div class="err"><?= h($err) ?></div><?php endif; ?>
<div class="card"><table>
  <tr><th>Kullanıcı</th><th>Rol</th><th>Durum</th><th class="hide-m">Son giriş (UTC)</th><th></th></tr>
<?php foreach ($users as $u): ?>
  <tr><td><?= h($u['username']) ?></td><td><?= h($u['role']) ?></td><td><?= (int)$u['active'] ? 'Aktif' : 'Pasif' ?></td>
      <td class="hide-m"><?= h($u['last_login'] ?? '—') ?></td>
      <td>
        <form method="post" class="inline"><input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>"><input type="hidden" name="action" value="toggle"><input type="hidden" name="id" value="<?= (int)$u['id'] ?>">
          <button class="sec"><?= (int)$u['active'] ? 'Pasifleştir' : 'Aktifleştir' ?></button></form>
        <form method="post" class="inline"><input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>"><input type="hidden" name="action" value="password"><input type="hidden" name="id" value="<?= (int)$u['id'] ?>">
          <input type="password" name="password" placeholder="yeni parola" required minlength="10" style="width:130px"><button class="sec">Parolayı değiştir</button></form>
      </td></tr>
<?php endforeach; ?>
</table></div>
<div class="card"><h1>Yeni kullanıcı</h1>
<form method="post" class="row"><input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>"><input type="hidden" name="action" value="create">
  <div><label>Kullanıcı adı</label><input name="username" required></div>
  <div><label>Parola</label><input name="password" type="password" required minlength="10"></div>
  <div><label>Rol</label><select name="role"><option value="viewer">viewer (yalnız görüntüler)</option><option value="admin">admin</option></select></div>
  <button>Ekle</button></form>
<p class="mut">Kullanıcılar silinmez, yalnızca pasifleştirilir.</p></div>
<?php web_footer();
