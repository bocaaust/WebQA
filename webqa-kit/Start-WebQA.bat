@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Please run Setup-WebQA.bat once before starting WebQA.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m webqa ui
if errorlevel 1 pause
