"""
TOYA ERP - İfade ve Hesaplama Motoru (Expression Engine)
Bant ve öğelerdeki dinamik formülleri, toplamları ve formatlamaları güvenle hesaplar.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


def sayiyi_yaziya_cevir(tutar: float, para_birimi: str = "TL", kurus_birimi: str = "Kuruş") -> str:
    """
    Sayısal tutarı Türkçe resmi fatura metnine çevirir.
    Örnek: 1450.50 -> "Yalnız Bin Dört Yüz Elli TL Elli Kuruştur"
    """
    try:
        tutar_float = round(float(tutar), 2)
    except (ValueError, TypeError):
        return ""

    birler = ["", "Bir", "İki", "Üç", "Dört", "Beş", "Altı", "Yedi", "Sekiz", "Dokuz"]
    onlar = ["", "On", "Yirmi", "Otuz", "Kırk", "Elli", "Altmış", "Yetmiş", "Seksen", "Doksan"]
    basamaklar = ["", "Bin", "Milyon", "Milyar", "Trilyon"]

    tam_kisim = int(abs(tutar_float))
    ondalik_kisim = int(round((abs(tutar_float) - tam_kisim) * 100))

    if tam_kisim == 0 and ondalik_kisim == 0:
        return f"Yalnız Sıfır {para_birimi}dir"

    def uclu_oku(sayi: int) -> str:
        yuz = sayi // 100
        on = (sayi % 100) // 10
        bir = sayi % 10
        sonuc = []
        if yuz == 1:
            sonuc.append("Yüz")
        elif yuz > 1:
            sonuc.append(f"{birler[yuz]} Yüz")
        if on > 0:
            sonuc.append(onlar[on])
        if bir > 0:
            sonuc.append(birler[bir])
        return " ".join(sonuc)

    gruplar = []
    temp = tam_kisim
    while temp > 0:
        gruplar.append(temp % 1000)
        temp //= 1000

    metin_parcalari = []
    for i in reversed(range(len(gruplar))):
        grup_sayisi = gruplar[i]
        if grup_sayisi == 0:
            continue
        # Bin basamağında özel durum: "Bir Bin" denmez, "Bin" denir.
        if i == 1 and grup_sayisi == 1:
            metin_parcalari.append("Bin")
        else:
            okunan = uclu_oku(grup_sayisi)
            basamak = basamaklar[i]
            if basamak:
                metin_parcalari.append(f"{okunan} {basamak}")
            else:
                metin_parcalari.append(okunan)

    tam_metin = " ".join(metin_parcalari).strip()
    if not tam_metin:
        tam_metin = "Sıfır"

    sonuc_metni = f"Yalnız {tam_metin} {para_birimi}"

    if ondalik_kisim > 0:
        ondalik_okunan = uclu_oku(ondalik_kisim)
        sonuc_metni += f" {ondalik_okunan} {kurus_birimi}tur"
    else:
        sonuc_metni += "dir"

    return sonuc_metni


class ExpressionEngine:
    """Formül ve veri çözümleme yöneticisi."""

    @staticmethod
    def resolve_field(field_path: str, context: dict[str, Any]) -> Any:
        """
        Nokta notasyonu ile nested dictionary veya nesneden değer okur.
        Örnek: "cari.unvan" -> context["cari"]["unvan"] veya getattr(context["cari"], "unvan")
        """
        if not field_path:
            return ""

        # Köşeli veya süslü parantez temizliği
        clean_path = field_path.strip("{}[] ")
        parts = clean_path.split(".")

        curr = context
        for p in parts:
            if curr is None:
                return ""
            if isinstance(curr, dict):
                curr = curr.get(p, "")
            elif hasattr(curr, p):
                curr = getattr(curr, p, "")
            else:
                return ""
        return curr

    @staticmethod
    def format_value(val: Any, fmt_type: str, mask: str = "") -> str:
        """Değeri belirtilen formata sokar."""
        if val is None or val == "":
            return ""

        if fmt_type == "currency":
            try:
                num = float(val)
                # Türk Lirası formatı: 1.234,50 ₺
                formatted = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return f"{formatted} ₺"
            except (ValueError, TypeError):
                return str(val)

        elif fmt_type == "number":
            try:
                num = float(val)
                return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except (ValueError, TypeError):
                return str(val)

        elif fmt_type == "integer":
            try:
                return f"{int(val):,}".replace(",", ".")
            except (ValueError, TypeError):
                return str(val)

        elif fmt_type == "date":
            if isinstance(val, (date, datetime)):
                return val.strftime(mask or "%d.%m.%Y")
            return str(val)

        elif fmt_type == "percent":
            try:
                num = float(val)
                return f"%{num:.2f}".replace(".", ",")
            except (ValueError, TypeError):
                return str(val)

        return str(val)

    @classmethod
    def evaluate_expression(cls, expr: str, context: dict[str, Any]) -> str:
        """
        Özel ifadeyi hesaplar:
        - [SUM(kalem.satir_tutari)]
        - [COUNT(kalem.id)]
        - [YAZIYLA(finans.genel_toplam, 'TL')]
        - [IIF(koşul, d, y)]
        """
        if not expr:
            return ""

        # YAZIYLA fonksiyonu
        yaziyla_match = re.search(r"\[\s*YAZIYLA\s*\(\s*([^,\)]+)(?:\s*,\s*['\"]([^'\"]+)['\"])?\s*\)\s*\]", expr, re.IGNORECASE)
        if yaziyla_match:
            field_name = yaziyla_match.group(1).strip()
            currency = yaziyla_match.group(2) or "TL"
            val = cls.resolve_field(field_name, context)
            try:
                num = float(val)
                return sayiyi_yaziya_cevir(num, para_birimi=currency)
            except (ValueError, TypeError):
                return ""

        # SUM fonksiyonu (dataset üzerinde toplama)
        sum_match = re.search(r"\[\s*SUM\s*\(\s*([^,\)]+)\s*\)\s*\]", expr, re.IGNORECASE)
        if sum_match:
            target_path = sum_match.group(1).strip()
            # Örn: kalem.satir_tutari -> context["kalemler"] veya context["lines"]
            parts = target_path.split(".")
            if len(parts) == 2:
                coll_name = parts[0] + "ler"  # kalem -> kalemler
                field_name = parts[1]
                items = context.get(coll_name, []) or context.get(parts[0], [])
                total = 0.0
                for itm in items:
                    val = itm.get(field_name, 0) if isinstance(itm, dict) else getattr(itm, field_name, 0)
                    try:
                        total += float(val or 0)
                    except (ValueError, TypeError):
                        pass
                return cls.format_value(total, "currency")

        # Standart veri alanı
        return str(cls.resolve_field(expr, context))
