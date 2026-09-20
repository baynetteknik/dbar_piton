<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

// Yalnızca giriş yapmış yönetici. Geri yükleme bilerek web'den YAPILMAZ (yalnızca komut satırı).
$user = web_require_login('admin');
$rep = web_reports();
$bk = portal_backup();
$msg = '';
$err = '';

// İndirme: yönetici oturumu + doğrulanmış yedek adı (yol gezintisi yok).
if (isset($_GET['download'])) {
    $p = $bk->path((string)$_GET['download']);
    if ($p === null) {
        http_response_code(404);
        echo 'Bulunamadı.';
        exit;
    }
    header('Content-Type: application/gzip');
    header('Content-Length: ' . filesize($p));
    header('Content-Disposition: attachment; filename="' . basename($p) . '"');
    header('Cache-Control: no-store');
    readfile($p);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    web_check_csrf();
    if (($_POST['action'] ?? '') === 'create') {
        $r = $bk->create();
        if ($r['ok']) {
            $pruned = $bk->applyRetention();
            $msg = "Yedek alındı: {$r['name']} ({$r['tables']} tablo, {$r['rows']} satır)" . ($pruned ? "; $pruned eski yedek silindi." : '.');
        } else {
            $err = $r['error'];
        }
    }
}

web_header('Yedekleme', $user, null, $rep->sources());
$list = $bk->list();
$keep = $bk->keep();
$root = dirname(__DIR__);
?>
<h1>Veritabanı Yedekleme</h1>
<?php if ($msg): ?><div class="okm"><?= h($msg) ?></div><?php endif; ?>
<?php if ($err): ?><div class="err"><?= h($err) ?></div><?php endif; ?>
<div class="card">
  <form method="post" class="row"><input type="hidden" name="csrf" value="<?= h(web_csrf()) ?>"><input type="hidden" name="action" value="create">
    <button>Şimdi yedek al</button><span class="mut">En yeni <?= $keep ?> yedek saklanır (config: <code>backup_keep</code>).</span></form>
</div>
<div class="card"><table>
  <tr><th>Tarih (UTC)</th><th>Dosya</th><th class="n">Boyut</th><th></th></tr>
<?php foreach ($list as $b): ?>
  <tr><td><?= h($b['created']) ?></td><td><?= h($b['name']) ?></td><td class="n"><?= h(number_format($b['size'] / 1024, 1, ',', '.')) ?> KB</td>
      <td><a href="backup.php?download=<?= h(urlencode($b['name'])) ?>">İndir</a></td></tr>
<?php endforeach; if (!$list): ?><tr><td colspan="4" class="mut">Henüz yedek yok.</td></tr><?php endif; ?>
</table></div>
<div class="card"><h1>Otomatik yedek ve geri yükleme</h1>
  <p class="mut"><strong>Otomatik yedek (cPanel → Cron Jobs):</strong><br><code>0 3 * * * php <?= h($root) ?>/bin/backup.php create</code></p>
  <p class="mut"><strong>Dış kopya:</strong> yedekler sunucuda durduğu sürece sunucu arızasına karşı koruma sağlamaz. TOYA masaüstü, ajan API anahtarıyla en son yedeği kendi bilgisayarına indirebilir.</p>
  <p class="mut"><strong>Geri yükleme</strong> yalnızca komut satırından yapılır (mevcut tabloların üzerine yazdığı için): <code>php <?= h($root) ?>/bin/backup.php restore &lt;yedek-adı&gt; --yes</code> — önce otomatik güvenlik yedeği alınır.</p>
  <p class="mut">Yedekler yapılandırma dosyasını (gizli anahtarlar) içermez; yalnızca veritabanı içeriğini taşır.</p></div>
<?php web_footer();
