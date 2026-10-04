<?php
declare(strict_types=1);

// Kullanım: php portal/tests/run.php   (PHPUnit gerektirmez; SQLite bellek DB'si kullanır)

require __DIR__ . '/../src/bootstrap.php';

use Toya\Portal\PortalService;

$passed = 0;
$failed = 0;
$now = 1_800_000_000; // sabit saat, testler süre dolmasını kontrol eder

/**
 * Varsayılan: SQLite bellek DB'si. `PORTAL_TEST_MYSQL_HOST` ortam değişkeni verilirse her db() çağrısı
 * gerçek bir MySQL/MariaDB sunucusunda geçici bir veritabanı oluşturur (migrations/ klasörü Migrator ile uygulanır) ve test bitince siler.
 * (İsteğe bağlı: PORTAL_TEST_MYSQL_USER, PORTAL_TEST_MYSQL_PASS.)
 */
function db(): PDO
{
    $host = getenv('PORTAL_TEST_MYSQL_HOST');
    if (!$host) {
        $pdo = new PDO('sqlite::memory:');
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->exec((string)file_get_contents(__DIR__ . '/../sql/schema.sqlite.sql'));
        return $pdo;
    }
    static $n = 0;
    static $created = [];
    $user = getenv('PORTAL_TEST_MYSQL_USER') ?: 'root';
    $pass = getenv('PORTAL_TEST_MYSQL_PASS') ?: '';
    $opts = [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION];
    $name = 'tpt_' . getmypid() . '_' . (++$n);
    $admin = new PDO("mysql:host=$host;charset=utf8mb4", $user, $pass, $opts);
    $admin->exec("CREATE DATABASE `$name` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
    if ($created === []) {
        register_shutdown_function(static function () use (&$created, $host, $user, $pass) {
            $a = new PDO("mysql:host=$host;charset=utf8mb4", $user, $pass);
            foreach ($created as $db) {
                $a->exec("DROP DATABASE IF EXISTS `$db`");
            }
        });
    }
    $created[] = $name;
    $pdo = new PDO("mysql:host=$host;dbname=$name;charset=utf8mb4", $user, $pass, $opts);
    $m = (new Toya\Portal\Migrator($pdo, __DIR__ . '/../migrations'))->migrate();
    if (!$m['ok']) {
        throw new RuntimeException('Migrasyon başarısız: ' . $m['error']);
    }
    return $pdo;
}

function check(string $name, bool $cond): void
{
    global $passed, $failed;
    if ($cond) {
        $passed++;
        echo "  ok   $name\n";
    } else {
        $failed++;
        echo "  FAIL $name\n";
    }
}

function payload(array $over = []): array
{
    return $over + [
        'source' => 'toya', 'external_ref' => 'TKL-001', 'title' => 'Test Teklifi',
        'customer_name' => 'ACME A.Ş.', 'currency' => 'TRY', 'grand_total' => 1200.5,
        'snapshot' => ['lines' => [['name' => 'Ürün A', 'qty' => 2, 'unit_price' => 500]]],
    ];
}

echo "publish\n";
$clock = $now;
$svc = new PortalService(db(), 30, function () use (&$clock) { return $clock; });
$r = $svc->publish(payload());
check('yeni yayın token üretir (64 hex)', $r['ok'] && preg_match('/^[0-9a-f]{64}$/', $r['token']) === 1);
$token = $r['token'];
$r2 = $svc->publish(payload(['title' => 'Güncel']));
check('aynı teklifi tekrar yayınlamak aynı token’ı korur', $r2['ok'] && $r2['token'] === $token);
check('eksik payload reddedilir', $svc->publish(['source' => 'toya'])['error'] === 'invalid_payload');

echo "view\n";
$v = $svc->view($token, '1.1.1.1', 'UA');
check('geçerli token görüntülenir', $v['ok'] && $v['data']['title'] === 'Güncel');
check('kalemler snapshot içinde döner', $v['data']['snapshot']['lines'][0]['name'] === 'Ürün A');
check('iç alanlar (token, id) sızmaz', !isset($v['data']['token']) && !isset($v['data']['id']));
$svc->view($token, '1.1.1.1', 'UA');
$svc->view($token, '2.2.2.2', 'UA');
$pdo = db();
check('geçersiz biçimli token not_found', $svc->view('abc')['error'] === 'not_found');
check('bilinmeyen token not_found', $svc->view(str_repeat('a', 64))['error'] === 'not_found');

echo "view sayacı\n";
$c2 = $now;
$pdo2 = db();
$s2 = new PortalService($pdo2, 30, function () use (&$c2) { return $c2; });
$t2 = $s2->publish(payload())['token'];
$s2->view($t2, '1.1.1.1', 'UA');
$s2->view($t2, '1.1.1.1', 'UA'); // aynı ip+ua, 30 dk içinde: sayılmaz
$s2->view($t2, '9.9.9.9', 'UA'); // farklı ip: sayılır
$cnt = (int)$pdo2->query('SELECT view_count FROM portal_publications')->fetchColumn();
check('aynı ip+ua tekrar sayılmaz, farklı ip sayılır (=2)', $cnt === 2);
$c2 += 1900;
$s2->view($t2, '1.1.1.1', 'UA');
check('30 dk sonra tekrar sayılır (=3)', (int)$pdo2->query('SELECT view_count FROM portal_publications')->fetchColumn() === 3);

echo "kabul / ret\n";
$c3 = $now;
$pdo3 = db();
$s3 = new PortalService($pdo3, 30, function () use (&$c3) { return $c3; });
$t3 = $s3->publish(payload())['token'];
check('kabul başarılı', $s3->decide($t3, 'accept', 'Onaylıyoruz')['ok']);
check('durum accepted olur', $s3->view($t3)['data']['status'] === 'accepted');
check('kabulden sonra ret yapılamaz', $s3->decide($t3, 'reject')['error'] === 'already_decided');
check('kabulden sonra tekrar yayınlanamaz', $s3->publish(payload())['error'] === 'already_decided');

$t4 = $s3->publish(payload(['external_ref' => 'TKL-002']))['token'];
check('ret başarılı', $s3->decide($t4, 'reject', 'Pahalı')['ok']);
check('durum rejected olur', $s3->view($t4)['data']['status'] === 'rejected');
check('geçersiz aksiyon reddedilir', $s3->decide($t4, 'foo')['error'] === 'invalid_action');

echo "karşı teklif\n";
$t5 = $s3->publish(payload(['external_ref' => 'TKL-003']))['token'];
check('tutarsız karşı teklif reddedilir', $s3->decide($t5, 'counter', 'x', 0)['error'] === 'invalid_amount');
check('karşı teklif kaydedilir', $s3->decide($t5, 'counter', 'İndirim', 900.0)['ok']);
$vv = $s3->view($t5)['data'];
check('karşı teklif durumu değiştirmez', $vv['status'] === 'published' && $vv['action_taken'] === 'countered');
check('ikinci karşı teklif (tekrar indirim isteme) engellenir', $s3->decide($t5, 'counter', 'Daha', 800.0)['error'] === 'counter_already_sent');
check('karşı tekliften sonra kabul edilebilir', $s3->decide($t5, 'accept')['ok']);

echo "geçerlilik tarihi (valid_until) ve yönetici listesi\n";
$cv = $now;
$sv = new PortalService(db(), 365, function () use (&$cv) { return $cv; });
$vu = gmdate('Y-m-d H:i:s', $now + 2 * 86400);
$tv1 = $sv->publish(payload(['external_ref' => 'V1', 'valid_until' => $vu]))['token'];
$tv2 = $sv->publish(payload(['external_ref' => 'V2', 'valid_until' => null]))['token'];
$tv3 = $sv->publish(payload(['external_ref' => 'V3', 'valid_until' => gmdate('Y-m-d', $now + 2 * 86400) . ' 00:00:00']))['token'];
check('süre dolmadan görüntülenir', $sv->view($tv1)['ok']);
$cv = $now + 2 * 86400 - 60;
check('son dakikada hâlâ üç teklif de bekliyor', $sv->counts()['bekleyen'] === 3);
$cv = $now + 2 * 86400 + 3600;
check('süre dolunca karar alınamaz (expired)', $sv->decide($tv1, 'accept')['error'] === 'expired');
check('süre dolunca görüntülenemez', $sv->view($tv1)['error'] === 'expired');
check('tarihi olmayan teklif dolmaz', $sv->view($tv2)['ok']);
check('saatsiz tarih o günün sonuna kadar geçerli', $sv->view($tv3)['ok']);
$cv = $now + 3 * 86400;
check('saatsiz tarih ertesi gün dolar', $sv->view($tv3)['error'] === 'expired');
$cnt = $sv->counts();
check('sekme sayaçları: süresi dolan 2, bekleyen 1', $cnt['suresi'] === 2 && $cnt['bekleyen'] === 1);
check('liste süresi dolanları verir', count($sv->listPublications('suresi')) === 2);
check('süre dolumu olayı TOYA’ya iletilir', count(array_filter($sv->decisions(0), fn($e) => $e['event_type'] === 'expire')) === 2);
check('detay olay geçmişini verir', ($sv->detail((int)$sv->listPublications('suresi')[0]['id'])['events'][0]['event_type'] ?? '') === 'expire');
$rp = $sv->publish(payload(['external_ref' => 'V1', 'valid_until' => gmdate('Y-m-d H:i:s', $cv + 86400)]));
check('süresi dolan teklif yeniden yayınlanınca canlanır', $rp['ok'] && $sv->view($rp['token'])['ok']);
$t6 = $s3->publish(payload(['external_ref' => 'TKL-004', 'allow_counter' => false]))['token'];
check('karşı teklife izin yoksa reddedilir', $s3->decide($t6, 'counter', null, 100.0)['error'] === 'counter_not_allowed');

echo "süre / iptal\n";
$c7 = $now;
$s7 = new PortalService(db(), 30, function () use (&$c7) { return $c7; });
$t7 = $s7->publish(payload())['token'];
$c7 += 31 * 86400;
check('süresi dolan token görüntülenemez', $s7->view($t7)['error'] === 'expired');
check('süresi dolan token karar alamaz', $s7->decide($t7, 'accept')['error'] === 'expired');
$c7 = $now;
$s7->revoke('toya', 'TKL-001');
check('iptal edilen token görüntülenemez', $s7->view($t7)['error'] === 'revoked');
check('olmayan teklif iptali not_found', $s7->revoke('toya', 'YOK')['error'] === 'not_found');
$c7 += 31 * 86400;
$re = $s7->publish(payload());
check('yeniden yayın aynı token’ı korur', $re['ok'] && $re['token'] === $t7);
check('iptal/süresi dolan teklif yeniden yayınlanınca tekrar görüntülenir', $s7->view($t7)['ok'] === true);

echo "ajan kararları\n";
$pdoA = db();
$sa = new PortalService($pdoA, 30, function () use ($now) { return $now; });
$ta = $sa->publish(payload(['external_ref' => 'A1']))['token'];
$tb = $sa->publish(payload(['external_ref' => 'A2']))['token'];
$sa->view($ta, '1.1.1.1', 'UA');
$sa->decide($ta, 'accept', 'ok');
$sa->decide($tb, 'counter', 'not', 750.0);
$d = $sa->decisions(0);
check('yalnız karar olayları döner (view/publish hariç)', count($d) === 2);
check('kabul olayı doğru teklifi gösterir', $d[0]['event_type'] === 'accept' && $d[0]['external_ref'] === 'A1');
check('karşı teklif tutarı iletilir', $d[1]['event_type'] === 'counter' && (float)$d[1]['counter_amount'] === 750.0);
check('imleç sonrası boş döner', $sa->decisions((int)$d[1]['event_id']) === []);

echo "cari hesap özeti\n";
$ca = $now;
$acc = new PortalService(db(), 30, function () use (&$ca) { return $ca; });
$ar = $acc->publishAccount([
    'source' => 'toya', 'external_ref' => 'C-1', 'customer_name' => 'ACME', 'balance' => 1500.25,
    'statement' => [['date' => '2026-09-01', 'doc_no' => 'FTR-1', 'debit' => 1500.25, 'credit' => 0]],
]);
check('hesap yayını token üretir', $ar['ok'] && strlen($ar['token']) === 64);
$av = $acc->viewAccount($ar['token'], '1.1.1.1', 'UA');
check('bakiye ve hareketler döner', $av['ok'] && $av['data']['balance'] === 1500.25 && $av['data']['statement'][0]['doc_no'] === 'FTR-1');
check('iç alanlar sızmaz', !isset($av['data']['token']) && !isset($av['data']['id']));
$ar2 = $acc->publishAccount(['source' => 'toya', 'external_ref' => 'C-1', 'balance' => -20]);
check('yeniden yayın token’ı korur, bakiyeyi günceller', $ar2['token'] === $ar['token'] && $acc->viewAccount($ar['token'])['data']['balance'] === -20.0);
check('geçersiz payload reddedilir', $acc->publishAccount(['source' => 'toya', 'external_ref' => 'X'])['error'] === 'invalid_payload');
check('bilinmeyen hesap tokenı not_found', $acc->viewAccount(str_repeat('d', 64))['error'] === 'not_found');
$acc->revokeAccount('toya', 'C-1');
check('iptal edilen hesap görüntülenemez', $acc->viewAccount($ar['token'])['error'] === 'revoked');
check('olmayan hesap iptali not_found', $acc->revokeAccount('toya', 'YOK')['error'] === 'not_found');
$acc->publishAccount(['source' => 'toya', 'external_ref' => 'C-1', 'balance' => 5]);
check('yeniden yayın iptali kaldırır', $acc->viewAccount($ar['token'])['ok'] === true);
$ca += 31 * 86400;
check('süresi dolan hesap linki görüntülenemez', $acc->viewAccount($ar['token'])['error'] === 'expired');

echo "ayna kabulü\n";
$mpdo = db();
$mc = $now;
$mir = new Toya\Portal\MirrorService($mpdo, function () use (&$mc) { return $mc; });
$cari = [['ext_id' => '1', 'cari_kodu' => 'A', 'unvan' => 'Alfa', 'aktif' => true],
         ['ext_id' => '2', 'cari_kodu' => 'B', 'unvan' => 'Beta', 'aktif' => true]];
$r1 = $mir->ingest('cari', 'wolvox', 'run1', $cari);
check('ilk yükleme kayıt ekler', $r1['ok'] && $r1['added'] === 2 && $r1['updated'] === 0);
$cari[0]['unvan'] = 'Alfa Yeni';
$r2 = $mir->ingest('cari', 'wolvox', 'run2', $cari);
check('aynı ext_id güncellenir, yenisi eklenmez', $r2['ok'] && $r2['added'] === 0 && $r2['updated'] === 2);
check('güncel değer yazılır', $mpdo->query("SELECT unvan FROM portal_mirror_cari WHERE ext_id='1'")->fetchColumn() === 'Alfa Yeni');

$mir->ingest('cari_hareket', 'wolvox', 'run2', [[
    'ext_id' => '10', 'cari_ext_id' => '1', 'tarihi' => '2026-01-05 00:00:00', 'borc' => '1000.5', 'alacak' => null,
    'ilgili_ext_id' => '100', 'evrak_no' => 'FTR-1',
]]);
$hr = $mpdo->query("SELECT borc, alacak, ilgili_ext_id FROM portal_mirror_cari_hareket")->fetch(PDO::FETCH_ASSOC);
check('sayısal dönüşüm: metin tutar sayıya, boş alacak 0', (float)$hr['borc'] === 1000.5 && (float)$hr['alacak'] === 0.0 && $hr['ilgili_ext_id'] === '100');

$r3 = $mir->finish('wolvox', 'run3', ['cari']); // run3'te hiç kayıt gönderilmedi
check('turda görülmeyen kayıtlar kaybolmuş işaretlenir', $r3['ok'] && $r3['vanished']['cari'] === 2);
check('kaybolanlar aktif sayımdan düşer', $mir->counts('wolvox')['cari'] === 0);
$mir->ingest('cari', 'wolvox', 'run4', [$cari[0]]);
check('yeniden gelen kayıt tekrar aktif olur', $mir->counts('wolvox')['cari'] === 1);
$mir->finish('wolvox', 'run4', ['cari']);
check('turda görülen kayıt korunur', $mir->counts('wolvox')['cari'] === 1);
check('finish yalnız istenen varlığı etkiler', $mir->counts('wolvox')['cari_hareket'] === 1);

$mir->ingest('cari', 'logo', 'r1', [['ext_id' => '1', 'unvan' => 'Logo Cari']]);
check('aynı ext_id farklı kaynakta ayrı kayıt', (int)$mpdo->query("SELECT COUNT(*) FROM portal_mirror_cari WHERE ext_id='1'")->fetchColumn() === 2);
$mir->finish('logo', 'r2', ['cari']);
check('bir kaynağın finish’i diğerini etkilemez', $mir->counts('wolvox')['cari'] === 1 && $mir->counts('logo')['cari'] === 0);

$mir->ingest('fatura', 'wolvox', 'r', [['ext_id' => '5', 'fatura_no' => 'SF3', 'yon' => 'satis', 'genel_toplam' => 6.49, 'iptal' => 0, 'silindi' => true]]);
check('silindi=true kaynak_silindi olarak gelir', (int)$mpdo->query("SELECT source_deleted FROM portal_mirror_fatura")->fetchColumn() === 1);
check('bilinmeyen varlık reddedilir', $mir->ingest('kullanici', 'x', 'r', [])['error'] === 'unknown_entity');
check('ext_id’siz kayıt reddedilir ve hiçbiri yazılmaz', $mir->ingest('stok', 'wolvox', 'r', [['ext_id' => '9', 'stok_adi' => 'X'], ['stok_adi' => 'Y']])['error'] === 'invalid_record'
    && (int)$mpdo->query("SELECT COUNT(*) FROM portal_mirror_stok")->fetchColumn() === 0);
check('kaynak/tur kimliği boşsa reddedilir', $mir->ingest('stok', '', 'r', [])['error'] === 'invalid_payload');
check('çok büyük parça reddedilir', $mir->ingest('stok', 'w', 'r', array_fill(0, 1001, ['ext_id' => 'x']))['error'] === 'too_many_records');
$mir->ingest('stok', 'wolvox', 'r', [['ext_id' => '1', 'stok_adi' => 'X', 'bilinmeyen_alan' => 'zararlı; DROP TABLE']]);
check('beyaz liste dışı alanlar yok sayılır', (int)$mpdo->query("SELECT COUNT(*) FROM portal_mirror_stok")->fetchColumn() === 1);

echo "aktarım günlüğü\n";
$lp = db();
$lm = new Toya\Portal\MirrorService($lp, function () use ($now) { return $now; });
$lm->ingest('cari', 'wolvox', 'r1', [['ext_id' => '1', 'unvan' => 'A'], ['ext_id' => '2', 'unvan' => 'B']], '9.9.9.9');
$lm->ingest('cari', 'wolvox', 'r2', [['ext_id' => '1', 'unvan' => 'A2']], '9.9.9.9');
$lm->ingest('kullanici', 'wolvox', 'r3', [], '9.9.9.9');
$lm->finish('wolvox', 'r2', ['cari'], '9.9.9.9');
$log = $lm->recentLog();
check('her çağrı günlüğe yazılır (4 kayıt)', count($log) === 4);
check('en yeni önce: finish, kaybolan sayısı 1', $log[0]['action'] === 'finish' && (int)$log[0]['vanished'] === 1 && $log[0]['status'] === 'ok');
check('hatalı çağrı error olarak, sebebiyle günlükte', $log[1]['status'] === 'error' && $log[1]['message'] === 'unknown_entity');
check('yükleme sayıları günlükte', (int)$log[3]['added'] === 2 && (int)$log[3]['received'] === 2 && $log[3]['ip_address'] === '9.9.9.9');
check('güncelleme sayısı günlükte', (int)$log[2]['updated'] === 1);
check('durum filtresi çalışır', count($lm->recentLog(100, 'error')) === 1);
check('kaynak filtresi çalışır', count($lm->recentLog(100, null, 'yok')) === 0);
$lp->exec("DROP TABLE portal_sync_log");
$okAfterDrop = $lm->ingest('cari', 'wolvox', 'r9', [['ext_id' => '5', 'unvan' => 'Z']]);
check('günlük yazılamazsa asıl işlem bozulmaz', $okAfterDrop['ok'] === true);

echo "kimlik doğrulama\n";
$ac = $now;
$ap = db();
$au = new Toya\Portal\AuthService($ap, 3, function () use (&$ac) { return $ac; });
check('ilk kullanıcı yok', $au->hasAnyUser() === false);
$a1 = $au->createUser('yonetici', 'uzun-ve-guclu-parola', 'admin');
check('kullanıcı oluşturulur', $a1['ok'] && $au->hasAnyUser());
check('kısa parola reddedilir', $au->createUser('kisa', '123456789', 'viewer')['error'] === 'weak_password');
check('geçersiz kullanıcı adı reddedilir', $au->createUser('a b', 'uzun-ve-guclu-parola')['error'] === 'invalid_username');
check('geçersiz rol reddedilir', $au->createUser('biri', 'uzun-ve-guclu-parola', 'root')['error'] === 'invalid_role');
check('aynı kullanıcı adı reddedilir', $au->createUser('yonetici', 'uzun-ve-guclu-parola')['error'] === 'username_taken');
$au->createUser('user2', 'uzun-ve-guclu-parola');
$au->createUser('user3', 'uzun-ve-guclu-parola');
check('kullanıcı sınırı aşılamaz (3)', $au->createUser('user4', 'uzun-ve-guclu-parola')['error'] === 'user_limit');
$hash = $ap->query("SELECT password_hash FROM portal_users WHERE username='user2'")->fetchColumn();
check('parola düz metin saklanmaz', strpos($hash, 'uzun-ve-guclu-parola') === false && password_verify('uzun-ve-guclu-parola', $hash));

$g = $au->authenticate('yonetici', 'uzun-ve-guclu-parola');
check('doğru parola girişi başarılı, karma dönmez', $g['ok'] && !isset($g['user']['password_hash']) && $g['user']['role'] === 'admin');
check('yanlış parola genel hata', $au->authenticate('yonetici', 'yanlis')['error'] === 'invalid');
check('olmayan kullanıcı aynı genel hata', $au->authenticate('yok', 'x')['error'] === 'invalid');
for ($i = 0; $i < 4; $i++) { $au->authenticate('user2', 'yanlis-parola'); }
check('5. hatalı denemede hesap kilitlenir', $au->authenticate('user2', 'yanlis-parola')['error'] === 'locked');
check('kilitliyken doğru parola da reddedilir', $au->authenticate('user2', 'uzun-ve-guclu-parola')['error'] === 'locked');
$ac += 901;
check('kilit süresi dolunca giriş açılır', $au->authenticate('user2', 'uzun-ve-guclu-parola')['ok'] === true);
check('başarılı girişten sonra sayaç sıfırlanır', (int)$ap->query("SELECT failed_attempts FROM portal_users WHERE username='user2'")->fetchColumn() === 0);

check('tek yönetici pasifleştirilemez', $au->setActive((int)$a1['id'], false)['error'] === 'last_admin');
$u3 = $au->createUser('extra1', 'uzun-ve-guclu-parola');
$au->setActive(2, false);
check('pasif kullanıcı giremez', $au->authenticate('user2', 'uzun-ve-guclu-parola')['error'] === 'invalid');
$au->createUser('user5', 'uzun-ve-guclu-parola');
check('pasif kullanıcıyı geri açmak da sınırı aşamaz', $au->setActive(2, true)['error'] === 'user_limit');
check('parola değiştirilir ve kilidi açar', $au->setPassword(1, 'tamamen-yeni-parola')['ok'] && $au->authenticate('yonetici', 'tamamen-yeni-parola')['ok']);
check('listede karma yok', !array_key_exists('password_hash', $au->listUsers()[0]));

echo "raporlar\n";
$rp = db();
$rm = new Toya\Portal\MirrorService($rp, function () use ($now) { return $now; });
$rm->ingest('cari', 'wolvox', 'r', [['ext_id' => '1', 'cari_kodu' => 'A', 'unvan' => 'Alfa'], ['ext_id' => '2', 'cari_kodu' => 'B', 'unvan' => 'Beta']]);
$rm->ingest('cari_hareket', 'wolvox', 'r', [
    ['ext_id' => '10', 'cari_ext_id' => '1', 'tarihi' => '2026-01-05 00:00:00', 'evrak_no' => 'FTR-1', 'borc' => 1000, 'ilgili_ext_id' => '100'],
    ['ext_id' => '11', 'cari_ext_id' => '1', 'tarihi' => '2026-02-05 00:00:00', 'evrak_no' => 'TAH-1', 'alacak' => 400],
    ['ext_id' => '12', 'cari_ext_id' => '2', 'tarihi' => '2026-02-06 00:00:00', 'evrak_no' => 'AF-1', 'alacak' => 250],
    ['ext_id' => '13', 'cari_ext_id' => '1', 'tarihi' => '2026-03-01 00:00:00', 'borc' => 9999, 'silindi' => true],
]);
$rm->ingest('fatura', 'wolvox', 'r', [
    ['ext_id' => '100', 'fatura_no' => 'SF1', 'tarihi' => '2026-01-05 00:00:00', 'cari_ext_id' => '1', 'yon' => 'satis', 'genel_toplam' => 1000],
    ['ext_id' => '101', 'fatura_no' => 'SF1', 'tarihi' => '2026-01-06 00:00:00', 'cari_ext_id' => '1', 'yon' => 'satis', 'genel_toplam' => 500],
    ['ext_id' => '102', 'fatura_no' => 'AF1', 'tarihi' => '2026-02-06 00:00:00', 'cari_ext_id' => '2', 'yon' => 'alis', 'genel_toplam' => 250],
    ['ext_id' => '103', 'fatura_no' => 'IP1', 'tarihi' => '2026-02-07 00:00:00', 'cari_ext_id' => '1', 'yon' => 'satis', 'genel_toplam' => 999, 'iptal' => 1],
    ['ext_id' => '104', 'fatura_no' => 'XX', 'tarihi' => '2026-02-08 00:00:00', 'cari_ext_id' => '1', 'genel_toplam' => 10],
]);
$rm->ingest('fatura_kalem', 'wolvox', 'r', [
    ['ext_id' => '1', 'fatura_ext_id' => '100', 'stok_adi' => 'Ürün', 'miktar' => 2, 'fiyat' => 500, 'tutar' => 1000, 'kdvli_tutar' => 1180, 'sira_no' => 1],
]);
$rr = new Toya\Portal\ReportService($rp);
check('kaynak listesi', $rr->sources() === ['wolvox']);
$bk = [];
foreach ($rr->cariBakiyeleri('wolvox') as $b) { $bk[$b['cari_kodu']] = $b['bakiye']; }
check('cari bakiyesi: borç - alacak, silinen hareket hariç', $bk['A'] === 600.0 && $bk['B'] === -250.0);
$oz = $rr->firmaOzeti('wolvox');
check('firma özeti: borç/alacak toplamı', $oz['toplam_borc'] === 600.0 && $oz['toplam_alacak'] === 250.0);
check('firma özeti: iptal hariç fatura sayıları', $oz['fatura_adedi'] === 4 && $oz['satis_adet'] === 2 && $oz['satis_toplam'] === 1500.0 && $oz['alis_toplam'] === 250.0);
check('firma özeti: yönü bilinmeyen ayrı sayılır', $oz['yonu_bilinmeyen_adet'] === 1);
$ek = $rr->ekstre('wolvox', '1');
check('ekstre yürüyen bakiye', array_column($ek['satirlar'], 'bakiye') === [1000.0, 600.0] && $ek['devir'] === 0.0);
check('ekstrede faturaya bağ', $ek['satirlar'][0]['ilgili_ext_id'] === '100');
$ek2 = $rr->ekstre('wolvox', '1', '2026-02-01 00:00:00');
check('ekstre devir ve dönem', $ek2['devir'] === 1000.0 && count($ek2['satirlar']) === 1 && $ek2['bakiye'] === 600.0);
check('fatura listesi iptali dışlar', count($rr->faturalar('wolvox')) === 4);
check('fatura listesi cari filtresi', count($rr->faturalar('wolvox', null, null, '2')) === 1);
$fd = $rr->fatura('wolvox', '100');
check('fatura detayı kalemleriyle', $fd['fatura']['cari_unvan'] === 'Alfa' && $fd['kalemler'][0]['stok_adi'] === 'Ürün');
check('iptal edilen fatura detayı yok', $rr->fatura('wolvox', '103') === null);
check('olmayan cari null', $rr->cari('wolvox', '99') === null);
check('başka kaynağın verisi görünmez', $rr->cariBakiyeleri('logo') === []);

echo "migrasyon\n";
$mdir = sys_get_temp_dir() . '/toya_mig_' . bin2hex(random_bytes(4));
mkdir($mdir);
$wm = function (string $name, string $sql) use ($mdir) { file_put_contents($mdir . '/' . $name, $sql); };
$wm('001_a.sql', "CREATE TABLE mig_a (id INTEGER, v VARCHAR(20));\nINSERT INTO mig_a (id, v) VALUES (1, 'a;b');");
$wm('002_b.sql', "-- yorum; içinde noktalı virgül\nCREATE TABLE mig_b (id INTEGER);");
$wm('readme.sql', 'GEÇERSİZ ad, çalışmamalı');
$wm('10_kisa.sql', 'yanlış numara biçimi');
$mp = db();
$mg = new Toya\Portal\Migrator($mp, $mdir);
check('yalnız NNN_ad.sql biçimindeki dosyalar, sıralı', $mg->files() === ['001_a.sql', '002_b.sql']);
check('başlangıçta ikisi de bekliyor', $mg->pending() === ['001_a.sql', '002_b.sql']);
$r = $mg->migrate();
check('migrasyonlar sırayla uygulanır', $r['ok'] && $r['executed'] === ['001_a.sql', '002_b.sql']);
check('tırnak içindeki ; ifadeyi bölmez', $mp->query('SELECT v FROM mig_a')->fetchColumn() === 'a;b');
check('tablo oluştu', (int)$mp->query('SELECT COUNT(*) FROM mig_b')->fetchColumn() === 0);
$r2 = $mg->migrate();
check('ikinci tur hiçbir şeyi yeniden çalıştırmaz', $r2['ok'] && $r2['executed'] === [] && $r2['skipped'] === ['001_a.sql', '002_b.sql']);
check('pending boş', $mg->pending() === []);

$wm('003_bad.sql', "CREATE TABLE mig_c (id INTEGER);\nBU GECERSIZ SQL;");
$wm('004_after.sql', 'CREATE TABLE mig_d (id INTEGER);');
$r3 = $mg->migrate();
check('hatalı migrasyonda durur ve bildirir', $r3['ok'] === false && $r3['failed'] === '003_bad.sql' && $r3['error'] !== null);
check('hatadan sonraki migrasyon çalışmaz', $mg->applied()['003_bad.sql']['status'] === 'failed' && !isset($mg->applied()['004_after.sql']));
$wm('003_bad.sql', 'CREATE TABLE mig_c2 (id INTEGER);');
$r4 = $mg->migrate();
check('düzeltilince hatalı olan yeniden denenir, sonrakiler de çalışır', $r4['ok'] && $r4['executed'] === ['003_bad.sql', '004_after.sql']);
$wm('001_a.sql', "CREATE TABLE IF NOT EXISTS mig_a (id INTEGER);");
$r5 = $mg->migrate();
check('uygulanmış migrasyon değişirse uyarılır ama yeniden çalışmaz', $r5['ok'] && $r5['modified'] === ['001_a.sql'] && $r5['executed'] === []);

$parts = Toya\Portal\Migrator::splitStatements("SELECT 'it''s; ok'; -- son; yorum\nSELECT \"a;b\"; /* x; y */ SELECT 3");
check('ifade bölücü: kaçışlı tırnak, yorumlar', $parts === ["SELECT 'it''s; ok'", 'SELECT "a;b"', 'SELECT 3']);
foreach (glob($mdir . '/*') as $f) { unlink($f); }
rmdir($mdir);

echo "güncelleme kurucusu\n";
use Toya\Portal\Updater;

function rmtree(string $d): void
{
    if (!is_dir($d)) { return; }
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($d, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST) as $f) {
        $f->isDir() ? rmdir($f->getPathname()) : unlink($f->getPathname());
    }
    rmdir($d);
}

/** Test paketi üretir. opts: extra (manifest dışı zip girdisi), omit (manifest'te olup zip'te olmayan), tamper (zip içeriği farklı), sign_secret. */
function buildPkg(string $path, string $secret, string $version, array $files, array $opts = []): void
{
    $hashes = [];
    foreach ($files as $p => $c) { $hashes[$p] = hash('sha256', $c); }
    $created = '2026-09-19T12:00:00Z';
    $sig = Updater::sign($opts['sign_secret'] ?? $secret, 1, $version, $created, $hashes);
    $z = new ZipArchive();
    $z->open($path, ZipArchive::CREATE | ZipArchive::OVERWRITE);
    $z->addFromString('manifest.json', json_encode([
        'format' => 1, 'name' => 'toya-portal', 'version' => $version, 'created' => $created, 'files' => $hashes, 'signature' => $sig,
    ]));
    foreach ($files as $p => $c) {
        if (in_array($p, $opts['omit'] ?? [], true)) { continue; }
        $z->addFromString('files/' . $p, $opts['tamper'][$p] ?? $c);
    }
    foreach ($opts['extra'] ?? [] as $n => $c) { $z->addFromString($n, $c); }
    $z->close();
}

const UPD_SECRET = 'test-gizli-anahtar-en-az-32-karakter-x';
function updRoot(): array
{
    $base = sys_get_temp_dir() . '/toya_upd_' . bin2hex(random_bytes(4));
    $root = $base . '/portal';
    mkdir($root . '/src', 0777, true);
    mkdir($root . '/migrations', 0777, true);
    mkdir($root . '/storage', 0777, true);
    file_put_contents($root . '/VERSION', "1.0.0\n");
    file_put_contents($root . '/src/a.php', '<?php // eski');
    file_put_contents($root . '/config.local.php', '<?php return ["secret" => "korunmali"];');
    file_put_contents($root . '/migrations/001_init.sql', 'CREATE TABLE upd_base (id INTEGER);');
    $pdo = db();
    (new Toya\Portal\Migrator($pdo, $root . '/migrations'))->migrate();
    return [$base, $root, $pdo];
}
function snapshot(string $root): string
{
    $h = [];
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS)) as $f) {
        if (strpos(str_replace('\\', '/', $f->getPathname()), '/storage/') === false) {
            $h[] = str_replace('\\', '/', substr($f->getPathname(), strlen($root))) . ':' . md5_file($f->getPathname());
        }
    }
    sort($h);
    return implode('|', $h);
}

// PHP ve Python aynı imzayı üretmeli (Python tarafında hesaplanmış sabit vektör)
$vec = Updater::sign('gizli-anahtar', 1, '1.2.3', '2026-09-19T12:00:00Z', [
    'src/b.php' => hash('sha256', 'B'), 'VERSION' => hash('sha256', "1.2.3\n"), 'public/a.php' => hash('sha256', 'A'),
]);
check('PHP imzası Python ile aynı (çapraz dil vektörü)', $vec === '1609f9f0084abae9e1bbf2625e2333dd03d511f3d90a6c018ef5ae94788e7f8f');

[$base, $root, $upd] = updRoot();
$u = new Updater($upd, $root, UPD_SECRET, function () use ($now) { return $now; });
check('kurulu sürüm okunur', $u->currentVersion() === '1.0.0');

$good = $base . '/good.zip';
buildPkg($good, UPD_SECRET, '1.1.0', [
    'src/a.php' => '<?php // yeni', 'src/new.php' => '<?php // eklenen', 'public/x.php' => 'x',
    'migrations/002_new.sql' => 'CREATE TABLE upd_new (id INTEGER);', 'VERSION' => "1.1.0\n",
]);
$r = $u->apply($good);
check('geçerli paket kurulur', $r['ok'] === true && $r['from'] === '1.0.0' && $r['to'] === '1.1.0');
check('dosyalar güncellendi/eklendi', file_get_contents($root . '/src/a.php') === '<?php // yeni' && is_file($root . '/src/new.php'));
check('migrasyon çalıştı', $r['migrations']['executed'] === ['002_new.sql'] && (int)$upd->query('SELECT COUNT(*) FROM upd_new')->fetchColumn() === 0);
check('VERSION güncellendi', $u->currentVersion() === '1.1.0');
check('config.local.php ezilmedi', strpos((string)file_get_contents($root . '/config.local.php'), 'korunmali') !== false);
check('ezilen dosyalar yedeklendi', $r['backup'] !== null && is_file($root . '/storage/backups/' . $r['backup']));
check('geçici .new dosyası kalmadı', glob($root . '/src/*.new.*') === []);
check('aynı sürüm tekrar kurulamaz', $u->apply($good)['error'] !== null && strpos((string)$u->apply($good)['error'], 'zaten kurulu') !== false);
check('açıkça istenirse aynı sürüm yeniden kurulur', $u->apply($good, true)['ok'] === true);

$before = snapshot($root);
$attack = function (string $label, callable $mk, string $needle) use ($base, $root, $u, &$before) {
    $z = $base . '/atk_' . bin2hex(random_bytes(3)) . '.zip';
    $mk($z);
    $r = $u->apply($z);
    check("saldırı reddedilir: $label", $r['ok'] === false && $r['error'] !== null && strpos($r['error'], $needle) !== false);
    check("  → hiçbir dosya değişmedi ($label)", snapshot($root) === $before);
};
$attack('yanlış anahtarla imzalı', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['src/e.php' => 'X', 'VERSION' => "1.2.0\n"], ['sign_secret' => 'baska-gizli-anahtar-en-az-32-karakter']), 'imza');
$attack('içerik imzadan sonra değiştirilmiş', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['src/e.php' => 'X', 'VERSION' => "1.2.0\n"], ['tamper' => ['src/e.php' => '<?php system($_GET[1]);']]), 'özeti uyuşmuyor');
$attack('manifest dışı ekstra dosya', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['src/e.php' => 'X', 'VERSION' => "1.2.0\n"], ['extra' => ['files/src/shell.php' => 'S']]), 'manifest');
$attack('manifest\'te olup zip\'te olmayan', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['src/e.php' => 'X', 'src/y.php' => 'Y', 'VERSION' => "1.2.0\n"], ['omit' => ['src/y.php']]), 'bulunmayan');
$attack('geçerli imzalı ama ../ yol', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['src/../../evil.php' => 'X', 'VERSION' => "1.2.0\n"]), 'izin verilmeyen');
$attack('geçerli imzalı ama config.local.php', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['config.local.php' => '<?php // ele geçir', 'VERSION' => "1.2.0\n"]), 'izin verilmeyen');
$attack('geçerli imzalı ama storage/', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['storage/x.php' => 'X', 'VERSION' => "1.2.0\n"]), 'izin verilmeyen');
$attack('geçerli imzalı ama kökte rastgele php', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['evil.php' => 'X', 'VERSION' => "1.2.0\n"]), 'izin verilmeyen');
$attack('geçerli imzalı ama mutlak yol', fn($z) => buildPkg($z, UPD_SECRET, '1.2.0', ['/etc/x.php' => 'X', 'VERSION' => "1.2.0\n"]), 'izin verilmeyen');
$attack('eski sürüme geri alma', fn($z) => buildPkg($z, UPD_SECRET, '1.0.5', ['src/e.php' => 'X', 'VERSION' => "1.0.5\n"]), 'eski bir sürüm');
$attack('ZIP değil', fn($z) => file_put_contents($z, 'bu bir zip değil'), 'ZIP');
$attack('manifest yok', function ($z) { $a = new ZipArchive(); $a->open($z, ZipArchive::CREATE); $a->addFromString('files/src/x.php', 'X'); $a->close(); }, 'manifest');
$nosecret = new Updater($upd, $root, '', function () use ($now) { return $now; });
check('secret tanımsızken güncelleme kapalı', strpos((string)$nosecret->apply($good, true)['error'], 'update_secret') !== false);
foreach (['kisa-secret', 'DEGISTIR-en-az-32-karakter-rastgele'] as $weak) {
    $wu = new Updater($upd, $root, $weak, function () use ($now) { return $now; });
    $we = (string)$wu->apply($good, true)['error'];
    check("zayıf/örnek secret reddedilir: $weak", strpos($we, 'zayıf veya örnek') !== false);
}

// migrasyon hatası: dosyalar eski haline dönmeli
$bad = $base . '/badmig.zip';
buildPkg($bad, UPD_SECRET, '1.3.0', [
    'src/a.php' => '<?php // 1.3.0', 'src/added.php' => '<?php // yeni eklenen',
    'migrations/003_broken.sql' => 'BU GECERSIZ SQL;', 'VERSION' => "1.3.0\n",
]);
$snap = snapshot($root);
$rb = $u->apply($bad);
check('migrasyon hatasında kurulum başarısız', $rb['ok'] === false && strpos((string)$rb['error'], 'Migrasyon başarısız') !== false);
check('  → dosyalar yedekten geri yüklendi, yeni dosya silindi', $rb['restored'] === true && file_get_contents($root . '/src/a.php') === '<?php // yeni' && !is_file($root . '/src/added.php'));
check('  → VERSION değişmedi (1.1.0)', $u->currentVersion() === '1.1.0');

// Masaüstünün FTP'den sonra çağırdığı otomatik kurulum API ucu (bkz. bootstrap.php::portal_route '/update/apply')
mkdir($root . '/update_inbox', 0777, true);
buildPkg($root . '/update_inbox/toya-portal-1.4.0.zip', UPD_SECRET, '1.4.0', ['src/a.php' => '<?php // 1.4.0', 'VERSION' => "1.4.0\n"]);
$svc = new Toya\Portal\PortalService($upd, 30);
[$code, $out] = portal_route($svc, 'POST', '/update/apply', ['package' => 'toya-portal-1.4.0.zip'], [], true, null, null, null, null, $u);
check('API: yetkili ajan paketi kurar', $code === 200 && $out['ok'] === true && $out['to'] === '1.4.0');
check('  → kurulan paket update_inbox/den storage/applied/e taşındı', !is_file($root . '/update_inbox/toya-portal-1.4.0.zip') && is_file($root . '/storage/applied/toya-portal-1.4.0.zip'));
[$code2] = portal_route($svc, 'POST', '/update/apply', ['package' => 'toya-portal-1.4.0.zip'], [], false, null, null, null, null, $u);
check('API: agent_api_key olmadan reddedilir', $code2 === 401);
[$code3, $out3] = portal_route($svc, 'POST', '/update/apply', ['package' => '../../etc/passwd'], [], true, null, null, null, null, $u);
check('API: geçersiz paket adı reddedilir', $code3 === 400 && $out3['ok'] === false);
[$code4] = portal_route($svc, 'POST', '/update/apply', ['package' => 'toya-portal-9.9.9.zip'], [], true, null, null, null, null, $u);
check('API: sunucuda olmayan paket 404', $code4 === 404);
[$code5] = portal_route($svc, 'POST', '/update/apply', ['package' => 'toya-portal-1.4.0.zip'], [], true, null, null, null, null, null);
check('API: Updater bağlanmamışsa 500', $code5 === 500);
rmtree($base);

echo "kurulum sihirbazı\n";
use Toya\Portal\Installer;

/** Yeni bir portal kökü + SQLite dosya veritabanı üretir (Installer testleri için). */
function instEnv(string $migrationSql = null): array
{
    $base = sys_get_temp_dir() . '/toya_inst_' . bin2hex(random_bytes(4));
    $root = $base . '/portal';
    mkdir($root . '/migrations', 0777, true);
    file_put_contents($root . '/VERSION', "1.0.0\n");
    file_put_contents($root . '/migrations/001_schema.sql', $migrationSql ?? (string)file_get_contents(__DIR__ . '/../sql/schema.sqlite.sql'));
    $dbFile = $base . '/test.sqlite';
    return [$base, $root, 'sqlite:' . $dbFile, $dbFile];
}
function instInput(array $over = []): array
{
    return array_replace_recursive([
        'db' => ['host' => 'x', 'port' => 3306, 'name' => 'x', 'user' => 'u', 'pass' => 'p'],
        'admin' => ['username' => 'yonetici', 'password' => 'cok-guclu-parola-1', 'password2' => 'cok-guclu-parola-1'],
        'base_url' => 'https://firma.example/portal/',
    ], $over);
}

[$ib, $ir, $idsn, $idb] = instEnv();
$inst = new Installer($ir, $idsn);
check('yeni portal kurulu sayılmaz', $inst->isInstalled() === false);
check('kurulum anahtarı üretilir', $inst->ensureToken() && preg_match('/^[0-9a-f]{32}$/', trim((string)file_get_contents($inst->tokenPath()))) === 1);
$tok = trim((string)file_get_contents($inst->tokenPath()));
$inst->ensureToken();
check('anahtar ikinci çağrıda değişmez', trim((string)file_get_contents($inst->tokenPath())) === $tok);
check('doğru anahtar kabul edilir (boşluk kırpılır)', $inst->verifyToken("  $tok\n") === true);
check('yanlış/boş anahtar reddedilir', $inst->verifyToken('yanlis') === false && $inst->verifyToken('') === false);
$reqs = $inst->requirements();
check('gereksinim listesi PHP sürümünü ve eklentileri içerir', count($reqs) >= 8 && $reqs[0]['ok'] === true);
check('bu makinede gereksinimler karşılanıyor', $inst->requirementsMet() === true);

$raw = new Installer($ir); // DSN geçersiz kılma yok: gerçek doğrulama yolu
foreach ([['host' => 'x;dbname=baska'], ['host' => 'a b'], ['host' => '../evil'], ['port' => 70000], ['name' => 'db;drop'], ['name' => '']] as $bad) {
    $c = $raw->connect(array_replace(['host' => 'localhost', 'port' => 3306, 'name' => 'db', 'user' => 'u', 'pass' => 'p'], $bad));
    check('DSN enjeksiyonu/geçersiz girdi reddedilir: ' . json_encode($bad), $c['ok'] === false);
}
$c = $raw->connect(['host' => '127.0.0.1', 'port' => 1, 'name' => 'db', 'user' => 'u', 'pass' => 'sifre-gizli-xyz']);
check('erişilemeyen sunucuda hata var ve parola sızmaz', $c['ok'] === false && strpos($c['error'], 'sifre-gizli-xyz') === false);

// başarılı kurulum
$r = $inst->install(instInput());
check('kurulum başarılı', $r['ok'] === true && strlen($r['keys']['agent_api_key']) === 48 && strlen($r['keys']['update_secret']) === 48);
check('  → adres sondaki / atılmış', $r['base_url'] === 'https://firma.example/portal');
$cfg = require $inst->configPath();
check('  → yapılandırma anahtarları doğru', $cfg['agent_api_key'] === $r['keys']['agent_api_key'] && $cfg['update_secret'] === $r['keys']['update_secret']
    && $cfg['db_dsn'] === $idsn && $cfg['max_users'] === 5 && $cfg['token_days'] === 30);
check('  → kilit yazıldı, anahtar dosyası silindi', is_file($inst->lockPath()) && !is_file($inst->tokenPath()) && $inst->isInstalled());
$pdoI = new PDO($idsn);
$au2 = new Toya\Portal\AuthService($pdoI, 5);
$g = $au2->authenticate('yonetici', 'cok-guclu-parola-1');
check('  → yönetici veritabanında, admin rolüyle giriş yapabilir', $g['ok'] && $g['user']['role'] === 'admin');
check('  → parola düz metin saklanmadı', strpos((string)$pdoI->query('SELECT password_hash FROM portal_users')->fetchColumn(), 'cok-guclu-parola-1') === false);
check('kurulu portalda ikinci kurulum reddedilir', strpos((string)$inst->install(instInput())['error'], 'zaten kurulu') !== false);

// yapılandırma üretimi: özel karakterli parola roundtrip
$tricky = "p'a\"\$b\\c;{\$x}";
$tmpc = sys_get_temp_dir() . '/toya_cfg_' . bin2hex(random_bytes(3)) . '.php';
file_put_contents($tmpc, Installer::renderConfig(['db_pass' => $tricky, 'x' => 1]));
check('özel karakterli parola yapılandırmada aynen korunur', (require $tmpc)['db_pass'] === $tricky);
unlink($tmpc);

// geçersiz yönetici girdisi: hiçbir şey yazılmaz
foreach ([
    'kısa kullanıcı adı' => ['admin' => ['username' => 'ab']],
    'boşluklu kullanıcı adı' => ['admin' => ['username' => 'a b c']],
    'zayıf parola' => ['admin' => ['password' => 'kisa', 'password2' => 'kisa']],
    'parolalar farklı' => ['admin' => ['password2' => 'baska-parola-xxxx']],
] as $label => $over) {
    [$b2, $r2, $d2] = instEnv();
    $i2 = new Installer($r2, $d2);
    $res = $i2->install(instInput($over));
    check("geçersiz yönetici girdisi reddedilir: $label", $res['ok'] === false && !is_file($i2->configPath()) && !is_file($i2->lockPath()));
    rmtree($b2);
}

// veritabanında zaten kullanıcı varsa dokunma
[$b3, $r3, $d3, $f3] = instEnv();
$pre = new PDO($d3);
$pre->exec((string)file_get_contents(__DIR__ . '/../sql/schema.sqlite.sql'));
(new Toya\Portal\AuthService($pre, 5))->createUser('eski-yonetici', 'eski-guclu-parola-1', 'admin');
$i3 = new Installer($r3, $d3);
$res3 = $i3->install(instInput());
check('dolu veritabanına kurulum reddedilir ve hiçbir şey yazılmaz', $res3['ok'] === false && strpos($res3['error'], 'zaten kullanıcı') !== false
    && !is_file($i3->configPath()) && !is_file($i3->lockPath()));
$pre = null;
$i3 = null;
rmtree($b3);

// yarım kalmış kurulum (yapılandırma var, kilit yok): yeniden çalıştırılabilir
[$b4, $r4, $d4] = instEnv();
file_put_contents($r4 . '/config.local.php', '<?php return [];');
$i4 = new Installer($r4, $d4);
check('yapılandırma var ama kilit yok: kurulu sayılmaz', $i4->isInstalled() === false);
check('yarım kalmış kurulum tamamlanabilir', $i4->install(instInput())['ok'] === true && $i4->isInstalled());
rmtree($b4);

// hatalı migrasyon: tablo yok → kurulum durur, dosya yazılmaz
[$b5, $r5, $d5] = instEnv('BU GECERSIZ SQL;');
$i5 = new Installer($r5, $d5);
$res5 = $i5->install(instInput());
check('bozuk migrasyonda kurulum durur, yapılandırma/kilit yazılmaz', $res5['ok'] === false && strpos($res5['error'], '001_schema.sql') !== false
    && !is_file($i5->configPath()) && !is_file($i5->lockPath()));
rmtree($b5);
$pdoI = null;
$au2 = null;
rmtree($ib);

// gerçek MariaDB ile, gerçek migrasyonlarla (yalnızca PORTAL_TEST_MYSQL_HOST verilirse)
if (getenv('PORTAL_TEST_MYSQL_HOST')) {
    $h = getenv('PORTAL_TEST_MYSQL_HOST');
    $dbn = 'tpt_inst_' . getmypid();
    $adm = new PDO("mysql:host=$h;charset=utf8mb4", getenv('PORTAL_TEST_MYSQL_USER') ?: 'root', getenv('PORTAL_TEST_MYSQL_PASS') ?: '');
    $adm->exec("CREATE DATABASE `$dbn` CHARACTER SET utf8mb4");
    $mb = sys_get_temp_dir() . '/toya_instm_' . bin2hex(random_bytes(4));
    mkdir($mb . '/portal', 0777, true);
    $mi = new Installer($mb . '/portal', null, __DIR__ . '/../migrations');
    $rm = $mi->install(instInput(['db' => ['host' => $h, 'port' => 3306, 'name' => $dbn, 'user' => getenv('PORTAL_TEST_MYSQL_USER') ?: 'root', 'pass' => getenv('PORTAL_TEST_MYSQL_PASS') ?: '']]));
    check('[MariaDB] gerçek migrasyonlarla kurulum başarılı', $rm['ok'] === true);
    $mp = new PDO("mysql:host=$h;dbname=$dbn;charset=utf8mb4", getenv('PORTAL_TEST_MYSQL_USER') ?: 'root', getenv('PORTAL_TEST_MYSQL_PASS') ?: '');
    check('[MariaDB] tablolar ve yönetici oluştu', (int)$mp->query("SELECT COUNT(*) FROM portal_users WHERE role='admin'")->fetchColumn() === 1
        && (int)$mp->query("SELECT COUNT(*) FROM portal_migrations WHERE status='success'")->fetchColumn() >= 1);
    $mcfg = require $mb . '/portal/config.local.php';
    check('[MariaDB] yapılandırma MySQL DSN içerir', strpos($mcfg['db_dsn'], "mysql:host=$h") === 0 && strpos($mcfg['db_dsn'], "dbname=$dbn") !== false);
    $wrong = (new Installer($mb . '/w', null, __DIR__ . '/../migrations'))->connect(['host' => $h, 'port' => 3306, 'name' => $dbn, 'user' => 'root', 'pass' => 'kesinlikle-yanlis-parola-qq']);
    check('[MariaDB] yanlış parola anlaşılır mesajla reddedilir', $wrong['ok'] === false && strpos($wrong['error'], 'kesinlikle-yanlis-parola-qq') === false);
    $nodb = (new Installer($mb . '/w', null, __DIR__ . '/../migrations'))->connect(['host' => $h, 'port' => 3306, 'name' => 'olmayan_veritabani_zz', 'user' => 'root', 'pass' => '']);
    check('[MariaDB] olmayan veritabanı anlaşılır mesajla bildirilir', $nodb['ok'] === false && strpos($nodb['error'], 'bulunamadı') !== false);
    $mp = null;
    rmtree($mb);
    $adm->exec("DROP DATABASE IF EXISTS `$dbn`");
}

echo "softaculous\n";
$sv = ['softdbhost' => 'localhost:3307', 'softdbname' => 'x', 'softdbuser' => 'u', 'softdbpass' => 'p',
    'admin_username' => 'yonetici', 'admin_pass' => 'cok-guclu-parola-1', 'site_url' => 'https://firma.example/portal/'];
[$sb, $sr, $sd] = instEnv();
$si = new Installer($sr, $sd);
check('upgrade: kurulu olmayan portalda reddedilir', $si->upgrade()['ok'] === false);
$rs = $si->installFromSoftaculous($sv);
check('Softaculous kurulumu başarılı; adres public/ ile biter', $rs['ok'] === true && $rs['base_url'] === 'https://firma.example/portal/public');
check('  → anahtarlar sonuçta dönmez (çıktıya/e-postaya sızmaz)', !isset($rs['keys']) && strpos(json_encode($rs), (require $si->configPath())['agent_api_key']) === false);
check('  → kilit ve yapılandırma yazıldı', $si->isInstalled());
$sp = new PDO($sd);
check('  → yönetici oluştu ve parola düz saklanmadı', (int)$sp->query("SELECT COUNT(*) FROM portal_users WHERE role='admin'")->fetchColumn() === 1
    && strpos((string)$sp->query('SELECT password_hash FROM portal_users')->fetchColumn(), 'cok-guclu-parola-1') === false);
check('ikinci Softaculous kurulumu reddedilir', $si->installFromSoftaculous($sv)['ok'] === false);
file_put_contents($sr . '/migrations/002_ek.sql', 'CREATE TABLE soft_ek (id INTEGER PRIMARY KEY);');
$up = $si->upgrade();
check('yükseltme yeni migrasyonu uygular', $up['ok'] === true && $up['applied'] === ['002_ek.sql']);
check('  → veri korunur', (int)$sp->query("SELECT COUNT(*) FROM portal_users")->fetchColumn() === 1);
check('yükseltme tekrar çalışırsa yeni bir şey uygulamaz', $si->upgrade()['applied'] === []);
$sp = null;
$si = null;
rmtree($sb);
foreach ([['admin_pass' => 'kisa'], ['admin_username' => 'a b'], ['softdbname' => 'x;drop']] as $bad) {
    [$b6, $r6] = instEnv();
    $i6 = new Installer($r6);
    $res6 = $i6->installFromSoftaculous(array_replace($sv, ['softdbhost' => 'localhost'], $bad));
    check('geçersiz Softaculous girdisi reddedilir: ' . json_encode(array_keys($bad)), $res6['ok'] === false && !is_file($i6->configPath()) && !is_file($i6->lockPath()));
    rmtree($b6);
}
if (getenv('PORTAL_TEST_MYSQL_HOST')) {
    $h = getenv('PORTAL_TEST_MYSQL_HOST');
    $dbn = 'tpt_soft_' . getmypid();
    $adm = new PDO("mysql:host=$h;charset=utf8mb4", getenv('PORTAL_TEST_MYSQL_USER') ?: 'root', getenv('PORTAL_TEST_MYSQL_PASS') ?: '');
    $adm->exec("CREATE DATABASE `$dbn` CHARACTER SET utf8mb4");
    $mb = sys_get_temp_dir() . '/toya_softm_' . bin2hex(random_bytes(4));
    mkdir($mb . '/portal', 0777, true);
    $mi = new Installer($mb . '/portal', null, __DIR__ . '/../migrations');
    $rm = $mi->installFromSoftaculous(array_replace($sv, ['softdbhost' => $h . ':3306', 'softdbname' => $dbn,
        'softdbuser' => getenv('PORTAL_TEST_MYSQL_USER') ?: 'root', 'softdbpass' => getenv('PORTAL_TEST_MYSQL_PASS') ?: '']));
    check('[MariaDB] Softaculous kurulumu (sunucu:port biçimi) başarılı', $rm['ok'] === true);
    $mcfg = require $mb . '/portal/config.local.php';
    check('[MariaDB] yapılandırma doğru sunucu/port/veritabanını içerir', strpos($mcfg['db_dsn'], "host=$h;port=3306;dbname=$dbn") !== false);
    check('[MariaDB] yükseltme (bekleyen migrasyon yok) başarılı', $mi->upgrade() === ['ok' => true, 'applied' => []]);
    rmtree($mb);
    $adm->exec("DROP DATABASE IF EXISTS `$dbn`");
}

echo "yedekleme\n";
use Toya\Portal\BackupService;

$bkDir = sys_get_temp_dir() . '/toya_bk_' . bin2hex(random_bytes(4));
$bkc = $now;
$bpdo = db();
$bpdo->exec("CREATE TABLE bk_tricky (id INTEGER PRIMARY KEY, txt TEXT, num REAL, code VARCHAR(20), note TEXT)");
$tricky = [
    [1, "tek ' tırnak, \"çift\", ters \\ bölü; noktalı virgül", 0.1, '00123', null],
    [2, "satır\nsonu\r\nve\ttab", 1234567.891234567, '-0', ''],
    [3, 'Türkçe: ğüşiöçİĞÜŞÖÇ ✅', 1.0E+25, '0', '-- SQL yorum gibi görünen metin'],
    [4, "/* blok */ INSERT INTO x VALUES (1); DROP TABLE y;", -3.5, '9007199254740993', 'x'],
];
$ins = $bpdo->prepare('INSERT INTO bk_tricky (id, txt, num, code, note) VALUES (?,?,?,?,?)');
foreach ($tricky as $row) { $ins->execute($row); }
$bpdo->exec("INSERT INTO portal_users (username, password_hash, role, active, created_at) VALUES ('u1','hash1','admin',1,'2026-01-01 00:00:00')");
$bk = new BackupService($bpdo, $bkDir, null, function () use (&$bkc) { return $bkc; });
$snap = static function (PDO $p): string {
    $out = [];
    foreach (['bk_tricky', 'portal_users'] as $t) {
        $out[$t] = $p->query("SELECT * FROM $t ORDER BY 1")->fetchAll(PDO::FETCH_ASSOC);
    }
    return json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION);
};
$before = $snap($bpdo);

$c = $bk->create();
check('yedek alınır (ad biçimi, boyut, tablo/satır sayısı)', $c['ok'] && preg_match(BackupService::NAME_RE, $c['name']) === 1 && $c['size'] > 0 && $c['tables'] >= 2 && $c['rows'] >= 5);
check('  → geçici .part dosyası kalmadı', glob($bkDir . '/*.part') === []);
$vv = $bk->verify($bkDir . '/' . $c['name']);
check('  → bütünlük doğrulaması geçer, sayılar tutar', $vv['ok'] && $vv['tables'] === $c['tables'] && $vv['rows'] === $c['rows']);
check('  → yedek gizli anahtar/config içermez', strpos($vv['sql'], 'update_secret') === false && strpos($vv['sql'], 'agent_api_key') === false);
$c2 = $bk->create();
check('aynı saniyede ikinci yedek üzerine yazmaz (ek numara)', $c2['ok'] && $c2['name'] !== $c['name'] && count($bk->list()) === 2);

// veriyi boz, tabloyu düşür, geri yükle → birebir aynı olmalı
$bpdo->exec('DELETE FROM bk_tricky WHERE id IN (1,3)');
$bpdo->exec("UPDATE bk_tricky SET txt='bozuldu' WHERE id=2");
$bpdo->exec('DROP TABLE portal_users');
$rs = $bk->restore($c['name']);
check('geri yükleme başarılı', $rs['ok'] === true && $rs['statements'] > 5);
check('  → geri yüklenen veri BİREBİR aynı (tırnak, ters bölü, satır sonu, Türkçe, NULL, boş, hassas double)', $snap($bpdo) === $before);
check('  → bozulan/silinen/düşen her şey geri geldi', (int)$bpdo->query('SELECT COUNT(*) FROM bk_tricky')->fetchColumn() === 4 && (int)$bpdo->query('SELECT COUNT(*) FROM portal_users')->fetchColumn() === 1);

// bozuk / yarım / yabancı dosyalar reddedilir
$good = file_get_contents($bkDir . '/' . $c['name']);
file_put_contents($bkDir . '/portal-db-20200101-000000.sql.gz', substr($good, 0, (int)(strlen($good) / 2)));
check('yarım (kesik) yedek geri yüklenmez', $bk->restore('portal-db-20200101-000000.sql.gz')['ok'] === false);
file_put_contents($bkDir . '/portal-db-20200101-000001.sql.gz', gzencode("-- TOYA-PORTAL-BACKUP v1\n-- driver: sqlite\nDROP TABLE portal_users;\n"));
$rf = $bk->restore('portal-db-20200101-000001.sql.gz');
check('bütünlük işareti olmayan yedek geri yüklenmez (tablo düşürülmedi)', $rf['ok'] === false && strpos($rf['error'], 'yarım') !== false
    && (int)$bpdo->query('SELECT COUNT(*) FROM portal_users')->fetchColumn() === 1);
file_put_contents($bkDir . '/portal-db-20200101-000002.sql.gz', gzencode("baska bir dosya\n"));
check('TOYA yedeği olmayan dosya reddedilir', strpos((string)$bk->restore('portal-db-20200101-000002.sql.gz')['error'], 'TOYA portal yedeği değil') !== false);
$otherDriver = $bpdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite' ? 'mysql' : 'sqlite';
file_put_contents($bkDir . '/portal-db-20200101-000003.sql.gz', gzencode("-- TOYA-PORTAL-BACKUP v1\n-- driver: $otherDriver\nDROP TABLE portal_users;\n-- END TOYA-PORTAL-BACKUP tables=0 rows=0\n"));
$rd = $bk->restore('portal-db-20200101-000003.sql.gz');
check('başka veritabanı türünün yedeği reddedilir (ve hiçbir şey çalıştırılmaz)', $rd['ok'] === false && strpos($rd['error'], $otherDriver) !== false
    && (int)$bpdo->query('SELECT COUNT(*) FROM portal_users')->fetchColumn() === 1);

// yol güvenliği ve listeleme
foreach (['../../etc/passwd', 'portal-db-20200101-000000.sql.gz/../x', 'x.sql.gz', 'portal-db-2020.sql.gz', "portal-db-20200101-000000.sql.gz\0.php", '/etc/passwd'] as $badName) {
    check('geçersiz yedek adı reddedilir: ' . json_encode($badName), $bk->path($badName) === null);
}
$names = array_column($bk->list(), 'name');
$sortedDesc = $names;
rsort($sortedDesc, SORT_STRING);
check('liste en yeni önce sıralı ve özet (sha256) içerir', $names === $sortedDesc && count($names) >= 4 && strlen($bk->list()[0]['sha256']) === 64);
$total = count($bk->list());
$del = $bk->prune(2);
check('prune en yeni 2 yedeği bırakır', $del === $total - 2 && count($bk->list()) === 2 && $bk->list()[0]['name'] === max($names));
check('prune en az 1 yedek bırakır', $bk->prune(0) === 1 && count($bk->list()) === 1);
foreach (glob($bkDir . '/*') as $f) { unlink($f); }
rmdir($bkDir);

echo "yedek: çok sayfalı tablo\n";
$pgDir = sys_get_temp_dir() . '/toya_bkp_' . bin2hex(random_bytes(4));
$pgpdo = db();
$pgIns = $pgpdo->prepare("INSERT INTO portal_sync_log (created_at, source, entity, run, action, status, received, message) VALUES (?,?,?,?,?,?,?,?)");
$pgpdo->beginTransaction();
for ($i = 1; $i <= 2350; $i++) { // 1000'lik sayfa sınırını iki kez aşar
    $pgIns->execute(['2026-01-01 00:00:00', 'src', 'ent', 'run', 'ingest', 'ok', $i, "satır $i"]);
}
$pgpdo->commit();
$pgbk = new BackupService($pgpdo, $pgDir);
$pgr = $pgbk->create();
$pgSum = static fn(PDO $p): string => $p->query("SELECT COUNT(*) || ':' || COALESCE(SUM(received),0) FROM portal_sync_log")->fetchColumn();
if ($pgpdo->getAttribute(PDO::ATTR_DRIVER_NAME) !== 'sqlite') {
    $pgSum = static fn(PDO $p): string => $p->query("SELECT CONCAT(COUNT(*), ':', COALESCE(SUM(received),0)) FROM portal_sync_log")->fetchColumn();
}
$pgBefore = $pgSum($pgpdo);
check('çok sayfalı tabloda hiçbir satır atlanmaz/tekrarlanmaz (2350 satır)', $pgr['ok'] && $pgBefore === '2350:' . (2350 * 2351 / 2));
$pgpdo->exec('DELETE FROM portal_sync_log');
$pgbk->restore($pgr['name']);
check('  → geri yükleme sonrası satır sayısı ve toplam aynı', $pgSum($pgpdo) === $pgBefore);
foreach (glob($pgDir . '/*') as $f) { unlink($f); }
rmdir($pgDir);

echo "yedek api\n";
$adir = sys_get_temp_dir() . '/toya_bka_' . bin2hex(random_bytes(4));
$apdo = db();
$abk = new BackupService($apdo, $adir);
$asvc = new PortalService($apdo, 30, function () use ($now) { return $now; });
[$c, $o] = portal_route($asvc, 'GET', '/backups', [], [], false, null, null, null, $abk);
check('yedek listesi anahtarsız 401', $c === 401);
[$c, $o] = portal_route($asvc, 'POST', '/backups', [], [], false, null, null, null, $abk);
check('yedek alma anahtarsız 401', $c === 401 && $abk->list() === []);
[$c, $o] = portal_route($asvc, 'GET', '/backups/portal-db-20200101-000000.sql.gz', [], [], false, null, null, null, $abk);
check('yedek indirme anahtarsız 401', $c === 401);
[$c, $o] = portal_route($asvc, 'POST', '/backups', [], [], true, null, null, null, $abk);
check('ajan yedek aldırabilir', $c === 200 && $o['ok'] && preg_match(BackupService::NAME_RE, $o['name']) === 1 && $o['pruned'] === 0);
$bname = $o['name'];
[$c, $o] = portal_route($asvc, 'GET', '/backups', [], [], true, null, null, null, $abk);
check('ajan yedekleri listeler (sha256 dahil)', $c === 200 && $o['backups'][0]['name'] === $bname && strlen($o['backups'][0]['sha256']) === 64);
[$c, $o] = portal_route($asvc, 'GET', "/backups/$bname", [], [], true, null, null, null, $abk);
check('ajan yedeği indirebilir (dosya yolu döner)', $c === 200 && is_file($o['__file']) && $o['__name'] === $bname);
foreach (['..', 'portal-db-20200101-000000.sql.gz', 'passwd', 'x.sql.gz', '..%2f..%2fconfig.local.php'] as $bn) {
    [$c, $o] = portal_route($asvc, 'GET', "/backups/$bn", [], [], true, null, null, null, $abk);
    check("olmayan/geçersiz yedek adı 404: $bn", $c === 404);
}
[$c, $o] = portal_route($asvc, 'GET', '/backups/../../config.local.php', [], [], true, null, null, null, $abk);
check('yol gezintisi denemesi eşleşmez (404)', $c === 404);
[$c, $o] = portal_route($asvc, 'DELETE', "/backups/$bname", [], [], true, null, null, null, $abk);
check('API ile yedek SİLİNEMEZ (silme ucu yok)', $c === 404 && is_file($adir . '/' . $bname));
foreach (glob($adir . '/*') as $f) { unlink($f); }
rmdir($adir);

echo "ayna http\n";
$hp = db();
$hm = new Toya\Portal\MirrorService($hp, function () use ($now) { return $now; });
$hs = new PortalService($hp, 30, function () use ($now) { return $now; });
[$c, $o] = portal_route($hs, 'POST', '/mirror/cari', ['source' => 'wolvox', 'run' => 'r1', 'records' => [['ext_id' => '1']]], [], false, null, null, $hm);
check('ayna yükleme anahtarsız 401', $c === 401);
[$c, $o] = portal_route($hs, 'POST', '/mirror/cari', ['source' => 'wolvox', 'run' => 'r1', 'records' => [['ext_id' => '1', 'unvan' => 'A']]], [], true, null, null, $hm);
check('ayna yükleme ajanla 200', $c === 200 && $o['added'] === 1);
[$c, $o] = portal_route($hs, 'POST', '/mirror/kullanici', ['source' => 'w', 'run' => 'r', 'records' => []], [], true, null, null, $hm);
check('bilinmeyen varlık 404', $c === 404);
[$c, $o] = portal_route($hs, 'POST', '/mirror/finish', ['source' => 'wolvox', 'run' => 'r2', 'entities' => ['cari']], [], true, null, null, $hm);
check('finish 200 ve kaybolan sayısı', $c === 200 && $o['vanished']['cari'] === 1);
[$c, $o] = portal_route($hs, 'GET', '/mirror/counts', [], ['source' => 'wolvox'], true, null, null, $hm);
check('sayım ucu çalışır', $c === 200 && $o['counts']['cari'] === 0);
[$c, $o] = portal_route($hs, 'GET', '/mirror/counts', [], ['source' => 'wolvox'], false, null, null, $hm);
check('sayım anahtarsız 401', $c === 401);

echo "http yönlendirme\n";
[$c, $o] = portal_route($rs = new PortalService(db(), 30, function () use ($now) { return $now; }), 'POST', '/accounts', ['source' => 'toya', 'external_ref' => 'C-9', 'balance' => 10], [], false, null, null);
check('hesap yayını anahtarsız 401', $c === 401);
[$c, $o] = portal_route($rs, 'POST', '/accounts', ['source' => 'toya', 'external_ref' => 'C-9', 'balance' => 10], [], true, null, null);
check('hesap yayını ajanla 200', $c === 200 && strlen($o['token']) === 64);
[$c, $o2] = portal_route($rs, 'GET', '/a/' . $o['token'], [], [], false, '1.1.1.1', 'UA');
check('müşteri hesap görüntüleme 200 (anahtarsız)', $c === 200 && $o2['data']['balance'] === 10.0);
$rs = new PortalService(db(), 30, function () use ($now) { return $now; });
[$c, $o] = portal_route($rs, 'POST', '/publications', payload(), [], false, null, null);
check('ajan anahtarı olmadan yayın 401', $c === 401);
[$c, $o] = portal_route($rs, 'POST', '/publications', payload(), [], true, null, null);
check('ajan yayını 200 ve token döner', $c === 200 && strlen($o['token']) === 64);
$tok = $o['token'];
[$c, $o] = portal_route($rs, 'GET', "/p/$tok", [], [], false, '1.1.1.1', 'UA');
check('müşteri görüntüleme 200 (anahtarsız)', $c === 200 && $o['data']['external_ref'] === 'TKL-001');
[$c, $o] = portal_route($rs, 'GET', '/decisions', [], [], false, null, null);
check('kararları anahtarsız çekmek 401', $c === 401);
[$c, $o] = portal_route($rs, 'POST', "/p/$tok/counter", ['amount' => 'abc'], [], false, null, null);
check('geçersiz tutar 422', $c === 422);
[$c, $o] = portal_route($rs, 'POST', "/p/$tok/accept", ['note' => 'tamam'], [], false, '1.1.1.1', 'UA');
check('kabul 200', $c === 200);
[$c, $o] = portal_route($rs, 'POST', "/p/$tok/reject", [], [], false, null, null);
check('kabulden sonra ret 409', $c === 409);
[$c, $o] = portal_route($rs, 'GET', '/decisions', [], ['after' => 0], true, null, null);
check('ajan kararı çeker', $c === 200 && $o['decisions'][0]['event_type'] === 'accept');
[$c, $o] = portal_route($rs, 'GET', '/p/' . str_repeat('b', 64), [], [], false, null, null);
check('bilinmeyen token 404', $c === 404);
[$c, $o] = portal_route($rs, 'GET', '/bilinmeyen', [], [], false, null, null);
check('bilinmeyen rota 404', $c === 404);

echo "\n$passed geçti, $failed başarısız\n";
exit($failed > 0 ? 1 : 0);
