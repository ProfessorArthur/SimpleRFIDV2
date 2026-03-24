@echo off
setlocal

set "TASK_NAME=SimpleRFIDBridge"
set "STARTUP_FILE=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SimpleRFIDBridge.cmd"

echo Removing scheduled task "%TASK_NAME%"...
schtasks /Delete /TN "%TASK_NAME%" /F >nul
if not errorlevel 1 (
    echo Scheduled task removed.
)

if exist "%STARTUP_FILE%" (
    del /f /q "%STARTUP_FILE%" >nul
    if not errorlevel 1 (
        echo Startup folder launcher removed.
    )
)

echo Autostart cleanup complete.
exit /b 0
