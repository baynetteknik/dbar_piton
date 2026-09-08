@echo off
chcp 65001 > nul
title TOYA ERP Masaustu - YENI Belge Detay Ekrani (TOYA_NEW_DOC_SCREEN=1)
cd /d "C:\toya_erp"
set PYTHONPATH=.
set TOYA_NEW_DOC_SCREEN=1
echo.
echo   TOYA_NEW_DOC_SCREEN = %TOYA_NEW_DOC_SCREEN%
echo   Teklif listesinde "Yeni" / "Duzenle" -> YENI DocumentDetailScreen acilir.
echo   (Bayrak calismazsa: Teklif listesinde satira SAG TIK -> "Yeni Tasarim Ekrani (deneme)")
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src/desktop/main.py
) else (
    python src/desktop/main.py
)
pause
