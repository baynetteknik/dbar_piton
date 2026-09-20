"""
TOYA ERP - Harici Sistem Bağlayıcı Sözleşmesi

Wolvox, Logo, Mikro, Paraşüt vb. bir dış sistemi TOYA'ya bağlamak için bir bağlayıcının
uyması gereken arayüz. Bağlayıcı kaynağa özgü her şeyi (tablo/alan adları, kod
anlamları, kimlik doğrulama) içine saklar ve TOYA'nın ortak kayıt biçimini döner;
ayna servisi, raporlar, ekranlar ve portal kaynağı bilmez.

Kayıt biçimi (sözlük anahtarları). `ext_id` kaynağın kendi kayıt kimliğidir (metin);
diğer kayıtlara `*_ext_id` ile başvurulur. `silindi=True` kaynakta silinmiş demektir.

  fetch_cariler            : ext_id, cari_kodu, unvan, email, telefon, vergi_no, aktif, silindi
  fetch_cari_hareketleri   : ext_id, cari_ext_id, tarihi, vadesi, evrak_no, kaynak_tur, borc, alacak,
                             aciklama, ilgili_ext_id, silindi        (+ = müşteri bize borçlu)
  fetch_faturalar          : ext_id, fatura_no, tarihi, vadesi, cari_ext_id, yon ('satis'|'alis'|None),
                             kaynak_durum, iptal, ara_toplam, iskonto, kdv, genel_toplam, doviz,
                             ek_bilgi, aciklama, silindi
  fetch_fatura_kalemleri   : ext_id, fatura_ext_id, stok_kodu, stok_adi, birim, miktar, fiyat,
                             kdv_orani, tutar, kdvli_tutar, sira_no, silindi
  fetch_stoklar            : ext_id, stok_kodu, stok_adi, birim, kdv_orani, aktif, satis_fiyati, miktar, silindi

Tutarlar ana para biriminde. Bir bağlayıcı desteklemediği bir varlık için boş liste döner
(`capabilities` bunu bildirir). Bağlayıcılar varsayılan olarak SALT OKUNURDUR.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

#: Bir bağlayıcının bildirebileceği yetenekler.
CAP_READ = "read"
CAP_WRITE = "write"  # kaynağa resmî yoldan kayıt yazabilir (Wolvox için henüz yok)

Record = dict


@runtime_checkable
class SourceConnector(Protocol):
    #: Ayna tablolarında `source` sütununa yazılan kısa ad (örn. "wolvox").
    source_name: str
    capabilities: frozenset[str]

    def test_connection(self) -> str: ...
    def fetch_cariler(self) -> list[Record]: ...
    def fetch_cari_hareketleri(self) -> list[Record]: ...
    def fetch_faturalar(self) -> list[Record]: ...
    def fetch_fatura_kalemleri(self) -> list[Record]: ...
    def fetch_stoklar(self) -> list[Record]: ...
