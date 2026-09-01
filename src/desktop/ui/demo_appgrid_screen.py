"""
TOYA ERP - AppGrid ve Modüler Ekran Demo Penceresi
Bu dosya yeni mimariyi TOYA ERP içinde test etmek için hazırlanmış örnek ekrandır.
"""

from PyQt6.QtWidgets import QMessageBox
from src.desktop.ui.components.base_list_screen import BaseListScreen


class AppGridCariDemoScreen(BaseListScreen):
    """TOYA ERP Cari Hesap Listesi - AppGrid Standart Ekranı"""
    
    def __init__(self, parent=None):
        super().__init__(screen_id="scr_cari_list", parent=parent)
        self.load_data()

    def load_data(self):
        """Örnek TOYA ERP Cari Hesap Kayıtları"""
        dummy_cari_data = [
            ["C-001", "TOYA BİLİŞİM VE YAZILIM A.Ş.", "1234567890", "0212 555 0101", 145000.00, 0.00],
            ["C-002", "DELTA LOJİSTİK VE ANTREPO LTD.", "9876543210", "0216 444 0202", 32500.50, 15000.00],
            ["C-003", "GLOBAL ELEKTRİK & OTOMASYON", "4567891230", "0312 333 0303", 0.00, 89500.50],
            ["C-004", "YILMAZLAR MAKİNA VE YEDEK PARÇA", "7891234560", "0224 222 0404", 512000.00, 75000.00],
            ["C-005", "KAFKAS GIDA VE TÜKETİM MAD. A.Ş.", "3216549870", "0232 111 0505", 18200.00, 18200.00],
            ["C-006", "ANADOLU MÜHENDİSLİK VE İNŞAAT", "6549873210", "0322 999 0606", 950000.00, 320000.00],
            ["C-007", "MEPA ENDÜSTRİYEL METAL LTD.", "1597534862", "0262 888 0707", 78000.00, 0.00],
            ["C-008", "TEKNO OFİS KIRTASİYE SANAYİ", "3579514860", "0212 777 0808", 6400.00, 6400.00]
        ]
        self.set_data(dummy_cari_data)

    def on_action_triggered(self, action_id: str):
        """Header buton aksiyonları"""
        if action_id == "act_new":
            QMessageBox.information(self, "Yeni Cari", "TOYA ERP: Yeni Cari Kart Formu tetiklendi.")
        elif action_id == "act_edit":
            selected = self.grid.selectedRanges()
            if selected:
                row = selected[0].topRow()
                unvan = self.grid.item(row, 1).text() if self.grid.item(row, 1) else ""
                QMessageBox.information(self, "Cari Düzenle", f"Düzenlenen: {unvan}")
            else:
                QMessageBox.warning(self, "Uyarı", "Lütfen tablodan bir cari seçiniz.")
        elif action_id == "act_delete":
            QMessageBox.warning(self, "Cari Sil", "Seçili cariyi silmek/pasife almak istiyor musunuz?")
        elif action_id == "act_refresh":
            self.load_data()
            self.lbl_status_msg.setText("Kayıtlar güncellendi.")

    def on_row_double_clicked(self, row_idx: int, row_dict: dict):
        QMessageBox.information(
            self, 
            "Cari Detayı", 
            f"Kod: {row_dict.get('KOD')}\nÜnvan: {row_dict.get('ÜNVAN')}\nBorç: {row_dict.get('BORÇ')} ₺"
        )
