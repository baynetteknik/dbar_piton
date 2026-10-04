"""TOYA ERP - YardimWidget: Genel Ayarlar'da "📖 Yardım" paneli.

Bu oturumda inşa edilen (Şirket Tanımları, Ödeme Planları otomasyon zinciri, Çok Türlü Ödeme Planları,
Banka Ödeme Planları, POS Otomatik Mahsup...) bölümlerin KULLANICIYA yönelik kısa açıklamalarını — ekran
görüntüsü/geliştirici notu değil, "bu ekran ne işe yarar, nasıl kullanılır" — bir arada tutar. Teknik
detaylar `gelistirme/*.md` dosyalarında kalır; bu panel yalnızca son kullanıcı içindir.

Konu listesi statik bir Python listesidir (`_KONULAR`) — yeni bir bölüm tamamlanınca buraya bir madde
eklemek yeterlidir, ayrı bir ekran/DB tablosu gerekmez."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import settings_menu as sm
from src.desktop.ui.components.collapsible_section import CollapsibleSection

#: (başlık, HTML içerik). Yeni bir bölüm tamamlanınca buraya eklenir.
_KONULAR: list[tuple[str, str]] = [
    (
        "⚙️ Genel Ayarlar Panosu",
        "Genel Ayarlar'a girince karşınıza çıkan ikonlu kart ekranından istediğiniz bölüme tek tıkla "
        "gidersiniz. Herhangi bir ekranın sol üstündeki <b>🏠 Ayarlar Panosu</b> butonuyla her zaman bu "
        "ana ekrana geri dönebilirsiniz.",
    ),
    (
        "🏢 Şirket Tanımları",
        "<b>Firma Detayı</b> ekranında firma kimliği, vergi/sicil bilgileri, adres, logo/kaşe-imza, "
        "<b>Dönemler</b>, <b>Şube &amp; Depo Tanımları</b> ve Yetkililer/Ortaklar/Banka Hesapları bir "
        "arada yönetilir. Her şirketin kendi dönem/şube/depo/KDV/birim tanımları olur. "
        "<b>Bir şirket tanımlanmadan diğer modüller kullanılamaz</b> — program ilk açıldığında sizi "
        "otomatik olarak bu ekrana yönlendirir.",
    ),
    (
        "💳 Ödeme Planları — Otomatik Kasa/Banka Fişi",
        "Fatura/İrsaliye'de seçtiğiniz Ödeme Planı'na göre sistem kaydettiğiniz anda otomatik bir kasa/"
        "banka fişi oluşturabilir:<ul>"
        "<li><b>Nakit</b> → otomatik <i>Kasa Tahsilat</i> fişi</li>"
        "<li><b>Havale/EFT, Kredi Kartı, POS</b> → otomatik <i>Banka</i> fişi (ilgili hesaba)</li>"
        "<li><b>Açık Hesap</b> → otomatik fiş OLUŞTURULMAZ, yalnızca cari borç kalır</li></ul>"
        "Her planda bir <b>Hedef Hesap</b> (fişin düşeceği kasa/banka/POS hesabı) ve "
        "<b>Otomatik Fiş</b> (bu otomasyonun açık/kapalı olması) seçilir. Faturayı tekrar kaydederseniz "
        "AYNI fiş güncellenir — ikinci bir fiş açılmaz; ödeme tipini sonradan değiştirirseniz önceki "
        "otomatik fiş kendiliğinden geri alınır (silinmez, gizlenir).",
    ),
    (
        "📑 Çok Türlü Ödeme Planları (Satırlar)",
        "Bir fatura TEK bir ödeme tipiyle değil, <b>BİRDEN FAZLA</b> tiple de ödenebilir — ör. yarısı "
        "nakit, yarısı kredi kartı; ya da bir bölümü açık hesap, bir bölümü havale, kalanı kredi kartı. "
        "Ödeme Planları panelinde ilgili planı seçip <b>📑 Çok Türlü Satırları Düzenle</b> ile her biri "
        "ayrı tutar ve tip taşıyan satırlar eklenir. <b>Tutar Formülü</b> basit bir hesap dilidir:"
        "<ul>"
        "<li><code>TUTAR</code> — faturanın genel toplamı</li>"
        "<li><code>ARATOPLAM</code> — KDV hariç tutar</li>"
        "<li><code>KDV</code> — toplam KDV</li>"
        "<li><code>KALAN</code> — bu plandaki ÖNCEKİ satırlardan arta kalan</li></ul>"
        "Örnek: <code>TUTAR/2</code> (yarısı). Formülü BOŞ bırakırsanız <code>KALAN</code>'a eşit "
        "sayılır — bu yüzden SON satırı genelde boş bırakın, küsürat/yuvarlama farkı kaybolmaz. "
        "<code>round</code>/<code>abs</code>/<code>min</code>/<code>max</code>/<code>sum</code> "
        "fonksiyonları da kullanılabilir: <code>round(TUTAR*0.3,2)</code>.",
    ),
    (
        "🏦 Banka Ödeme Planları",
        "Kredi Kartı/POS/Havale gibi banka ile ilgili Ödeme Planları'na isteğe bağlı olarak bağlanan, "
        "<b>taksit sayısına göre değişen</b> komisyon/BSMV/hizmet bedeli tanımlarıdır. "
        "<b>BSMV, komisyon TUTARI üzerinden</b> hesaplanır (bankaların standart uygulaması) — hizmet "
        "bedeli ise sabit bir kesintidir.",
    ),
    (
        "🔁 POS Otomatik Mahsup (POS → Banka)",
        "Banka &amp; POS Kartı düzenleme ekranında bir POS hesabına <b>Otomatik Mahsup</b> açılıp bir "
        "<b>Hedef Banka Hesabı</b> seçilebilir. Valör günü (ör. 2 gün) geçmiş POS bakiyesi, "
        "<b>Banka Hareketleri</b> ekranı her açıldığında otomatik kontrol edilip hedef hesaba virmanla "
        "aktarılır — ayrı bir zamanlayıcı çalıştırmanıza gerek yoktur, ekranı açmanız yeterlidir.",
    ),
]


class YardimWidget(QWidget):
    """Genel Ayarlar > Yardım paneli — arama kutusu + konu başlıklarına göre açılır/kapanır bölümler."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("YardimWidget")
        self._bolumler: list[tuple[CollapsibleSection, str, str]] = []
        self._init_ui()

    def _init_ui(self) -> None:
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 12, 16, 12)
        lyt.setSpacing(10)

        baslik = QLabel("📖 <b>Yardım</b> — bu bölümlerin kullanım kılavuzu")
        baslik.setStyleSheet("font-size:14px;color:#1e3a8a;")
        lyt.addWidget(baslik)

        self.txt_ara = QLineEdit()
        self.txt_ara.setPlaceholderText("🔍 Konu ara (örn. ödeme planı, formül, BSMV, POS)...")
        self.txt_ara.setClearButtonEnabled(True)
        self.txt_ara.setStyleSheet(
            "QLineEdit{border:1px solid #cbd5e1;border-radius:6px;padding:6px 10px;"
            "font-size:11px;background:#ffffff;color:#0f172a;}"
            "QLineEdit:focus{border-color:#2563eb;}",
        )
        self.txt_ara.textChanged.connect(self._ara)
        lyt.addWidget(self.txt_ara)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        icerik = QWidget()
        icerik_lyt = QVBoxLayout(icerik)
        icerik_lyt.setContentsMargins(0, 0, 4, 0)
        icerik_lyt.setSpacing(8)

        for baslik_metni, html in _KONULAR:
            sec = CollapsibleSection(baslik_metni, is_expanded=False)
            lbl = QLabel(html)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setStyleSheet("font-size:11px;color:#1e293b;padding:4px 6px;")
            sec.add_widget(lbl)
            icerik_lyt.addWidget(sec)
            self._bolumler.append((sec, baslik_metni, html))
        icerik_lyt.addStretch()

        scroll.setWidget(icerik)
        lyt.addWidget(scroll, 1)

    def _ara(self, metin: str) -> None:
        q = metin.strip()
        for sec, baslik_metni, html in self._bolumler:
            uyuyor = sm.matches(q, baslik_metni, html)
            sec.setVisible(uyuyor)
            if q and uyuyor:
                sec.set_expanded(True)
            elif not q:
                sec.set_expanded(False)
