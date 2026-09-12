@echo off
setlocal
cd /d "%~dp0"
python Scripts\package_local_release.py --prompt-version
set "package_exit=%errorlevel%"
echo.
if not "%package_exit%"=="0" echo 打包失败，版本号已自动回滚。
pause
exit /b %package_exit%
