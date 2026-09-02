@echo off
chcp 65001 > nul
title TOYA ERP - Kurumsal Teklif Formu Baski Onizleme (PoC)
echo ===============================================================================
echo   TOYA ERP - Teklif Formu Baski Onizleme ve PDF Motoru Baslatiliyor...
echo   (Mevcut UI kodlarina dokunulmadan bagimsiz tasarimci motoru calisir)
echo ===============================================================================
cd /d "C:\toya_erp"
set PYTHONPATH=.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_teklif_designer_preview.py
) else (
    python run_teklif_designer_preview.py
)
pause
