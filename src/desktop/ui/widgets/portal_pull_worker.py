"""TOYA ERP - Portal karar çekme işçisi: ağ isteğini arka plan iş parçacığında yapar, sonucu ana iş parçacığına sinyalle verir
(yavaş / erişilemeyen sunucu arayüzü dondurmasın). Veritabanına dokunmaz; uygulama `apply_decisions` ile ana iş parçacığında yapılır."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from src.desktop.services import portal_sync_service


class PortalPullWorker(QThread):
    bitti = pyqtSignal(object, str)          # gövde (dict | None), hata metni

    def __init__(self, istek: tuple, timeout: int = 8, parent=None) -> None:
        super().__init__(parent)
        self.istek, self.zaman_asimi = istek, timeout

    def run(self) -> None:
        body, err = portal_sync_service.fetch_decisions(*self.istek, timeout=self.zaman_asimi)
        self.bitti.emit(body, err)
