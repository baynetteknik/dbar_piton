<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';

use Toya\Portal\AuthService;
use Toya\Portal\MirrorService;
use Toya\Portal\ReportService;

const WEB_IDLE_SECONDS = 3600;

// Kurulmamış portalda tüm web sayfaları kurulum sihirbazına yönlenir (sihirbazın kendisi hariç).
if (!portal_installed() && basename((string)($_SERVER['SCRIPT_NAME'] ?? '')) !== 'install.php') {
    header('Location: install.php');
    exit;
}

function web_session(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || ($_SERVER['SERVER_PORT'] ?? '') === '443';
    session_name('toya_portal');
    session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'secure' => $https, 'httponly' => true, 'samesite' => 'Strict']);
    session_start();
    header('Cache-Control: no-store');
    header('X-Robots-Tag: noindex, nofollow');
    header('X-Frame-Options: DENY');
    header('X-Content-Type-Options: nosniff');
    header("Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'");
    if (isset($_SESSION['last']) && time() - (int)$_SESSION['last'] > WEB_IDLE_SECONDS) {
        $_SESSION = [];
    }
    $_SESSION['last'] = time();
}

function web_auth(): AuthService
{
    return new AuthService(portal_pdo(), (int)(portal_config()['max_users'] ?? 5));
}

function web_reports(): ReportService
{
    return new ReportService(portal_pdo());
}

/** @return array<string,mixed>|null */
function web_user(): ?array
{
    web_session();
    return $_SESSION['user'] ?? null;
}

/** @return array<string,mixed> */
function web_require_login(?string $role = null): array
{
    $u = web_user();
    if ($u === null) {
        header('Location: login.php');
        exit;
    }
    if ($role !== null && ($u['role'] ?? '') !== $role) {
        http_response_code(403);
        echo 'Bu sayfa için yetkiniz yok.';
        exit;
    }
    return $u;
}

function web_csrf(): string
{
    web_session();
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(16));
    }
    return (string)$_SESSION['csrf'];
}

function web_check_csrf(): void
{
    web_session();
    $sent = (string)($_POST['csrf'] ?? '');
    if ($sent === '' || !hash_equals((string)($_SESSION['csrf'] ?? ''), $sent)) {
        http_response_code(400);
        echo 'Geçersiz istek (oturum süresi dolmuş olabilir). Sayfayı yenileyip tekrar deneyin.';
        exit;
    }
}

function h(mixed $v): string
{
    return htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function money(mixed $v): string
{
    return number_format((float)$v, 2, ',', '.');
}

function fdate(?string $v): string
{
    return $v ? substr($v, 0, 10) : '';
}

/** Geçerli kaynak: ?s= sorgu parametresi (kayıtlı kaynaklardan biriyse), yoksa ilki. */
function web_source(ReportService $r): ?string
{
    $all = $r->sources();
    $s = (string)($_GET['s'] ?? '');
    if ($s !== '' && in_array($s, $all, true)) {
        return $s;
    }
    return $all[0] ?? null;
}

function web_header(string $title, ?array $user = null, ?string $source = null, array $sources = []): void
{
    $q = $source !== null ? '?s=' . urlencode($source) : '';
    echo '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width, initial-scale=1">'
        . '<meta name="robots" content="noindex,nofollow"><title>' . h($title) . ' · TOYA Portal</title>'
        . '<style>
:root{--bg:#f8fafc;--card:#fff;--ink:#1e293b;--mut:#64748b;--line:#e2e8f0;--pri:#2563eb;--bad:#b91c1c;--ok:#15803d}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--line:#334155}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:16px}nav{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;padding:10px 16px;background:var(--card);border-bottom:1px solid var(--line)}
nav a{color:var(--ink);text-decoration:none;font-weight:600}nav a:hover{color:var(--pri)}nav .sp{flex:1}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
h1{font-size:20px;margin:0 0 10px}.mut{color:var(--mut);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.tile .v{font-size:22px;font-weight:800}
.debt{color:var(--bad)}.credit{color:var(--ok)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--mut);text-transform:uppercase}td.n,th.n{text-align:right;white-space:nowrap}
input,select,button{font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
button{background:var(--pri);color:#fff;border:0;font-weight:600;cursor:pointer}button.sec{background:var(--card);color:var(--ink);border:1px solid var(--line)}
form.inline{display:inline}.err{background:#fee2e2;color:var(--bad);padding:10px;border-radius:8px;margin-bottom:12px}.okm{background:#dcfce7;color:var(--ok);padding:10px;border-radius:8px;margin-bottom:12px}
label{display:block;margin:8px 0 2px;font-weight:600;font-size:13px}.row{display:flex;flex-wrap:wrap;gap:8px;align-items:end}
@media (max-width:640px){.hide-m{display:none}}
</style></head><body>';
    if ($user !== null) {
        echo '<nav><strong>TOYA Portal</strong>'
            . '<a href="teklifler.php">Teklifler</a>'
            . '<a href="index.php' . h($q) . '">Özet</a>'
            . '<a href="cariler.php' . h($q) . '">Cariler</a>'
            . '<a href="faturalar.php' . h($q) . '">Faturalar</a>';
        if (($user['role'] ?? '') === 'admin') {
            echo '<a href="sync_log.php">Aktarım Günlüğü</a><a href="backup.php">Yedekleme</a><a href="update.php">Güncelleme</a><a href="users.php">Kullanıcılar</a>';
        }
        echo '<span class="sp"></span>';
        if (count($sources) > 1) {
            echo '<form method="get" class="inline"><select name="s" onchange="this.form.submit()">';
            foreach ($sources as $s) {
                echo '<option value="' . h($s) . '"' . ($s === $source ? ' selected' : '') . '>' . h($s) . '</option>';
            }
            echo '</select></form>';
        }
        echo '<span class="mut">' . h($user['username'] ?? '') . '</span>'
            . '<form method="post" action="logout.php" class="inline"><input type="hidden" name="csrf" value="' . h(web_csrf()) . '">'
            . '<button class="sec">Çıkış</button></form></nav>';
    }
    echo '<div class="wrap">';
}

function web_footer(): void
{
    echo '</div></body></html>';
}
