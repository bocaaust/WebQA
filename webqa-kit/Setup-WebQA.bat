@echo off
cd /d "%~dp0"
echo Setting up WebQA. This is only needed once.
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install .
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto failed
echo Setup complete. Double-click Start-WebQA.bat to use WebQA.
pause
exit /b 0
:failed
echo Setup could not finish. See docs\START_HERE.md or ask your setup helper.
pause
exit /b 1
