<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login();
$rep = web_reports();
$sources = $rep->sources();
$src = web_source($rep);
web_header('Fatura', $user, $src, $sources);
$d = $src !== null ? $rep->fatura($src, (string)($_GET['id'] ?? '')) : null;
if ($d === null) { echo '<div class="card">Fatura bulunamadı.</div>'; web_footer(); exit; }
$f = $d['fatura'];
$yon = ['satis' => 'Satış', 'alis' => 'Alış'];
?>
<h1>Fatura <?= h($f['fatura_no']) ?></h1>
<div class="card"><p><?= h($f['cari_unvan']) ?> · <?= h(fdate($f['tarihi'])) ?> · <?= h($yon[$f['yon'] ?? ''] ?? 'Yön belirsiz') ?></p>
<table>
  <tr><th>Stok</th><th class="n hide-m">Miktar</th><th class="n">Fiyat</th><th class="n">Tutar</th><th class="n hide-m">KDV dahil</th></tr>
<?php foreach ($d['kalemler'] as $k): ?>
  <tr><td><?= h($k['stok_adi']) ?> <span class="mut"><?= h($k['stok_kodu']) ?></span></td>
      <td class="n hide-m"><?= h(rtrim(rtrim(number_format((float)$k['miktar'], 3, ',', '.'), '0'), ',')) ?> <?= h($k['birim']) ?></td>
      <td class="n"><?= h(money($k['fiyat'])) ?></td><td class="n"><?= h(money($k['tutar'])) ?></td>
      <td class="n hide-m"><?= h(money($k['kdvli_tutar'])) ?></td></tr>
<?php endforeach; if (!$d['kalemler']): ?><tr><td colspan="5" class="mut">Kalem yok.</td></tr><?php endif; ?>
</table>
<p style="text-align:right">Ara toplam: <?= h(money($f['ara_toplam'])) ?> · İskonto: <?= h(money($f['iskonto'])) ?> · KDV: <?= h(money($f['kdv'])) ?><br>
<strong>Genel toplam: <?= h(money($f['genel_toplam'])) ?></strong></p></div>
<?php web_footer();
