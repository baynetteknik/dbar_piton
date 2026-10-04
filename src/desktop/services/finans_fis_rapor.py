"""TOYA ERP - Kasa / banka hareket fişi çıktıları: HTML (yazdırma / PDF) ve Excel (kayıtlı fişten)."""

from __future__ import annotations

from html import escape

from src.desktop.services.cari_fis_rapor import _tl, pdf_yaz_html, yazdir_html
from src.desktop.services.finans_fis_service import FIS_TIPLERI, GRUPLAR, TURLER, FinansFisService


def rapor_verisi(db, fis_id: int) -> dict:
    fis, satirlar = FinansFisService(db).fis_getir(fis_id)
    rows, toplam = [], {}
    for h in satirlar:
        giris = h.tutar if (h.yon == "giris" or h.karsi_hesap_id) else 0.0
        cikis = h.tutar if (h.yon == "cikis" or h.karsi_hesap_id) else 0.0
        rows.append({"sn": h.satir_no or len(rows) + 1, "tur": TURLER.get(h.tur, (h.tur,))[0], "hesap": f"{h.hesap.kod} {h.hesap.ad}",
                     "karsi": f"{h.karsi_hesap.kod} {h.karsi_hesap.ad}" if h.karsi_hesap else "",
                     "cari": h.customer.fullname if h.customer else "", "not": h.aciklama or "", "tutar": h.tutar, "doviz": h.para_birimi,
                     "kur": h.kur, "yerel": h.tutar_tl, "makbuz": h.belge_no or ""})
        t = toplam.setdefault(h.para_birimi, [0.0, 0.0, 0.0, 0.0])
        t[0] += giris
        t[1] += cikis
        t[2] += h.tutar_tl if giris else 0.0
        t[3] += h.tutar_tl if cikis else 0.0
    tip = FIS_TIPLERI[fis.grup].get(fis.varsayilan_tur, f"{GRUPLAR[fis.grup]} Fişi")
    return {"baslik": {"fis_no": fis.fis_no, "tur": f"{GRUPLAR[fis.grup]} Hareket Fişi ({tip})", "tarih": fis.tarih.strftime("%d.%m.%Y"),
                       "saat": fis.saat or "", "belge_no": fis.belge_no or "", "sube": fis.sube or "", "ozel_kod": fis.ozel_kod or "",
                       "yetki_kodu": fis.yetki_kodu or ""},
            "satirlar": rows, "toplamlar": {k: tuple(v) for k, v in toplam.items()},
            "aciklamalar": [a for a in (fis.aciklama1, fis.aciklama2, fis.aciklama3) if a]}


def html(veri: dict) -> str:
    b, e = veri["baslik"], escape
    th = "style='background:#1e3a8a;color:#ffffff;padding:3px;'"
    satir = "".join(
        f"<tr><td align='center'>{r['sn']}</td><td>{e(r['tur'])}</td><td>{e(r['hesap'])}</td><td>{e(r['cari'])}</td><td>{e(r['karsi'])}</td>"
        f"<td align='right'>{_tl(r['tutar'])}</td><td align='center'>{e(r['doviz'])}</td><td align='right'>{_tl(r['kur'], 4)}</td>"
        f"<td align='right'>{_tl(r['yerel'])}</td><td>{e(r['makbuz'])}</td><td>{e(r['not'])}</td></tr>" for r in veri["satirlar"])
    top = "".join(f"<tr><td>{e(k)}</td><td align='right'>{_tl(v[0])}</td><td align='right'>{_tl(v[1])}</td>"
                  f"<td align='right'>{_tl(v[0] - v[1])}</td><td align='right'>{_tl(v[2])}</td><td align='right'>{_tl(v[3])}</td></tr>"
                  for k, v in sorted(veri["toplamlar"].items()))
    acik = "".join(f"<p>{e(a)}</p>" for a in veri["aciklamalar"])
    return f"""
<html><body style="font-family:'Segoe UI'; font-size:9pt; color:#0f172a;">
<h2 style="color:#1e3a8a;">{e(b['tur'])} — {e(b['fis_no'])}</h2>
<p>Tarih: <b>{b['tarih']}</b> {e(b['saat'])} &nbsp; Belge No: <b>{e(b['belge_no'])}</b> &nbsp; Şube: {e(b['sube'])}</p>
<table border="1" cellspacing="0" cellpadding="3" width="100%" style="border-color:#cbd5e1;">
<tr><th {th}>SN</th><th {th}>Tür</th><th {th}>Hesap</th><th {th}>Cari</th><th {th}>Karşı Hesap</th><th {th}>Tutar</th><th {th}>Dvz</th>
<th {th}>Kur</th><th {th}>Yerel Tutar</th><th {th}>Makbuz</th><th {th}>Not</th></tr>{satir}</table>
<h4>Toplamlar</h4>
<table border="1" cellspacing="0" cellpadding="3" style="border-color:#cbd5e1;">
<tr><th {th}>Döviz</th><th {th}>Giriş</th><th {th}>Çıkış</th><th {th}>Net</th><th {th}>Yerel Giriş</th><th {th}>Yerel Çıkış</th></tr>{top}</table>
{acik}</body></html>"""


def excel_yaz(path: str, veri: dict) -> None:
    import openpyxl
    b = veri["baslik"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kasa-Banka Fişi"
    ws.append([b["tur"], b["fis_no"]])
    ws.append(["Tarih", b["tarih"], "Saat", b["saat"], "Belge No", b["belge_no"]])
    ws.append([])
    ws.append(["SN", "Tür", "Hesap", "Cari", "Karşı Hesap", "Tutar", "Döviz", "Kur", "Yerel Tutar", "Makbuz", "Not"])
    for r in veri["satirlar"]:
        ws.append([r["sn"], r["tur"], r["hesap"], r["cari"], r["karsi"], r["tutar"], r["doviz"], r["kur"], r["yerel"], r["makbuz"], r["not"]])
    ws.append([])
    ws.append(["Döviz", "Giriş", "Çıkış", "Net", "Yerel Giriş", "Yerel Çıkış"])
    for k, v in sorted(veri["toplamlar"].items()):
        ws.append([k, v[0], v[1], v[0] - v[1], v[2], v[3]])
    wb.save(path)


def pdf_yaz(path: str, veri: dict) -> None:
    pdf_yaz_html(path, html(veri))


def yazdir(printer, veri: dict) -> None:
    yazdir_html(printer, html(veri))
