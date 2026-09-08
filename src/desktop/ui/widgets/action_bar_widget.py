"""
ToyaUI — ActionBarWidget
Sol EdgePanel aksiyonlar widget'ı.
Tüm liste ekranlarında kullanılabilir.
"""


from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel


class ActionBarWidget(QWidget):
    """Sol açılır/kapanır EdgePanel içinde işlem ve aksiyon butonları sağlayan bileşen."""

    new_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
    duplicate_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    bulk_delete_clicked = pyqtSignal()
    passive_clicked = pyqtSignal()
    convert_clicked = pyqtSignal()
    excel_clicked = pyqtSignal()
    refresh_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(
        self,
        group_title: str = "İŞLEMLER",
        convert_label: str = "🔄 Dönüştür",
        show_buttons: list[str] | None = None,
        hide_buttons: list[str] | None = None,
        initial_open: bool = False,
        panel_width: int = 220,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.group_title = group_title
        self.convert_label = convert_label
        self.show_buttons = show_buttons
        self.hide_buttons = hide_buttons if hide_buttons is not None else []
        self.initial_open = initial_open
        self.panel_width_val = panel_width

        self.init_ui()

    def _default_btn_style(self) -> str:
        """Standart işlem butonu stili."""
        return """
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
                font-family: 'Segoe UI';
            }
            QPushButton:hover { background-color: #f1f5f9; }
            QPushButton:disabled { color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }
        """

    def _danger_btn_style(self) -> str:
        """Kırmızı uyarı/silme butonu stili."""
        return """
            QPushButton {
                background-color: #fff1f2;
                color: #e11d48;
                border: 1px solid #fecdd3;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
                font-family: 'Segoe UI';
            }
            QPushButton:hover { background-color: #ffe4e6; border-color: #fda4af; }
            QPushButton:disabled { color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }
        """

    def _warning_btn_style(self) -> str:
        """Sarı pasife alma/uyarı butonu stili."""
        return """
            QPushButton {
                background-color: #fefce8;
                color: #ca8a04;
                border: 1px solid #fef08a;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
                font-family: 'Segoe UI';
            }
            QPushButton:hover { background-color: #fef9c3; border-color: #fde047; }
            QPushButton:disabled { color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }
        """

    def _close_btn_style(self) -> str:
        """Pembe/Kırmızı kapatma butonu stili."""
        return """
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
                border-radius: 6px;
                padding: 4px 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #991b1b;
                font-weight: bold;
                text-align: center;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """

    def init_ui(self):
        """EdgeTriggeredPanel ve içerik butonlarını yapılandırır."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sol Kenar Paneli
        self.edge_panel = EdgeTriggeredPanel(side="left", default_width=self.panel_width_val, parent=self)
        if hasattr(self.edge_panel, "set_panel_width"):
            self.edge_panel.set_panel_width(self.panel_width_val)

        # Scroll Alanı
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content_frame = QFrame()
        content_frame.setStyleSheet("background-color: transparent; border: none;")
        self.content_layout = QVBoxLayout(content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        # Akordiyon Bölümü
        self.sec_actions = CollapsibleSection(self.group_title, is_expanded=True)
        self.sec_actions.setObjectName("cmp.act.001")

        # Buton Tanımları
        self.buttons_dict = {}

        # 1. Yeni (F3)
        self.btn_new = QPushButton("➕ Yeni (F3)")
        self.btn_new.setObjectName("act.add.001")
        self.btn_new.setToolTip("Yeni Kayıt Ekle (F3)")
        self.btn_new.setShortcut("F3")
        self.btn_new.setStyleSheet(self._default_btn_style())
        self.btn_new.clicked.connect(self.new_clicked.emit)
        self.buttons_dict["new"] = self.btn_new

        # 2. Değiştir (F4)
        self.btn_edit = QPushButton("✏️ Değiştir (F4)")
        self.btn_edit.setObjectName("act.edt.001")
        self.btn_edit.setToolTip("Seçili Kaydı Değiştir (F4)")
        self.btn_edit.setShortcut("F4")
        self.btn_edit.setStyleSheet(self._default_btn_style())
        self.btn_edit.clicked.connect(self.edit_clicked.emit)
        self.buttons_dict["edit"] = self.btn_edit

        # 3. Kopyala
        self.btn_duplicate = QPushButton("📋 Kopyala")
        self.btn_duplicate.setObjectName("act.dup.001")
        self.btn_duplicate.setToolTip("Kaydı Kopyala")
        self.btn_duplicate.setStyleSheet(self._default_btn_style())
        self.btn_duplicate.clicked.connect(self.duplicate_clicked.emit)
        self.buttons_dict["duplicate"] = self.btn_duplicate

        # 4. Sil (Del)
        self.btn_delete = QPushButton("❌ Sil (Del)")
        self.btn_delete.setObjectName("act.del.001")
        self.btn_delete.setToolTip("Seçili Kaydı Sil (Del)")
        self.btn_delete.setShortcut("Del")
        self.btn_delete.setStyleSheet(self._danger_btn_style())
        self.btn_delete.clicked.connect(self.delete_clicked.emit)
        self.buttons_dict["delete"] = self.btn_delete

        # 5. Toplu Sil
        self.btn_bulk_delete = QPushButton("🗑️ Toplu Sil")
        self.btn_bulk_delete.setObjectName("act.bdel.001")
        self.btn_bulk_delete.setToolTip("Seçili Tüm Kayıtları Toplu Sil")
        self.btn_bulk_delete.setStyleSheet(self._danger_btn_style())
        self.btn_bulk_delete.clicked.connect(self.bulk_delete_clicked.emit)
        self.buttons_dict["bulk_delete"] = self.btn_bulk_delete

        # 6. Pasife Al
        self.btn_passive = QPushButton("⏸️ Pasife Al")
        self.btn_passive.setObjectName("act.pas.001")
        self.btn_passive.setToolTip("Kaydı Pasif Duruma Getir")
        self.btn_passive.setStyleSheet(self._warning_btn_style())
        self.btn_passive.clicked.connect(self.passive_clicked.emit)
        self.buttons_dict["passive"] = self.btn_passive

        # 7. Dönüştür
        self.btn_convert = QPushButton(self.convert_label)
        self.btn_convert.setObjectName("act.cnv.001")
        self.btn_convert.setToolTip(self.convert_label)
        self.btn_convert.setStyleSheet(self._default_btn_style())
        self.btn_convert.clicked.connect(self.convert_clicked.emit)
        self.buttons_dict["convert"] = self.btn_convert

        # 8. Yazdır / Excel (F9)
        self.btn_excel = QPushButton("🖨️ Yazdır / Excel (F9)")
        self.btn_excel.setObjectName("act.xls.001")
        self.btn_excel.setToolTip("Yazdır veya Excel'e Aktar (F9)")
        self.btn_excel.setShortcut("F9")
        self.btn_excel.setStyleSheet(self._default_btn_style())
        self.btn_excel.clicked.connect(self.excel_clicked.emit)
        self.buttons_dict["excel"] = self.btn_excel

        # 9. Yenile (F5)
        self.btn_refresh = QPushButton("🔄 Yenile (F5)")
        self.btn_refresh.setObjectName("act.ref.001")
        self.btn_refresh.setToolTip("Listeyi Yenile (F5)")
        self.btn_refresh.setShortcut("F5")
        self.btn_refresh.setStyleSheet(self._default_btn_style())
        self.btn_refresh.clicked.connect(self.refresh_clicked.emit)
        self.buttons_dict["refresh"] = self.btn_refresh

        # 10. Kapat
        self.btn_close = QPushButton("🚪 Kapat")
        self.btn_close.setObjectName("act.cls.001")
        self.btn_close.setToolTip("Ekranı / Sekmeyi Kapat")
        self.btn_close.setStyleSheet(self._close_btn_style())
        self.btn_close.clicked.connect(self.close_clicked.emit)
        self.buttons_dict["close"] = self.btn_close

        # Butonları filtreye göre ekle
        button_order = [
            "new", "edit", "duplicate", "delete", "bulk_delete",
            "passive", "convert", "excel", "refresh", "close",
        ]

        for key in button_order:
            btn = self.buttons_dict[key]
            # show_buttons belirtilmişse sadece oradakiler gösterilir
            if self.show_buttons is not None and key not in self.show_buttons:
                btn.hide()
                continue
            # hide_buttons belirtilmişse gizlenir
            if key in self.hide_buttons:
                btn.hide()
                continue

            self.sec_actions.add_widget(btn)

        self.content_layout.addWidget(self.sec_actions)
        self.content_layout.addStretch()

        scroll_area.setWidget(content_frame)
        self.edge_panel.set_content(scroll_area)
        main_layout.addWidget(self.edge_panel)

        # Başlangıç durumu
        if self.initial_open:
            self.edge_panel.open_panel()
        else:
            self.edge_panel.close_panel()

    def open_panel(self):
        """Paneli açar."""
        self.edge_panel.open_panel()

    def close_panel(self):
        """Paneli kapatır."""
        self.edge_panel.close_panel()

    def toggle_panel(self):
        """Paneli açıp kapatır."""
        self.edge_panel.toggle_panel()

    def is_open(self) -> bool:
        """Panelin açık olup olmadığını döndürür."""
        return self.edge_panel.is_open

    def set_group_title(self, title: str):
        """Aksiyonlar akordiyonunun başlığını günceller (örn. '... · 3 seçili')."""
        self.group_title = title
        if hasattr(self, "sec_actions"):
            self.sec_actions.set_title(title)

    def add_custom_section(self, section: CollapsibleSection):
        """Sol sidebar altına özel bir akordiyon bölümü ekler (örn: Görünüm Profilleri)."""
        # Stretch'ten önce ekle
        idx = self.content_layout.count() - 1
        if idx >= 0:
            self.content_layout.insertWidget(idx, section)
        else:
            self.content_layout.addWidget(section)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    bar = ActionBarWidget(
        group_title="TEKLİF İŞLEMLERİ",
        convert_label="Siparişe Dönüştür",
        hide_buttons=["bulk_delete"],
        initial_open=True,
        panel_width=220,
    )
    bar.new_clicked.connect(lambda: print("✅ Yeni tıklandı"))
    bar.delete_clicked.connect(lambda: print("✅ Sil tıklandı"))
    bar.show()
    print("ActionBarWidget başarıyla oluşturuldu.")
    sys.exit(0)
