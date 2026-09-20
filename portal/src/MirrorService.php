<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

/**
 * Ajanın gönderdiği harici sistem ayna kayıtlarını (cari, hareket, fatura, kalem, stok)
 * kabul eder. Kayıtlar (source, ext_id) ile upsert edilir. Tam senkron turlarında
 * `run` kimliği ile işaretlenir; tur bitince `finish` çağrısı turda görülmeyen kayıtları
 * source_deleted yapar (kaynakta silinmiş/kaybolmuş sayılır, fiziksel silinmez).
 */
final class MirrorService
{
    /** varlık => [tablo, izin verilen sütunlar (beyaz liste), sayısal sütunlar, mantıksal sütunlar] */
    private const ENTITIES = [
        'cari' => ['portal_mirror_cari',
            ['cari_kodu', 'unvan', 'email', 'telefon', 'vergi_no', 'aktif'], [], ['aktif']],
        'cari_hareket' => ['portal_mirror_cari_hareket',
            ['cari_ext_id', 'tarihi', 'vadesi', 'evrak_no', 'kaynak_tur', 'borc', 'alacak', 'aciklama', 'ilgili_ext_id'],
            ['borc', 'alacak'], []],
        'fatura' => ['portal_mirror_fatura',
            ['fatura_no', 'tarihi', 'vadesi', 'cari_ext_id', 'yon', 'kaynak_durum', 'iptal', 'ara_toplam',
             'iskonto', 'kdv', 'genel_toplam', 'doviz', 'ek_bilgi', 'aciklama'],
            ['ara_toplam', 'iskonto', 'kdv', 'genel_toplam'], ['iptal']],
        'fatura_kalem' => ['portal_mirror_fatura_kalem',
            ['fatura_ext_id', 'stok_kodu', 'stok_adi', 'birim', 'miktar', 'fiyat', 'kdv_orani', 'tutar',
             'kdvli_tutar', 'sira_no'],
            ['miktar', 'fiyat', 'kdv_orani', 'tutar', 'kdvli_tutar'], []],
        'stok' => ['portal_mirror_stok',
            ['stok_kodu', 'stok_adi', 'birim', 'kdv_orani', 'aktif', 'satis_fiyati', 'miktar'],
            ['kdv_orani', 'satis_fiyati', 'miktar'], ['aktif']],
    ];

    public const MAX_RECORDS_PER_REQUEST = 1000;

    private PDO $pdo;
    /** @var callable():int */
    private $clock;

    public function __construct(PDO $pdo, ?callable $clock = null)
    {
        $this->pdo = $pdo;
        $this->clock = $clock ?? static fn(): int => time();
    }

    public static function entities(): array
    {
        return array_keys(self::ENTITIES);
    }

    private function nowStr(): string
    {
        return gmdate('Y-m-d H:i:s', ($this->clock)());
    }

    /** @return mixed */
    private function coerce(string $col, mixed $v, array $numeric, array $bool)
    {
        if (in_array($col, $bool, true)) {
            return empty($v) ? 0 : 1;
        }
        if (in_array($col, $numeric, true)) {
            return is_numeric($v) ? (float)$v : 0.0;
        }
        if ($col === 'sira_no') {
            return is_numeric($v) ? (int)$v : null;
        }
        return $v === null ? null : (string)$v;
    }

    /**
     * @param array<int,array<string,mixed>> $records ext_id + izinli sütunlar; silindi=true kaynakta silinmiş
     * @return array{ok:bool, error?:string, added?:int, updated?:int}
     */
    public function ingest(string $entity, string $source, string $run, array $records, ?string $ip = null): array
    {
        try {
            $r = $this->ingestInner($entity, $source, $run, $records);
        } catch (\Throwable $e) {
            $this->log('ingest', $source, $entity, $run, 'error', count($records), 0, 0, 0, 'server_error', $ip);
            throw $e;
        }
        $this->log(
            'ingest', $source, $entity, $run, $r['ok'] ? 'ok' : 'error', count($records),
            $r['added'] ?? 0, $r['updated'] ?? 0, 0, $r['error'] ?? null, $ip
        );
        return $r;
    }

    /**
     * Günlük yazımı asla asıl işlemi bozmamalı; hata olursa yutulur.
     */
    private function log(
        string $action, ?string $source, ?string $entity, ?string $run, string $status,
        int $received, int $added, int $updated, int $vanished, ?string $message, ?string $ip
    ): void {
        try {
            $this->pdo->prepare(
                'INSERT INTO portal_sync_log (created_at, source, entity, run, action, status, received, added,
                 updated, vanished, message, ip_address) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)'
            )->execute([
                $this->nowStr(), $source !== null ? mb_substr($source, 0, 30) : null,
                $entity !== null ? mb_substr($entity, 0, 30) : null, $run !== null ? mb_substr($run, 0, 40) : null,
                $action, $status, $received, $added, $updated, $vanished,
                $message !== null ? mb_substr($message, 0, 255) : null, $ip,
            ]);
        } catch (\Throwable $e) {
            error_log('portal_sync_log yazılamadı: ' . $e->getMessage());
        }
    }

    /**
     * @param array<int,array<string,mixed>> $records
     * @return array{ok:bool, error?:string, added?:int, updated?:int}
     */
    private function ingestInner(string $entity, string $source, string $run, array $records): array
    {
        if (!isset(self::ENTITIES[$entity])) {
            return ['ok' => false, 'error' => 'unknown_entity'];
        }
        $source = trim($source);
        $run = trim($run);
        if ($source === '' || strlen($source) > 30 || $run === '' || strlen($run) > 40) {
            return ['ok' => false, 'error' => 'invalid_payload'];
        }
        if (count($records) > self::MAX_RECORDS_PER_REQUEST) {
            return ['ok' => false, 'error' => 'too_many_records'];
        }
        [$table, $allowed, $numeric, $bool] = self::ENTITIES[$entity];
        $now = $this->nowStr();
        $added = $updated = 0;

        $this->pdo->beginTransaction();
        try {
            $sel = $this->pdo->prepare("SELECT id FROM $table WHERE source = ? AND ext_id = ?");
            foreach ($records as $rec) {
                if (!is_array($rec) || !isset($rec['ext_id']) || (string)$rec['ext_id'] === '') {
                    $this->pdo->rollBack();
                    return ['ok' => false, 'error' => 'invalid_record'];
                }
                $ext = (string)$rec['ext_id'];
                $vals = [];
                foreach ($allowed as $col) {
                    $vals[$col] = $this->coerce($col, $rec[$col] ?? null, $numeric, $bool);
                }
                $deleted = empty($rec['silindi']) ? 0 : 1;

                $sel->execute([$source, $ext]);
                $id = $sel->fetchColumn();
                if ($id === false) {
                    $cols = array_merge(['source', 'ext_id'], $allowed, ['source_deleted', 'sync_run', 'updated_at']);
                    $params = array_merge([$source, $ext], array_values($vals), [$deleted, $run, $now]);
                    $ph = implode(',', array_fill(0, count($cols), '?'));
                    $this->pdo->prepare("INSERT INTO $table (" . implode(',', $cols) . ") VALUES ($ph)")->execute($params);
                    $added++;
                } else {
                    $set = implode(',', array_map(static fn($c) => "$c = ?", array_merge($allowed, ['source_deleted', 'sync_run', 'updated_at'])));
                    $this->pdo->prepare("UPDATE $table SET $set WHERE id = ?")
                        ->execute(array_merge(array_values($vals), [$deleted, $run, $now, $id]));
                    $updated++;
                }
            }
            $this->pdo->commit();
        } catch (\Throwable $e) {
            $this->pdo->rollBack();
            throw $e;
        }
        return ['ok' => true, 'added' => $added, 'updated' => $updated];
    }

    /**
     * Tam senkron turunu kapatır: bu turda (`run`) görülmeyen kayıtlar source_deleted olur.
     * Yalnızca belirtilen varlıklar için çalışır; böylece kısmi tur diğer varlıkları etkilemez.
     *
     * @param string[] $entities
     * @return array{ok:bool, error?:string, vanished?:array<string,int>}
     */
    public function finish(string $source, string $run, array $entities, ?string $ip = null): array
    {
        $r = $this->finishInner($source, $run, $entities);
        $this->log(
            'finish', $source, implode(',', array_map('strval', $entities)), $run, $r['ok'] ? 'ok' : 'error', 0, 0, 0,
            array_sum($r['vanished'] ?? []), $r['error'] ?? null, $ip
        );
        return $r;
    }

    /**
     * @param string[] $entities
     * @return array{ok:bool, error?:string, vanished?:array<string,int>}
     */
    private function finishInner(string $source, string $run, array $entities): array
    {
        $source = trim($source);
        $run = trim($run);
        if ($source === '' || $run === '' || $entities === []) {
            return ['ok' => false, 'error' => 'invalid_payload'];
        }
        $vanished = [];
        foreach ($entities as $entity) {
            if (!isset(self::ENTITIES[$entity])) {
                return ['ok' => false, 'error' => 'unknown_entity'];
            }
        }
        foreach ($entities as $entity) {
            $table = self::ENTITIES[$entity][0];
            $st = $this->pdo->prepare(
                "UPDATE $table SET source_deleted = 1, updated_at = ?
                 WHERE source = ? AND source_deleted = 0 AND (sync_run IS NULL OR sync_run <> ?)"
            );
            $st->execute([$this->nowStr(), $source, $run]);
            $vanished[$entity] = $st->rowCount();
        }
        return ['ok' => true, 'vanished' => $vanished];
    }

    /**
     * Aktarım günlüğü, en yeni önce. Filtreler isteğe bağlı.
     *
     * @return array<int,array<string,mixed>>
     */
    public function recentLog(int $limit = 100, ?string $status = null, ?string $source = null): array
    {
        $sql = 'SELECT * FROM portal_sync_log WHERE 1=1';
        $p = [];
        if ($status !== null && $status !== '') {
            $sql .= ' AND status = ?';
            $p[] = $status;
        }
        if ($source !== null && $source !== '') {
            $sql .= ' AND source = ?';
            $p[] = $source;
        }
        $sql .= ' ORDER BY id DESC LIMIT ' . max(1, min(500, $limit));
        $st = $this->pdo->prepare($sql);
        $st->execute($p);
        return $st->fetchAll(PDO::FETCH_ASSOC);
    }

    /** @return array<string,int> varlık => aktif (silinmemiş) kayıt sayısı */
    public function counts(string $source): array
    {
        $out = [];
        foreach (self::ENTITIES as $entity => [$table]) {
            $st = $this->pdo->prepare("SELECT COUNT(*) FROM $table WHERE source = ? AND source_deleted = 0");
            $st->execute([$source]);
            $out[$entity] = (int)$st->fetchColumn();
        }
        return $out;
    }
}
