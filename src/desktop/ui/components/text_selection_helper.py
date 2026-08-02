import logging

from PyQt6.QtCore import QEvent, QObject, QSettings, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

logger = logging.getLogger(__name__)


class GlobalTextSelectionFilter(QObject):
    """Tüm uygulamadaki pencere ve diyaloglarda bulunan QLabel metinlerinin seçilebilir/kopyalanabilir olmasını sağlayan küresel filtre."""

    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_enabled = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = GlobalTextSelectionFilter()
        return cls._instance

    def eventFilter(self, obj, event):  # noqa: N802
        if self.is_enabled and event.type() == QEvent.Type.Show and isinstance(obj, QWidget):
            self.apply_to_widget(obj)
        return super().eventFilter(obj, event)

    def apply_to_widget(self, widget: QWidget):
        """Bir widget ve tüm QLabel alt bileşenlerine metin seçilebilirlik bayraklarını uygular."""
        if not widget:
            return

        flags = (
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        ) if self.is_enabled else Qt.TextInteractionFlag.NoTextInteraction

        if isinstance(widget, QLabel):
            widget.setTextInteractionFlags(flags)

        for child_label in widget.findChildren(QLabel):
            child_label.setTextInteractionFlags(flags)

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        app = QApplication.instance()
        if not app:
            return

        if enabled:
            app.installEventFilter(self)
        else:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass

        # Açık tüm pencerelere anında uygula
        for top_widget in app.topLevelWidgets():
            self.apply_to_widget(top_widget)

        logger.info(f"Küresel metin seçilebilirlik özelliği: {'Aktif' if enabled else 'Pasif'}")


def set_global_text_selection_enabled(enabled: bool):
    """Küresel metin seçilebilirliğini aktif veya pasif yapar ve QSettings içine kaydeder."""
    settings = QSettings("baynetteknik", "dbar_piton")
    settings.setValue("enable_selectable_text", enabled)
    settings.sync()

    filter_obj = GlobalTextSelectionFilter.get_instance()
    filter_obj.set_enabled(enabled)


def is_global_text_selection_enabled() -> bool:
    """Küresel metin seçilebilirliğinin aktif olup olmadığını döndürür."""
    settings = QSettings("baynetteknik", "dbar_piton")
    return settings.value("enable_selectable_text", False, type=bool)


def init_global_text_selection():
    """Uygulama başlangıcında ayarı okur ve küresel filtreyi başlatır."""
    enabled = is_global_text_selection_enabled()
    filter_obj = GlobalTextSelectionFilter.get_instance()
    filter_obj.set_enabled(enabled)
