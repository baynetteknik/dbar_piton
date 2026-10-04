"""TOYA ERP - Maksimize pencerelerin ilk gösterimde tam oturması.

Qt, `showMaximized()` çağrıldığı anda iç içe QSplitter/QTabWidget ağaçlarının yerleşimini bazen
pencerenin henüz kesinleşmemiş (eski/varsayılan) boyutuna göre hesaplıyor; kullanıcı pencereyi elle
küçültüp büyütene ya da başlık çubuğunda çift tıklayana kadar bu düzelmiyor. Aynı sorun daha önce
MainWindow'un gösterge panelinde (`dash_splitter`) görülüp `_ilk_yerlesimi_zorla` ile çözülmüştü;
bu modül aynı çözümü tüm maksimize pencereler (kart editörleri, belge diyalogları) için tekrar
kullanılabilir hale getirir."""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QSplitter, QWidget


def zorla_ilk_yerlesim(widget: QWidget) -> None:
    """`showMaximized()` çağrısından hemen sonra çağrılır; bir sonraki olay döngüsü turunda widget
    içindeki tüm QSplitter'ları güncel (gerçek) boyutlarına göre yeniden dağıtır."""
    def _uygula() -> None:
        if sip.isdeleted(widget):
            return
        for sp in widget.findChildren(QSplitter):
            sp.setSizes(sp.sizes())
        widget.updateGeometry()
    QTimer.singleShot(0, _uygula)


def ekrana_sigdir_boyut(width: int, height: int, kenar_payi: int = 40) -> tuple[int, int]:
    """İstenen (width, height) değerini birincil ekranın kullanılabilir alanına (görev çubuğu hariç)
    sığacak şekilde küçültür. Düşük çözünürlüklü (ör. 1366x768) ekranlarda sabit `resize(1600, 900)`
    gibi çağrılar pencerenin bir kısmını ekran dışına taşırıyordu; bu, ekrana sığmayan kısmı kırpmak
    yerine isteneni küçültür. Ekran bilgisi alınamazsa (ör. test ortamı, headless) değerler aynen
    döner — büyük ekranlarda da istenen boyut zaten sığıyorsa davranış değişmez."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return width, height
    avail = screen.availableGeometry()
    return (
        min(width, max(avail.width() - kenar_payi, 320)),
        min(height, max(avail.height() - kenar_payi, 240)),
    )


def ekrana_sigdir(widget: QWidget, width: int, height: int, *, fixed: bool = False) -> None:
    """`widget.resize(width, height)` / `widget.setFixedSize(width, height)` yerine kullanılır:
    istenen boyut ekrana sığmıyorsa `ekrana_sigdir_boyut` ile küçültülmüş hâliyle uygulanır."""
    w, h = ekrana_sigdir_boyut(width, height)
    if fixed:
        widget.setFixedSize(w, h)
    else:
        widget.resize(w, h)
