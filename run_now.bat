@echo off
echo ==========================================
echo   Travis Dixon Content Agent - Run Now
echo ==========================================
echo.
cd /d "%~dp0"
python agent.py --now
echo.
echo ==========================================
echo   Done! Check Buffer dashboard.
echo ==========================================
pause
