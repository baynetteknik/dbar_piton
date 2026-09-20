<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

use Toya\Portal\UpdateException;
use Toya\Portal\Updater;

// Yalnızca giriş yapmış yönetici (koşulsuz). Kurulum ayrıca paket imzası doğrulamasından geçer.
$user = web_require_login('admin');
$rep = web_reports();
$root = dirname(__DIR__);
$inbox = $root . '/update_inbox';
$secret = (string)(portal_config()['update_secret'] ?? '');
$updater = new Updater(portal_pdo(), $root, $secret);

if (!is_dir($inbox)) {
    @mkdir($inbox, 0755, true);
}

$msg = '';
$err = '';
$result = null;

/** Yalnızca güvenli bir dosya adı (toya-portal-X.Y.Z.zip) kabul edilir. */
function safe_package_name(string $n): ?string
{
    $n = basename($n);
    return preg_match('/^toya-portal-\d+\.\d+\.\d+\.zip$/', $n) ? $n : null;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    web_check_csrf();
    $action = (string)($_POST['action'] ?? '');

    if ($action === 'upload') {
        $f = $_FILES['package'] ?? null;
        $name = $f ? safe_package_name((string)($f['name'] ?? '')) : null;
        if (!$f || ($f['error'] ?? 1) !== UPLOAD_ERR_OK) {
            $err = 'Dosya yüklenemedi.';
        } elseif ($name === null) {
            $err = 'Dosya adı toya-portal-X.Y.Z.zip biçiminde olmalıdır.';
        } elseif (($f['size'] ?? 0) > 64 * 1024 * 1024) {
            $err = 'Dosya çok büyük (en fazla 64 MB).';
        } elseif (!move_uploaded_file($f['tmp_name'], $inbox . '/' . $name)) {
            $err = 'Dosya kaydedilemedi (klasör yazma izni?).';
        } else {
            $msg = "$name yüklendi. Aşağıdan doğrulayıp kurabilirsiniz.";
        }
    } elseif ($action === 'apply') {
        $name = safe_package_name((string)($_POST['package'] ?? ''));
        if ($name === null || !is_file($inbox . '/' . $name)) {
            $err = 'Paket bulunamadı.';
        } else {
            $result = $updater->apply($inbox . '/' . $name, !empty($_POST['reinstall']));
            if ($result['ok']) {
                $done = $root . '/storage/applied';
                if (!is_dir($done)) {
                    @mkdir($done, 0755, true);
                }
                @rename($inbox . '/' . $name, $done . '/' . $name);
            }
        }
    }
}

web_header('Güncelleme', $user, null, $rep->sources());
$current = $updater->currentVersion();
$packages = [];
foreach (glob($inbox . '/toya-portal-*.zip') ?: [] as $p) {
    $n = safe_package_name($p);
    if ($n === null) {
        continue;
    }
    $status = ['ok' => false, 'text' => ''];
    try {
        $m = $updater->verify($p);
        $status = ['ok' => true, 'text' => 'Geçerli · sürüm ' . $m['version'] . ' · ' . count($m['files']) . ' dosya'];
    } catch (UpdateException $e) {
        $status['text'] = $e->getMessage();
    }
    $packages[] = ['name' => $n, 'status' => $status];
}
?>
<h1>Portal Güncelleme <span class="mut">(kurulu sürüm <?= h($current) ?>)</span></h1>
<?php if ($secret === ''): ?>
  <div class="err"><code>update_secret</code> tanımlı değil; güncelleme kapalıdır. <code>config.local.php</code> içine ekleyin.</div>
<?php endif; ?>
<?php if ($msg): ?><div class="okm"><?= h($msg) ?></div><?php endif; ?>
<?php if ($err): ?><div class="err"><?= h($err) ?></div><?php endif; ?>
<?php if ($result !== null): ?>
  <?php if ($result['ok']): ?>
    <div class="okm">Kuruldu: <?= h($result['from']) ?> → <?= h($result['to']) ?> · <?= (int)$result['files'] ?> dosya · yedek: <?= h($result['backup'] ?? 'yok') ?>
      <?php if (!empty($result['migrations']['executed'])): ?><br>Migrasyonlar: <?= h(implode(', ', $result['migrations']['executed'])) ?><?php endif; ?></div>
  <?php else: ?>
    <div class="err">Kurulum başarısız: <?= h($result['error']) ?><?= $result['restored'] ? ' — dosyalar önceki sürüme geri yüklendi.' : '' ?></div>
  <?php endif; ?>
<?php endif; ?>

<div class="card"><h1>Yüklenmiş paketler</h1>
<?php if (!$packages): ?><p class="mut">Bekleyen paket yok. Aşağıdan yükleyin ya da FTP ile <code>update_inbox/</code> klasörüne atın.</p><?php endif; ?>
<?php foreach ($packages as $p): ?>
  <form method="post" class="row" style="margin-bottom:8px">
    <input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>"><input type="hidden" name="action" value="apply">
    <input type="hidden" name="package" value="<?= h($p['name']) ?>">
    <div style="flex:1"><strong><?= h($p['name']) ?></strong><br><span class="<?= $p['status']['ok'] ? 'credit' : 'debt' ?>"><?= h($p['status']['text']) ?></span></div>
    <button<?= $p['status']['ok'] && $secret !== '' ? '' : ' disabled' ?>>Kur</button>
  </form>
<?php endforeach; ?>
</div>

<div class="card"><h1>Paket yükle</h1>
<form method="post" enctype="multipart/form-data" class="row">
  <input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>"><input type="hidden" name="action" value="upload">
  <div><label>toya-portal-X.Y.Z.zip</label><input type="file" name="package" accept=".zip" required></div><button>Yükle</button>
</form>
<p class="mut">Paket, yalnızca TOYA masaüstünde üretilen imzalı paket olmalıdır; imzası ve her dosyanın özeti kurulumdan önce doğrulanır.
Kurulumdan önce ezilecek dosyalar <code>storage/backups/</code> altına yedeklenir; migrasyon hatasında dosyalar geri yüklenir.</p></div>
<?php web_footer();
