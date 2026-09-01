@echo off
title TOYA ERP PyQt6 Masaustu
cd /d "C:\toya_erp"

set PYTHONPATH=.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src/desktop/main.py
    if errorlevel 1 (
        echo.
        echo ========================================================
        echo [HATA] Uygulama bir hata ile sonlandi! (Hata Kodu: %ERRORLEVEL%)
        echo ========================================================
        echo.
        pause
    ) else (
        echo.
        echo Uygulama normal sekilde kapatildi.
        pause
    )
) else (
    echo Python sanal ortami bulunamadi!
    pause
)
