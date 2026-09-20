import pytest
import responses
from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.models import Base


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _no_blocking_message_boxes(monkeypatch):
    """QMessageBox.warning/information/critical/question çağrıları modal
    olduğundan, testte kimse tıklamayınca çalıştırma süresiz asılı kalır
    (bkz. test_backup_ui.py::test_new_task_dialog_duplicate_name_validation —
    tam takım koşusunu 300s zaman aşımına kadar kilitleyen gerçek bir örnek).
    Bu yüzden tüm testlerde varsayılan olarak "kullanıcı Tamam/Evet'e bastı"
    davranışı simüle edilir; bir testin gerçek buton seçimini doğrulaması
    gerekiyorsa kendi içinde ayrıca monkeypatch edip üzerine yazabilir."""
    ok = QMessageBox.StandardButton.Ok
    yes = QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: yes))


@pytest.fixture(autouse=True)
def _cleanup_qt_widgets():
    """Her testten sonra açık kalan üst düzey widget'ları kapatıp siler.

    Testler ekranları (GeneralSettingsScreen, DocumentDetailScreen...) hiç
    kapatmadığından, tam takım koşusunda yüzlerce yerel pencere birikiyor ve bir
    noktada Qt "access violation" ile tüm Python sürecini çökertiyordu (çöküş
    noktası, o ana kadar biriken widget sayısına bağlıydı)."""
    yield
    app = QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        w.close()


@pytest.fixture(autouse=True)
def _isolate_permission_manager():
    """PermissionManager bir singleton'dur; testler arası rol/yetki sızıntısını önler.

    Yetki kapısı (``gate``) testlerinin bıraktığı kısıtlı rol, sonraki UI
    testlerinde butonları pasifleştirip yanıltıcı hatalara yol açıyordu.
    """
    yield
    try:
        from src.desktop.managers.permission_manager import PermissionManager
        PermissionManager().reset()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture
def mock_api() -> Generator[responses.RequestsMock, None, None]:
    """Provides a mocked requests container for HTTP requests."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a clean in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_class = sessionmaker(bind=engine)
    session = session_class()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
