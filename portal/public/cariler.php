<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login();
$rep = web_reports();
$sources = $rep->sources();
$src = web_source($rep);
web_header('Cariler', $user, $src, $sources);
if ($src === null) { echo '<div class="card">Henüz veri yok.</div>'; web_footer(); exit; }
$qtxt = trim((string)($_GET['q'] ?? ''));
$rows = $rep->cariBakiyeleri($src);
if ($qtxt !== '') {
    $rows = array_values(array_filter($rows, static fn($r) =>
        stripos((string)$r['unvan'], $qtxt) !== false || stripos((string)$r['cari_kodu'], $qtxt) !== false));
}
?>
<h1>Cari Bakiyeleri</h1>
<form method="get" class="row card"><input type="hidden" name="s" value="<?= h($src) ?>">
  <div><label>Ara (kod / unvan)</label><input name="q" value="<?= h($qtxt) ?>"></div><button>Ara</button></form>
<div class="card"><table>
  <tr><th>Kod</th><th>Unvan</th><th class="n hide-m">Borç</th><th class="n hide-m">Alacak</th><th class="n">Bakiye</th></tr>
<?php foreach ($rows as $r): $cls = $r['bakiye'] > 0 ? 'debt' : ($r['bakiye'] < 0 ? 'credit' : ''); ?>
  <tr><td><?= h($r['cari_kodu']) ?></td>
      <td><a href="ekstre.php?s=<?= h(urlencode($src)) ?>&amp;c=<?= h(urlencode((string)$r['ext_id'])) ?>"><?= h($r['unvan']) ?></a></td>
      <td class="n hide-m"><?= h(money($r['borc'])) ?></td><td class="n hide-m"><?= h(money($r['alacak'])) ?></td>
      <td class="n <?= $cls ?>"><?= h(money($r['bakiye'])) ?></td></tr>
<?php endforeach; if (!$rows): ?><tr><td colspan="5" class="mut">Kayıt yok.</td></tr><?php endif; ?>
</table></div>
<p class="mut">+ bakiye: müşteri bize borçlu · − bakiye: biz müşteriye borçluyuz.</p>
<?php web_footer();
