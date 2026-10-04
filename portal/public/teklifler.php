<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login();
$svc = portal_service();
$tabs = [
    'bekleyen' => 'Cevap Bekleyen', 'karsi' => 'Karşı Teklif Gelen', 'kabul' => 'Kabul Edilen',
    'red' => 'Reddedilen', 'suresi' => 'Süresi Dolan', 'iptal' => 'İptal', 'tumu' => 'Tümü',
];
$f = (string)($_GET['d'] ?? 'bekleyen');
if (!isset($tabs[$f])) {
    $f = 'bekleyen';
}
$counts = $svc->counts();
$rows = $svc->listPublications($f);
$label = [
    'published' => ['Cevap bekliyor', 'st-wait'], 'accepted' => ['Kabul edildi', 'st-ok'], 'rejected' => ['Reddedildi', 'st-bad'],
    'expired' => ['Süresi doldu', 'st-mut'], 'revoked' => ['İptal edildi', 'st-mut'],
];
web_header('Teklifler', $user);
?>
<style>
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.tabs a{padding:6px 12px;border:1px solid var(--line);border-radius:999px;text-decoration:none;color:var(--ink);background:var(--card);font-size:13px;font-weight:600}
.tabs a.on{background:var(--pri);color:#fff;border-color:var(--pri)}
.tabs .c{opacity:.75;margin-left:4px}
.st{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700}
.st-wait{background:#dbeafe;color:#1e40af}.st-ok{background:#dcfce7;color:var(--ok)}.st-bad{background:#fee2e2;color:var(--bad)}.st-mut{background:var(--line);color:var(--mut)}
.st-cnt{background:#fef3c7;color:#92400e}
</style>
<h1>Teklifler</h1>
<div class="tabs">
<?php foreach ($tabs as $k => $t): ?>
  <a href="teklifler.php?d=<?= h($k) ?>" class="<?= $k === $f ? 'on' : '' ?>"><?= h($t) ?><span class="c"><?= (int)($counts[$k] ?? 0) ?></span></a>
<?php endforeach; ?>
</div>
<div class="card"><table>
  <tr><th>No</th><th>Müşteri</th><th class="hide-m">Başlık</th><th class="n">Tutar</th><th class="hide-m">Geçerlilik</th><th>Durum</th><th class="n hide-m">Görüntüleme</th></tr>
<?php foreach ($rows as $r):
    $cnt = $r['status'] === 'published' && $r['action_taken'] === 'countered';
    [$txt, $cls] = $cnt ? ['Karşı teklif geldi', 'st-cnt'] : ($label[$r['status']] ?? [$r['status'], 'st-mut']); ?>
  <tr><td><a href="teklif.php?id=<?= (int)$r['id'] ?>"><?= h($r['external_ref']) ?></a></td>
      <td><?= h($r['customer_name']) ?></td><td class="hide-m"><?= h($r['title']) ?></td>
      <td class="n"><?= h(money($r['grand_total'])) ?> <?= h($r['currency']) ?></td>
      <td class="hide-m"><?= h(fdate($r['valid_until'])) ?></td>
      <td><span class="st <?= h($cls) ?>"><?= h($txt) ?></span><?php if ($cnt): ?> <span class="mut"><?= h(money($r['counter_amount'])) ?></span><?php endif; ?></td>
      <td class="n hide-m"><?= (int)$r['view_count'] ?></td></tr>
<?php endforeach; if (!$rows): ?><tr><td colspan="7" class="mut">Bu bölümde teklif yok.</td></tr><?php endif; ?>
</table></div>
<p class="mut">Geçerlilik tarihi geçen ve karar verilmemiş teklifler otomatik olarak "Süresi doldu" olur; müşteri bağlantısı kapanır.</p>
<?php web_footer();
