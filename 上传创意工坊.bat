@echo off
cd /d "%~dp0"
python Scripts\upload_workshop.py --upload
set "workflow_exit=%errorlevel%"
pause
exit /b %workflow_exit%
