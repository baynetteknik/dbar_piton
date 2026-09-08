# YZ 2 — Görev 22: Kritik Düzeltmeler (Devam)

> **Dosyalar:** `transaction_document_dialog.py`, `hareket_finans_widget.py`  
> **Kural:** Sadece belirtilen metodları değiştir.

---

## 22.1 — F6/F7 Kısayolları (eventFilter ile)

Mevcut QShortcut çalışmıyor çünkü iç widget'lar focus alıyor.
Çözüm: Dialog seviyesinde `keyPressEvent` override et.

### transaction_document_dialog.py içine ekle:

```python
def keyPressEvent(self, event):
    """Dialog seviyesinde kısayol yakalama."""
    from PyQt6.QtCore import Qt
    key = event.key()

    if key == Qt.Key.Key_F6:
        self.toggle_bottom_panel()
        event.accept()
        return
    elif key == Qt.Key.Key_F7:
        self.toggle_info_panel()
        event.accept()
        return
    elif key == Qt.Key.Key_F5:
        self.calculate_totals()
        event.accept()
        return
    elif key == Qt.Key.Key_F2:
        self.save_document()
        event.accept()
        return
    elif key == Qt.Key.Key_F9:
        self.save_and_print_document()
        event.accept()
        return
    elif key == Qt.Key.Key_Escape:
        self.reject()
        event.accept()
        return

    super().keyPressEvent(event)
```

---

## 22.2 — HareketFinansWidget Yükseklikler

### hareket_finans_widget.py içinde _init_ui metodunda
Her widget oluşturulduktan hemen sonra `setFixedHeight(self.FIELD_H)` ekle:

```python
# Mevcut FIELD_H = 24

# Döviz satırı:
self.cmb_doviz.setFixedHeight(self.FIELD_H)
self.txt_kur.setFixedHeight(self.FIELD_H)
self.cmb_kdv.setFixedHeight(self.FIELD_H)

# Şekil/Kasa satırı:
self.cmb_sekil.setFixedHeight(self.FIELD_H)
self.cmb_kasa.setFixedHeight(self.FIELD_H)

# Tüm widget'lar için max height de ayarla:
self.cmb_doviz.setMaximumHeight(self.FIELD_H)
self.cmb_kdv.setMaximumHeight(self.FIELD_H)
self.cmb_sekil.setMaximumHeight(self.FIELD_H)
self.cmb_kasa.setMaximumHeight(self.FIELD_H)
```

---

## 22.3 — Boş Fiş Uyarısı

### transaction_document_dialog.py içinde save_document başına ekle:

```python
def save_document(self):
    # Boş fiş kontrolü
    cari_bos = not self.cari_widget.txt_cari_kodu.text().strip() \
               and not self.cari_widget.txt_cari_unvan.text().strip()
    kalem_bos = len(self.hareket_kalemleri.get_all_rows()) == 0

    if cari_bos and kalem_bos:
        reply = QMessageBox.question(
            self,
            "Boş Fiş",
            "Cari ve kalem bilgisi girilmemiş.\n"
            "Fiş boş olarak kaydedilecek. Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
    elif cari_bos:
        reply = QMessageBox.question(
            self,
            "Cari Seçilmedi",
            "Cari hesap seçilmedi.\n"
            "Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

    # ... mevcut kayıt kodu devam eder
```

---

## 22.4 — Sağ Üstteki Fazla Kutu Kaldır

Üst panelde KDV Hariç'in üstünde fazladan bir collapse butonu var.
Bu `HareketFinansWidget` içinde yanlışlıkla eklenen bir buton.

### hareket_finans_widget.py içinde _init_ui'de:

```python
# Eğer başlık satırında collapse butonu varsa KALDIR:
# Şu satırları sil (varsa):
# self.btn_collapse = QPushButton("∧")
# hdr_row.addWidget(self.btn_collapse)

# HareketFinansWidget'ın kendi collapse butonu OLMAMALI
# Collapse işlemi transaction_document_dialog tarafından yönetilir
```

### Kontrol et:
`hareket_finans_widget.py` içinde `btn_collapse` veya `toggle_collapse`
kelimesi geçiyorsa o bloğu tamamen sil.

---

## Test

```
1. Teklif detay aç
   → F6 → Alt panel kapandı mı?
   → F6 tekrar → açıldı mı?
   → F7 → Üst panel kapandı mı?
   → F7 tekrar → açıldı mı?

2. HareketFinansWidget
   → Döviz/KDV/Şekil/Kasa dropdown'lar 24px mi?
   → Sağ üstte fazla kutu yok mu?

3. Boş fiş kaydet
   → "Fiş boş olarak kaydedilecek" uyarısı çıkıyor mu?
   → Hayır → kayıt iptal mi?

4. Sadece cari seç, kalem yok
   → Uyarı çıkmıyor (kalem var sayılır)
   
5. Cari yok, kalem var
   → "Cari seçilmedi" uyarısı çıkıyor mu?
```

---

## Özet

| # | Sorun | Çözüm |
|---|-------|-------|
| 22.1 | F6/F7 çalışmıyor | keyPressEvent override |
| 22.2 | Dropdown yükseklikler | setFixedHeight + setMaximumHeight |
| 22.3 | Boş fiş uyarısı | save_document başına kontrol |
| 22.4 | Fazla collapse butonu | hareket_finans_widget'tan sil |
