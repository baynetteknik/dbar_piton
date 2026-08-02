import logging
import time
from enum import Enum

import requests
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class NetworkState(Enum):
    """Ağ bağlantı durumları."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"  # Yavaş bağlantı veya kısmi erişim


class NetworkMonitor(QObject):
    """Ağ bağlantısını izleyen monitör.
    
    DIAApp3'teki ağ izleme mantığını temel alır.
    Periyodik olarak bağlantı kontrolü yapar ve durum değişikliklerini bildirir.
    
    Özellikler:
    - Periyodik connectivity check
    - State makinası: ONLINE, OFFLINE, DEGRADED
    - Otomatik retry mekanizması
    - Sinyal tabanlı UI bildirimleri
    
    Kullanım:
        monitor = NetworkMonitor()
        monitor.status_changed.connect(on_network_changed)
        monitor.start()
    """
    
    # Sinyaller
    status_changed = pyqtSignal(NetworkState)
    connection_restored = pyqtSignal()
    connection_lost = pyqtSignal()
    
    def __init__(
        self,
        check_urls: list[str] | None = None,
        interval_ms: int = 5000,
        timeout_seconds: int = 3,
        degraded_threshold_ms: int = 2000,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        
        # Varsayılan kontrol URL'leri
        self.check_urls = check_urls or [
            "https://httpbin.org/get",
            "https://www.google.com",
            "https://1.1.1.1",  # Cloudflare DNS
        ]
        
        # Ayarlar
        self.interval_ms = interval_ms
        self.timeout_seconds = timeout_seconds
        self.degraded_threshold_ms = degraded_threshold_ms
        
        # Durum
        self.state = NetworkState.ONLINE
        self.last_check_time: float = 0
        self.last_response_time: float = 0
        self.consecutive_failures: int = 0
        self.max_consecutive_failures: int = 3
        
        # Zamanlayıcı
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_connectivity)
        
        # İlk kontrol için kısa gecikme
        self._initial_timer = QTimer(self)
        self._initial_timer.setSingleShot(True)
        self._initial_timer.timeout.connect(self._check_connectivity)
    
    def start(self):
        """Network monitoring'i başlatır."""
        logger.info("Network monitor starting", interval_ms=self.interval_ms)
        self._initial_timer.start(1000)  # 1 saniye sonra ilk kontrol
    
    def stop(self):
        """Network monitoring'i durdurur."""
        logger.info("Network monitor stopping")
        self.timer.stop()
        self._initial_timer.stop()
    
    def _check_connectivity(self):
        """Bağlantı kontrolü yapar."""
        # Zamanlayıcıyı başlat (bir sonraki kontrol için)
        if not self.timer.isActive():
            self.timer.start(self.interval_ms)
        
        start_time = time.time()
        is_connected = False
        response_time = 0
        
        for url in self.check_urls:
            try:
                response = requests.get(url, timeout=self.timeout_seconds)
                if response.status_code == 200:
                    is_connected = True
                    response_time = (time.time() - start_time) * 1000  # ms
                    break
            except requests.RequestException:
                continue
        
        self.last_check_time = time.time()
        self.last_response_time = response_time
        
        # Durum belirleme
        if is_connected:
            self.consecutive_failures = 0
            
            if response_time > self.degraded_threshold_ms:
                new_state = NetworkState.DEGRADED
            else:
                new_state = NetworkState.ONLINE
            
            # Durum değişikliği varsa
            if new_state != self.state:
                old_state = self.state
                self.state = new_state
                logger.info(
                    "Network state changed",
                    old=old_state.value,
                    new=new_state.value,
                    response_time_ms=response_time,
                )
                self.status_changed.emit(new_state)
                
                # Önceki durum OFFLINE ise bağlantı restored
                if old_state == NetworkState.OFFLINE:
                    self.connection_restored.emit()
        else:
            self.consecutive_failures += 1
            
            # Bağlantı kesildi
            if self.state != NetworkState.OFFLINE:
                self.state = NetworkState.OFFLINE
                logger.warning(
                    "Network connection lost",
                    consecutive_failures=self.consecutive_failures,
                )
                self.status_changed.emit(NetworkState.OFFLINE)
                self.connection_lost.emit()
    
    def get_state(self) -> NetworkState:
        """Mevcut ağ durumunu döndürür."""
        return self.state
    
    def is_online(self) -> bool:
        """İnternet bağlantısı var mı?"""
        return self.state in (NetworkState.ONLINE, NetworkState.DEGRADED)
    
    def is_offline(self) -> bool:
        """İnternet bağlantısı kesik mi?"""
        return self.state == NetworkState.OFFLINE
    
    def is_degraded(self) -> bool:
        """Bağlantı yavaş mı?"""
        return self.state == NetworkState.DEGRADED
    
    def get_status_info(self) -> dict:
        """Mevcut durum hakkında detaylı bilgi döndürür."""
        return {
            "state": self.state.value,
            "last_check": self.last_check_time,
            "last_response_time_ms": self.last_response_time,
            "consecutive_failures": self.consecutive_failures,
            "is_online": self.is_online(),
            "check_urls": self.check_urls,
        }
    
    def force_check(self):
        """Zorla bağlantı kontrolü yapar ( zamanlayıcıyı beklemeden)."""
        self._check_connectivity()
    
    def add_check_url(self, url: str):
        """Yeni bir kontrol URL'i ekler."""
        if url not in self.check_urls:
            self.check_urls.append(url)
            logger.debug("Check URL added", url=url)
    
    def remove_check_url(self, url: str):
        """Bir kontrol URL'ini kaldırır."""
        if url in self.check_urls:
            self.check_urls.remove(url)
            logger.debug("Check URL removed", url=url)


# Modül seviyesinde kolay erişim için
_network_monitor: NetworkMonitor | None = None


def get_network_monitor() -> NetworkMonitor:
    """Global NetworkMonitor instance'ını döndürür."""
    global _network_monitor
    if _network_monitor is None:
        _network_monitor = NetworkMonitor()
    return _network_monitor


def check_network() -> bool:
    """Tek seferlik bağlantı kontrolü yapar."""
    monitor = get_network_monitor()
    monitor.force_check()
    return monitor.is_online()
