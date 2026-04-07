@echo off
setlocal
cd /d "%~dp0"

set "TASK_NAME=SimpleRFIDBridge"
set "WORK_DIR=%~dp0"
set "RUNNER=%~dp0dist\RFIDBridgeControl.exe"
if not exist "%RUNNER%" set "RUNNER=%~dp0start_rfid_gui.bat"
set "STARTUP_FILE=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SimpleRFIDBridge.cmd"

echo Creating Startup-folder autostart launcher...
>"%STARTUP_FILE%" echo @echo off
>>"%STARTUP_FILE%" echo cd /d "%WORK_DIR%"
>>"%STARTUP_FILE%" echo start "" "%RUNNER%" --tray
>>"%STARTUP_FILE%" echo exit /b 0

if not exist "%STARTUP_FILE%" (
    echo Failed to create Startup folder launcher.
    exit /b 1
)

echo Creating scheduled task "%TASK_NAME%" for current user (optional)...
schtasks /Create /TN "%TASK_NAME%" /SC ONLOGON /TR "cmd /c \"\"%STARTUP_FILE%\"\"" /F >nul
if errorlevel 1 (
    echo Task Scheduler create failed. Startup-folder launcher is still active.
) else (
    echo Task created successfully.
)

echo It will start automatically when you sign in.
echo.
echo Startup launcher:
echo %STARTUP_FILE%

echo.
echo Task details (if task exists):
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST >nul 2>nul
if errorlevel 1 (
    echo No Task Scheduler entry found. This is OK because Startup launcher is enabled.
) else (
    schtasks /Query /TN "%TASK_NAME%" /V /FO LIST
)

exit /b 0
