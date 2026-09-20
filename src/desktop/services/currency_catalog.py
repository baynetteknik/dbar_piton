"""
TOYA ERP - Statik Döviz Kataloğu

Döviz tanımlanırken (Genel Ayarlar > Döviz & Kur > "Yeni Döviz Ekle", ilk
kurulumda "kullanmak istediğiniz dövizleri seçin" popup'ı, Firma tanımlarken
"Döviz Birimi" alanı) kod/isim/sembolün serbest metinle elden yazılması yerine
seçilecek sabit, geniş kapsamlı bir ISO 4217 referans listesi sağlar.

Bayraklar internetten indirilen görsel değil, ülke kodundan (ISO 3166-1
alpha-2) Unicode "regional indicator" karakterleriyle anlık üretilen emoji
bayraklardır (`flag_emoji`) — böylece liste tamamen yerel/offline çalışır,
ayrı bir ikon indirme/önbellekleme mekanizmasına ihtiyaç duymaz.
"""

from __future__ import annotations

from dataclasses import dataclass


def flag_emoji(country_iso2: str) -> str:
    """İki harfli ülke koduna karşılık gelen bayrak emojisini üretir.

    Unicode "regional indicator symbol" karakterleri A-Z için U+1F1E6'dan
    başlar; iki harfin bu aralığa kaydırılmış hâli yan yana yazıldığında
    ilgili ülke bayrağı olarak render edilir (ör. "TR" → 🇹🇷).
    """
    code = (country_iso2 or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code)


@dataclass(frozen=True)
class CurrencyInfo:
    code: str
    country: str  # ISO 3166-1 alpha-2 (bayrak üretimi için) — çok uluslu paralarda temsili ülke
    name: str
    symbol: str

    @property
    def flag(self) -> str:
        return flag_emoji(self.country)


#: (kod, ülke, isim, sembol) — kod bazında benzersiz, alfabetik değil önem
#: sırasına göre (en sık kullanılanlar başta) listelenmiştir.
_RAW_CATALOG: list[tuple[str, str, str, str]] = [
    ("TRY", "TR", "Türk Lirası", "₺"),
    ("USD", "US", "Amerikan Doları", "$"),
    ("EUR", "EU", "Euro", "€"),
    ("GBP", "GB", "İngiliz Sterlini", "£"),
    ("CHF", "CH", "İsviçre Frangı", "CHF"),
    ("JPY", "JP", "Japon Yeni", "¥"),
    ("CAD", "CA", "Kanada Doları", "$"),
    ("AUD", "AU", "Avustralya Doları", "$"),
    ("NZD", "NZ", "Yeni Zelanda Doları", "$"),
    ("CNY", "CN", "Çin Yuanı", "¥"),
    ("HKD", "HK", "Hong Kong Doları", "$"),
    ("TWD", "TW", "Tayvan Doları", "$"),
    ("SGD", "SG", "Singapur Doları", "$"),
    ("KRW", "KR", "Güney Kore Wonu", "₩"),
    ("INR", "IN", "Hindistan Rupisi", "₹"),
    ("PKR", "PK", "Pakistan Rupisi", "₨"),
    ("BDT", "BD", "Bangladeş Takası", "৳"),
    ("LKR", "LK", "Sri Lanka Rupisi", "Rs"),
    ("NPR", "NP", "Nepal Rupisi", "Rs"),
    ("MMK", "MM", "Myanmar Kyatı", "K"),
    ("THB", "TH", "Tayland Bahtı", "฿"),
    ("VND", "VN", "Vietnam Dongu", "₫"),
    ("IDR", "ID", "Endonezya Rupiahı", "Rp"),
    ("MYR", "MY", "Malezya Ringgiti", "RM"),
    ("PHP", "PH", "Filipin Pesosu", "₱"),
    ("KHR", "KH", "Kamboçya Rieli", "៛"),
    ("LAK", "LA", "Laos Kipi", "₭"),
    ("MNT", "MN", "Moğolistan Tugriki", "₮"),
    ("BND", "BN", "Brunei Doları", "$"),
    ("MOP", "MO", "Makao Patacası", "MOP$"),
    ("KZT", "KZ", "Kazakistan Tengesi", "₸"),
    ("UZS", "UZ", "Özbekistan Somu", "so'm"),
    ("TJS", "TJ", "Tacikistan Somonisi", "SM"),
    ("TMT", "TM", "Türkmenistan Manatı", "m"),
    ("KGS", "KG", "Kırgızistan Somu", "с"),
    ("AFN", "AF", "Afganistan Afganisi", "؋"),
    ("GEL", "GE", "Gürcistan Larisi", "₾"),
    ("AMD", "AM", "Ermenistan Dramı", "֏"),
    ("AZN", "AZ", "Azerbaycan Manatı", "₼"),
    ("RUB", "RU", "Rus Rublesi", "₽"),
    ("UAH", "UA", "Ukrayna Grivnası", "₴"),
    ("BYN", "BY", "Belarus Rublesi", "Br"),
    ("MDL", "MD", "Moldova Leyi", "L"),
    ("PLN", "PL", "Polonya Zlotisi", "zł"),
    ("CZK", "CZ", "Çek Korunası", "Kč"),
    ("HUF", "HU", "Macar Forinti", "Ft"),
    ("RON", "RO", "Romen Leyi", "lei"),
    ("BGN", "BG", "Bulgar Levası", "лв"),
    ("RSD", "RS", "Sırbistan Dinarı", "дин"),
    ("MKD", "MK", "K. Makedonya Dinarı", "ден"),
    ("ALL", "AL", "Arnavutluk Leki", "L"),
    ("BAM", "BA", "Bosna Hersek Markı", "KM"),
    ("ISK", "IS", "İzlanda Kronu", "kr"),
    ("NOK", "NO", "Norveç Kronu", "kr"),
    ("SEK", "SE", "İsveç Kronu", "kr"),
    ("DKK", "DK", "Danimarka Kronu", "kr"),
    ("ILS", "IL", "İsrail Şekeli", "₪"),
    ("JOD", "JO", "Ürdün Dinarı", "د.ا"),
    ("LBP", "LB", "Lübnan Lirası", "ل.ل"),
    ("SYP", "SY", "Suriye Lirası", "£S"),
    ("IQD", "IQ", "Irak Dinarı", "ع.د"),
    ("IRR", "IR", "İran Riyali", "﷼"),
    ("SAR", "SA", "Suudi Arabistan Riyali", "﷼"),
    ("YER", "YE", "Yemen Riyali", "﷼"),
    ("OMR", "OM", "Umman Riyali", "﷼"),
    ("QAR", "QA", "Katar Riyali", "﷼"),
    ("AED", "AE", "BAE Dirhemi", "د.إ"),
    ("KWD", "KW", "Kuveyt Dinarı", "د.ك"),
    ("BHD", "BH", "Bahreyn Dinarı", ".د.ب"),
    ("EGP", "EG", "Mısır Lirası", "£"),
    ("LYD", "LY", "Libya Dinarı", "ل.د"),
    ("TND", "TN", "Tunus Dinarı", "د.ت"),
    ("DZD", "DZ", "Cezayir Dinarı", "د.ج"),
    ("MAD", "MA", "Fas Dirhemi", "د.م."),
    ("SDG", "SD", "Sudan Lirası", "ج.س."),
    ("ETB", "ET", "Etiyopya Birri", "Br"),
    ("KES", "KE", "Kenya Şilini", "KSh"),
    ("TZS", "TZ", "Tanzanya Şilini", "TSh"),
    ("UGX", "UG", "Uganda Şilini", "USh"),
    ("RWF", "RW", "Ruanda Frangı", "FRw"),
    ("NGN", "NG", "Nijerya Nayrası", "₦"),
    ("GHS", "GH", "Gana Sedisi", "₵"),
    ("XOF", "SN", "Batı Afrika CFA Frangı", "CFA"),
    ("XAF", "CM", "Orta Afrika CFA Frangı", "FCFA"),
    ("ZAR", "ZA", "Güney Afrika Randı", "R"),
    ("NAD", "NA", "Namibya Doları", "$"),
    ("BWP", "BW", "Botsvana Pulası", "P"),
    ("MUR", "MU", "Mauritius Rupisi", "₨"),
    ("MZN", "MZ", "Mozambik Metikali", "MT"),
    ("AOA", "AO", "Angola Kwanzası", "Kz"),
    ("ZMW", "ZM", "Zambiya Kvaçası", "ZK"),
    ("MWK", "MW", "Malavi Kvaçası", "MK"),
    ("XCD", "AG", "Doğu Karayip Doları", "$"),
    ("BRL", "BR", "Brezilya Reali", "R$"),
    ("ARS", "AR", "Arjantin Pesosu", "$"),
    ("CLP", "CL", "Şili Pesosu", "$"),
    ("COP", "CO", "Kolombiya Pesosu", "$"),
    ("PEN", "PE", "Peru Solü", "S/"),
    ("UYU", "UY", "Uruguay Pesosu", "$"),
    ("PYG", "PY", "Paraguay Guaranisi", "₲"),
    ("BOB", "BO", "Bolivya Bolivianosu", "Bs"),
    ("VES", "VE", "Venezuela Bolivarı", "Bs"),
    ("GYD", "GY", "Guyana Doları", "$"),
    ("SRD", "SR", "Surinam Doları", "$"),
    ("MXN", "MX", "Meksika Pesosu", "$"),
    ("GTQ", "GT", "Guatemala Quetzali", "Q"),
    ("HNL", "HN", "Honduras Lempirası", "L"),
    ("NIO", "NI", "Nikaragua Kordobası", "C$"),
    ("CRC", "CR", "Kosta Rika Kolonu", "₡"),
    ("PAB", "PA", "Panama Balboası", "B/."),
    ("DOP", "DO", "Dominik Pesosu", "RD$"),
    ("JMD", "JM", "Jamaika Doları", "$"),
    ("TTD", "TT", "Trinidad ve Tobago Doları", "$"),
    ("BBD", "BB", "Barbados Doları", "$"),
    ("BSD", "BS", "Bahama Doları", "$"),
    ("CUP", "CU", "Küba Pesosu", "$"),
    ("HTG", "HT", "Haiti Gurdu", "G"),
    ("BZD", "BZ", "Belize Doları", "$"),
    ("FJD", "FJ", "Fiji Doları", "$"),
    ("PGK", "PG", "Papua Yeni Gine Kinası", "K"),
    ("WST", "WS", "Samoa Talası", "T"),
    ("TOP", "TO", "Tonga Pa'angası", "T$"),
    ("XPF", "PF", "CFP Frangı", "₣"),
    ("SBD", "SB", "Solomon Adaları Doları", "$"),
    ("VUV", "VU", "Vanuatu Vatusu", "VT"),
]

CURRENCY_CATALOG: list[CurrencyInfo] = [CurrencyInfo(*row) for row in _RAW_CATALOG]

#: Yalnızca kodlar — dropdown/fallback listeleri için.
CURRENCY_CODES: list[str] = [c.code for c in CURRENCY_CATALOG]

_BY_CODE: dict[str, CurrencyInfo] = {c.code: c for c in CURRENCY_CATALOG}


def get_currency_info(code: str) -> CurrencyInfo | None:
    return _BY_CODE.get((code or "").strip().upper())
