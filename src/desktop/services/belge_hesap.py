"""TOYA ERP - Belge hesaplaması (satır, KDV, toplam, dip toplam) — TEK sahip.

Satır tutarı, TL karşılığı, iskonto, KDV dağılımı ve dip toplam başka hiçbir yerde yeniden yazılmaz: belge kalem gridi, belge ekranının dip
toplamı, belge kayıt/hareket servisleri ve raporlar bu modülü kullanır. Arayüzden bağımsızdır (widget okumaz); girdi düz sayılardır.

Kurallar:
- Satır net tutarı = miktar × birim fiyat × (1 − iskonto%/100), SATIRIN KENDİ döviz cinsindedir (`net_para`).
- Belge toplamları TL karşılığı üzerindendir: satır TL tutarı = satır tutarı × kur (TRY satırında kur = 1).
- KDV = TL net × KDV%/100; KDV dağılımı oran bazında (matrah + KDV) tutulur.
- Dip toplam = kalem toplamları − ek iskonto + masraf (matraha), + ek KDV; genel toplam = matrah + KDV.
- `kdv_yuvarla` verilirse satır KDV'si o ondalığa yuvarlanır (kayıt/hareket servisleri 2 hane kullanır; ekran yuvarlamadan hesaplar)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SatirSonuc:
    brut: float            # miktar × birim fiyat × kur (TL)
    iskonto: float         # TL
    net: float             # TL, KDV hariç
    kdv: float             # TL
    kdv_yuzde: float
    net_para: float        # satırın kendi dövizinde net tutar


@dataclass
class BelgeToplam:
    ara_toplam: float = 0.0
    iskonto: float = 0.0
    kdv_matrahi: float = 0.0
    kdv_toplam: float = 0.0
    genel_toplam: float = 0.0
    satir_sayisi: int = 0
    kdv_dagilim: dict[float, dict[str, float]] = field(default_factory=dict)


def satir(miktar: float, birim_fiyat: float, iskonto_yuzde: float = 0.0, kdv_yuzde: float = 0.0, kur: float = 1.0,
          kdv_yuvarla: int | None = None) -> SatirSonuc:
    """Miktar/fiyat/iskonto/KDV/kur'dan satır sonucu. `kur` 0 ya da boşsa 1 sayılır."""
    kur = kur or 1.0
    brut_para = miktar * birim_fiyat
    net_para = brut_para * (1 - iskonto_yuzde / 100.0)
    brut = brut_para * kur
    iskonto = brut * (iskonto_yuzde / 100.0)
    net = brut - iskonto
    kdv = net * (kdv_yuzde / 100.0)
    if kdv_yuvarla is not None:
        kdv = round(kdv, kdv_yuvarla)
    return SatirSonuc(brut, iskonto, net, kdv, kdv_yuzde, net_para)


def eski_diyalog_satir_toplami(satir_verisi: dict) -> float:
    """Eski teklif diyaloğunun satırı (miktar/fiyat/3 kademeli iskonto/KDV) için KDV DAHİL toplam. Eski diyalog ve `QuotationSaveService`
    aynı formülü ayrı ayrı yazıyordu; tek sahibi burasıdır. Boş miktar 1, boş KDV %20 sayılır; hatada 0."""
    try:
        miktar = float(satir_verisi.get("qty", 1) or 1)
        fiyat = float(satir_verisi.get("price", 0) or 0)
        kdv = float(satir_verisi.get("vat", 20) or 20)
        tutar = miktar * fiyat
        for anahtar in ("disc1", "disc2", "disc3"):
            tutar *= 1 - float(satir_verisi.get(anahtar, 0) or 0) / 100
        return round(tutar * (1 + kdv / 100), 2)
    except (TypeError, ValueError):
        return 0.0


def satir_netten(net_para: float, kdv_yuzde: float = 0.0, kur: float = 1.0, kdv_yuvarla: int | None = None) -> SatirSonuc:
    """Net tutarı (KDV hariç, satır dövizinde) zaten bilinen satır (kayıtlı belge satırı): iskonto zaten net'e işlenmiştir."""
    kur = kur or 1.0
    net = net_para * kur
    kdv = net * (kdv_yuzde / 100.0)
    if kdv_yuvarla is not None:
        kdv = round(kdv, kdv_yuvarla)
    return SatirSonuc(net, 0.0, net, kdv, kdv_yuzde, net_para)


def belge_toplami(satirlar: list[SatirSonuc]) -> BelgeToplam:
    """Satır sonuçlarından belge (kalem) toplamı ve oran bazında KDV dağılımı."""
    t = BelgeToplam(satir_sayisi=len(satirlar))
    for s in satirlar:
        t.ara_toplam += s.brut
        t.iskonto += s.iskonto
        t.kdv_matrahi += s.net
        t.kdv_toplam += s.kdv
        d = t.kdv_dagilim.setdefault(s.kdv_yuzde, {"matrah": 0.0, "kdv": 0.0})
        d["matrah"] += s.net
        d["kdv"] += s.kdv
    t.genel_toplam = t.kdv_matrahi + t.kdv_toplam
    return t


def dip_toplam(kalem: BelgeToplam | dict, ek_indirim: float = 0.0, masraf: float = 0.0, ek_kdv: float = 0.0) -> dict:
    """Kalem toplamına ek indirim / masraf / ek KDV'yi uygular (belge ekranının alt toplam paneli)."""
    g = (lambda a: kalem.get(a, 0.0)) if isinstance(kalem, dict) else (lambda a: getattr(kalem, a))
    matrah = g("kdv_matrahi") - ek_indirim + masraf
    kdv = g("kdv_toplam") + ek_kdv
    return {
        "ara_toplam": g("ara_toplam"), "iskonto": g("iskonto") + ek_indirim, "masraflar": masraf,
        "kdv_matrahi": matrah, "kdv_toplam": kdv, "genel_toplam": matrah + kdv,
    }


def kdv_dagilimi_birlestir(*kaynaklar: dict) -> dict[float, dict[str, float]]:
    """Birden çok oran-bazlı KDV dağılımını (kalemler + masraf/indirim satırları) tek dağılımda toplar."""
    out: dict[float, dict[str, float]] = {}
    for src in kaynaklar:
        for oran, d in (src or {}).items():
            m = out.setdefault(float(oran), {"matrah": 0.0, "kdv": 0.0})
            m["matrah"] += d.get("matrah", 0.0)
            m["kdv"] += d.get("kdv", 0.0)
    return out
