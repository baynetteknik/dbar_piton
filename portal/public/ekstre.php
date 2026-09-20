<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login();
$rep = web_reports();
$sources = $rep->sources();
$src = web_source($rep);
$c = (string)($_GET['c'] ?? '');
$cari = $src !== null ? $rep->cari($src, $c) : null;
web_header('Cari Ekstresi', $user, $src, $sources);
if ($cari === null) { echo '<div class="card">Cari bulunamadı.</div>'; web_footer(); exit; }
$dateRe = '/^\d{4}-\d{2}-\d{2}$/';
$from = preg_match($dateRe, (string)($_GET['from'] ?? '')) ? $_GET['from'] . ' 00:00:00' : null;
$to = preg_match($dateRe, (string)($_GET['to'] ?? '')) ? $_GET['to'] . ' 23:59:59' : null;
$e = $rep->ekstre($src, $c, $from, $to);
?>
<h1><?= h($cari['unvan']) ?> <span class="mut">(<?= h($cari['cari_kodu']) ?>)</span></h1>
<form method="get" class="row card"><input type="hidden" name="s" value="<?= h($src) ?>"><input type="hidden" name="c" value="<?= h($c) ?>">
  <div><label>Başlangıç</label><input type="date" name="from" value="<?= h($_GET['from'] ?? '') ?>"></div>
  <div><label>Bitiş</label><input type="date" name="to" value="<?= h($_GET['to'] ?? '') ?>"></div><button>Göster</button></form>
<div class="card"><table>
  <tr><th>Tarih</th><th>Evrak</th><th class="hide-m">Açıklama</th><th class="n">Borç</th><th class="n">Alacak</th><th class="n">Bakiye</th></tr>
<?php if ($from !== null): ?><tr><td colspan="5" class="mut">Devir</td><td class="n"><?= h(money($e['devir'])) ?></td></tr><?php endif; ?>
<?php foreach ($e['satirlar'] as $r): ?>
  <tr><td><?= h(fdate($r['tarihi'])) ?></td>
      <td><?php if (!empty($r['ilgili_ext_id'])): ?><a href="fatura.php?s=<?= h(urlencode($src)) ?>&amp;id=<?= h(urlencode((string)$r['ilgili_ext_id'])) ?>"><?= h($r['evrak_no']) ?></a><?php else: ?><?= h($r['evrak_no']) ?><?php endif; ?></td>
      <td class="hide-m"><?= h($r['aciklama']) ?></td>
      <td class="n"><?= $r['borc'] ? h(money($r['borc'])) : '' ?></td><td class="n"><?= $r['alacak'] ? h(money($r['alacak'])) : '' ?></td>
      <td class="n"><?= h(money($r['bakiye'])) ?></td></tr>
<?php endforeach; if (!$e['satirlar']): ?><tr><td colspan="6" class="mut">Hareket yok.</td></tr><?php endif; ?>
</table><p><strong>Bakiye: <?= h(money($e['bakiye'])) ?></strong></p></div>
<?php web_footer();
