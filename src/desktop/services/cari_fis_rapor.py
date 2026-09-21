"""TOYA ERP - Cari hesap fişi çıktıları: HTML (yazdırma / PDF) ve Excel.

Çıktılar kayıtlı fişten üretilir (fiş numarası ve satırlar veritabanındakiyle aynıdır). Yazıcı şablonları (tasarımcı)
sonraki aşamadır; bu yalın belge tüm fiş türlerinde ortak kullanılır."""

from __future__ import annotations

from html import escape

from src.desktop.services.cari_hareket_service import FIS_TIPLERI, TURLER, YONLER, CariHareketService, arac_etiket


def _tl(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rapor_verisi(db, fis_id: int) -> dict:
    fis, satirlar = CariHareketService(db).fis_getir(fis_id)
    rows, toplam = [], {}
    for h in satirlar:
        borc = h.tutar if h.yon == "borc" else 0.0
        alacak = h.tutar if h.yon == "alacak" else 0.0
        arac = " / ".join(x for x in (arac_etiket(h.odeme_araci), h.hesap or "") if x)
        rows.append({"sn": h.satir_no or len(rows) + 1, "tur": TURLER.get(h.tur, (h.tur,))[0], "yon": YONLER.get(h.yon, h.yon),
                     "kod": h.customer.customer_code or "", "unvan": h.customer.fullname, "not": h.aciklama or "",
                     "tutar": h.tutar, "doviz": h.para_birimi, "kur": h.kur, "yerel": h.tutar_tl,
                     "vade": h.vade.strftime("%d.%m.%Y") if h.vade else "", "makbuz": h.belge_no or "", "arac": arac})
        t = toplam.setdefault(h.para_birimi, [0.0, 0.0, 0.0, 0.0])
        t[0] += borc
        t[1] += alacak
        t[2] += h.tutar_tl if h.yon == "borc" else 0.0
        t[3] += h.tutar_tl if h.yon == "alacak" else 0.0
    return {
        "baslik": {"fis_no": fis.fis_no, "tur": FIS_TIPLERI.get(fis.varsayilan_tur, "Cari Hesap Fişi"),
                   "tarih": fis.tarih.strftime("%d.%m.%Y"), "saat": fis.saat or "", "belge_no": fis.belge_no or "",
                   "sube": fis.sube or "", "ozel_kod": fis.ozel_kod or "", "yetki_kodu": fis.yetki_kodu or ""},
        "satirlar": rows, "toplamlar": {k: tuple(v) for k, v in toplam.items()},
        "aciklamalar": [a for a in (fis.aciklama1, fis.aciklama2, fis.aciklama3) if a],
    }


def html(veri: dict) -> str:
    b = veri["baslik"]
    e = escape
    satir_html = "".join(
        f"<tr><td align='center'>{r['sn']}</td><td>{e(r['tur'])}</td><td>{e(r['kod'])}</td><td>{e(r['unvan'])}</td>"
        f"<td>{e(r['not'])}</td><td align='right'>{_tl(r['tutar'])}</td><td align='center'>{e(r['doviz'])}</td>"
        f"<td align='right'>{_tl(r['kur'], 4)}</td><td align='right'>{_tl(r['yerel'])}</td><td align='center'>{r['vade']}</td>"
        f"<td>{e(r['makbuz'])}</td><td>{e(r['arac'])}</td></tr>" for r in veri["satirlar"])
    toplam_html = "".join(
        f"<tr><td>{e(k)}</td><td align='right'>{_tl(v[0])}</td><td align='right'>{_tl(v[1])}</td>"
        f"<td align='right'>{_tl(abs(v[0] - v[1]))}</td><td align='right'>{_tl(v[2])}</td><td align='right'>{_tl(v[3])}</td>"
        f"<td align='right'>{_tl(abs(v[2] - v[3]))}</td></tr>" for k, v in sorted(veri["toplamlar"].items()))
    acik = "".join(f"<p>{e(a)}</p>" for a in veri["aciklamalar"])
    th = "style='background:#1e3a8a;color:#ffffff;padding:3px;'"
    return f"""
<html><body style="font-family:'Segoe UI'; font-size:9pt; color:#0f172a;">
<h2 style="color:#1e3a8a;">{e(b['tur'])} — {e(b['fis_no'])}</h2>
<p>Tarih: <b>{b['tarih']}</b> {e(b['saat'])} &nbsp; Belge No: <b>{e(b['belge_no'])}</b> &nbsp; Şube: {e(b['sube'])}
&nbsp; Özel Kod: {e(b['ozel_kod'])} &nbsp; Yetki Kodu: {e(b['yetki_kodu'])}</p>
<table border="1" cellspacing="0" cellpadding="3" width="100%" style="border-color:#cbd5e1;">
<tr><th {th}>SN</th><th {th}>Tür</th><th {th}>Cari Kodu</th><th {th}>Ünvan</th><th {th}>Not</th><th {th}>Tutar</th>
<th {th}>Dvz</th><th {th}>Kur</th><th {th}>Yerel Tutar</th><th {th}>Vade</th><th {th}>Makbuz</th><th {th}>Araç / Hesap</th></tr>
{satir_html}</table>
<h4>Toplamlar</h4>
<table border="1" cellspacing="0" cellpadding="3" style="border-color:#cbd5e1;">
<tr><th {th}>Döviz</th><th {th}>Borç</th><th {th}>Alacak</th><th {th}>Bakiye</th><th {th}>Yerel Borç</th>
<th {th}>Yerel Alacak</th><th {th}>Yerel Bakiye</th></tr>{toplam_html}</table>
{acik}</body></html>"""


def excel_yaz(path: str, veri: dict) -> None:
    import openpyxl
    b = veri["baslik"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cari Fiş"
    ws.append([b["tur"], b["fis_no"]])
    ws.append(["Tarih", b["tarih"], "Saat", b["saat"], "Belge No", b["belge_no"], "Şube", b["sube"]])
    ws.append([])
    ws.append(["SN", "Tür", "Cari Kodu", "Ünvan", "Not", "Tutar", "Döviz", "Kur", "Yerel Tutar", "Vade", "Makbuz", "Araç / Hesap"])
    for r in veri["satirlar"]:
        ws.append([r["sn"], r["tur"], r["kod"], r["unvan"], r["not"], r["tutar"], r["doviz"], r["kur"], r["yerel"], r["vade"],
                   r["makbuz"], r["arac"]])
    ws.append([])
    ws.append(["Döviz", "Borç", "Alacak", "Bakiye", "Yerel Borç", "Yerel Alacak", "Yerel Bakiye"])
    for k, v in sorted(veri["toplamlar"].items()):
        ws.append([k, v[0], v[1], abs(v[0] - v[1]), v[2], v[3], abs(v[2] - v[3])])
    wb.save(path)


def _belge_html(html_metni: str):
    from PyQt6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(html_metni)
    return doc


def pdf_yaz_html(path: str, html_metni: str) -> None:
    """HTML belgeyi A4 yatay PDF olarak yazar (fiş çıktılarında ortak kullanılır)."""
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(path)
    pr.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    pr.setPageOrientation(QPageLayout.Orientation.Landscape)
    _belge_html(html_metni).print(pr)


def yazdir_html(printer, html_metni: str) -> None:
    _belge_html(html_metni).print(printer)


def pdf_yaz(path: str, veri: dict) -> None:
    pdf_yaz_html(path, html(veri))


def yazdir(printer, veri: dict) -> None:
    yazdir_html(printer, html(veri))
