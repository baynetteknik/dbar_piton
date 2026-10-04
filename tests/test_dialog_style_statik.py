"""Statik QMessageBox/QInputDialog çağrıları kurulumdan sonra açık temalı diyalog açar; imza ve dönüş değerleri Qt ile aynıdır."""

import pytest
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from src.desktop.ui.components import dialog_style


@pytest.fixture
def kurulu(monkeypatch, qapp):
    for sinif, ad in [(QMessageBox, "information"), (QMessageBox, "warning"), (QMessageBox, "critical"), (QMessageBox, "question"),
                      (QInputDialog, "getText"), (QInputDialog, "getItem")]:
        monkeypatch.setattr(sinif, ad, getattr(sinif, ad))               # test sonunda özgün değer geri gelir
    monkeypatch.delattr(QMessageBox, "_toya_temali", raising=False)
    dialog_style.temali_statikleri_kur()
    gorulen = {}

    def exec_(self):
        gorulen["stil"] = self.styleSheet()
        gorulen["butonlar"] = self.standardButtons() if isinstance(self, QMessageBox) else None
        return int(QMessageBox.StandardButton.Yes) if isinstance(self, QMessageBox) else 1
    monkeypatch.setattr(QMessageBox, "exec", exec_)
    monkeypatch.setattr(QInputDialog, "exec", lambda self: (gorulen.update(stil=self.styleSheet()), 1)[1])
    return gorulen


def test_mesaj_kutulari_temali_ve_ayni_imzali(kurulu):
    sonuc = QMessageBox.question(None, "Başlık", "Soru?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
    assert sonuc == QMessageBox.StandardButton.Yes and "#f8fafc" in kurulu["stil"]
    QMessageBox.warning(None, "B", "M")
    assert kurulu["butonlar"] == QMessageBox.StandardButton.Ok
    QMessageBox.question(None, "B", "M")
    assert kurulu["butonlar"] == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No


def test_girdi_diyaloglari_temali_ve_tuple_doner(kurulu):
    metin, ok = QInputDialog.getText(None, "B", "Ad:", QLineEdit.EchoMode.Password, text="abc")
    assert (metin, ok) == ("abc", True) and "#f8fafc" in kurulu["stil"]
    secim, ok = QInputDialog.getItem(None, "B", "Seç:", ["a", "b"], 1, False)
    assert (secim, ok) == ("b", True)
