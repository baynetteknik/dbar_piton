"""
TOYA ERP - Grid Preset (Ön Tanım) Sistemi
Her liste ekranı için sütun başlıkları, genişlik oranları, hizalamalar ve tipler burada tanımlanır.
Yeni presetler register_preset() fonksiyonu ile dinamik olarak sisteme eklenebilir.
"""

from typing import Dict, Any, List

GRID_PRESETS: Dict[str, Dict[str, Any]] = {
    # 1. Fiş / Evrak Listesi Preseti
    "dbgrid_fis": {
        "name": "Fiş Listesi",
        "columns": ["SEÇ", "EVRAK NO", "TARİH", "CARİ", "TOPLAM", "DURUM"],
        "width_ratios": [0.05, 0.12, 0.12, 0.30, 0.15, 0.26],
        "alignments": ["C", "C", "C", "L", "R", "C"],
        "types": ["checkbox", "text", "date", "text", "currency", "badge"],
    },
    
    # 2. Cari Kart Listesi Preseti
    "dbgrid_cari": {
        "name": "Cari Hesap Listesi",
        "columns": ["KOD", "ÜNVAN", "VERGİ NO", "TELEFON", "BORÇ", "ALACAK"],
        "width_ratios": [0.10, 0.35, 0.15, 0.15, 0.12, 0.13],
        "alignments": ["C", "L", "C", "C", "R", "R"],
        "types": ["text", "text", "text", "text", "currency", "currency"],
    },
    
    # 3. Stok Kart Listesi Preseti
    "dbgrid_stok": {
        "name": "Stok Kart Listesi",
        "columns": ["KOD", "ADI", "BİRİM", "KDV", "ALIŞ FİYAT", "SATIŞ FİYAT", "STOK"],
        "width_ratios": [0.08, 0.30, 0.08, 0.08, 0.15, 0.15, 0.16],
        "alignments": ["C", "L", "C", "C", "R", "R", "R"],
        "types": ["text", "text", "text", "percent", "currency", "currency", "number"],
    },
    
    # 4. Hızlı Arama Listeleri Preseti
    "dbgrid_search": {
        "name": "Hızlı Arama Listesi",
        "columns": ["KOD", "AÇIKLAMA"],
        "width_ratios": [0.30, 0.70],
        "alignments": ["C", "L"],
        "types": ["text", "text"],
    },
    
    # 5. Git Commit ve Push Geçmişi Preseti
    "dbgrid_git_commits": {
        "name": "Git Commit ve Push Geçmişi",
        "columns": ["DURUM", "HASH", "TARİH", "DAL", "YAZAR", "MESAJ"],
        "width_ratios": [0.12, 0.10, 0.16, 0.16, 0.14, 0.32],
        "alignments": ["C", "C", "C", "C", "L", "L"],
        "types": ["badge", "text", "date", "text", "text", "text"],
    },

    # 6. Yol Haritası ve Görev Takip Preseti
    "dbgrid_git_tasks": {
        "name": "Yol Haritası ve Görevler",
        "columns": ["ID", "KATEGORİ", "GÖREV", "AÇIKLAMA", "DURUM", "İLGİLİ DAL"],
        "width_ratios": [0.06, 0.16, 0.24, 0.28, 0.12, 0.14],
        "alignments": ["C", "L", "L", "L", "C", "C"],
        "types": ["number", "text", "text", "text", "badge", "text"],
    },

    # 7. İş Görevleri Listesi Preseti
    "dbgrid_work_tasks": {
        "name": "Görevler Listesi",
        "columns": ["ID", "KATEGORİ", "BAŞLIK", "DURUM", "DAL", "TARİH"],
        "width_ratios": [0.06, 0.16, 0.32, 0.14, 0.16, 0.16],
        "alignments": ["C", "L", "L", "C", "L", "C"],
        "types": ["number", "text", "text", "badge", "text", "date"],
    },

    # 8. Yedekleme Görevleri Preseti
    "dbgrid_backup": {
        "name": "Yedekleme Görevleri",
        "columns": ["KOD", "GÖREV ADI", "KAYNAK", "HEDEF", "ZAMANLAMA", "DURUM"],
        "width_ratios": [0.08, 0.26, 0.16, 0.18, 0.18, 0.14],
        "alignments": ["C", "L", "L", "L", "L", "C"],
        "types": ["text", "text", "text", "text", "text", "badge"],
    },

    # 9. Git Değişen Dosyalar Preseti
    "dbgrid_git_changes": {
        "name": "Değişen Dosyalar",
        "columns": ["DURUM", "KOD", "DOSYA YOLU"],
        "width_ratios": [0.20, 0.10, 0.70],
        "alignments": ["C", "C", "L"],
        "types": ["badge", "text", "text"],
    }
}


def register_preset(preset_id: str, columns: List[str], width_ratios: List[float], 
                    alignments: List[str] = None, types: List[str] = None, name: str = "") -> None:
    """
    Uygulamaya dinamik olarak yeni bir grid preseti kaydeder (Genişletilebilirlik için).
    """
    if sum(width_ratios) < 0.98 or sum(width_ratios) > 1.02:
        raise ValueError(f"Oranların toplamı 1.0 (~%100) olmalıdır! Mevcut: {sum(width_ratios)}")
    
    if alignments is None:
        alignments = ["L"] * len(columns)
    if types is None:
        types = ["text"] * len(columns)

    GRID_PRESETS[preset_id] = {
        "name": name or preset_id,
        "columns": columns,
        "width_ratios": width_ratios,
        "alignments": alignments,
        "types": types
    }


def get_preset(preset_id: str) -> Dict[str, Any]:
    """Preset tanımını döner, bulunamazsa hata fırlatır."""
    if preset_id not in GRID_PRESETS:
        raise KeyError(f"Tanımlanamayan Grid Preset ID: '{preset_id}'. Kayıtlılar: {list(GRID_PRESETS.keys())}")
    return GRID_PRESETS[preset_id]
