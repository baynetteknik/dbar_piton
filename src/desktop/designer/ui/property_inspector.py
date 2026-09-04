"""
TOYA ERP - Özellikler Denetçisi (PropertyInspector)
Sağ panelde seçilen görsel nesnenin milimetrik koordinatlarını,
fontunu, renklerini, kenarlıklarını ve veri bağlamalarını anlık düzenler.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import ItemConfig
from src.desktop.designer.ui.designer_item import DesignerItemWidget


class PropertyInspector(QWidget):
    """Milimetrik Özellikler Denetçisi."""

    property_changed = pyqtSignal(object)  # DesignerItemWidget

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.active_widget: DesignerItemWidget | None = None
        self._updating = False

        self._init_ui()
        self.clear_selection()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # ─── 1. Eleman Başlığı ───
        self.lbl_item_id = QLabel("Seçili Nesne: Yok", container)
        self.lbl_item_id.setStyleSheet("font-weight: bold; color: #1E293B; font-size: 11px; padding: 4px;")
        layout.addWidget(self.lbl_item_id)

        # ─── 2. Konum & Boyut (mm) ───
        grp_geom = QGroupBox("📐 Konum & Boyut (mm)", container)
        grp_geom.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; color: #334155; }")
        form_geom = QFormLayout(grp_geom)
        form_geom.setContentsMargins(6, 10, 6, 6)
        form_geom.setSpacing(4)

        self.spn_x = self._create_double_spin(0, 300, 0.5)
        self.spn_y = self._create_double_spin(0, 300, 0.5)
        self.spn_w = self._create_double_spin(1, 300, 0.5)
        self.spn_h = self._create_double_spin(1, 300, 0.5)

        form_geom.addRow("Sol (X):", self.spn_x)
        form_geom.addRow("Üst (Y):", self.spn_y)
        form_geom.addRow("Genişlik (W):", self.spn_w)
        form_geom.addRow("Yükseklik (H):", self.spn_h)
        layout.addWidget(grp_geom)

        # ─── 3. Veri & İçerik ───
        grp_data = QGroupBox("📊 Veri & İçerik", container)
        grp_data.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; color: #334155; }")
        form_data = QFormLayout(grp_data)
        form_data.setContentsMargins(6, 10, 6, 6)
        form_data.setSpacing(4)

        self.cmb_type = QComboBox(grp_data)
        self.cmb_type.addItems(["text", "data_field", "expression", "image", "barcode", "line", "box", "system_var"])
        self.cmb_type.currentTextChanged.connect(self._on_ui_changed)

        self.txt_text = QLineEdit(grp_data)
        self.txt_text.textChanged.connect(self._on_ui_changed)

        self.txt_field = QLineEdit(grp_data)
        self.txt_field.textChanged.connect(self._on_ui_changed)

        self.txt_expression = QLineEdit(grp_data)
        self.txt_expression.textChanged.connect(self._on_ui_changed)

        self.cmb_format = QComboBox(grp_data)
        self.cmb_format.addItems(["", "currency", "number", "integer", "date", "percent"])
        self.cmb_format.currentTextChanged.connect(self._on_ui_changed)

        form_data.addRow("Öğe Tipi:", self.cmb_type)
        form_data.addRow("Sabit Metin:", self.txt_text)
        form_data.addRow("Veri Alanı:", self.txt_field)
        form_data.addRow("Formül (Fx):", self.txt_expression)
        form_data.addRow("Format:", self.cmb_format)
        layout.addWidget(grp_data)

        # ─── 4. Tipografi & Hizalama ───
        grp_typo = QGroupBox("🔤 Tipografi & Hizalama", container)
        grp_typo.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; color: #334155; }")
        form_typo = QFormLayout(grp_typo)
        form_typo.setContentsMargins(6, 10, 6, 6)
        form_typo.setSpacing(4)

        self.cmb_font = QFontComboBox(grp_typo)
        self.cmb_font.currentFontChanged.connect(self._on_ui_changed)

        self.spn_font_size = QSpinBox(grp_typo)
        self.spn_font_size.setRange(5, 48)
        self.spn_font_size.valueChanged.connect(self._on_ui_changed)

        # Kalın / İtalik
        style_layout = QHBoxLayout()
        self.chk_bold = QCheckBox("Kalın (Bold)", grp_typo)
        self.chk_bold.toggled.connect(self._on_ui_changed)
        self.chk_italic = QCheckBox("İtalik", grp_typo)
        self.chk_italic.toggled.connect(self._on_ui_changed)
        style_layout.addWidget(self.chk_bold)
        style_layout.addWidget(self.chk_italic)

        # Hizalama
        self.cmb_align = QComboBox(grp_typo)
        self.cmb_align.addItems(["left", "center", "right"])
        self.cmb_align.currentTextChanged.connect(self._on_ui_changed)

        form_typo.addRow("Font:", self.cmb_font)
        form_typo.addRow("Boyut (pt):", self.spn_font_size)
        form_typo.addRow("Stil:", style_layout)
        form_typo.addRow("Hizalama:", self.cmb_align)
        layout.addWidget(grp_typo)

        # ─── 5. Çerçeve & Renkler ───
        grp_border = QGroupBox("🖼️ Çerçeve & Renkler", container)
        grp_border.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; color: #334155; }")
        form_border = QFormLayout(grp_border)
        form_border.setContentsMargins(6, 10, 6, 6)
        form_border.setSpacing(4)

        borders_layout = QHBoxLayout()
        self.chk_b_top = QCheckBox("Üst", grp_border)
        self.chk_b_bottom = QCheckBox("Alt", grp_border)
        self.chk_b_left = QCheckBox("Sol", grp_border)
        self.chk_b_right = QCheckBox("Sağ", grp_border)
        for chk in (self.chk_b_top, self.chk_b_bottom, self.chk_b_left, self.chk_b_right):
            chk.toggled.connect(self._on_ui_changed)
            borders_layout.addWidget(chk)

        self.btn_bg_color = QPushButton("Seç...", grp_border)
        self.btn_bg_color.clicked.connect(self._pick_bg_color)
        self.cur_bg_color = ""

        self.chk_word_wrap = QCheckBox("Metni Kaydır (Word Wrap)", grp_border)
        self.chk_word_wrap.toggled.connect(self._on_ui_changed)

        form_border.addRow("Kenarlıklar:", borders_layout)
        form_border.addRow("Arka Plan:", self.btn_bg_color)
        form_border.addRow("Kaydırma:", self.chk_word_wrap)
        layout.addWidget(grp_border)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_double_spin(self, min_v: float, max_v: float, step: float) -> QDoubleSpinBox:
        spn = QDoubleSpinBox(self)
        spn.setRange(min_v, max_v)
        spn.setSingleStep(step)
        spn.setDecimals(1)
        spn.valueChanged.connect(self._on_geometry_changed)
        return spn

    def clear_selection(self):
        self.active_widget = None
        self.lbl_item_id.setText("Seçili Nesne: Yok (Tuvalden bir nesne seçin)")
        self.setEnabled(False)

    def set_item_widget(self, item_widget: DesignerItemWidget | None):
        if item_widget is None:
            self.clear_selection()
            return

        self._updating = True
        self.active_widget = item_widget
        self.setEnabled(True)
        cfg = item_widget.item

        self.lbl_item_id.setText(f"Seçili: [{cfg.id}] ({cfg.type})")

        self.spn_x.setValue(cfg.x_mm)
        self.spn_y.setValue(cfg.y_mm)
        self.spn_w.setValue(cfg.w_mm)
        self.spn_h.setValue(cfg.h_mm)

        self.cmb_type.setCurrentText(cfg.type)
        self.txt_text.setText(cfg.text)
        self.txt_field.setText(cfg.field)
        self.txt_expression.setText(cfg.expression)
        self.cmb_format.setCurrentText(cfg.format)

        self.cmb_font.setCurrentText(cfg.font_family)
        self.spn_font_size.setValue(cfg.font_size)
        self.chk_bold.setChecked(cfg.font_bold)
        self.chk_italic.setChecked(cfg.font_italic)
        self.cmb_align.setCurrentText(cfg.align)

        self.chk_b_top.setChecked(cfg.border_top)
        self.chk_b_bottom.setChecked(cfg.border_bottom)
        self.chk_b_left.setChecked(cfg.border_left)
        self.chk_b_right.setChecked(cfg.border_right)
        self.chk_word_wrap.setChecked(cfg.word_wrap)

        self.cur_bg_color = cfg.bg_color
        self._update_bg_btn_color()

        self._updating = False

    def _update_bg_btn_color(self):
        if self.cur_bg_color:
            self.btn_bg_color.setStyleSheet(f"background-color: {self.cur_bg_color}; color: black;")
            self.btn_bg_color.setText(self.cur_bg_color)
        else:
            self.btn_bg_color.setStyleSheet("")
            self.btn_bg_color.setText("Şeffaf (Yok)")

    def _pick_bg_color(self):
        initial = QColor(self.cur_bg_color) if self.cur_bg_color else QColor("#FFFFFF")
        color = QColorDialog.getColor(initial, self, "Arka Plan Rengi Seç")
        if color.isValid():
            self.cur_bg_color = color.name().upper()
            self._update_bg_btn_color()
            self._on_ui_changed()

    def _on_geometry_changed(self):
        if self._updating or not self.active_widget:
            return
        cfg = self.active_widget.item
        cfg.x_mm = round(self.spn_x.value(), 1)
        cfg.y_mm = round(self.spn_y.value(), 1)
        cfg.w_mm = round(self.spn_w.value(), 1)
        cfg.h_mm = round(self.spn_h.value(), 1)

        self.active_widget.update_geometry_from_model()
        self.property_changed.emit(self.active_widget)

    def _on_ui_changed(self):
        if self._updating or not self.active_widget:
            return
        cfg = self.active_widget.item
        cfg.type = self.cmb_type.currentText()
        cfg.text = self.txt_text.text()
        cfg.field = self.txt_field.text()
        cfg.expression = self.txt_expression.text()
        cfg.format = self.cmb_format.currentText()

        cfg.font_family = self.cmb_font.currentFont().family()
        cfg.font_size = self.spn_font_size.value()
        cfg.font_bold = self.chk_bold.isChecked()
        cfg.font_italic = self.chk_italic.isChecked()
        cfg.align = self.cmb_align.currentText()

        cfg.border_top = self.chk_b_top.isChecked()
        cfg.border_bottom = self.chk_b_bottom.isChecked()
        cfg.border_left = self.chk_b_left.isChecked()
        cfg.border_right = self.chk_b_right.isChecked()
        cfg.word_wrap = self.chk_word_wrap.isChecked()
        cfg.bg_color = self.cur_bg_color

        self.active_widget.update()
        self.property_changed.emit(self.active_widget)
