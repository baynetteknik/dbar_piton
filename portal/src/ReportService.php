<?php
declare(strict_types=1);

namespace Toya\Portal;

use PDO;

/**
 * Portaldaki ayna tablolarından salt okunur raporlar (cari bakiye, ekstre, fatura, dashboard özeti).
 * Tüm sorgular parametrelidir; kaynakta silinmiş (`source_deleted`) ve iptal edilmiş kayıtlar dışlanır.
 */
final class ReportService
{
    private PDO $pdo;

    public function __construct(PDO $pdo)
    {
        $this->pdo = $pdo;
    }

    /** @return string[] */
    public function sources(): array
    {
        return $this->pdo->query(
            'SELECT DISTINCT source FROM portal_mirror_cari WHERE source_deleted = 0 ORDER BY source'
        )->fetchAll(PDO::FETCH_COLUMN);
    }

    public function lastSync(string $source): ?string
    {
        $st = $this->pdo->prepare(
            "SELECT MAX(created_at) FROM portal_sync_log WHERE source = ? AND action = 'finish' AND status = 'ok'"
        );
        $st->execute([$source]);
        $v = $st->fetchColumn();
        return $v ? (string)$v : null;
    }

    /** @return array<int,array<string,mixed>> bakiyeye göre azalan; + = müşteri bize borçlu */
    public function cariBakiyeleri(string $source): array
    {
        $st = $this->pdo->prepare(
            'SELECT c.ext_id, c.cari_kodu, c.unvan, COALESCE(SUM(h.borc), 0) AS borc, COALESCE(SUM(h.alacak), 0) AS alacak
             FROM portal_mirror_cari c
             LEFT JOIN portal_mirror_cari_hareket h
               ON h.source = c.source AND h.cari_ext_id = c.ext_id AND h.source_deleted = 0
             WHERE c.source = ? AND c.source_deleted = 0
             GROUP BY c.ext_id, c.cari_kodu, c.unvan'
        );
        $st->execute([$source]);
        $out = [];
        foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
            $borc = (float)$r['borc'];
            $alacak = (float)$r['alacak'];
            $out[] = [
                'ext_id' => $r['ext_id'], 'cari_kodu' => $r['cari_kodu'], 'unvan' => $r['unvan'],
                'borc' => round($borc, 2), 'alacak' => round($alacak, 2), 'bakiye' => round($borc - $alacak, 2),
            ];
        }
        usort($out, static fn($a, $b) => $b['bakiye'] <=> $a['bakiye']);
        return $out;
    }

    /** @return array<string,mixed>|null */
    public function cari(string $source, string $extId): ?array
    {
        $st = $this->pdo->prepare(
            'SELECT ext_id, cari_kodu, unvan FROM portal_mirror_cari WHERE source = ? AND ext_id = ? AND source_deleted = 0'
        );
        $st->execute([$source, $extId]);
        $r = $st->fetch(PDO::FETCH_ASSOC);
        return $r ?: null;
    }

    /**
     * Ekstre: devir ($from öncesi bakiye) + dönem hareketleri ve yürüyen bakiye.
     *
     * @return array{devir:float, satirlar:array<int,array<string,mixed>>, bakiye:float}
     */
    public function ekstre(string $source, string $cariExtId, ?string $from = null, ?string $to = null): array
    {
        $st = $this->pdo->prepare(
            'SELECT ext_id, tarihi, evrak_no, aciklama, kaynak_tur, ilgili_ext_id, borc, alacak
             FROM portal_mirror_cari_hareket
             WHERE source = ? AND cari_ext_id = ? AND source_deleted = 0
             ORDER BY tarihi, id'
        );
        $st->execute([$source, $cariExtId]);
        $devir = 0.0;
        $bakiye = 0.0;
        $lines = [];
        foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $h) {
            $net = (float)$h['borc'] - (float)$h['alacak'];
            $t = (string)($h['tarihi'] ?? '');
            if ($from !== null && $t !== '' && $t < $from) {
                $devir += $net;
                continue;
            }
            if ($to !== null && $t !== '' && $t > $to) {
                continue;
            }
            $lines[] = $h;
        }
        $bakiye = $devir;
        $out = [];
        foreach ($lines as $h) {
            $bakiye += (float)$h['borc'] - (float)$h['alacak'];
            $out[] = [
                'tarihi' => $h['tarihi'], 'evrak_no' => $h['evrak_no'], 'aciklama' => $h['aciklama'],
                'ilgili_ext_id' => $h['ilgili_ext_id'], 'borc' => (float)$h['borc'], 'alacak' => (float)$h['alacak'],
                'bakiye' => round($bakiye, 2),
            ];
        }
        return ['devir' => round($devir, 2), 'satirlar' => $out, 'bakiye' => round($bakiye, 2)];
    }

    /** @return array<string,mixed> */
    public function firmaOzeti(string $source): array
    {
        $bak = $this->cariBakiyeleri($source);
        $borc = 0.0;
        $alacak = 0.0;
        foreach ($bak as $b) {
            if ($b['bakiye'] > 0) {
                $borc += $b['bakiye'];
            } elseif ($b['bakiye'] < 0) {
                $alacak -= $b['bakiye'];
            }
        }
        $st = $this->pdo->prepare(
            "SELECT yon, COUNT(*) AS n, COALESCE(SUM(genel_toplam), 0) AS toplam FROM portal_mirror_fatura
             WHERE source = ? AND source_deleted = 0 AND iptal = 0 GROUP BY yon"
        );
        $st->execute([$source]);
        $o = ['satis' => [0, 0.0], 'alis' => [0, 0.0], 'bilinmeyen' => [0, 0.0]];
        foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
            $k = isset($o[$r['yon'] ?? '']) ? $r['yon'] : 'bilinmeyen';
            $o[$k][0] += (int)$r['n'];
            $o[$k][1] += (float)$r['toplam'];
        }
        return [
            'toplam_borc' => round($borc, 2), 'toplam_alacak' => round($alacak, 2),
            'satis_adet' => $o['satis'][0], 'satis_toplam' => round($o['satis'][1], 2),
            'alis_adet' => $o['alis'][0], 'alis_toplam' => round($o['alis'][1], 2),
            'yonu_bilinmeyen_adet' => $o['bilinmeyen'][0],
            'fatura_adedi' => $o['satis'][0] + $o['alis'][0] + $o['bilinmeyen'][0],
            'cari_adedi' => count($bak), 'son_senkron' => $this->lastSync($source),
        ];
    }

    /** @return array<int,array<string,mixed>> tarihe göre azalan */
    public function faturalar(string $source, ?string $from = null, ?string $to = null, ?string $cariExtId = null, int $limit = 200): array
    {
        $sql = 'SELECT f.ext_id, f.fatura_no, f.tarihi, f.yon, f.cari_ext_id, f.genel_toplam, f.kdv, c.unvan AS cari_unvan
                FROM portal_mirror_fatura f
                LEFT JOIN portal_mirror_cari c ON c.source = f.source AND c.ext_id = f.cari_ext_id
                WHERE f.source = ? AND f.source_deleted = 0 AND f.iptal = 0';
        $p = [$source];
        if ($from !== null && $from !== '') {
            $sql .= ' AND f.tarihi >= ?';
            $p[] = $from;
        }
        if ($to !== null && $to !== '') {
            $sql .= ' AND f.tarihi <= ?';
            $p[] = $to;
        }
        if ($cariExtId !== null && $cariExtId !== '') {
            $sql .= ' AND f.cari_ext_id = ?';
            $p[] = $cariExtId;
        }
        $sql .= ' ORDER BY f.tarihi DESC, f.id DESC LIMIT ' . max(1, min(1000, $limit));
        $st = $this->pdo->prepare($sql);
        $st->execute($p);
        return $st->fetchAll(PDO::FETCH_ASSOC);
    }

    /** @return array{fatura:array<string,mixed>, kalemler:array<int,array<string,mixed>>}|null */
    public function fatura(string $source, string $extId): ?array
    {
        $st = $this->pdo->prepare(
            'SELECT f.*, c.unvan AS cari_unvan FROM portal_mirror_fatura f
             LEFT JOIN portal_mirror_cari c ON c.source = f.source AND c.ext_id = f.cari_ext_id
             WHERE f.source = ? AND f.ext_id = ? AND f.source_deleted = 0 AND f.iptal = 0'
        );
        $st->execute([$source, $extId]);
        $f = $st->fetch(PDO::FETCH_ASSOC);
        if (!$f) {
            return null;
        }
        $k = $this->pdo->prepare(
            'SELECT stok_kodu, stok_adi, miktar, birim, fiyat, kdv_orani, tutar, kdvli_tutar
             FROM portal_mirror_fatura_kalem WHERE source = ? AND fatura_ext_id = ? AND source_deleted = 0
             ORDER BY sira_no, id'
        );
        $k->execute([$source, $extId]);
        return ['fatura' => $f, 'kalemler' => $k->fetchAll(PDO::FETCH_ASSOC)];
    }
}
