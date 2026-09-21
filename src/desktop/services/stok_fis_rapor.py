"""TOYA ERP - Stok hareket fişi çıktıları: HTML (yazdırma / PDF) ve Excel. Çıktı kayıtlı fişten üretilir."""

from __future__ import annotations

from html import escape

from src.desktop.services import cari_fis_rapor
from src.desktop.services.stok_fis_service import FIS_TIPLERI, TURLER, StokFisService


def _n(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rapor_verisi(db, fis_id: int) -> dict:
    from src.core.models import WarehouseDefinition
    fis, satirlar = StokFisService(db).fis_getir(fis_id)
    kod = {w.id: w.code for w in db.query(WarehouseDefinition).all()}
    rows, toplam = [], {}
    for h in satirlar:
        rows.append({"sn": h.satir_no or len(rows) + 1, "tur": TURLER.get(h.tur, (h.tur,))[0], "kod": h.product.sku,
                     "ad": h.product.name or "", "depo": kod.get(h.depo_id, ""), "hedef": kod.get(h.hedef_depo_id, "") if h.hedef_depo_id else "",
                     "miktar": h.miktar, "birim": h.birim or "", "fiyat": h.birim_fiyat, "tutar": h.tutar, "not": h.aciklama or ""})
        t = toplam.setdefault(h.birim or "Adet", [0.0] * 5)
        t[{"giris": 0, "acilis": 0, "cikis": 1, "transfer": 2, "sayim": 3}[h.tur]] += h.miktar
        t[4] += h.tutar
    return {
        "baslik": {"fis_no": fis.fis_no, "tur": FIS_TIPLERI.get(fis.varsayilan_tur, "Stok Fişi"),
                   "tarih": fis.tarih.strftime("%d.%m.%Y"), "saat": fis.saat or "", "belge_no": fis.belge_no or "",
                   "depo": kod.get(fis.depo_id, ""), "hedef": kod.get(fis.hedef_depo_id, "") if fis.hedef_depo_id else "",
                   "ozel_kod": fis.ozel_kod or "", "yetki_kodu": fis.yetki_kodu or ""},
        "satirlar": rows, "toplamlar": {k: tuple(v) for k, v in toplam.items()},
        "aciklamalar": [a for a in (fis.aciklama1, fis.aciklama2, fis.aciklama3) if a],
    }


def html(veri: dict) -> str:
    b, e = veri["baslik"], escape
    th = "style='background:#1e3a8a;color:#ffffff;padding:3px;'"
    satir = "".join(
        f"<tr><td align='center'>{r['sn']}</td><td>{e(r['tur'])}</td><td>{e(r['kod'])}</td><td>{e(r['ad'])}</td>"
        f"<td align='center'>{e(r['depo'])}</td><td align='center'>{e(r['hedef'])}</td><td align='right'>{_n(r['miktar'], 3)}</td>"
        f"<td align='center'>{e(r['birim'])}</td><td align='right'>{_n(r['fiyat'])}</td><td align='right'>{_n(r['tutar'])}</td>"
        f"<td>{e(r['not'])}</td></tr>" for r in veri["satirlar"])
    top = "".join(
        f"<tr><td>{e(k)}</td><td align='right'>{_n(v[0], 3)}</td><td align='right'>{_n(v[1], 3)}</td><td align='right'>{_n(v[2], 3)}</td>"
        f"<td align='right'>{_n(v[3], 3)}</td><td align='right'>{_n(v[4])}</td></tr>" for k, v in sorted(veri["toplamlar"].items()))
    acik = "".join(f"<p>{e(a)}</p>" for a in veri["aciklamalar"])
    return f"""
<html><body style="font-family:'Segoe UI'; font-size:9pt; color:#0f172a;">
<h2 style="color:#1e3a8a;">{e(b['tur'])} — {e(b['fis_no'])}</h2>
<p>Tarih: <b>{b['tarih']}</b> {e(b['saat'])} &nbsp; Belge No: <b>{e(b['belge_no'])}</b> &nbsp; Depo: <b>{e(b['depo'])}</b>
&nbsp; Hedef Depo: {e(b['hedef'])} &nbsp; Özel Kod: {e(b['ozel_kod'])} &nbsp; Yetki Kodu: {e(b['yetki_kodu'])}</p>
<table border="1" cellspacing="0" cellpadding="3" width="100%" style="border-color:#cbd5e1;">
<tr><th {th}>SN</th><th {th}>Tür</th><th {th}>Stok Kodu</th><th {th}>Stok Adı</th><th {th}>Depo</th><th {th}>Hedef</th>
<th {th}>Miktar</th><th {th}>Birim</th><th {th}>B.Fiyat</th><th {th}>Tutar</th><th {th}>Not</th></tr>{satir}</table>
<h4>Toplamlar</h4>
<table border="1" cellspacing="0" cellpadding="3" style="border-color:#cbd5e1;">
<tr><th {th}>Birim</th><th {th}>Giriş</th><th {th}>Çıkış</th><th {th}>Transfer</th><th {th}>Sayılan</th><th {th}>Tutar</th></tr>{top}</table>
{acik}</body></html>"""


def excel_yaz(path: str, veri: dict) -> None:
    import openpyxl
    b = veri["baslik"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stok Fişi"
    ws.append([b["tur"], b["fis_no"]])
    ws.append(["Tarih", b["tarih"], "Saat", b["saat"], "Belge No", b["belge_no"], "Depo", b["depo"], "Hedef Depo", b["hedef"]])
    ws.append([])
    ws.append(["SN", "Tür", "Stok Kodu", "Stok Adı", "Depo", "Hedef", "Miktar", "Birim", "Birim Fiyat", "Tutar", "Not"])
    for r in veri["satirlar"]:
        ws.append([r["sn"], r["tur"], r["kod"], r["ad"], r["depo"], r["hedef"], r["miktar"], r["birim"], r["fiyat"], r["tutar"], r["not"]])
    ws.append([])
    ws.append(["Birim", "Giriş", "Çıkış", "Transfer", "Sayılan", "Tutar"])
    for k, v in sorted(veri["toplamlar"].items()):
        ws.append([k, *v])
    wb.save(path)


def pdf_yaz(path: str, veri: dict) -> None:
    cari_fis_rapor.pdf_yaz_html(path, html(veri))


def yazdir(printer, veri: dict) -> None:
    cari_fis_rapor.yazdir_html(printer, html(veri))
