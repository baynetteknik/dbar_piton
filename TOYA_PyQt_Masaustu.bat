@echo off
title TOYA ERP PyQt6 Masaustu Baslatiliyor...
cd /d "C:\toya_erp"

set PYTHONPATH=.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src/desktop/main.py
) else (
    echo Python sanal ortami bulunamadi!
    pause
)
