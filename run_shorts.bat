@echo off
REM Auto-run wrapper for Windows Task Scheduler.
REM Logs every run so you can debug if something fails silently.

cd /d "C:\Users\murat\Desktop\yeni"

set LOGDIR=C:\Users\murat\Desktop\yeni\workspace\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

set TS=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
set TS=%TS: =0%
set LOGFILE=%LOGDIR%\%TS%.log

echo [%date% %time%] Starting Shorts pipeline > "%LOGFILE%"
"C:\Users\murat\miniconda3\python.exe" main.py --urls-file urls.txt >> "%LOGFILE%" 2>&1
echo [%date% %time%] Exit code: %ERRORLEVEL% >> "%LOGFILE%"
