<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

/**
 * Portal ilk kurulum çekirdeği (web sihirbazı `public/install.php` bunu kullanır).
 *
 * Güvenlik modeli:
 *  - Kurulum bittiğinde `storage/install.lock` yazılır; kilit ve yapılandırma varken sihirbaz kapalıdır.
 *  - Kurulumdan ÖNCEKİ açık kalma penceresinde sihirbazı bir yabancının kendi veritabanı/yöneticisiyle
 *    çalıştırmasını önlemek için tek kullanımlık bir kurulum anahtarı gerekir. Anahtar sunucudaki
 *    `storage/install_token.txt` dosyasında durur (web'den okunamaz); yalnızca dosya sistemine (FTP/Dosya Yöneticisi)
 *    erişimi olan kişi okuyup girebilir. Kurulum bitince dosya silinir.
 *  - Veritabanı bilgileri DSN'e girmeden doğrulanır (`;`, `=` vb. ile DSN enjeksiyonu engellenir).
 *  - Parolalar hata mesajlarına yazılmaz. Yapılandırma `var_export` ile üretilir (tırnak/`$` güvenli).
 */
final class Installer
{
    public const MIN_PHP = '8.0.0';
    private const REQUIRED_EXTENSIONS = ['pdo', 'pdo_mysql', 'zip', 'json', 'mbstring'];

    private string $root;
    private ?string $dsnOverride;
    private string $migrationsDir;
    /** @var callable():int */
    private $clock;

    /**
     * @param string|null $dsnOverride yalnızca testler için (web'den asla verilmez)
     */
    public function __construct(string $root, ?string $dsnOverride = null, ?string $migrationsDir = null, ?callable $clock = null)
    {
        $this->root = rtrim(str_replace('\\', '/', $root), '/');
        $this->dsnOverride = $dsnOverride;
        $this->migrationsDir = $migrationsDir ?? $this->root . '/migrations';
        $this->clock = $clock ?? static fn(): int => time();
    }

    public function configPath(): string
    {
        return $this->root . '/config.local.php';
    }

    public function lockPath(): string
    {
        return $this->root . '/storage/install.lock';
    }

    public function tokenPath(): string
    {
        return $this->root . '/storage/install_token.txt';
    }

    /** Kilit ve yapılandırma varsa kurulu sayılır. */
    public function isInstalled(): bool
    {
        return is_file($this->lockPath()) && is_file($this->configPath());
    }

    // ------------------------------------------------------------------
    // Kurulum anahtarı
    // ------------------------------------------------------------------

    /** Anahtar dosyası yoksa üretir. Anahtar web yanıtlarına ASLA konmaz. @return bool dosya hazır mı */
    public function ensureToken(): bool
    {
        if (is_file($this->tokenPath())) {
            return true;
        }
        $dir = dirname($this->tokenPath());
        if (!is_dir($dir) && !@mkdir($dir, 0755, true) && !is_dir($dir)) {
            return false;
        }
        $ok = @file_put_contents($this->tokenPath(), bin2hex(random_bytes(16)) . "\n") !== false;
        if ($ok) {
            @chmod($this->tokenPath(), 0600);
        }
        return $ok;
    }

    public function verifyToken(string $given): bool
    {
        $given = trim($given);
        if ($given === '' || !is_file($this->tokenPath())) {
            return false;
        }
        return hash_equals(trim((string)file_get_contents($this->tokenPath())), $given);
    }

    // ------------------------------------------------------------------
    // Gereksinimler
    // ------------------------------------------------------------------

    /** @return array<int,array{name:string,ok:bool,detail:string}> */
    public function requirements(): array
    {
        $out = [];
        $out[] = ['name' => 'PHP ' . self::MIN_PHP . '+', 'ok' => version_compare(PHP_VERSION, self::MIN_PHP, '>='),
            'detail' => 'Kurulu: ' . PHP_VERSION];
        foreach (self::REQUIRED_EXTENSIONS as $ext) {
            $out[] = ['name' => "PHP eklentisi: $ext", 'ok' => extension_loaded($ext), 'detail' => ''];
        }
        $storage = $this->root . '/storage';
        if (!is_dir($storage)) {
            @mkdir($storage, 0755, true);
        }
        foreach (['storage' => $storage, 'update_inbox' => $this->root . '/update_inbox'] as $label => $dir) {
            if (!is_dir($dir)) {
                @mkdir($dir, 0755, true);
            }
            $out[] = ['name' => "Yazılabilir klasör: $label/", 'ok' => is_dir($dir) && is_writable($dir), 'detail' => ''];
        }
        $out[] = ['name' => 'Yapılandırma yazılabilir (kök klasör)', 'ok' => is_writable($this->root) || is_file($this->configPath()) && is_writable($this->configPath()),
            'detail' => 'config.local.php buraya yazılır'];
        return $out;
    }

    public function requirementsMet(): bool
    {
        foreach ($this->requirements() as $r) {
            if (!$r['ok']) {
                return false;
            }
        }
        return true;
    }

    // ------------------------------------------------------------------
    // Veritabanı
    // ------------------------------------------------------------------

    /**
     * @param array<string,mixed> $db host, port, name, user, pass
     * @return array{ok:bool, error?:string, pdo?:PDO, dsn?:string}
     */
    public function connect(array $db): array
    {
        if ($this->dsnOverride !== null) {
            $dsn = $this->dsnOverride;
        } else {
            $host = trim((string)($db['host'] ?? ''));
            $port = (int)($db['port'] ?? 3306);
            $name = trim((string)($db['name'] ?? ''));
            if (!preg_match('/^[A-Za-z0-9._-]{1,253}$/', $host)) {
                return ['ok' => false, 'error' => 'Veritabanı sunucusu geçersiz (yalnızca harf, rakam, . _ - kullanılabilir).'];
            }
            if ($port < 1 || $port > 65535) {
                return ['ok' => false, 'error' => 'Port 1-65535 arasında olmalı.'];
            }
            if (!preg_match('/^[A-Za-z0-9_$-]{1,64}$/', $name)) {
                return ['ok' => false, 'error' => 'Veritabanı adı geçersiz (yalnızca harf, rakam, _ $ - kullanılabilir).'];
            }
            $dsn = "mysql:host=$host;port=$port;dbname=$name;charset=utf8mb4";
        }
        $user = (string)($db['user'] ?? '');
        $pass = (string)($db['pass'] ?? '');
        if (strpos($user . $pass, "\0") !== false) {
            return ['ok' => false, 'error' => 'Geçersiz karakter.'];
        }
        try {
            $pdo = new PDO($dsn, $user, $pass, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_TIMEOUT => 10]);
        } catch (\PDOException $e) {
            $msg = $e->getMessage();
            if ($pass !== '') {
                $msg = str_replace($pass, '***', $msg);
            }
            $code = (string)$e->getCode();
            if ($code === '1045' || stripos($msg, 'Access denied') !== false) {
                return ['ok' => false, 'error' => 'Veritabanı kullanıcı adı/parolası hatalı.'];
            }
            if ($code === '1049' || stripos($msg, 'Unknown database') !== false) {
                return ['ok' => false, 'error' => 'Veritabanı bulunamadı (cPanel\'de önce oluşturup kullanıcıya yetki verin).'];
            }
            return ['ok' => false, 'error' => 'Veritabanına bağlanılamadı: ' . mb_substr($msg, 0, 200)];
        }
        return ['ok' => true, 'pdo' => $pdo, 'dsn' => $dsn];
    }

    // ------------------------------------------------------------------
    // Kurulum
    // ------------------------------------------------------------------

    public static function randomSecret(): string
    {
        return bin2hex(random_bytes(24));
    }

    /** @param array<string,mixed> $cfg */
    public static function renderConfig(array $cfg): string
    {
        return "<?php\n// TOYA Portal yapılandırması (kurulum sihirbazı tarafından üretildi). Repoya/paketlere girmez.\nreturn "
            . var_export($cfg, true) . ";\n";
    }

    /**
     * @param array<string,mixed> $in db{host,port,name,user,pass}, admin{username,password}, base_url
     * @return array{ok:bool, error?:string, keys?:array{agent_api_key:string,update_secret:string}, base_url?:string}
     */
    public function install(array $in): array
    {
        if ($this->isInstalled()) {
            return ['ok' => false, 'error' => 'Portal zaten kurulu.'];
        }
        if (!$this->requirementsMet()) {
            return ['ok' => false, 'error' => 'Sistem gereksinimleri karşılanmıyor.'];
        }
        $admin = (array)($in['admin'] ?? []);
        $username = trim((string)($admin['username'] ?? ''));
        $password = (string)($admin['password'] ?? '');
        if (!preg_match('/^[A-Za-z0-9._-]{3,60}$/', $username)) {
            return ['ok' => false, 'error' => 'Yönetici kullanıcı adı 3-60 karakter; harf, rakam, . _ - kullanılabilir.'];
        }
        if (strlen($password) < AuthService::MIN_PASSWORD_LENGTH) {
            return ['ok' => false, 'error' => 'Yönetici parolası en az ' . AuthService::MIN_PASSWORD_LENGTH . ' karakter olmalı.'];
        }
        if (($admin['password2'] ?? $password) !== $password) {
            return ['ok' => false, 'error' => 'Parolalar aynı değil.'];
        }

        $c = $this->connect((array)($in['db'] ?? []));
        if (!$c['ok']) {
            return ['ok' => false, 'error' => $c['error']];
        }
        /** @var PDO $pdo */
        $pdo = $c['pdo'];

        $mig = (new Migrator($pdo, $this->migrationsDir, $this->clock))->migrate();
        if (!$mig['ok']) {
            return ['ok' => false, 'error' => 'Veritabanı tabloları oluşturulamadı (' . $mig['failed'] . '): ' . mb_substr((string)$mig['error'], 0, 200)];
        }
        $auth = new AuthService($pdo, 5, $this->clock);
        if ($auth->hasAnyUser()) {
            return ['ok' => false, 'error' => 'Bu veritabanında zaten kullanıcı var; kurulum durduruldu (mevcut verinin üzerine yazılmaz).'];
        }
        $r = $auth->createUser($username, $password, 'admin');
        if (!$r['ok']) {
            return ['ok' => false, 'error' => 'Yönetici oluşturulamadı: ' . $r['error']];
        }

        $keys = ['agent_api_key' => self::randomSecret(), 'update_secret' => self::randomSecret()];
        $db = (array)$in['db'];
        $baseUrl = rtrim(trim((string)($in['base_url'] ?? '')), '/');
        $cfg = [
            'db_dsn' => $c['dsn'], 'db_user' => (string)($db['user'] ?? ''), 'db_pass' => (string)($db['pass'] ?? ''),
            'agent_api_key' => $keys['agent_api_key'], 'token_days' => 30, 'max_users' => 5,
            'update_secret' => $keys['update_secret'], 'base_url' => $baseUrl,
        ];
        $tmp = $this->configPath() . '.tmp' . bin2hex(random_bytes(3));
        if (@file_put_contents($tmp, self::renderConfig($cfg)) === false) {
            return ['ok' => false, 'error' => 'Yapılandırma dosyası yazılamadı (klasör yazma izni?).'];
        }
        @chmod($tmp, 0640);
        if (!@rename($tmp, $this->configPath())) {
            @unlink($this->configPath());
            if (!@rename($tmp, $this->configPath())) {
                @unlink($tmp);
                return ['ok' => false, 'error' => 'Yapılandırma dosyası yerine konamadı.'];
            }
        }
        $version = is_file($this->root . '/VERSION') ? trim((string)file_get_contents($this->root . '/VERSION')) : '';
        if (@file_put_contents($this->lockPath(), 'installed ' . gmdate('Y-m-d H:i:s', ($this->clock)()) . " v$version\n") === false) {
            return ['ok' => false, 'error' => 'Kurulum kilidi yazılamadı.'];
        }
        @unlink($this->tokenPath());

        return ['ok' => true, 'keys' => $keys, 'base_url' => $baseUrl];
    }

    // ------------------------------------------------------------------
    // Softaculous (ikinci kurulum yolu; ana yol web sihirbazıdır)
    // ------------------------------------------------------------------

    /**
     * Softaculous değişkenlerini `install()` girdisine çevirir ve aynı kurulumu yapar (aynı doğrulamalar,
     * aynı kilit). Kurulum anahtarı gerekmez: betiği Softaculous, cPanel sahibinin oturumunda çalıştırır.
     * Üretilen anahtarlar sonuçta DÖNMEZ (Softaculous çıktısı e-posta/günlüğe düşebilir); yalnızca
     * `config.local.php` içinde durur.
     *
     * @param array<string,mixed> $v softdbhost ("sunucu" veya "sunucu:port"), softdbname, softdbuser, softdbpass,
     *                               admin_username, admin_pass, site_url
     * @return array{ok:bool, error?:string, base_url?:string}
     */
    public function installFromSoftaculous(array $v): array
    {
        $host = trim((string)($v['softdbhost'] ?? ''));
        $port = 3306;
        if (preg_match('/^([^:]+):(\d{1,5})$/', $host, $m)) {
            $host = $m[1];
            $port = (int)$m[2];
        }
        $siteUrl = rtrim(trim((string)($v['site_url'] ?? '')), '/');
        // Portalın web kökü public/ klasörüdür; Softaculous ise uygulamayı bir üst klasöre kurar.
        $baseUrl = $siteUrl === '' ? '' : $siteUrl . '/public';
        $pass = (string)($v['admin_pass'] ?? '');
        $r = $this->install([
            'db' => ['host' => $host, 'port' => $port, 'name' => (string)($v['softdbname'] ?? ''),
                'user' => (string)($v['softdbuser'] ?? ''), 'pass' => (string)($v['softdbpass'] ?? '')],
            'admin' => ['username' => (string)($v['admin_username'] ?? ''), 'password' => $pass, 'password2' => $pass],
            'base_url' => $baseUrl,
        ]);
        if (!$r['ok']) {
            return ['ok' => false, 'error' => $r['error']];
        }
        return ['ok' => true, 'base_url' => $r['base_url']];
    }

    /**
     * Kurulu portalın bekleyen veritabanı migrasyonlarını çalıştırır (Softaculous yükseltmesi dosyaları
     * değiştirdikten sonra). Yapılandırma ve veri korunur.
     *
     * @return array{ok:bool, error?:string, applied?:array<int,string>} applied = bu çalışmada uygulanan migrasyon dosyaları
     */
    public function upgrade(): array
    {
        if (!$this->isInstalled()) {
            return ['ok' => false, 'error' => 'Portal kurulu değil.'];
        }
        $cfg = require $this->configPath();
        $dsn = $this->dsnOverride ?? (string)($cfg['db_dsn'] ?? '');
        try {
            $pdo = new PDO($dsn, (string)($cfg['db_user'] ?? ''), (string)($cfg['db_pass'] ?? ''),
                [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_TIMEOUT => 10]);
        } catch (\PDOException $e) {
            return ['ok' => false, 'error' => 'Veritabanına bağlanılamadı.'];
        }
        $mig = (new Migrator($pdo, $this->migrationsDir, $this->clock))->migrate();
        if (!$mig['ok']) {
            return ['ok' => false, 'error' => 'Migrasyon başarısız (' . $mig['failed'] . '): ' . mb_substr((string)$mig['error'], 0, 200)];
        }
        return ['ok' => true, 'applied' => (array)$mig['executed']];
    }
}
