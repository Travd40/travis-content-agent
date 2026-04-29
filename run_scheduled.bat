@echo off
REM run_scheduled.bat — for Windows Task Scheduler (no pause, logs to file)
REM Runs the content pipeline once and exits. Output appended to scheduler.log.

cd /d "%~dp0"
echo. >> scheduler.log
echo ========================================== >> scheduler.log
echo Run at %date% %time% >> scheduler.log
echo ========================================== >> scheduler.log
python -u agent.py --now >> scheduler.log 2>&1
