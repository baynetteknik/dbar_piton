<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login();
$rep = web_reports();
$sources = $rep->sources();
$src = web_source($rep);
web_header('Özet', $user, $src, $sources);
if ($src === null) {
    echo '<div class="card"><h1>Henüz veri yok</h1><p class="mut">Şirketteki ajan ilk aktarımı yaptığında burada görünecek.</p></div>';
    web_footer();
    exit;
}
$o = $rep->firmaOzeti($src);
?>
<h1>Firma Durumu</h1>
<p class="mut">Kaynak: <?= h($src) ?> · Son aktarım: <?= h($o['son_senkron'] ?? 'bilinmiyor') ?> (UTC)</p>
<div class="grid">
  <div class="card tile"><div class="mut">Toplam alacağımız (müşteri borcu)</div><div class="v debt"><?= h(money($o['toplam_borc'])) ?></div></div>
  <div class="card tile"><div class="mut">Toplam borcumuz</div><div class="v credit"><?= h(money($o['toplam_alacak'])) ?></div></div>
  <div class="card tile"><div class="mut">Satış faturaları</div><div class="v"><?= h(money($o['satis_toplam'])) ?></div><div class="mut"><?= (int)$o['satis_adet'] ?> adet</div></div>
  <div class="card tile"><div class="mut">Alış faturaları</div><div class="v"><?= h(money($o['alis_toplam'])) ?></div><div class="mut"><?= (int)$o['alis_adet'] ?> adet</div></div>
</div>
<?php if ($o['yonu_bilinmeyen_adet'] > 0): ?>
<p class="mut"><?= (int)$o['yonu_bilinmeyen_adet'] ?> faturanın yönü (satış/alış) kaynaktan belirlenemedi; toplamlara dahil değildir.</p>
<?php endif; ?>
<p class="mut">Tutarlar ana para biriminde, cari hareketlerden hesaplanır. Bu ekranlar salt okunurdur.</p>
<?php web_footer();
