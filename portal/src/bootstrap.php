<?php
declare(strict_types=1);

require_once __DIR__ . '/PortalService.php';
require_once __DIR__ . '/MirrorService.php';
require_once __DIR__ . '/AuthService.php';
require_once __DIR__ . '/ReportService.php';
require_once __DIR__ . '/Migrator.php';
require_once __DIR__ . '/Updater.php';
require_once __DIR__ . '/Installer.php';
require_once __DIR__ . '/BackupService.php';

use Toya\Portal\BackupService;
use Toya\Portal\MirrorService;
use Toya\Portal\PortalService;
use Toya\Portal\Updater;

/**
 * config.local.php (repoya girmez) şu anahtarları döndürür:
 *   db_dsn, db_user, db_pass, agent_api_key, token_days, base_url
 * Örnek için config.sample.php'ye bakın.
 */
/** Kurulum tamamlandı mı (yapılandırma + kurulum kilidi var mı)? */
function portal_installed(): bool
{
    $root = dirname(__DIR__);
    return is_file($root . '/config.local.php') && is_file($root . '/storage/install.lock');
}

function portal_config(): array
{
    static $cfg = null;
    if ($cfg === null) {
        $path = __DIR__ . '/../config.local.php';
        if (!is_file($path)) {
            http_response_code(500);
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode(['ok' => false, 'error' => 'not_configured']);
            exit;
        }
        $cfg = require $path;
    }
    return $cfg;
}

function portal_pdo(): PDO
{
    static $pdo = null;
    if ($pdo === null) {
        $cfg = portal_config();
        $pdo = new PDO($cfg['db_dsn'], $cfg['db_user'] ?? null, $cfg['db_pass'] ?? null, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
    }
    return $pdo;
}

function portal_service(?PDO $pdo = null): PortalService
{
    return new PortalService($pdo ?? portal_pdo(), (int)(portal_config()['token_days'] ?? 30));
}

function portal_backup(?PDO $pdo = null): BackupService
{
    $root = dirname(__DIR__);
    return new BackupService(
        $pdo ?? portal_pdo(), $root . '/storage/db_backups', $root . '/VERSION', null,
        (int)(portal_config()['backup_keep'] ?? 14)
    );
}

function portal_mirror(?PDO $pdo = null): MirrorService
{
    return new MirrorService($pdo ?? portal_pdo());
}

function portal_updater(?PDO $pdo = null): Updater
{
    $root = dirname(__DIR__);
    $secret = (string)(portal_config()['update_secret'] ?? '');
    return new Updater($pdo ?? portal_pdo(), $root, $secret);
}

function json_out(array $payload, int $code = 200): void
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/** @return array<string,mixed> */
function json_body(): array
{
    $raw = file_get_contents('php://input') ?: '';
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

/**
 * HTTP yönlendirmesi. `$method` ve `$path` ("/publications" gibi, /api/v1 öneki olmadan) verilir;
 * test edilebilir olsun diye global durumdan bağımsızdır.
 *
 * @param array<string,mixed> $body
 * @param array<string,mixed> $query
 * @return array{0:int,1:array<string,mixed>} [http kodu, gövde]
 */
function portal_route(
    PortalService $svc, string $method, string $path, array $body, array $query,
    bool $isAgent, ?string $ip, ?string $ua, ?MirrorService $mirror = null, ?BackupService $backup = null,
    ?Updater $updater = null
): array {
    $errCode = static fn(string $e): int => match ($e) {
        'not_found' => 404,
        'expired', 'revoked' => 410,
        'already_decided', 'counter_already_sent' => 409,
        default => 422,
    };

    // ---- Ajan uçları ----
    if ($path === '/publications' && $method === 'POST') {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        $r = $svc->publish($body);
        return [$r['ok'] ? 200 : $errCode($r['error']), $r];
    }
    if ($path === '/publications/revoke' && $method === 'POST') {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        $r = $svc->revoke((string)($body['source'] ?? ''), (string)($body['external_ref'] ?? ''));
        return [$r['ok'] ? 200 : $errCode($r['error']), $r];
    }
    if ($path === '/accounts' && $method === 'POST') {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        $r = $svc->publishAccount($body);
        return [$r['ok'] ? 200 : $errCode($r['error']), $r];
    }
    if ($path === '/accounts/revoke' && $method === 'POST') {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        $r = $svc->revokeAccount((string)($body['source'] ?? ''), (string)($body['external_ref'] ?? ''));
        return [$r['ok'] ? 200 : $errCode($r['error']), $r];
    }
    if (preg_match('#^/mirror/(finish|counts|[a-z_]+)$#', $path, $m)) {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        if ($mirror === null) {
            return [500, ['ok' => false, 'error' => 'not_configured']];
        }
        $errCode2 = static fn(string $e): int => $e === 'unknown_entity' ? 404 : ($e === 'too_many_records' ? 413 : 422);
        if ($m[1] === 'counts' && $method === 'GET') {
            return [200, ['ok' => true, 'counts' => $mirror->counts((string)($query['source'] ?? ''))]];
        }
        if ($m[1] === 'finish' && $method === 'POST') {
            $r = $mirror->finish((string)($body['source'] ?? ''), (string)($body['run'] ?? ''),
                is_array($body['entities'] ?? null) ? $body['entities'] : [], $ip);
            return [$r['ok'] ? 200 : $errCode2($r['error']), $r];
        }
        if ($method === 'POST') {
            $r = $mirror->ingest($m[1], (string)($body['source'] ?? ''), (string)($body['run'] ?? ''),
                is_array($body['records'] ?? null) ? $body['records'] : [], $ip);
            return [$r['ok'] ? 200 : $errCode2($r['error']), $r];
        }
    }
    if (preg_match('#^/backups(?:/([A-Za-z0-9._-]+))?$#', $path, $m)) {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        if ($backup === null) {
            return [500, ['ok' => false, 'error' => 'not_configured']];
        }
        $bname = $m[1] ?? null;
        if ($bname === null && $method === 'GET') {
            return [200, ['ok' => true, 'backups' => $backup->list()]];
        }
        if ($bname === null && $method === 'POST') {
            $r = $backup->create();
            if ($r['ok']) {
                $r['pruned'] = $backup->applyRetention();
            }
            return [$r['ok'] ? 200 : 500, $r];
        }
        if ($bname !== null && $method === 'GET') {
            $p = $backup->path($bname);
            if ($p === null) {
                return [404, ['ok' => false, 'error' => 'not_found']];
            }
            return [200, ['__file' => $p, '__name' => $bname]];
        }
    }
    if ($path === '/decisions' && $method === 'GET') {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        return [200, ['ok' => true, 'decisions' => $svc->decisions((int)($query['after'] ?? 0))]];
    }
    // TOYA masaüstü, FTP ile update_inbox/'a paket bıraktıktan SONRA bunu çağırır — yöneticinin ayrıca
    // update.php'ye girip elle "Kur"a basmasına gerek kalmadan otomatik kurulum. Aynı `agent_api_key`
    // ile korunur (update_secret paket imzası için ayrı bir amaca hizmet ediyor, burada karıştırılmadı).
    if ($path === '/update/apply' && $method === 'POST') {
        if (!$isAgent) {
            return [401, ['ok' => false, 'error' => 'unauthorized']];
        }
        if ($updater === null) {
            return [500, ['ok' => false, 'error' => 'not_configured']];
        }
        $pkgName = basename((string)($body['package'] ?? ''));
        if (!preg_match('/^toya-portal-\d+\.\d+\.\d+\.zip$/', $pkgName)) {
            return [400, ['ok' => false, 'error' => 'invalid_package_name']];
        }
        $root = $updater->root();
        $pkgPath = $root . '/update_inbox/' . $pkgName;
        if (!is_file($pkgPath)) {
            return [404, ['ok' => false, 'error' => 'package_not_found']];
        }
        try {
            $result = $updater->apply($pkgPath, !empty($body['reinstall']));
        } catch (\Throwable $e) {
            return [500, ['ok' => false, 'error' => $e->getMessage()]];
        }
        if (!empty($result['ok'])) {
            $done = $root . '/storage/applied';
            if (!is_dir($done)) {
                @mkdir($done, 0755, true);
            }
            @rename($pkgPath, $done . '/' . $pkgName);
        }
        return [!empty($result['ok']) ? 200 : 500, ['ok' => !empty($result['ok'])] + $result];
    }

    // ---- Müşteri (herkese açık, token ile) uçları ----
    if (preg_match('#^/p/([0-9a-f]{64})$#', $path, $m) && $method === 'GET') {
        $r = $svc->view($m[1], $ip, $ua);
        return [$r['ok'] ? 200 : $errCode($r['error']), $r];
    }
    if (preg_match('#^/a/([0-9a-f]{64})$#', $path, $m) && $method === 'GET') {
        $r = $svc->viewAccount($m[1], $ip, $ua);
        return [$r['ok'] ? 200 : $errCode($r['error']), $r];
    }
    if (preg_match('#^/p/([0-9a-f]{64})/(accept|reject|counter)$#', $path, $m) && $method === 'POST') {
        $amount = isset($body['amount']) ? (float)$body['amount'] : null;
        $r = $svc->decide($m[1], $m[2], isset($body['note']) ? (string)$body['note'] : null, $amount, $ip, $ua);
        return [$r['ok'] ? 200 : $errCode($r['error']), $r];
    }

    return [404, ['ok' => false, 'error' => 'not_found']];
}
