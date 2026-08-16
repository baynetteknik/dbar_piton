@echo off
chcp 65001 > nul
title TOYA ERP - Evrensel Fatura, Fiş ve Evrak Detay Ekranı Önizleme
echo ===============================================================================
echo   TOYA ERP - Evrensel Fatura, Fiş, Sipariş ve Teklif Detay Ekranı Başlatılıyor...
echo ===============================================================================
cd /d "C:\toya_erp"
set PYTHONPATH=.
call .venv\Scripts\activate.bat
python test_transaction_dialog.py
pause
