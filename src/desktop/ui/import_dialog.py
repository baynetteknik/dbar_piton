import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.core.importer import (
    CUSTOMER_FIELDS,
    PRODUCT_FIELDS,
    find_best_match,
    generate_template_file,
    import_excel_data,
    read_excel_or_ods,
)
from src.core.models import Site


class ExcelImportDialog(QDialog):
    """Excel/ODS dosyalarından Cari Kart ve Ürün bilgilerini akıllı eşleştirme ile içeri aktaran ortak Dialog penceresi."""

    def __init__(self, db_session, entity_type="customer", parent=None):
        super().__init__(parent)
        self.db = db_session
        self.entity_type = entity_type  # "customer" veya "product"
        self.fields_dict = CUSTOMER_FIELDS if entity_type == "customer" else PRODUCT_FIELDS
        
        title_prefix = "Excel'den Cari" if entity_type == "customer" else "Excel'den Ürün"
        self.setWindowTitle(f"{title_prefix} Aktarımı")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        self.excel_headers = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # ==========================================
        # ÜST BAŞLIK ALANI
        # ==========================================
        title_lbl = QLabel("Excel'den Cari Aktarımı" if self.entity_type == "customer" else "Excel'den Ürün Aktarımı")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #1e293b; font-family: 'Segoe UI';")
        
        # Sağ üst kapat butonu
        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        btn_close.clicked.connect(self.reject)
        
        top_hbox = QHBoxLayout()
        top_hbox.addWidget(title_lbl)
        top_hbox.addStretch()
        top_hbox.addWidget(btn_close)
        main_layout.addLayout(top_hbox)

        # ==========================================
        # DOSYA YOLU VE ŞABLON BUTONLARI
        # ==========================================
        file_layout = QHBoxLayout()
        file_layout.setSpacing(10)
        
        path_lbl = QLabel("Excel Dosyası Yolu:")
        path_lbl.setStyleSheet("font-weight: 600; color: #475569;")
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Lütfen bir Excel (.xlsx, .xls) veya OpenOffice (.ods) dosyası seçin...")
        self.path_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 10px;
                background-color: white;
                color: #0f172a;
            }
        """)
        self.path_input.textChanged.connect(self.load_excel_headers)
        
        btn_browse = QPushButton("Gözat...")
        btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_browse.clicked.connect(self.browse_file)
        
        btn_template = QPushButton("Şablon İndir")
        btn_template.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        btn_template.clicked.connect(self.download_template)
        
        file_layout.addWidget(path_lbl)
        file_layout.addWidget(self.path_input)
        file_layout.addWidget(btn_browse)
        file_layout.addWidget(btn_template)
        main_layout.addLayout(file_layout)

        # ==========================================
        # YARDIMCI FİLTRELER VE SİTE SEÇİMİ
        # ==========================================
        options_layout = QHBoxLayout()
        options_layout.setSpacing(20)
        
        self.chk_headers = QCheckBox("İlk satır başlıkları içerir")
        self.chk_headers.setChecked(True)
        self.chk_headers.stateChanged.connect(self.load_excel_headers)
        self.chk_headers.setStyleSheet("font-weight: 600; color: #475569;")
        
        sheet_lbl = QLabel("Bilgilerin alınacağı çalışma sayfası:")
        sheet_lbl.setStyleSheet("font-weight: 600; color: #475569;")
        self.spin_sheet = QSpinBox()
        self.spin_sheet.setMinimum(1)
        self.spin_sheet.setValue(1)
        self.spin_sheet.valueChanged.connect(self.load_excel_headers)
        
        options_layout.addWidget(self.chk_headers)
        options_layout.addWidget(sheet_lbl)
        options_layout.addWidget(self.spin_sheet)
        
        # Hedef senkronizasyon sitesi / bağlantı seçimi
        site_lbl = QLabel("Hedef Senkronizasyon Sitesi:")
        site_lbl.setStyleSheet("font-weight: 600; color: #475569; margin-left: 20px;")
        self.combo_sites = QComboBox()
        self.combo_sites.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
            }
        """)
        self.load_active_sites()
        options_layout.addWidget(site_lbl)
        options_layout.addWidget(self.combo_sites)
            
        options_layout.addStretch()
        main_layout.addLayout(options_layout)

        # ==========================================
        # MEVCUT / YENİ ÇAKIŞMA STRATEJİLERİ
        # ==========================================
        conflict_layout = QHBoxLayout()
        conflict_layout.setSpacing(20)
        
        # Cari/Ürün Mevcutsa Grubu
        group_exist_title = "Cari Mevcutsa" if self.entity_type == "customer" else "Ürün Mevcutsa"
        group_exist = QGroupBox(group_exist_title)
        group_exist.setStyleSheet("QGroupBox { font-weight: bold; color: #1e293b; }")
        exist_lyt = QVBoxLayout(group_exist)
        self.rad_exist_update = QRadioButton("Bilgileri güncelle")
        self.rad_exist_update.setChecked(True)
        self.rad_exist_skip = QRadioButton("Hiçbir değişiklik yapma")
        exist_lyt.addWidget(self.rad_exist_update)
        exist_lyt.addWidget(self.rad_exist_skip)
        
        # Cari/Ürün Mevcut Değilse Grubu
        group_not_exist_title = "Cari Mevcut Değilse" if self.entity_type == "customer" else "Ürün Mevcut Değilse"
        group_not_exist = QGroupBox(group_not_exist_title)
        group_not_exist.setStyleSheet("QGroupBox { font-weight: bold; color: #1e293b; }")
        not_exist_lyt = QVBoxLayout(group_not_exist)
        rad_not_exist_insert_text = "Yeni cari olarak ekle" if self.entity_type == "customer" else "Yeni ürün olarak ekle"
        self.rad_not_exist_insert = QRadioButton(rad_not_exist_insert_text)
        self.rad_not_exist_insert.setChecked(True)
        self.rad_not_exist_skip = QRadioButton("Hiçbir işlem yapma")
        not_exist_lyt.addWidget(self.rad_not_exist_insert)
        not_exist_lyt.addWidget(self.rad_not_exist_skip)
        
        conflict_layout.addWidget(group_exist)
        conflict_layout.addWidget(group_not_exist)
        main_layout.addLayout(conflict_layout)

        # ==========================================
        # EŞLEŞTİRME TABLOSU
        # ==========================================
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Aktar", "Alan Adı", "Excel Sütunu", "Açıklama"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                background-color: white;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                font-weight: bold;
                color: #475569;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 6px;
            }
        """)
        
        self.populate_mapping_table()
        main_layout.addWidget(self.table)

        # ==========================================
        # ALT AKSİYON BUTONLARI
        # ==========================================
        btn_lyt = QHBoxLayout()
        
        btn_import = QPushButton("Bilgileri Aktar")
        btn_import.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_import.clicked.connect(self.start_import)
        
        btn_lyt.addStretch()
        btn_lyt.addWidget(btn_import)
        btn_lyt.addStretch()
        main_layout.addLayout(btn_lyt)

    def load_active_sites(self):
        """Aktif senkronizasyon sitelerini veritabanından combo box'a yükler."""
        self.combo_sites.clear()
        self.combo_sites.addItem("🖥️ Yerel Veritabanı (Senkronizasyon Yok)", None)
        try:
            sites = self.db.query(Site).filter(Site.is_active == True, Site.is_deleted == False).all()
            for site in sites:
                self.combo_sites.addItem(f"{site.name} ({site.cms_type.upper()})", site.id)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Aktif siteler yüklenemedi: {e}")

    def browse_file(self):
        """Excel veya ODS dökümanı seçmek için dosya penceresini açar."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Excel/ODS Dosyası Seç", "",
            "Excel / OpenOffice Tabloları (*.xlsx *.xls *.ods)",
        )
        if file_path:
            self.path_input.setText(file_path)

    def download_template(self):
        """Boş bir şablon indirmek için dosya kaydetme penceresi açar ve şablonu üretir."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Şablon Dosyasını Kaydet", "sablon.xlsx",
            "Excel Dosyası (*.xlsx)",
        )
        if file_path:
            try:
                generate_template_file(file_path, self.fields_dict)
                QMessageBox.information(self, "Başarılı", "Örnek şablon başarıyla oluşturuldu.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Şablon oluşturulamadı: {e}")

    def populate_mapping_table(self):
        """Hedef alanları tabloya listeler."""
        self.table.setRowCount(len(self.fields_dict))
        
        for row_idx, (field_name, info) in enumerate(self.fields_dict.items()):
            # 0. Aktar (Checkbox veya X)
            # Varsayılan olarak X (kırmızı renkte) koyalım.
            status_item = QTableWidgetItem("❌")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setFlags(status_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 0, status_item)
            
            # 1. Alan Adı (display name)
            name_item = QTableWidgetItem(info["display"])
            name_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            name_item.setFlags(name_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 1, name_item)
            
            # 2. Excel Sütunu (Combo Box)
            combo = QComboBox()
            combo.addItem("-- Seçilmedi --", None)
            combo.setProperty("field_name", field_name)
            combo.setProperty("row_index", row_idx)
            combo.currentIndexChanged.connect(self.combo_index_changed)
            self.table.setCellWidget(row_idx, 2, combo)
            
            # 3. Açıklama
            desc_item = QTableWidgetItem("Eşleşme bekleniyor...")
            desc_item.setFlags(desc_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 3, desc_item)

    def load_excel_headers(self):
        """Excel dosyasını okuyarak başlıkları çıkartır ve tablodaki combobox'ları doldurur."""
        file_path = self.path_input.text().strip()
        if not file_path or not os.path.exists(file_path):
            return
            
        try:
            columns_info, _ = read_excel_or_ods(file_path, self.spin_sheet.value(), self.chk_headers.isChecked())
            
            # Tablodaki her combobox'ı güncelle
            for row_idx in range(self.table.rowCount()):
                combo = self.table.cellWidget(row_idx, 2)
                if isinstance(combo, QComboBox):
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItem("-- Seçilmedi --", None)
                    for col in columns_info:
                        combo.addItem(col["display"], col["letter"])
                        
                    field_name = combo.property("field_name")
                    
                    matched_letter = None
                    for col in columns_info:
                        if col["header"]:
                            best_match = find_best_match(col["header"], {field_name: self.fields_dict[field_name]})
                            if best_match == field_name:
                                matched_letter = col["letter"]
                                break
                                
                    if matched_letter:
                        index_to_set = combo.findData(matched_letter)
                        if index_to_set >= 0:
                            combo.setCurrentIndex(index_to_set)
                        combo.blockSignals(False)
                        self.update_row_status(row_idx, matched_letter)
                    else:
                        combo.setCurrentIndex(0)
                        combo.blockSignals(False)
                        self.update_row_status(row_idx, None)
                        
        except Exception as e:
            QMessageBox.warning(self, "Dosya Okuma Hatası", f"Excel başlıkları okunamadı:\n{e}")

    def combo_index_changed(self, index):
        """Kullanıcı combobox'tan sütun seçtiğinde satır durumunu günceller."""
        combo = self.sender()
        if isinstance(combo, QComboBox):
            row_idx = combo.property("row_index")
            selected_header = combo.currentData()
            self.update_row_status(row_idx, selected_header)

    def update_row_status(self, row_idx, selected_header):
        """Satırdaki eşleşme durumuna göre Aktar (Evet/X) ve Açıklama hücrelerini günceller."""
        status_item = self.table.item(row_idx, 0)
        desc_item = self.table.item(row_idx, 3)
        
        if selected_header:
            status_item.setText("✅ Evet")
            status_item.setForeground(QColor("#10B981"))
            desc_item.setText(f"Excel'deki '{selected_header}' sütunu ile eşleştirildi.")
        else:
            status_item.setText("❌")
            status_item.setForeground(QColor("#EF4444"))
            desc_item.setText("Eşleşmedi. Bu alan içeri aktarılmayacak.")

    def start_import(self):
        """Aktarımı başlatan ana fonksiyon."""
        file_path = self.path_input.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Hata", "Lütfen geçerli bir Excel/ODS dosyası seçin.")
            return
            
        # UI'dan eşleşme bilgilerini (mapping) topla
        mapping = {}
        for row_idx in range(self.table.rowCount()):
            combo = self.table.cellWidget(row_idx, 2)
            if isinstance(combo, QComboBox):
                field_name = combo.property("field_name")
                selected_header = combo.currentData()
                if selected_header:
                    mapping[field_name] = selected_header
                    
        if not mapping:
            QMessageBox.warning(self, "Hata", "En az bir sütunu eşleştirmeniz gerekmektedir.")
            return
            
        # Stratejiler
        conflict_exist = "update" if self.rad_exist_update.isChecked() else "skip"
        conflict_not_exist = "insert" if self.rad_not_exist_insert.isChecked() else "skip"
        
        # Site ID (seçildiyse)
        site_id = self.combo_sites.currentData()
                
        # Aktarımı çalıştır
        try:
            added, updated, skipped = import_excel_data(
                file_path=file_path,
                fields_dict=self.fields_dict,
                field_mapping=mapping,
                db=self.db,
                entity_type=self.entity_type,
                conflict_exist=conflict_exist,
                conflict_not_exist=conflict_not_exist,
                site_id=site_id,
                sheet_index=self.spin_sheet.value(),
                has_headers=self.chk_headers.isChecked(),
            )
            
            # Sonuç dökümü
            msg = f"Aktarım Başarıyla Tamamlandı!\n\n" \
                  f"➕ Eklenen: {added}\n" \
                  f"🔄 Güncellenen: {updated}\n" \
                  f"⏭️ Atlanan: {skipped}\n\n" \
                  f"Not: Eklenen/güncellenen tüm kayıtlar otomatik olarak Dolibarr'a senkronize edilmek üzere arka plana kuyruklandı."
                  
            QMessageBox.information(self, "Başarılı", msg)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Aktarım Hatası", f"Aktarım esnasında bir hata oluştu:\n{e}")
