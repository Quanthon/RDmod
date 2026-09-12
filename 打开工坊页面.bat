@echo off
cd /d "%~dp0"
python Scripts\upload_workshop.py --open-page
set "workflow_exit=%errorlevel%"
pause
exit /b %workflow_exit%
