@echo off
cd /d "%~dp0"
python Scripts\upload_workshop.py --login-github
set "workflow_exit=%errorlevel%"
pause
exit /b %workflow_exit%
