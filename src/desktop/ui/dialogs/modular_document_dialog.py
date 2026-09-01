"""
TOYA ERP - Modüler Evrak ve Fiş Detay Penceresi (ModularDocumentDetailDialog)
CariHesapKunyesiWidget, BelgeVadeDetaylariWidget, HareketAyarlariWidget,
HareketKalemleriDbGridWidget ve FinansWidget bileşenlerini %100 modüler birleştiren
canlı hesaplamalı tam ekran Teklif / Fatura / Sipariş form penceresidir.
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QFrame, QLabel, QPushButton, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QFont

from src.desktop.ui.widgets.crud_actions_widget import CrudActionsWidget
from src.desktop.ui.widgets.export_actions_widget import ExportActionsWidget
from src.desktop.ui.widgets.document_form.cari_kunyesi_widget import CariHesapKunyesiWidget
from src.desktop.ui.widgets.document_form.belge_vade_widget import BelgeVadeDetaylariWidget
from src.desktop.ui.widgets.document_form.hareket_ayarlari_widget import HareketAyarlariWidget
from src.desktop.ui.widgets.document_form.finans_widget import FinansWidget
from src.desktop.ui.widgets.document_form.hareket_kalemleri_widget import HareketKalemleriDbGridWidget
from src.desktop.managers.theme_manager import ThemeManager


class ModularDocumentDetailDialog(QDialog):
    """Atomik widget'lardan oluşan modüler evrak detay formu (Teklif/Fatura/Sipariş)."""

    document_saved = pyqtSignal(dict)

    def __init__(self, doc_type: str = "Teklif", doc_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.doc_type = doc_type
        self.doc_id = doc_id or "TEK-2026-0001"
        self.theme = ThemeManager()
        
        self.setWindowTitle(f"📄 {self.doc_type} Detay Formu - [{self.doc_id}]")
        self.setMinimumSize(1150, 750)
        self.setWindowState(Qt.WindowState.WindowMaximized)
        
        self._init_ui()
        self._wire_signals()

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(8, 8, 8, 8)
        main_lyt.setSpacing(6)

        # 1. ÜST İNCE BAŞLIK ŞERİDİ
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #1e3a8a;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QLabel { color: white; }
        """)
        top_lyt = QHBoxLayout(top_bar)
        top_lyt.setContentsMargins(8, 4, 8, 4)

        lbl_logo = QLabel(f"📄 TOYA ERP | {self.doc_type.upper()} FORMU")
        lbl_logo.setStyleSheet("font-weight: 900; font-size: 13px; color: #93c5fd;")
        top_lyt.addWidget(lbl_logo)

        lbl_badge = QLabel(f"[{self.doc_id}]")
        lbl_badge.setStyleSheet("font-size: 11px; color: #bfdbfe; font-family: monospace; font-weight: bold;")
        top_lyt.addWidget(lbl_badge)

        top_lyt.addStretch()
        lbl_hint = QLabel("⌨️ F2: Kaydet | Ins: Satır Ekle | Del: Satır Sil | Esc: Vazgeç")
        lbl_hint.setStyleSheet("font-size: 10px; color: #cbd5e1;")
        top_lyt.addWidget(lbl_hint)

        main_lyt.addWidget(top_bar)

        # 2. ORTA BÖLÜM: SOL İŞLEM SIDEBAR'I + SAĞ MODÜLER FORM GÖVDESİ (SPLITTER)
        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cbd5e1;
                width: 6px;
                margin: 4px 2px;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background-color: #2563eb;
            }
        """)

        # 👈 SOL İŞLEM SIDEBAR'I
        left_panel = QWidget()
        left_vlyt = QVBoxLayout(left_panel)
        left_vlyt.setContentsMargins(0, 0, 0, 0)
        left_vlyt.setSpacing(8)

        self.crud_widget = CrudActionsWidget(title="EVRAK İŞLEMLERİ", enable_bulk=False, parent=self)
        self.export_widget = ExportActionsWidget(title="YAZDIR & AKTAR", parent=self)

        left_vlyt.addWidget(self.crud_widget)
        left_vlyt.addWidget(self.export_widget)
        left_vlyt.addStretch()

        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(320)
        body_splitter.addWidget(left_panel)

        # 👉 SAĞ MODÜLER FORM ALANI
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_content = QWidget()
        form_lyt = QVBoxLayout(right_content)
        form_lyt.setContentsMargins(4, 0, 4, 4)
        form_lyt.setSpacing(8)

        # 1. BÖLÜM: CARİ KÜNYESİ + BELGE VADE BİLGİLERİ (YAN YANA / GRID)
        header_grid = QHBoxLayout()
        header_grid.setSpacing(8)

        self.cari_widget = CariHesapKunyesiWidget(parent=self)
        self.belge_vade_widget = BelgeVadeDetaylariWidget(parent=self)
        
        header_grid.addWidget(self.cari_widget, 3)
        header_grid.addWidget(self.belge_vade_widget, 2)
        form_lyt.addLayout(header_grid)

        # 2. BÖLÜM: HAREKET AYARLARI (DEPO, FİYAT LİSTESİ)
        self.hareket_ayarlari_widget = HareketAyarlariWidget(parent=self)
        form_lyt.addWidget(self.hareket_ayarlari_widget)

        # 3. BÖLÜM: HAREKET KALEMLERİ CANLI APPGRIID SATIR TABLOSU
        self.grid_lines_widget = HareketKalemleriDbGridWidget(parent=self)
        form_lyt.addWidget(self.grid_lines_widget, 1)

        # 4. BÖLÜM: FİNANS VE GENEL TOPLAMLAR KARTI
        self.finans_widget = FinansWidget(parent=self)
        form_lyt.addWidget(self.finans_widget)

        right_scroll.setWidget(right_content)
        body_splitter.addWidget(right_scroll)

        body_splitter.setSizes([230, 950])
        main_lyt.addWidget(body_splitter, 1)

    def _wire_signals(self):
        """Tüm atomik bileşenler arasındaki canlı veri akışını bağlar."""
        # Satırlar değiştiğinde finans toplamlarını canlı güncelle
        self.grid_lines_widget.totals_changed.connect(self._on_totals_updated)
        
        # CRUD Buton Sinyalleri
        self.crud_widget.new_requested.connect(self.grid_lines_widget.add_empty_row)
        self.crud_widget.delete_requested.connect(self.grid_lines_widget.delete_selected_row)
        self.crud_widget.refresh_requested.connect(self._recalculate_all)
        
        # Cari Rehberi
        self.cari_widget.cari_browse_requested.connect(self._on_cari_browse)

        # Başlangıçta 2 örnek satır ekle
        self.grid_lines_widget.add_empty_row()
        self.grid_lines_widget.add_empty_row()

    def _on_totals_updated(self, subtotal: float, discount: float, vat: float, grand_total: float):
        currency = self.belge_vade_widget.cmb_currency.currentText().split("(")[-1].replace(")", "")
        self.finans_widget.update_totals(subtotal, discount, vat, grand_total, currency=currency)

    def _recalculate_all(self):
        self.grid_lines_widget._recalculate_totals()

    def _on_cari_browse(self):
        # Örnek cari rehberi seçimi
        sample_cari = {
            "code": "CARI-00124",
            "name": "ANADOLU ENDÜSTRİ VE LOJİSTİK A.Ş.",
            "tax_office": "Büyük Mükellefler V.D.",
            "tax_no": "1234567890",
            "balance": -45200.00
        }
        self.cari_widget.set_cari_data(sample_cari)
        QMessageBox.information(self, "Cari Seçildi", f"'{sample_cari['name']}' bilgileri forma aktarıldı.")
