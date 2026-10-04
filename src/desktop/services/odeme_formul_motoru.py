"""TOYA ERP - Ödeme Planı Formül Motoru.

Çok satırlı Ödeme Planı'nda (bkz. gelistirme/04_odeme_planlari/tasarim.md, 04.11) her satırın tutarı
TOYA'ya özgü, okunaklı değişken adlarıyla hesaplanır — DIA'nın tek harfli kısaltmaları (G/T/K/M) ya da
Logo'nun $P1/$P2 parametreleri yerine Türkçe isimler:

    TUTAR       belgenin genel toplamı (KDV dahil)
    ARATOPLAM   ara toplam (KDV hariç)
    KDV         toplam KDV tutarı
    KALAN       bu plandaki ÖNCEKİ satırlardan arta kalan tutar (ilk satırda TUTAR'a eşittir)

Gerçek ayrıştırma/değerlendirme DRY gereği mevcut, test edilmiş `FormulaService`'e (bkz.
`formula_service.py` — Görünüm Profilleri kural motoru için yazılmış, AST tabanlı GÜVENLİ bir ifade
değerlendirici; eval() KULLANMAZ) devredilir — iki ayrı "formül motoru" icat edilmez. Bu modül yalnızca
TOYA'nın ödeme-planı-özel sözlüğünü (değişken adları, KALAN varsayılanı, bilinmeyen değişken/sözdizimi
hatalarının AÇIKÇA raporlanması) üstüne ekler. Fonksiyon adları `FormulaService`'inkiyle AYNI (round, abs,
min, max, sum) — Türkçe takma ad eklemek (ör. YUVARLA) kırılgan kaynak-düzeyinde metin değişimi gerektirir,
bu fazda buna gerek görülmedi ("formülasyon yolda geliştirilecek").

Örnekler: "TUTAR/2" (yarısı), "TUTAR*0.3" (%30), "round(TUTAR/3,2)" (üçte biri, 2 hane)."""

from __future__ import annotations

import ast

from src.desktop.services.formula_service import FormulaSecurityError, FormulaService

_DEGISKENLER = {"TUTAR", "ARATOPLAM", "KDV", "KALAN"}


class OdemeFormulHatasi(ValueError):  # noqa: N818 - TOYA'da Türkçe "...Hatasi" adlandırması kabul edilmiş desen (bkz. SablonHatasi)
    """Formül ayrıştırma/değerlendirme hatası; mesaj kullanıcıya gösterilebilir."""


def degerlendir(formul: str | None, baglam: dict[str, float]) -> float:
    """`formul` boşsa `baglam["KALAN"]`ı döner. `baglam` en az TUTAR/ARATOPLAM/KDV/KALAN anahtarlarını
    içermelidir (bkz. `_DEGISKENLER`, `baglam_olustur`)."""
    formul = (formul or "").strip()
    if not formul:
        return float(baglam.get("KALAN", 0.0))
    try:
        agac = ast.parse(formul, mode="eval")
    except SyntaxError as e:
        raise OdemeFormulHatasi(f"Formül ayrıştırılamadı: {e}") from e
    _bilinmeyen_degiskenleri_reddet(agac)
    try:
        return float(FormulaService.evaluate(formul, baglam))
    except FormulaSecurityError as e:
        raise OdemeFormulHatasi(f"Formülde desteklenmeyen bir ifade var: {e}") from e


def _bilinmeyen_degiskenleri_reddet(agac: ast.AST) -> None:
    """`FormulaService` tanımadığı bir değişkeni SESSİZCE 0 sayar (görünüm kuralları için uygun bir
    davranış) — ödeme planı formüllerinde bu bir YAZIM HATASINI gizler, bu yüzden burada AÇIKÇA
    reddedilir. Fonksiyon çağrılarının adı (ör. `round(...)`daki `round`) değişken sayılmaz."""
    cagri_adlari = {n.func.id for n in ast.walk(agac) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    for node in ast.walk(agac):
        if isinstance(node, ast.Name) and node.id not in _DEGISKENLER and node.id not in cagri_adlari:
            raise OdemeFormulHatasi(f"Bilinmeyen değişken: {node.id} (geçerli: {', '.join(sorted(_DEGISKENLER))})")


def baglam_olustur(tutar: float, aratoplam: float, kdv: float, kalan: float) -> dict[str, float]:
    return {"TUTAR": tutar, "ARATOPLAM": aratoplam, "KDV": kdv, "KALAN": kalan}
