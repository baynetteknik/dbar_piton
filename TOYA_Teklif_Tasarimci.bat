@echo off
chcp 65001 > nul
title TOYA ERP - Gorsel Form ve Rapor Tasarimcisi (Asama 2 PoC)
echo ===============================================================================
echo   TOYA ERP - Gorsel Form ve Rapor Tasarimcisi Baslatiliyor...
echo   (Bant Tabanli Milimetrik Tuval, Cetveller, Surukle-Birak ve Ozellik Denetcisi)
echo ===============================================================================
cd /d "C:\toya_erp"
set PYTHONPATH=.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_teklif_designer.py
) else (
    python run_teklif_designer.py
)
pause
