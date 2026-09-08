@echo off
chcp 65001 > nul
title TOYA ERP - Yeni Belge Detay Ekrani (DocumentDetailScreen PoC)
echo ===============================================================================
echo   TOYA ERP - Yeni Belge/Fis Detay Ekrani (Adim E PoC) baslatiliyor...
echo   Cari + Belge/Vade + Finans widgetlari + entry-modda kalemler gridi + Toplam
echo ===============================================================================
cd /d "C:\toya_erp"
set PYTHONPATH=.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m src.desktop.ui.screens.document_detail_screen
) else (
    python -m src.desktop.ui.screens.document_detail_screen
)
pause
