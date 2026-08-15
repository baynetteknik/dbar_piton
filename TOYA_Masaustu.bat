@echo off
title TOYA ERP Masaustu Baslatiliyor...
cd /d "C:\toya_erp\aknsoft"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" desktop.py
) else (
    echo Python sanal ortami bulunamadi!
    pause
)
