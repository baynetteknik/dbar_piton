"""
TOYA ERP - SecurityQuestionsWidget

İki güvenlik sorusu + cevap alanı sunan yeniden kullanılabilir form parçası.
İlk kurulum sihirbazında ve Kullanıcı editöründe kullanılır.

Kullanım:
    w = SecurityQuestionsWidget()
    w.set_existing("Soru 1 metni", "Soru 2 metni", has_answers=True)
    payload = w.get_payload()   # {"q1","a1","q2","a2"}  (cevaplar boşsa değiştirme)
    ok, msg = w.validate()
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.auth_service import SECURITY_QUESTION_PRESETS


_COMBO_STYLE = """
    QComboBox {
        combobox-popup: 0;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 4px 6px;
        background-color: white;
        color: #0f172a;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #cbd5e1;
        background-color: #ffffff;
        color: #0f172a;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
"""

class SecurityQuestionsWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._has_answers = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        info = QLabel(
            "Parolanızı unutursanız bu iki sorunun cevabıyla sıfırlayabilirsiniz. "
            "Cevaplar büyük/küçük harf ve baş/son boşluk gözetmez.",
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(info)

        form = QFormLayout()
        form.setSpacing(6)

        self.cmb_q1 = QComboBox()
        self.cmb_q1.setStyleSheet(_COMBO_STYLE)
        self.cmb_q1.setEditable(True)
        self.cmb_q1.addItems(SECURITY_QUESTION_PRESETS)
        self.txt_a1 = QLineEdit()
        self.txt_a1.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_a1.setPlaceholderText("1. sorunun cevabı")

        self.cmb_q2 = QComboBox()
        self.cmb_q2.setStyleSheet(_COMBO_STYLE)
        self.cmb_q2.setEditable(True)
        self.cmb_q2.addItems(SECURITY_QUESTION_PRESETS)
        if self.cmb_q2.count() > 1:
            self.cmb_q2.setCurrentIndex(1)
        self.txt_a2 = QLineEdit()
        self.txt_a2.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_a2.setPlaceholderText("2. sorunun cevabı")

        form.addRow("Soru 1", self.cmb_q1)
        form.addRow("Cevap 1", self.txt_a1)
        form.addRow("Soru 2", self.cmb_q2)
        form.addRow("Cevap 2", self.txt_a2)
        root.addLayout(form)

        self.lbl_hint = QLabel("")
        self.lbl_hint.setStyleSheet("color:#94a3b8; font-size:11px;")
        root.addWidget(self.lbl_hint)

    # ------------------------------------------------------------------
    def set_existing(self, q1: str | None, q2: str | None, *, has_answers: bool) -> None:
        if q1:
            self.cmb_q1.setCurrentText(q1)
        if q2:
            self.cmb_q2.setCurrentText(q2)
        self._has_answers = has_answers
        if has_answers:
            self.txt_a1.setPlaceholderText("Değiştirmemek için boş bırakın")
            self.txt_a2.setPlaceholderText("Değiştirmemek için boş bırakın")
            self.lbl_hint.setText("Güvenlik soruları tanımlı. Yeniden ayarlamak için her iki cevabı da girin.")

    def get_payload(self) -> dict:
        return {
            "q1": self.cmb_q1.currentText().strip(),
            "a1": self.txt_a1.text(),
            "q2": self.cmb_q2.currentText().strip(),
            "a2": self.txt_a2.text(),
        }

    def is_dirty(self) -> bool:
        """Kullanıcı cevap girdiyse (yani yazılacak bir değişiklik varsa) True."""
        return bool(self.txt_a1.text().strip() or self.txt_a2.text().strip())

    def validate(self, *, required: bool = False) -> tuple[bool, str]:
        p = self.get_payload()
        a1, a2 = p["a1"].strip(), p["a2"].strip()

        if not a1 and not a2:
            if required and not self._has_answers:
                return False, "Lütfen iki güvenlik sorusunu da cevaplayın."
            return True, ""  # değişiklik yok

        if not (a1 and a2):
            return False, "İki cevabı da girin (biri boş)."
        if not (p["q1"] and p["q2"]):
            return False, "İki soru da seçili/dolu olmalı."
        if p["q1"] == p["q2"]:
            return False, "İki soru farklı olmalı."
        if len(a1) < 2 or len(a2) < 2:
            return False, "Cevaplar en az 2 karakter olmalı."
        return True, ""
