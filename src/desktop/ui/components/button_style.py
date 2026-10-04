"""TOYA ERP - Standart düğme stili (Genel Ayarlar'daki derinlikli düğme): tüm ekranlar aynı düğmeyi kullanır.

Beyaz zemin, alt kenarı kalın (gölge hissi), üzerine gelince koyulaşır, basınca çöker; renkli düğmede kenar rengin koyu tonudur.
Ekrana özel düğme stili yazma; `btn_style(bg, fg)` kullan (birincil: `btn_style(PRIMARY, "#ffffff")`, tehlike: `btn_style(DANGER_BG, DANGER_FG)`)."""

from __future__ import annotations

PRIMARY = "#2563eb"
DANGER_BG, DANGER_FG = "#fee2e2", "#991b1b"


def darken(hex_color: str, amount: float = 0.15) -> str:
    """Hex rengi koyulaştırır (hover / kenar); renkli düğmede beyaz yazının kontrastı korunur."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return hex_color
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(*(max(0, int(c * (1 - amount))) for c in (r, g, b)))


def btn_style(bg: str = "#ffffff", fg: str = "#1e293b") -> str:
    white = bg.lower() in ("#ffffff", "#fff")
    hover = "#f1f5f9" if white else darken(bg)
    edge = "#94a3b8" if white else darken(bg, 0.30)
    return (
        f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {edge}; border-bottom:3px solid {edge}; border-radius:6px;"
        f" padding:5px 8px; font-size:11px; font-weight:600; text-align:left; min-height:24px; }}"
        f" QPushButton:hover {{ background:{hover}; }}"
        f" QPushButton:pressed {{ border-bottom:1px solid {edge}; padding-top:7px; }}"
        f" QPushButton:checked {{ background:#dbeafe; color:#1e3a8a; border-color:#2563eb; }}"
        f" QPushButton:disabled {{ color:#94a3b8; background:#f8fafc; border-color:#e2e8f0; }}"
    )
