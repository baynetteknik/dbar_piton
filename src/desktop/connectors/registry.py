"""
TOYA ERP - Bağlayıcı Kayıt Defteri

Kullanılabilir dış sistem bağlayıcıları ad -> (görünen ad, fabrika) olarak burada
tutulur. Yeni bir dış sistem eklemek: bağlayıcı sınıfını `SourceConnector` sözleşmesine
uygun yazıp `register()` ile buraya eklemek yeterlidir; ekranlar/servisler değişmez.

Fabrika `factory(db) -> SourceConnector` imzasındadır ve ayarlardan bağlayıcıyı kurar
(ayar eksikse anlaşılır bir istisna fırlatır).
"""

from __future__ import annotations

from typing import Callable

from src.desktop.connectors.base import SourceConnector

_REGISTRY: dict[str, tuple[str, Callable[..., SourceConnector]]] = {}


def register(name: str, label: str, factory: Callable[..., SourceConnector]) -> None:
    _REGISTRY[name] = (label, factory)


def available() -> dict[str, str]:
    """{kaynak_adı: görünen ad}"""
    return {name: label for name, (label, _f) in _REGISTRY.items()}


def get_connector(db, name: str) -> SourceConnector:
    if name not in _REGISTRY:
        raise KeyError(f"Bilinmeyen kaynak: {name}")
    return _REGISTRY[name][1](db)


def _register_builtin() -> None:
    from src.desktop.connectors.wolvox_connector import WolvoxConnector

    register("wolvox", "Akınsoft Wolvox 9", lambda db: WolvoxConnector.from_settings(db))


_register_builtin()
