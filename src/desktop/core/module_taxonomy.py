"""
TOYA ERP - Dinamik Modül Taksonomi Motoru (ModuleTaxonomy)
Tüm ERP modüllerini, kategorilerini (Tanım, İşlem, Finans, İletişim, Sistem)
ve alt ekran tiplerini (Liste, Fiş Detay, Rapor) dinamik JSON veri yapısı
(data/module_taxonomy.json) üzerinden yöneten merkezi servis.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import copy

TAXONOMY_FILE = Path("data") / "module_taxonomy.json"

DEFAULT_TAXONOMY_DATA: Dict[str, Any] = {
    "categories": [
        {
            "code": "tan",
            "name": "Tanım & Master Kartlar",
            "icon": "📦",
            "modules": [
                {
                    "code": "tan.car",
                    "name": "Cari Kart Yönetimi",
                    "screens": {
                        "list": {"id": "tan.car.001", "template": "tpl_kart_list", "title": "Cari Hesap Listesi"},
                        "detail": {"id": "tan.car.detail", "template": "tpl_kart_detail", "title": "Cari Kart Tanım Formu"}
                    }
                },
                {
                    "code": "tan.stk",
                    "name": "Stok & Hizmet Kartları",
                    "screens": {
                        "list": {"id": "tan.stk.001", "template": "tpl_kart_list", "title": "Stok Kartları Listesi"},
                        "detail": {"id": "tan.stk.detail", "template": "tpl_kart_detail", "title": "Stok Kartı Tanım Formu"}
                    }
                }
            ]
        },
        {
            "code": "isl",
            "name": "İşlem & Ticari Hareketler",
            "icon": "📄",
            "modules": [
                {
                    "code": "isl.quo",
                    "name": "Teklif Yönetimi",
                    "screens": {
                        "list": {"id": "isl.quo.001", "template": "tpl_fis_list", "title": "Teklif Listesi"},
                        "detail": {"id": "isl.quo.detail", "template": "tpl_fis_detail", "title": "Teklif Detay Formu"},
                        "report": {"id": "rep.quo.001", "template": "tpl_rapor_list", "title": "Teklif Analiz Raporu"}
                    }
                },
                {
                    "code": "isl.ord",
                    "name": "Sipariş Yönetimi",
                    "screens": {
                        "list": {"id": "isl.ord.001", "template": "tpl_fis_list", "title": "Sipariş Listesi"},
                        "detail": {"id": "isl.ord.detail", "template": "tpl_fis_detail", "title": "Sipariş Detay Formu"}
                    }
                },
                {
                    "code": "isl.way",
                    "name": "İrsaliye Yönetimi",
                    "screens": {
                        "list": {"id": "isl.way.001", "template": "tpl_fis_list", "title": "İrsaliye Listesi"},
                        "detail": {"id": "isl.way.detail", "template": "tpl_fis_detail", "title": "İrsaliye Detay Formu"}
                    }
                },
                {
                    "code": "isl.inv",
                    "name": "Fatura Yönetimi",
                    "screens": {
                        "list": {"id": "isl.inv.001", "template": "tpl_fis_list", "title": "Fatura Listesi"},
                        "detail": {"id": "isl.inv.detail", "template": "tpl_fis_detail", "title": "Fatura Detay Formu"}
                    }
                },
                {
                    "code": "isl.stk",
                    "name": "Depo Fişleri & Transfer",
                    "screens": {
                        "list": {"id": "isl.stk.001", "template": "tpl_fis_list", "title": "Depo Fişleri Listesi"},
                        "detail": {"id": "isl.stk.detail", "template": "tpl_fis_detail", "title": "Depo Transfer / Fiş Detayı"}
                    }
                }
            ]
        },
        {
            "code": "fin",
            "name": "Finans & Muhasebe",
            "icon": "💵",
            "modules": [
                {
                    "code": "fin.csh",
                    "name": "Kasa Hareketleri",
                    "screens": {
                        "list": {"id": "isl.csh.001", "template": "tpl_fis_list", "title": "Kasa Fişleri Listesi"}
                    }
                },
                {
                    "code": "fin.bnk",
                    "name": "Banka Hareketleri",
                    "screens": {
                        "list": {"id": "isl.bnk.001", "template": "tpl_fis_list", "title": "Banka Fişleri Listesi"}
                    }
                },
                {
                    "code": "fin.car",
                    "name": "Cari Fiş & Virman",
                    "screens": {
                        "list": {"id": "isl.car.001", "template": "tpl_fis_list", "title": "Cari Fiş Listesi"}
                    }
                }
            ]
        },
        {
            "code": "com",
            "name": "İletişim & Görevler",
            "icon": "💬",
            "modules": [
                {
                    "code": "com.tsk",
                    "name": "Görev Takibi",
                    "screens": {
                        "list": {
                            "id": "com.tsk.001",
                            "template": "tpl_default_list",
                            "title": "Görevler & İş Emirleri",
                            "shortcut": "GOREVLST001",
                            "status": "active",
                        }
                    }
                },
                {
                    "code": "com.cht",
                    "name": "Ekip İçi Chat",
                    "screens": {
                        "list": {
                            "id": "com.cht.001",
                            "template": "tpl_default_list",
                            "title": "Sohbet & İletişim",
                            "shortcut": "CHATLST001",
                            "status": "planned",
                        }
                    }
                },
                {
                    "code": "com.mail",
                    "name": "Mail Gönderim Sistemi",
                    "screens": {
                        "list": {
                            "id": "com.mail.001",
                            "template": "tpl_default_list",
                            "title": "Mail Kuyruğu & Gönderim",
                            "shortcut": "MAILLST001",
                            "status": "planned",
                        }
                    }
                },
                {
                    "code": "com.cal",
                    "name": "Takvim Entegrasyonu",
                    "screens": {
                        "list": {
                            "id": "com.cal.001",
                            "template": "tpl_default_list",
                            "title": "Takvim & Hatırlatıcılar",
                            "shortcut": "TAKVIM001",
                            "status": "planned",
                        }
                    }
                }
            ]
        },
        {
            "code": "sys",
            "name": "Sistem & Ayarlar",
            "icon": "⚙️",
            "modules": [
                {
                    "code": "sys.grd",
                    "name": "Ekran & Grid Tanımları",
                    "screens": {
                        "list": {
                            "id": "sys.grd.001",
                            "template": "tpl_default_list",
                            "title": "Ekran & Grid Tanımları",
                            "shortcut": "EKRTNM001",
                            "status": "active",
                        }
                    }
                },
                {
                    "code": "sys.bak",
                    "name": "Yedekleme & Geri Yükleme",
                    "screens": {
                        "list": {
                            "id": "sys.bak.001",
                            "template": "tpl_default_list",
                            "title": "Yedekleme Görevleri",
                            "shortcut": "YEDEKLST001",
                            "status": "active",
                        }
                    }
                },
                {
                    "code": "sys.git",
                    "name": "Sürüm & Git Takibi",
                    "screens": {
                        "list": {
                            "id": "sys.git.001",
                            "template": "tpl_default_list",
                            "title": "Git Takip Merkezi",
                            "shortcut": "GITTRK001",
                            "status": "active",
                        }
                    }
                }
            ]
        }
    ]
}


class ModuleTaxonomyManager:
    """Modül taksonomisini diske yazan ve disken yükleyen yönetici sınıfı."""

    def __init__(self):
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULT_TAXONOMY_DATA)
        self.load()

    def load(self) -> None:
        """Taksonomi verisini JSON dosyasından yükler."""
        if TAXONOMY_FILE.exists():
            try:
                with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict) and "categories" in content:
                        self.data = content
            except Exception as e:
                print(f"[ModuleTaxonomy] Yükleme hatası: {e}")
        self._merge_missing_defaults()

    def _merge_missing_defaults(self) -> None:
        """Kayıtlı JSON'da olmayan varsayılan kategori/modülleri ekler."""
        existing = {c.get("code"): c for c in self.data.get("categories", [])}
        for default_cat in DEFAULT_TAXONOMY_DATA["categories"]:
            code = default_cat["code"]
            if code not in existing:
                self.data.setdefault("categories", []).append(
                    copy.deepcopy(default_cat)
                )
                continue
            live_mods = {
                m.get("code"): m for m in existing[code].get("modules", [])
            }
            for default_mod in default_cat.get("modules", []):
                if default_mod["code"] not in live_mods:
                    existing[code].setdefault("modules", []).append(
                        copy.deepcopy(default_mod)
                    )

    def save(self) -> None:
        """Taksonomi verisini JSON dosyasına kaydeder."""
        try:
            TAXONOMY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TAXONOMY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ModuleTaxonomy] Kaydetme hatası: {e}")

    def get_categories(self) -> List[Dict[str, Any]]:
        return self.data.get("categories", [])

    def add_category(self, code: str, name: str, icon: str = "📁") -> Dict[str, Any]:
        """Yeni bir modül kategorisi ekler."""
        for cat in self.data["categories"]:
            if cat["code"] == code:
                cat["name"] = name
                cat["icon"] = icon
                self.save()
                return cat

        new_cat = {"code": code, "name": name, "icon": icon, "modules": []}
        self.data["categories"].append(new_cat)
        self.save()
        return new_cat

    def add_module(self, category_code: str, module_code: str, module_name: str) -> Optional[Dict[str, Any]]:
        """Kategori altına yeni modül ekler."""
        for cat in self.data["categories"]:
            if cat["code"] == category_code:
                for mod in cat.get("modules", []):
                    if mod["code"] == module_code:
                        mod["name"] = module_name
                        self.save()
                        return mod
                
                new_mod = {
                    "code": module_code,
                    "name": module_name,
                    "screens": {
                        "list": {
                            "id": f"{module_code}.001",
                            "template": "tpl_default_list",
                            "title": f"{module_name} Listesi"
                        }
                    }
                }
                cat["modules"].append(new_mod)
                self.save()
                return new_mod
        return None

    def add_screen_to_module(self, module_code: str, screen_type: str, screen_id: str, template: str, title: str) -> bool:
        """Modül altına yeni bir ekran tanımı (list, detail, report) ekler."""
        for cat in self.data["categories"]:
            for mod in cat.get("modules", []):
                if mod["code"] == module_code:
                    if "screens" not in mod:
                        mod["screens"] = {}
                    mod["screens"][screen_type] = {
                        "id": screen_id,
                        "template": template,
                        "title": title
                    }
                    self.save()
                    return True
        return False

    def find_screen(self, screen_id: str) -> Optional[Dict[str, Any]]:
        """Ekran kimliğine göre taksonomi kaydını döner."""
        for cat in self.get_categories():
            for mod in cat.get("modules", []):
                for screen in (mod.get("screens") or {}).values():
                    if screen.get("id") == screen_id:
                        return {
                            "category": cat,
                            "module": mod,
                            "screen": screen,
                        }
        return None

    def iter_screens(self) -> List[Dict[str, Any]]:
        """Tüm ekran tanımlarını düz liste olarak döner."""
        rows: List[Dict[str, Any]] = []
        for cat in self.get_categories():
            for mod in cat.get("modules", []):
                for stype, screen in (mod.get("screens") or {}).items():
                    rows.append({
                        "category_code": cat.get("code"),
                        "category_name": cat.get("name"),
                        "module_code": mod.get("code"),
                        "module_name": mod.get("name"),
                        "screen_type": stype,
                        **screen,
                    })
        return rows

    def is_planned(self, screen_id: str) -> bool:
        found = self.find_screen(screen_id)
        if not found:
            return False
        return found["screen"].get("status") == "planned"


# Global Singleton Instance
taxonomy_manager = ModuleTaxonomyManager()
