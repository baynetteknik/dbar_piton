# YZ 2 — Görev 15: Raporlama Motoru Entegrasyonu

> **Değiştirilecek Dosya:** `src/desktop/ui/dialogs/transaction_document_dialog.py`  
> **Yeni Klasör:** `src/desktop/reports/` (hazır — sadece kopyala)  
> **Kural:** Sadece belirtilen değişiklikleri yap.

---

## Adım 1 — Dosyaları Kopyala

Şu dosyaları `src/desktop/reports/` klasörüne kopyala:

```
src/desktop/reports/
├── __init__.py
├── report_engine.py
├── excel_engine.py
├── email_engine.py
├── share_engine.py
├── teklif_report_service.py
└── templates/
    └── teklif/
        └── teklif_print.html
```

---

## Adım 2 — Eksik Kütüphaneleri Kur

```bash
.venv\Scripts\pip install jinja2
```

WeasyPrint zaten kurulu. jinja2 yoksa kur.

---

## Adım 3 — transaction_document_dialog.py Değişiklikleri

### 3.1 Import Ekle (En üste, diğer importların yanına)

```python
# Raporlama motoru
from src.desktop.reports.teklif_report_service import TeklifReportService
```

### 3.2 Constructor'a Ekle (__init__ içinde, en sona)

```python
# Raporlama servisi — lazy init (ilk kullanımda oluşturulur)
self._report_service: TeklifReportService | None = None
```

### 3.3 Yardımcı Metot Ekle

```python
def _get_report_service(self) -> TeklifReportService:
    """Raporlama servisini lazy init ile döndür."""
    if not self._report_service:
        self._report_service = TeklifReportService(
            db_session=self.db,
            company_id=self.company_id,
        )
    return self._report_service

def _get_current_teklif_data(self) -> dict:
    """
    Ekrandaki mevcut veriyi raporlama için dict olarak hazırla.
    DB'ye kaydetmeden önce de çalışır — ekran verisi kullanılır.
    """
    # Firma bilgisi
    firma = {
        "adi":   "BAYNET BİLİŞİM TEKNOLOJİLERİ",
        "adres": "Ankara",
        "tel":   "",
        "email": "",
        "web":   "",
        "logo_base64": "",
    }

    # Müşteri
    musteri = {
        "adi":         self.txt_cari_unvan.text().strip(),
        "vergi_daire": self.txt_vergi_daire.text().strip(),
        "vergi_no":    self.txt_vergi_no.text().strip(),
        "adres":       self.txt_sevk_adres.text().strip(),
        "tel":         "",
        "email":       "",
    }

    # Belge
    belge = {
        "teklif_no":   self.txt_top_doc_no.text().strip(),
        "tarih":       self.date_belge.date().toString("yyyy-MM-dd"),
        "vade":        self.date_vade.date().toString("yyyy-MM-dd"),
        "para_birimi": self.cmb_doviz.currentText(),
        "durum":       "Açık",
        "odeme_plani": self.cmb_odeme_plani.currentText()
                       if hasattr(self, "cmb_odeme_plani") else "",
        "aciklama":    "",
    }

    # Kalemler tablosundan oku
    kalemler = []
    for r in range(self.table_items.rowCount()):
        row_data = self.get_row_data(r)
        if not row_data.get("name"):
            continue
        kalemler.append({
            "kod":         row_data.get("code", ""),
            "aciklama":    row_data.get("name", ""),
            "not2":        row_data.get("note2", ""),
            "miktar":      float(row_data.get("qty", 1)),
            "birim":       row_data.get("unit", "Adet"),
            "birim_fiyat": float(row_data.get("price", 0)),
            "iskonto":     float(row_data.get("disc1", 0)),
            "kdv":         int(row_data.get("vat", 20)),
            "tutar":       self._calc_line_total(row_data),
        })

    # Toplamlar — mevcut label değerlerinden oku
    def parse_currency(lbl) -> float:
        try:
            txt = lbl.text().replace("₺","").replace("$","").replace("€","")
            txt = txt.replace(".","").replace(",",".").replace("+","").replace("-","").strip()
            return float(txt)
        except Exception:
            return 0.0

    toplamlar = {
        "ara_toplam":   parse_currency(self.lbl_subtotal),
        "iskonto":      parse_currency(self.lbl_discount),
        "masraflar":    parse_currency(self.lbl_expense_total),
        "kdv_matrahi":  parse_currency(self.lbl_subtotal),
        "kdv_toplam":   parse_currency(self.lbl_vat_total),
        "genel_toplam": parse_currency(self.lbl_grand_total),
    }

    return {
        "firma":     firma,
        "musteri":   musteri,
        "belge":     belge,
        "kalemler":  kalemler,
        "toplamlar": toplamlar,
        "notlar":    self.doc_note1 + "\n" + self.doc_note2,
    }

def _calc_line_total(self, row_data: dict) -> float:
    """Tek satır tutarını hesapla."""
    try:
        qty   = float(row_data.get("qty", 1) or 1)
        price = float(row_data.get("price", 0) or 0)
        d1    = float(row_data.get("disc1", 0) or 0)
        d2    = float(row_data.get("disc2", 0) or 0)
        d3    = float(row_data.get("disc3", 0) or 0)
        vat   = float(row_data.get("vat", 20) or 20)
        base  = qty * price
        after_d = base * (1 - d1/100) * (1 - d2/100) * (1 - d3/100)
        return round(after_d * (1 + vat/100), 2)
    except Exception:
        return 0.0
```

### 3.4 save_and_print_document Metodunu Güncelle

```python
def save_and_print_document(self):
    """Kaydet ve PDF olarak yazdır."""
    from PyQt6.QtWidgets import QProgressDialog
    from PyQt6.QtCore import Qt

    # İlerleme göstergesi
    progress = QProgressDialog("PDF hazırlanıyor...", None, 0, 0, self)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setWindowTitle("Yazdırılıyor")
    progress.show()

    try:
        data = self._get_current_teklif_data()
        service = self._get_report_service()

        # Direkt veri ile PDF üret (DB'ye kayıt gerekmez)
        pdf_bytes = service.pdf_engine.render_pdf(
            "teklif/teklif_print.html", data
        )
        service.pdf_engine.open_pdf(pdf_bytes)

        progress.close()
        self.toast_requested.emit("PDF açıldı.", "success") \
            if hasattr(self, "toast_requested") else None

    except Exception as e:
        progress.close()
        QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı:\n{e}")
```

### 3.5 Excel Butonu İçin Metot Ekle

```python
def export_to_excel(self):
    """Mevcut teklifi Excel olarak dışa aktar."""
    from PyQt6.QtWidgets import QFileDialog

    path, _ = QFileDialog.getSaveFileName(
        self,
        "Excel Kaydet",
        f"{self.txt_top_doc_no.text().replace('/', '-')}.xlsx",
        "Excel Dosyası (*.xlsx)"
    )
    if not path:
        return

    try:
        data    = self._get_current_teklif_data()
        service = self._get_report_service()
        wb      = service.excel_engine.render_teklif(data)
        service.excel_engine.save(wb, path)

        import os
        os.startfile(path)  # Windows'ta Excel ile aç

        self.toast_requested.emit("Excel dışa aktarıldı.", "success") \
            if hasattr(self, "toast_requested") else None

    except Exception as e:
        QMessageBox.critical(self, "Hata", f"Excel oluşturulamadı:\n{e}")
```

### 3.6 Paylaşım Dialog Metodu Ekle

```python
def open_share_dialog(self):
    """
    Teklif paylaşım dialogunu aç.
    Dolibarr'daki Teklif Gönderme Paneli'nin masaüstü versiyonu.
    """
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QFrame
    )
    from PyQt6.QtCore import Qt

    data = self._get_current_teklif_data()
    teklif_no   = data["belge"]["teklif_no"]
    musteri_adi = data["musteri"]["adi"]
    musteri_email = data["musteri"].get("email", "")

    dlg = QDialog(self)
    dlg.setWindowTitle(f"📤 Teklif Paylaş — {teklif_no}")
    dlg.setMinimumWidth(480)
    dlg.setStyleSheet("font-family:'Segoe UI'; background:white;")

    lyt = QVBoxLayout(dlg)
    lyt.setContentsMargins(20, 20, 20, 20)
    lyt.setSpacing(12)

    # Başlık
    lbl_title = QLabel(f"📄 {teklif_no} — {musteri_adi}")
    lbl_title.setStyleSheet(
        "font-size:13px; font-weight:700; color:#1e3a8a;"
    )
    lyt.addWidget(lbl_title)

    # E-posta alanı
    lbl_email = QLabel("E-posta Adresi:")
    lbl_email.setStyleSheet("font-weight:600; color:#475569; font-size:11px;")
    txt_email = QLineEdit(musteri_email)
    txt_email.setPlaceholderText("musteri@example.com")
    txt_email.setFixedHeight(28)
    lyt.addWidget(lbl_email)
    lyt.addWidget(txt_email)

    # Butonlar
    def make_btn(text, color, hover):
        b = QPushButton(text)
        b.setFixedHeight(36)
        b.setStyleSheet(f"""
            QPushButton {{
                background:{color}; color:white;
                border:none; border-radius:6px;
                font-size:12px; font-weight:600;
            }}
            QPushButton:hover {{ background:{hover}; }}
        """)
        return b

    btn_send = make_btn("📧 E-posta Gönder", "#2563eb", "#1d4ed8")
    btn_pdf  = make_btn("🖨️ PDF İndir / Yazdır", "#475569", "#334155")
    btn_copy = make_btn("🔗 Linki Kopyala", "#7c3aed", "#6d28d9")
    btn_wa   = make_btn("💬 WhatsApp ile Gönder", "#16a34a", "#15803d")
    btn_xls  = make_btn("📊 Excel İndir", "#0284c7", "#0369a1")
    btn_close= make_btn("✖ Kapat", "#64748b", "#475569")

    def send_email():
        email = txt_email.text().strip()
        if not email:
            QMessageBox.warning(dlg, "Uyarı", "E-posta adresi girin.")
            return
        try:
            pdf_bytes = self._get_report_service().pdf_engine.render_pdf(
                "teklif/teklif_print.html", data
            )
            ok, msg = self._get_report_service().email_engine.send_teklif_email(
                to_email=email,
                teklif_data=data,
                pdf_bytes=pdf_bytes,
            )
            if ok:
                QMessageBox.information(dlg, "Başarılı", msg)
            else:
                QMessageBox.critical(dlg, "Hata", msg)
        except Exception as e:
            QMessageBox.critical(dlg, "Hata", str(e))

    def copy_link():
        fake_token = f"DEMO-{teklif_no.replace('/', '-')}"
        url = f"https://baynetbilisim.tr/teklif/view?token={fake_token}"
        self._get_report_service().share_engine.copy_to_clipboard(url)
        QMessageBox.information(dlg, "Kopyalandı", f"Link panoya kopyalandı:\n{url}")

    def share_wa():
        dlg.accept()
        self._get_report_service().share_engine.share_whatsapp(
            url=f"https://baynetbilisim.tr/teklif/view?token=DEMO",
            musteri_adi=musteri_adi,
            teklif_no=teklif_no,
            firma_adi=data["firma"]["adi"],
        )

    btn_send.clicked.connect(send_email)
    btn_pdf.clicked.connect(lambda: (self.save_and_print_document(), dlg.accept()))
    btn_copy.clicked.connect(copy_link)
    btn_wa.clicked.connect(share_wa)
    btn_xls.clicked.connect(lambda: (self.export_to_excel(), dlg.accept()))
    btn_close.clicked.connect(dlg.reject)

    for btn in [btn_send, btn_pdf, btn_copy, btn_wa, btn_xls]:
        lyt.addWidget(btn)

    # Ayırıcı
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color:#e2e8f0;")
    lyt.addWidget(line)
    lyt.addWidget(btn_close)

    dlg.exec()
```

### 3.7 Sol Sidebar'a Paylaşım Butonu Ekle

`sec_actions` içine ekle (btn_cancel'dan önce):

```python
# Paylaşım butonu
self.btn_share = QPushButton("📤 Gönder / Paylaş")
self.btn_share.setStyleSheet(self.sidebar_btn_style("#7c3aed", "#ffffff"))
self.btn_share.clicked.connect(self.open_share_dialog)
self.sec_actions.add_widget(self.btn_share)
```

### 3.8 Alt Bar'a Excel Butonu Ekle

`bar_lyt` içinde `btn_bottom_save_print`'ten önce:

```python
self.btn_bottom_excel = QPushButton("📊 Excel")
self.btn_bottom_excel.setFixedHeight(28)
self.btn_bottom_excel.setStyleSheet("""
    QPushButton {
        background-color: #0284c7; color: white;
        font-weight:700; font-size:11px;
        border:1px solid #0369a1; border-radius:4px;
        padding:5px 10px; min-height:26px;
    }
    QPushButton:hover { background-color:#0369a1; }
""")
self.btn_bottom_excel.clicked.connect(self.export_to_excel)
bar_lyt.addWidget(self.btn_bottom_excel)
```

---

## Test Senaryosu

```
1. Teklif detay ekranını aç
   → Sol sidebar'da "📤 Gönder / Paylaş" butonu var mı?
   → Alt bar'da "📊 Excel" butonu var mı?

2. "Kaydet & Yazdır (F9)" butonuna bas
   → PDF açılıyor mu?
   → Teklif numarası, müşteri bilgileri, kalemler doğru mu?

3. "📊 Excel" butonuna bas
   → Kayıt yeri sor → Excel açılıyor mu?
   → Kalemler ve toplamlar doğru mu?

4. "📤 Gönder / Paylaş" butonuna bas
   → Dialog açılıyor mu?
   → "🔗 Linki Kopyala" → panoya kopyalandı mesajı geliyor mu?
   → "💬 WhatsApp" → tarayıcıda WhatsApp açılıyor mu?

5. E-posta gönder (SMTP ayarı yapılmışsa)
   → E-posta gidiyor mu? PDF eki var mı?
```

---

## Özet

| Adım | Değişiklik |
|------|-----------|
| 1 | `src/desktop/reports/` klasörünü kopyala |
| 2 | `jinja2` kur |
| 3.1 | Import ekle |
| 3.2-3.3 | Servis + veri hazırlama metodları |
| 3.4 | `save_and_print_document` → PDF motor ile |
| 3.5 | `export_to_excel` metodu |
| 3.6 | `open_share_dialog` — E-posta/Link/WhatsApp/Excel |
| 3.7 | Sol sidebar'a Gönder/Paylaş butonu |
| 3.8 | Alt bar'a Excel butonu |

> `transaction_document_dialog.py` dışında hiçbir dosyaya dokunma.
