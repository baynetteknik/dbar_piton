"""MaskedDecimalField - hesap makinesi tarzı maskeli ondalık giriş alanı."""

import pytest
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.widgets.masked_decimal_field import MaskedDecimalField


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_initial_mask_is_zero(qapp):
    f = MaskedDecimalField(decimals=2)
    assert f.text() == "0,00"
    f4 = MaskedDecimalField(decimals=4)
    assert f4.text() == "0,0000"


def test_digits_before_comma_fill_integer_part(qapp):
    f = MaskedDecimalField(decimals=2)
    QTest.keyClicks(f, "1585686")
    assert f.text() == "1.585.686,00"
    assert f.value() == pytest.approx(1585686.0)


def test_comma_switches_to_decimal_entry(qapp):
    f = MaskedDecimalField(decimals=2)
    QTest.keyClicks(f, "123")
    QTest.keyClick(f, Qt.Key.Key_Comma)
    QTest.keyClicks(f, "5")
    assert f.text() == "123,50"
    QTest.keyClicks(f, "9")
    assert f.text() == "123,59"
    assert f.value() == pytest.approx(123.59)


def test_decimal_digits_beyond_capacity_are_ignored(qapp):
    f = MaskedDecimalField(decimals=2)
    QTest.keyClicks(f, "1")
    QTest.keyClick(f, Qt.Key.Key_Comma)
    QTest.keyClicks(f, "1234")  # sadece ilk 2 hane alınmalı
    assert f.text() == "1,12"


def test_backspace_walks_back_through_decimal_then_integer(qapp):
    f = MaskedDecimalField(decimals=2)
    QTest.keyClicks(f, "12")
    QTest.keyClick(f, Qt.Key.Key_Comma)
    QTest.keyClicks(f, "5")
    assert f.text() == "12,50"
    QTest.keyClick(f, Qt.Key.Key_Backspace)  # ondalık haneyi siler
    assert f.text() == "12,00"
    QTest.keyClick(f, Qt.Key.Key_Backspace)  # artık virgül modundan çıkar
    QTest.keyClick(f, Qt.Key.Key_Backspace)  # tam sayının son hanesini siler
    assert f.text() == "1,00"


def test_set_value_and_round_trip(qapp):
    f = MaskedDecimalField(decimals=2)
    f.setValue(1585686.5)
    assert f.text() == "1.585.686,50"
    assert f.value() == pytest.approx(1585686.5)


def test_comma_key_with_empty_text_still_switches_mode(qapp):
    """Bazı klavye düzenlerinde (Türkçe numpad ondalık tuşu vb.) sanal tuş kodu
    Key_Comma olsa da event.text() boş gelebilir; tuş koduna da bakılmalı."""
    f = MaskedDecimalField(decimals=2)
    QTest.keyClicks(f, "12")
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Comma, Qt.KeyboardModifier.NoModifier, "")
    QApplication.sendEvent(f, ev)
    QTest.keyClicks(f, "5")
    assert f.text() == "12,50"


def test_typing_decimal_after_prior_set_value_works(qapp):
    """Gerçek dünya senaryosu: form açılırken `setValue(0.0)` (veya başka bir
    değer) çağrılır — bu, ondalık arabelleği görüntü amaçlı "00" ile
    doldurur. Kullanıcı daha sonra virgüle basıp rakam girdiğinde bu "00"
    yeni rakamlara yer bırakmamalı; virgül basılan her an ondalık haneler
    sıfırdan yazılmaya başlamalı."""
    f = MaskedDecimalField(decimals=2)
    f.setValue(0.0)  # DefinitionEditorScreen.set_data() ile aynı çağrı
    QTest.keyClicks(f, "150")
    QTest.keyClick(f, Qt.Key.Key_Comma)
    QTest.keyClicks(f, "5")
    assert f.text() == "150,50"


def test_typing_decimal_after_editing_existing_value(qapp):
    f = MaskedDecimalField(decimals=2)
    f.setValue(150.0)  # mevcut bir ürünü düzenlerken olduğu gibi
    QTest.keyClick(f, Qt.Key.Key_Comma)
    QTest.keyClicks(f, "75")
    assert f.text() == "150,75"


def test_click_on_decimal_zone_switches_mode_without_comma(qapp):
    """Kullanıcı virgül tuşuna basmadan doğrudan kuruş hanesine tıklayıp
    yazabilmeli (ör. Alış/Satış Fiyatı alanına fareyle tıklama senaryosu)."""
    f = MaskedDecimalField(decimals=2)
    f.setValue(150.0)
    QTest.mouseClick(f, Qt.MouseButton.LeftButton, pos=QPoint(9999, 5))
    QTest.keyClicks(f, "75")
    assert f.text() == "150,75"


def test_click_on_integer_zone_switches_back_to_integer_mode(qapp):
    f = MaskedDecimalField(decimals=2)
    f.setValue(150.5)
    QTest.mouseClick(f, Qt.MouseButton.LeftButton, pos=QPoint(0, 5))
    QTest.keyClicks(f, "9")
    assert f.text() == "1.509,50"


def test_set_decimals_changes_mask_parametrically(qapp):
    f = MaskedDecimalField(decimals=2)
    f.setValue(12.3)
    f.set_decimals(4)
    assert f.text() == "12,3000"
    assert f.value() == pytest.approx(12.3)
