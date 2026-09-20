<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login();
$rep = web_reports();
$sources = $rep->sources();
$src = web_source($rep);
web_header('Faturalar', $user, $src, $sources);
if ($src === null) { echo '<div class="card">Henüz veri yok.</div>'; web_footer(); exit; }
$dateRe = '/^\d{4}-\d{2}-\d{2}$/';
$from = preg_match($dateRe, (string)($_GET['from'] ?? '')) ? $_GET['from'] . ' 00:00:00' : null;
$to = preg_match($dateRe, (string)($_GET['to'] ?? '')) ? $_GET['to'] . ' 23:59:59' : null;
$rows = $rep->faturalar($src, $from, $to);
$yon = ['satis' => 'Satış', 'alis' => 'Alış'];
?>
<h1>Faturalar</h1>
<form method="get" class="row card"><input type="hidden" name="s" value="<?= h($src) ?>">
  <div><label>Başlangıç</label><input type="date" name="from" value="<?= h($_GET['from'] ?? '') ?>"></div>
  <div><label>Bitiş</label><input type="date" name="to" value="<?= h($_GET['to'] ?? '') ?>"></div><button>Filtrele</button></form>
<div class="card"><table>
  <tr><th>Tarih</th><th>No</th><th class="hide-m">Yön</th><th>Cari</th><th class="n">Toplam</th></tr>
<?php foreach ($rows as $r): ?>
  <tr><td><?= h(fdate($r['tarihi'])) ?></td>
      <td><a href="fatura.php?s=<?= h(urlencode($src)) ?>&amp;id=<?= h(urlencode((string)$r['ext_id'])) ?>"><?= h($r['fatura_no']) ?></a></td>
      <td class="hide-m"><?= h($yon[$r['yon'] ?? ''] ?? '?') ?></td><td><?= h($r['cari_unvan']) ?></td>
      <td class="n"><?= h(money($r['genel_toplam'])) ?></td></tr>
<?php endforeach; if (!$rows): ?><tr><td colspan="5" class="mut">Kayıt yok.</td></tr><?php endif; ?>
</table></div><p class="mut">İptal edilen faturalar gösterilmez. En fazla 200 kayıt listelenir.</p>
<?php web_footer();
