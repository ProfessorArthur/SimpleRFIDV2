@echo off
setlocal
cd /d "%~dp0"

set "TASK_NAME=SimpleRFIDBridge"
set "RUNNER=%~dp0start_rfid_gui.bat"
set "STARTUP_FILE=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SimpleRFIDBridge.cmd"

echo Creating scheduled task "%TASK_NAME%" for current user...
schtasks /Create /TN "%TASK_NAME%" /SC ONLOGON /TR "\"%RUNNER%\" --tray" /F >nul
if errorlevel 1 (
    echo Task Scheduler create failed. Falling back to Startup folder autostart...
    >"%STARTUP_FILE%" echo @echo off
    >>"%STARTUP_FILE%" echo cd /d "%~dp0"
    >>"%STARTUP_FILE%" echo start "" "dist\RFIDBridgeControl.exe" --tray
    if not exist "%STARTUP_FILE%" (
        echo Failed to create Startup folder launcher.
        exit /b 1
    )
    echo Startup launcher created successfully:
    echo %STARTUP_FILE%
    echo It will start automatically when you sign in.
    exit /b 0
)

echo Task created successfully.
echo It will start automatically when you sign in.
echo.
echo Task details:
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST

exit /b 0
