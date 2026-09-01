# YZ 2 — Görev 20: Widget Entegrasyonu

> **Dosya:** `src/desktop/ui/dialogs/transaction_document_dialog.py`  
> **Kural:** Mevcut save/load/rapor metodlarını KORU. Sadece UI kısmını widget'larla değiştir.  
> **Widget Dosyaları:** `src/desktop/ui/widgets/` klasöründe hazır.

---

## Genel Yaklaşım

```
ESKİ: dialog içinde 500+ satır hardcoded QLineEdit/QComboBox
YENİ: 5 widget → dialog sadece bunları bir araya getirir

self.cari_widget   = CariKunyeWidget()
self.belge_widget  = BelgeVadeWidget()
self.finans_widget = HareketFinansWidget()
self.kalem_widget  = HareketKalemleriWidget()  ← zaten var
self.toplam_widget = ToplamWidget()
```

---

## Adım 1 — Import Ekle

```python
from src.desktop.ui.widgets.cari_kunye_widget import CariKunyeWidget
from src.desktop.ui.widgets.belge_vade_widget import BelgeVadeWidget
from src.desktop.ui.widgets.hareket_finans_widget import HareketFinansWidget
from src.desktop.ui.widgets.toplam_widget import ToplamWidget
```

---

## Adım 2 — create_info_panels metodunu yeniden yaz

Mevcut `create_info_panels` (veya üst bilgi paneli oluşturan metod) içindeki
hardcoded QLineEdit/QComboBox bloklarını sil, widget'larla değiştir:

```python
def create_info_panels(self) -> QWidget:
    """
    Üst bilgi paneli — 3 widget yan yana.
    Tek ∧ butonu ile hepsi birden kapanır/açılır.
    """
    container = QFrame()
    container.setStyleSheet(
        "QFrame { background:#f8fafc; border-bottom:1px solid #e2e8f0; }"
    )
    lyt = QVBoxLayout(container)
    lyt.setContentsMargins(4, 2, 4, 2)
    lyt.setSpacing(0)

    # ── Tek collapse butonu ──
    hdr_row = QHBoxLayout()
    hdr_row.setContentsMargins(0, 0, 0, 2)

    self.btn_collapse_info = QPushButton("∧")
    self.btn_collapse_info.setFixedSize(20, 20)
    self.btn_collapse_info.setStyleSheet("""
        QPushButton {
            background:#e2e8f0; border:none; border-radius:3px;
            font-size:10px; color:#64748b;
        }
        QPushButton:hover { background:#cbd5e1; }
    """)
    self.btn_collapse_info.setToolTip("Üst Paneli Kapat/Aç (F7)")
    self.btn_collapse_info.clicked.connect(self.toggle_info_panel)
    self._info_visible = True

    # F7 kısayolu
    from PyQt6.QtGui import QKeySequence, QShortcut
    sc_f7 = QShortcut(QKeySequence("F7"), self)
    sc_f7.activated.connect(self.toggle_info_panel)

    hdr_row.addStretch()
    hdr_row.addWidget(self.btn_collapse_info)
    lyt.addLayout(hdr_row)

    # ── 3 Widget yan yana ──
    self.info_panels_widget = QWidget()
    panels_lyt = QHBoxLayout(self.info_panels_widget)
    panels_lyt.setContentsMargins(0, 0, 0, 0)
    panels_lyt.setSpacing(4)

    # Cari Künye
    self.cari_widget = CariKunyeWidget(
        customers_catalog=self.customers_catalog,
        db_session=self.db,
        collapsible=False,
        parent=self,
    )
    self.cari_widget.customer_selected.connect(self._on_customer_selected)
    self.cari_widget.balance_requested.connect(self._show_balance)

    # Belge & Vade
    self.belge_widget = BelgeVadeWidget(
        db_session=self.db,
        parent=self,
    )
    self.belge_widget.vade_changed.connect(
        lambda d: None  # İleride kullanılabilir
    )

    # Hareket Finans
    self.finans_widget = HareketFinansWidget(
        db_session=self.db,
        parent=self,
    )
    self.finans_widget.doviz_changed.connect(self._on_doviz_changed)

    panels_lyt.addWidget(self.cari_widget, 3)
    panels_lyt.addWidget(self.belge_widget, 3)
    panels_lyt.addWidget(self.finans_widget, 2)

    lyt.addWidget(self.info_panels_widget)
    return container

def toggle_info_panel(self):
    """Üst paneli aç/kapat — 3 widget birden."""
    self._info_visible = not self._info_visible
    self.info_panels_widget.setVisible(self._info_visible)
    self.btn_collapse_info.setText(
        "∧" if self._info_visible else "∨ ÜST PANEL (F7)"
    )
```

---

## Adım 3 — ToplamWidget Entegrasyonu

Alt paneldeki hardcoded toplam label'larını `ToplamWidget` ile değiştir:

```python
def create_totals_panel(self) -> QWidget:
    """Toplamlar paneli — ToplamWidget kullanır."""
    self.toplam_widget = ToplamWidget(parent=self)
    return self.toplam_widget
```

---

## Adım 4 — Geriye Dönük Uyumluluk (ÖNEMLİ)

Mevcut kodlarda `self.txt_cari_kodu`, `self.date_belge` gibi
widget attribute'larına erişim var. Bunları property olarak tanımla:

```python
# __init__ içinde widget'lar oluşturulduktan sonra:

# CariKunyeWidget proxy'leri
@property
def txt_cari_kodu(self):
    return self.cari_widget.txt_cari_kodu

@property
def txt_cari_unvan(self):
    return self.cari_widget.txt_cari_unvan

@property
def txt_vergi_daire(self):
    return self.cari_widget.txt_vergi_daire

@property
def txt_vergi_no(self):
    return self.cari_widget.txt_vergi_no

@property
def txt_sevk_adres(self):
    return self.cari_widget.txt_sevk_adres

# BelgeVadeWidget proxy'leri
@property
def date_belge(self):
    return self.belge_widget.date_belge

@property
def date_vade(self):
    return self.belge_widget.date_vade

@property
def txt_saat(self):
    return self.belge_widget.txt_saat

@property
def cmb_odeme_plani(self):
    return self.belge_widget.cmb_odeme_plani

# HareketFinansWidget proxy'leri
@property
def cmb_doviz(self):
    return self.finans_widget.cmb_doviz

@property
def txt_doviz_kuru(self):
    return self.finans_widget.txt_kur

@property
def cmb_kdv_durumu(self):
    return self.finans_widget.cmb_kdv

@property
def cmb_fatura_sekli(self):
    return self.finans_widget.cmb_sekil

@property
def cmb_kasa(self):
    return self.finans_widget.cmb_kasa

@property
def chk_cari_islesin(self):
    return self.finans_widget.chk_cari

@property
def chk_stok_islesin(self):
    return self.finans_widget.chk_stok

# ToplamWidget proxy'leri
@property
def lbl_subtotal(self):
    return self.toplam_widget._lbl_values["ara_toplam"][0]

@property
def lbl_discount(self):
    return self.toplam_widget._lbl_values["iskonto"][0]

@property
def lbl_expense_total(self):
    return self.toplam_widget._lbl_values["masraflar"][0]

@property
def lbl_vat_total(self):
    return self.toplam_widget._lbl_values["kdv_toplam"][0]

@property
def lbl_grand_total(self):
    return self.toplam_widget.lbl_grand_total

@property
def lbl_grand_total_doviz(self):
    return self.toplam_widget.lbl_grand_total_doviz
```

---

## Adım 5 — Sinyal Bağlantıları

```python
def _on_customer_selected(self, customer: dict):
    """Cari seçilince vadeyi güncelle."""
    terms = customer.get("terms", 30)
    self.belge_widget.set_vade_from_terms(terms)

def _show_balance(self, cari_kodu: str):
    """Bakiye butonu — ileride cari bakiye dialog."""
    QMessageBox.information(
        self, "Bakiye",
        f"{cari_kodu} — Bakiye bilgisi yükleniyor..."
    )

def _on_doviz_changed(self, kod: str, kur: float):
    """Döviz değişince toplam widget'ı güncelle."""
    sembol = self.finans_widget.get_currency_symbol()
    self.toplam_widget.set_doviz(sembol, kur)
    self.calculate_totals()
```

---

## Adım 6 — calculate_totals Güncelle

```python
def calculate_totals(self):
    """Kalem toplamlarını hesapla ve ToplamWidget'a aktar."""
    try:
        ara_toplam   = 0.0
        iskonto      = 0.0
        kdv_toplam   = 0.0

        for r in range(self.table_items.rowCount()):
            d = self.hareket_kalemleri.get_row_data(r)
            if not d.get("name") and not d.get("code"):
                continue

            qty   = float(d.get("qty",   1) or 1)
            price = float(d.get("price", 0) or 0)
            d1    = float(d.get("disc1", 0) or 0)
            d2    = float(d.get("disc2", 0) or 0)
            d3    = float(d.get("disc3", 0) or 0)
            vat   = float(d.get("vat",  20) or 20)

            base   = qty * price
            after  = base * (1-d1/100) * (1-d2/100) * (1-d3/100)
            kdv_t  = after * vat / 100

            ara_toplam += base
            iskonto    += base - after
            kdv_toplam += kdv_t

        # İndirim & Masraflar tablosundan ek iskonto/masraf
        masraflar = 0.0
        for r in range(self.table_alt_iskonto.rowCount()):
            # Tür ve değeri oku
            tur_w = self.table_alt_iskonto.cellWidget(r, 0)
            val_w = self.table_alt_iskonto.cellWidget(r, 2)
            if tur_w and val_w:
                try:
                    tur = tur_w.currentText() if hasattr(tur_w, "currentText") else ""
                    val = float(val_w.text().replace(",", ".") or "0")
                    if "masraf" in tur.lower() or "nakliye" in tur.lower():
                        masraflar += val
                    elif "indirim" in tur.lower():
                        iskonto += val
                except Exception:
                    pass

        # ToplamWidget güncelle
        sembol = self.finans_widget.get_currency_symbol()
        kur    = self.finans_widget.get_exchange_rate()

        self.toplam_widget.update_totals(
            ara_toplam   = ara_toplam,
            iskonto      = iskonto,
            masraflar    = masraflar,
            kdv_toplam   = kdv_toplam,
            doviz_sembol = sembol,
            doviz_kur    = kur,
        )

        # Sağ panel özetini güncelle
        if hasattr(self, "_update_right_panel_summary"):
            self._update_right_panel_summary()

    except Exception as e:
        logger.error(f"calculate_totals hatası: {e}")
```

---

## Adım 7 — apply_customer_info Güncelle

```python
def apply_customer_info(self, customer: dict):
    """
    Cari bilgilerini CariKunyeWidget'a aktar.
    quotation_save_service load_to_dialog buradan çağırır.
    """
    if hasattr(self, "cari_widget"):
        self.cari_widget.apply_customer(customer)
    else:
        # Geriye dönük uyumluluk
        if hasattr(self, "txt_cari_kodu"):
            self.txt_cari_kodu.setText(customer.get("code", ""))
        if hasattr(self, "txt_cari_unvan"):
            self.txt_cari_unvan.setText(customer.get("name", ""))
```

---

## Adım 8 — _get_current_teklif_data Güncelle

```python
def _get_current_teklif_data(self) -> dict:
    """Widget'lardan veri topla."""

    # Firma
    firma = self._get_firma_data()

    # Cari — CariKunyeWidget'tan
    cari_data = self.cari_widget.get_data()
    musteri = {
        "adi":         cari_data.get("name", ""),
        "vergi_daire": cari_data.get("tax_office", ""),
        "vergi_no":    cari_data.get("tax_no", ""),
        "adres":       cari_data.get("address", ""),
        "tel":         "",
        "email":       "",
    }

    # Belge — BelgeVadeWidget'tan
    belge_data = self.belge_widget.get_data()
    belge = {
        "teklif_no":   belge_data.get("belge_no", ""),
        "tarih":       belge_data.get("tarih", ""),
        "vade":        belge_data.get("vade", ""),
        "para_birimi": self.finans_widget.get_data().get("doviz_kod", "TRY"),
        "durum":       "Açık",
        "odeme_plani": belge_data.get("odeme_plani", ""),
    }

    # Kalemler
    kalemler = []
    for row_data in self.hareket_kalemleri.get_all_rows():
        kalemler.append({
            "kod":         row_data.get("code", ""),
            "aciklama":    row_data.get("name", ""),
            "not2":        row_data.get("note2", ""),
            "miktar":      float(row_data.get("qty", 1)),
            "birim":       row_data.get("unit", "Adet"),
            "birim_fiyat": float(row_data.get("price", 0)),
            "iskonto":     float(row_data.get("disc1", 0)),
            "kdv":         int(row_data.get("vat", 20)),
            "tutar":       self.hareket_kalemleri._calc_row_total(0),
        })

    # Toplamlar — ToplamWidget'tan
    toplam_data = self.toplam_widget.get_data()
    toplamlar = {
        "ara_toplam":   toplam_data.get("ara_toplam", 0),
        "iskonto":      toplam_data.get("iskonto", 0),
        "masraflar":    toplam_data.get("masraflar", 0),
        "kdv_matrahi":  toplam_data.get("net_toplam", 0),
        "kdv_toplam":   toplam_data.get("kdv_toplam", 0),
        "genel_toplam": toplam_data.get("genel_toplam", 0),
    }

    return {
        "firma":     firma,
        "musteri":   musteri,
        "belge":     belge,
        "kalemler":  kalemler,
        "toplamlar": toplamlar,
        "notlar":    getattr(self, "doc_note1", ""),
    }
```

---

## Test

```
1. Programı çalıştır
2. Teklif Yönetimi → Yeni
3. Üst panel görünüyor mu? (3 widget yan yana)
4. F7 → 3 panel birden kapandı mı?
5. Cari koduna yaz → Enter → cari bilgileri doldu mu?
6. 🔍 Seç → cari listesi açıldı mı?
7. Ödeme planı seç → vade otomatik değişti mi?
8. Döviz seç → kur geldi mi? Toplamlar güncellendi mi?
9. Kalem ekle, fiyat gir → G.TOPLAM güncellendi mi?
10. KAYDET → liste güncellendi mi?
```

---

## Özet

| Adım | Değişiklik |
|------|-----------|
| 1 | Import ekle |
| 2 | create_info_panels → 3 widget |
| 3 | ToplamWidget entegre |
| 4 | Property proxy'leri — geriye uyumluluk |
| 5 | Sinyal bağlantıları |
| 6 | calculate_totals → ToplamWidget'a aktar |
| 7 | apply_customer_info → CariKunyeWidget |
| 8 | _get_current_teklif_data → widget'lardan oku |

> Mevcut save_document, load_to_dialog, PDF/Excel metodlarına DOKUNMA.
> Sadece UI ve veri okuma kısmı değişiyor.
