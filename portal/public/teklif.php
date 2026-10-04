<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

$user = web_require_login();
$d = portal_service()->detail((int)($_GET['id'] ?? 0));
web_header('Teklif', $user);
if ($d === null) {
    echo '<div class="card">Teklif bulunamadı. <a href="teklifler.php">Listeye dön</a></div>';
    web_footer();
    exit;
}
$p = $d['pub'];
$snap = json_decode((string)$p['snapshot_json'], true) ?: [];
$lines = is_array($snap['lines'] ?? null) ? $snap['lines'] : [];
$https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || ($_SERVER['SERVER_PORT'] ?? '') === '443';
$link = ($https ? 'https://' : 'http://') . ($_SERVER['HTTP_HOST'] ?? '') . rtrim(dirname((string)($_SERVER['SCRIPT_NAME'] ?? '')), '/') . '/view.php?t=' . $p['token'];
$status = [
    'published' => $p['action_taken'] === 'countered' ? 'Karşı teklif geldi' : 'Cevap bekliyor', 'accepted' => 'Kabul edildi',
    'rejected' => 'Reddedildi', 'expired' => 'Süresi doldu', 'revoked' => 'İptal edildi',
][$p['status']] ?? $p['status'];
$evName = [
    'publish' => 'Yayınlandı', 'view' => 'Müşteri görüntüledi', 'accept' => 'Kabul etti', 'reject' => 'Reddetti',
    'counter' => 'Karşı teklif verdi', 'revoke' => 'Yayın iptal edildi', 'expire' => 'Süresi doldu',
];
?>
<p><a href="teklifler.php">← Teklifler</a></p>
<div class="card">
  <h1><?= h($p['title'] ?: ('Teklif ' . $p['external_ref'])) ?></h1>
  <p class="mut"><?= h($p['customer_name']) ?> · No: <?= h($p['external_ref']) ?> · Kaynak: <?= h($p['source']) ?></p>
  <div class="grid">
    <div class="tile"><div class="mut">Durum</div><div class="v" style="font-size:18px"><?= h($status) ?></div></div>
    <div class="tile"><div class="mut">Tutar</div><div class="v" style="font-size:18px"><?= h(money($p['grand_total'])) ?> <?= h($p['currency']) ?></div></div>
    <div class="tile"><div class="mut">Geçerlilik</div><div class="v" style="font-size:18px"><?= h(fdate($p['valid_until']) ?: '—') ?></div></div>
    <div class="tile"><div class="mut">Görüntüleme</div><div class="v" style="font-size:18px"><?= (int)$p['view_count'] ?></div></div>
  </div>
  <?php if ($p['action_taken'] === 'countered'): ?>
    <p><strong>Karşı teklif:</strong> <?= h(money($p['counter_amount'])) ?> <?= h($p['currency']) ?><?= $p['counter_note'] ? ' — ' . h($p['counter_note']) : '' ?></p>
  <?php endif; ?>
  <?php if ($p['decision_note']): ?><p><strong>Müşteri notu:</strong> <?= h($p['decision_note']) ?></p><?php endif; ?>
  <?php if (in_array($p['status'], ['published'], true)): ?>
    <label>Müşteri bağlantısı</label><input readonly style="width:100%" value="<?= h($link) ?>" onclick="this.select()">
  <?php endif; ?>
</div>
<div class="card"><h1>Kalemler</h1><table>
  <tr><th>Ürün / Hizmet</th><th class="n">Miktar</th><th class="n hide-m">Birim Fiyat</th><th class="n">Tutar</th></tr>
<?php foreach ($lines as $l): ?>
  <tr><td><?= h($l['name'] ?? '') ?><?php if (!empty($l['sku'])): ?><div class="mut"><?= h($l['sku']) ?></div><?php endif; ?></td>
      <td class="n"><?= h($l['qty'] ?? '') ?> <?= h($l['unit'] ?? '') ?></td>
      <td class="n hide-m"><?= h(money($l['unit_price'] ?? 0)) ?></td><td class="n"><?= h(money($l['total'] ?? 0)) ?></td></tr>
<?php endforeach; if (!$lines): ?><tr><td colspan="4" class="mut">Kalem yok.</td></tr><?php endif; ?>
</table></div>
<div class="card"><h1>Geçmiş</h1><table>
<?php foreach ($d['events'] as $e): ?>
  <tr><td><?= h($e['created_at']) ?> UTC</td><td><?= h($evName[$e['event_type']] ?? $e['event_type']) ?></td>
      <td class="mut hide-m"><?= h($e['ip_address'] ?? '') ?></td></tr>
<?php endforeach; ?>
</table></div>
<?php web_footer();
