"""Unit tests for FilterableTableView profile management and column restoration."""

import pytest
from PyQt6.QtWidgets import QApplication

from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.ui.backup import BackupWidget
from src.desktop.ui.components.filterable_table import FilterableTableView


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_filterable_table_column_order_restoration(qapp):
    """Test saving custom column order, widths, and visibilities, then recalling them."""
    headers = {
        0: ("ID", "id"),
        1: ("Name", "name"),
        2: ("Source", "source"),
        3: ("Status", "status"),
    }
    profile_key = "test_table_profile_restore"
    pm = ProfileManager(profile_key=profile_key)
    
    # Instantiate table
    table = FilterableTableView(headers_dict=headers, profile_key=profile_key, enable_profile_bar=True)
    from PyQt6.QtGui import QStandardItemModel
    model = QStandardItemModel(0, 4)
    table.table_view.setModel(model)
    header = table.table_view.horizontalHeader()

    # Move section 0 ("id") to visual position 2
    header.moveSection(0, 2)
    # Hide section 1 ("name")
    table.set_column_hidden(1, True)
    # Set width of section 2 ("source")
    table.table_view.setColumnWidth(2, 220)

    # Capture current profile
    profile = table.capture_current_view_profile(profile_name="Özel Sıralama")
    pm.save_profile(profile)

    # Reset table sections to default order
    header.moveSection(header.visualIndex(0), 0)
    table.set_column_hidden(1, False)

    # Apply saved profile
    table.apply_view_profile(profile)

    # Assert column order, visibility, and width restoration
    assert header.visualIndex(0) == 2
    assert header.isSectionHidden(1) is True
    assert table.table_view.columnWidth(2) == 220


def test_asiri_genis_sutun_kaydedilirken_ve_uygulanirken_sinirlanir(qapp):
    """Gerçek hata (2026-09-30): bir sütun (ör. bir grid'in 'Başlık' sütunu) herhangi bir sebeple
    binlerce piksele genişleyip profile kaydedilirse, her açılışta tüm alanı kaplayıp sağındaki
    diğer sütunları (ID, No, Durum vb.) ekran dışına itiyordu — kullanıcı bunu "sütunlar kayboldu"
    olarak yaşıyordu. `MAX_COLUMN_WIDTH` hem kayıtta hem uygulamada bu tür bir genişliği sınırlamalı."""
    headers = {0: ("ID", "id"), 1: ("Name", "name"), 2: ("Status", "status")}
    profile_key = "test_table_profile_asiri_genislik"

    table = FilterableTableView(headers_dict=headers, profile_key=profile_key, enable_profile_bar=True)
    from PyQt6.QtGui import QStandardItemModel
    model = QStandardItemModel(0, 3)
    table.table_view.setModel(model)

    # Sütun bir şekilde (sürükleme kazası, çift tık vb.) aşırı genişlemiş olsun.
    table.table_view.setColumnWidth(1, 4701)
    profile = table.capture_current_view_profile(profile_name="Bozuk")
    assert profile.column_settings.individual_columns["name"].width <= FilterableTableView.MAX_COLUMN_WIDTH

    # Daha önce (bu düzeltmeden önce) kaydedilmiş, halihazırda bozuk bir profil de uygulanınca sınırlanmalı.
    profile.column_settings.individual_columns["name"].width = 4701
    table.apply_view_profile(profile)
    assert table.table_view.columnWidth(1) == FilterableTableView.MAX_COLUMN_WIDTH


def test_backup_widget_profile_key_isolation(qapp):
    """Test switching categories in BackupWidget changes profile_key."""
    widget = BackupWidget(db_session=None)
    assert widget.filterable_table.profile_key == "backup_tasks"

    # Switch category to Restore
    widget.switch_category("Restore")
    assert widget.filterable_table.profile_key == "restore_tasks"

    # Switch back to Backup
    widget.switch_category("Backup")
    assert widget.filterable_table.profile_key == "backup_tasks"


def test_profile_menu_combo_shows_saved_profile_immediately(qapp):
    """Profil menüsünden kaydedilen profil, menüyü kapatıp açmadan listede görünmeli (silince de kalkmalı)."""
    from PyQt6.QtWidgets import QComboBox

    headers = {0: ("ID", "id"), 1: ("Ad", "name")}
    table = FilterableTableView(headers_dict=headers, profile_key="test_profile_combo_refresh", enable_profile_bar=False)
    combo = QComboBox()
    combo.addItem("Varsayılan")
    table.save_column_profile("Anlık Profil")
    table._refresh_profile_combo(combo)
    assert combo.findText("Anlık Profil") >= 0 and combo.currentText() == "Anlık Profil"
    table.delete_column_profile("Anlık Profil")
    table._refresh_profile_combo(combo)
    assert combo.findText("Anlık Profil") < 0
