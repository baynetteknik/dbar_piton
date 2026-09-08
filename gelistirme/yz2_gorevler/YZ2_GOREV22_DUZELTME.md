# transaction_document_dialog.py — F6/F7 Kalıcı Çözüm

## Sorun
keyPressEvent override çalışmıyor çünkü
QTableWidget, QComboBox, QLineEdit gibi iç widget'lar
klavye eventlerini önce kendileri yakalıyor.

## Çözüm — eventFilter (application seviyesinde)

### __init__ içine ekle (super().__init__(parent) sonrası):

```python
# Application seviyesinde event filter
from PyQt6.QtWidgets import QApplication
QApplication.instance().installEventFilter(self)
```

### eventFilter metodunu ekle:

```python
def eventFilter(self, obj, event):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtCore import Qt

    if event.type() == QEvent.Type.KeyPress:
        key = event.key()
        # Sadece bu dialog aktifken çalış
        if self.isActiveWindow():
            if key == Qt.Key.Key_F6:
                self.toggle_bottom_panel()
                return True
            elif key == Qt.Key.Key_F7:
                self.toggle_info_panel()
                return True
            elif key == Qt.Key.Key_F5:
                self.calculate_totals()
                return True

    return super().eventFilter(obj, event)
```

### closeEvent içine temizle:

```python
def closeEvent(self, event):
    from PyQt6.QtWidgets import QApplication
    QApplication.instance().removeEventFilter(self)
    super().closeEvent(event)
```

### reject ve accept override:

```python
def accept(self):
    from PyQt6.QtWidgets import QApplication
    QApplication.instance().removeEventFilter(self)
    super().accept()

def reject(self):
    from PyQt6.QtWidgets import QApplication
    QApplication.instance().removeEventFilter(self)
    super().reject()
```

---

## Fazla Collapse Butonu

HareketFinansWidget içinde başlık satırı var mı kontrol et:

```python
# hareket_finans_widget.py içinde _init_ui'de
# Şu satırları ARA ve SİL (varsa):

lbl_hdr = QLabel("⚙️ HAREKET AYARLARI & FİNANS")
# Bu label'ın yanında btn_collapse veya ∧ butonu varsa SİL

# Sadece şu kalmalı:
lbl_hdr = QLabel("⚙️ HAREKET AYARLARI & FİNANS")
lbl_hdr.setStyleSheet("font-weight:800; color:#1e3a8a; font-size:10px;")
main_lyt.addWidget(lbl_hdr)
# Başka buton YOK
```

---

## HareketFinansWidget Yükseklik

```python
# _init_ui içinde tüm combo ve input'lara:
self.cmb_doviz.setFixedHeight(24)
self.cmb_doviz.setSizePolicy(
    QSizePolicy.Policy.Expanding,
    QSizePolicy.Policy.Fixed   # ← Fixed olmalı
)
self.txt_kur.setFixedHeight(24)
self.cmb_kdv.setFixedHeight(24)
self.cmb_sekil.setFixedHeight(24)
self.cmb_kasa.setFixedHeight(24)

# Frame'e de max height ver:
main_lyt.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
```
