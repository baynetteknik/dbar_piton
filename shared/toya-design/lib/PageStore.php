<?php
declare(strict_types=1);
namespace Toya\Design;

/** Host-owned content. Never place this directory inside a release package. */
final class PageStore
{
    public function __construct(private string $directory) {}

    private function path(string $key): string
    {
        if (!preg_match('/\A[a-z][a-z0-9-]{0,63}\z/', $key)) {
            throw new \InvalidArgumentException('Geçersiz tasarım adı.');
        }
        return $this->directory . '/' . $key . '.json';
    }

    public function load(string $key): ?array
    {
        $path = $this->path($key);
        if (!is_file($path)) { return null; }
        $data = json_decode((string)file_get_contents($path), true, 128, JSON_THROW_ON_ERROR);
        if (!is_array($data)) { throw new \RuntimeException('Tasarım dosyası okunamadı.'); }
        return $data;
    }

    public function save(string $key, array $document, int $revision): array
    {
        $path = $this->path($key);
        if (!is_dir($this->directory) && !mkdir($this->directory, 0700, true) && !is_dir($this->directory)) {
            throw new \RuntimeException('Tasarım klasörü oluşturulamadı.');
        }
        $lock = fopen($this->directory . '/.write.lock', 'c');
        if (!$lock || !flock($lock, LOCK_EX)) { throw new \RuntimeException('Kayıt kilidi alınamadı.'); }
        $tmp = null;
        try {
            $current = $this->load($key);
            if (($current['revision'] ?? 0) !== $revision) {
                throw new \DomainException('Tasarım başka bir pencerede değiştirildi. Sayfayı yeniden açın.');
            }
            $document['revision'] = $revision + 1;
            $document['updated_at'] = gmdate('c');
            $json = json_encode($document, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
            if (strlen($json) > 4 * 1024 * 1024) { throw new \InvalidArgumentException('Tasarım en fazla 4 MB olabilir.'); }
            if (is_file($path) && !copy($path, $path . '.previous')) {
                throw new \RuntimeException('Önceki tasarım yedeklenemedi.');
            }
            $tmp = tempnam($this->directory, '.design-');
            if ($tmp === false || file_put_contents($tmp, $json) !== strlen($json) || !rename($tmp, $path)) {
                throw new \RuntimeException('Tasarım kaydedilemedi.');
            }
            return $document;
        } finally {
            if ($tmp && is_file($tmp)) { unlink($tmp); }
            flock($lock, LOCK_UN);
            fclose($lock);
        }
    }
}
