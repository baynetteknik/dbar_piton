<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login('admin');
$rep = web_reports();
$mirror = portal_mirror();
$status = in_array($_GET['status'] ?? '', ['ok', 'error'], true) ? (string)$_GET['status'] : '';
$source = trim((string)($_GET['source'] ?? ''));
$rows = $mirror->recentLog(200, $status, $source);
web_header('Aktarım Günlüğü', $user, null, $rep->sources());
?>
<h1>Veri Aktarım Günlüğü</h1>
<p class="mut">Şirketteki ajanın portala yaptığı her gönderim ve tur kapatma çağrısı burada saklanır (silinmez). En yeni 200 kayıt.</p>
<form method="get" class="row card">
  <div><label>Durum</label><select name="status"><option value="">Hepsi</option>
    <option value="ok"<?= $status === 'ok' ? ' selected' : '' ?>>Başarılı</option>
    <option value="error"<?= $status === 'error' ? ' selected' : '' ?>>Hatalı</option></select></div>
  <div><label>Kaynak</label><input name="source" value="<?= h($source) ?>"></div><button>Filtrele</button></form>
<div class="card"><table>
  <tr><th>Zaman (UTC)</th><th>İşlem</th><th class="hide-m">Kaynak</th><th>Varlık</th><th>Durum</th>
      <th class="n">Gelen</th><th class="n">Yeni</th><th class="n">Güncel</th><th class="n">Kayıp</th><th class="hide-m">Not</th></tr>
<?php foreach ($rows as $r): ?>
  <tr><td><?= h($r['created_at']) ?></td><td><?= h($r['action']) ?></td><td class="hide-m"><?= h($r['source']) ?></td>
      <td><?= h($r['entity']) ?></td><td class="<?= $r['status'] === 'ok' ? 'credit' : 'debt' ?>"><?= $r['status'] === 'ok' ? 'Başarılı' : 'Hatalı' ?></td>
      <td class="n"><?= (int)$r['received'] ?></td><td class="n"><?= (int)$r['added'] ?></td><td class="n"><?= (int)$r['updated'] ?></td><td class="n"><?= (int)$r['vanished'] ?></td>
      <td class="hide-m"><?= h($r['message']) ?><?= $r['ip_address'] ? ' <span class="mut">' . h($r['ip_address']) . '</span>' : '' ?></td></tr>
<?php endforeach; if (!$rows): ?><tr><td colspan="10" class="mut">Kayıt yok.</td></tr><?php endif; ?>
</table></div>
<?php web_footer();
