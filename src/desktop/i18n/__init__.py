import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TranslationManager:
    """Çeviri yönetim sistemi.
    
    referans alınan DCC.TRANSLATIONS benzeri yapı ile çalışır.
    JSON formatındaki çeviri dosyalarını yükler ve yönetir.
    
    Kullanım:
        manager = TranslationManager()
        manager.set_language("tr")
        
        # Widget'larda kullanım
        label.setText(manager.translate("customers.title"))
        
        # Veya self.tr() ile entegrasyon
        QApplication.instance().installTranslator(manager.get_translator())
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern ile tek bir TranslationManager instance'ı保证."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.i18n_dir = Path(__file__).parent
        self.current_language = "tr"
        self.translations: dict[str, Any] = {}
        self.available_languages = self._detect_available_languages()
        
        # Varsayılan dili yükle
        self.load_language(self.current_language)
    
    def _detect_available_languages(self) -> list[str]:
        """Mevcut çeviri dosyalarını algılar."""
        languages = []
        for file_path in self.i18n_dir.glob("translations_*.json"):
            lang_code = file_path.stem.replace("translations_", "")
            languages.append(lang_code)
        return sorted(languages)
    
    def load_language(self, lang_code: str) -> bool:
        """Belirtilen dilin çeviri dosyasını yükler.
        
        Args:
            lang_code: Dil kodu (ör: "tr", "en", "de")
            
        Returns:
            bool: Yükleme başarılıysa True
        """
        file_path = self.i18n_dir / f"translations_{lang_code}.json"
        
        if not file_path.exists():
            logger.warning(f"Translation file not found: {file_path}")
            return False
        
        try:
            with open(file_path, encoding="utf-8") as f:
                self.translations = json.load(f)
            self.current_language = lang_code
            logger.info(f"Language loaded: {lang_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to load language {lang_code}: {e}")
            return False
    
    def set_language(self, lang_code: str) -> bool:
        """Dili değiştirir.
        
        Args:
            lang_code: Yeni dil kodu
            
        Returns:
            bool: Değiştirme başarılıysa True
        """
        if lang_code == self.current_language:
            return True
        
        return self.load_language(lang_code)
    
    def translate(self, key: str, **kwargs) -> str:
        """Verilen anahtar için çeviriyi döndürür.
        
        Args:
            key: Çeviri anahtarı (nokta notasyonu ile, ör: "customers.title")
            **kwargs: Format parametreleri (ör: count=5 ile "Seçilen {count} adet")
            
        Returns:
            str: Çevrilmiş metin veya anahtarın kendisi (bulunamazsa)
        """
        # Nokta notasyonu ile iç içe erişim
        keys = key.split(".")
        value = self.translations
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Çeviri bulunamadı, anahtarı döndür
                logger.debug(f"Translation not found: {key}")
                return key
        
        if not isinstance(value, str):
            logger.warning(f"Translation value is not a string: {key}")
            return key
        
        # Format parametrelerini uygula
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format parameter {e} in translation: {key}")
                return value
        
        return value
    
    def get_available_languages(self) -> list[str]:
        """Mevcut dillerin listesini döndürür."""
        return self.available_languages.copy()
    
    def get_current_language(self) -> str:
        """Mevcut dil kodunu döndürür."""
        return self.current_language
    
    def get_language_name(self, lang_code: str) -> str:
        """Dil kodu için insan-okunabilir isim döndürür."""
        language_names = {
            "tr": "Türkçe",
            "en": "English",
            "de": "Deutsch",
            "ru": "Русский",
            "fr": "Français",
            "uk": "Українська",
        }
        return language_names.get(lang_code, lang_code.upper())


# Modül seviyesinde kolay erişim için singleton instance
translation_manager = TranslationManager()


def tr(key: str, **kwargs) -> str:
    """Kolay çeviri fonksiyonu.
    
    Kullanım:
        from src.desktop.i18n import tr
        label.setText(tr("customers.title"))
        label.setText(tr("customers.messages.confirm_bulk_delete", count=5))
    """
    return translation_manager.translate(key, **kwargs)
