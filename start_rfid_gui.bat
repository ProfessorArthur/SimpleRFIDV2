@echo off
cd /d "%~dp0"
set "PY_CMD=%~dp0.venv\Scripts\python.exe"
if not exist "%PY_CMD%" set "PY_CMD=python"
if exist "dist\RFIDBridgeControl.exe" (
	echo Launching RFIDBridgeControl.exe...
	start "" "dist\RFIDBridgeControl.exe" %*
	rem Wait briefly and check whether the process is still alive.
	timeout /t 2 /nobreak >nul
	tasklist /FI "IMAGENAME eq RFIDBridgeControl.exe" | find /I "RFIDBridgeControl.exe" >nul
	if errorlevel 1 (
		echo.
		echo The EXE appears to have exited right after launch.
		echo Starting Python version for visible error output...
		"%PY_CMD%" rfid_bridge_gui.py %*
		echo.
		echo If this still closes, run this file from a terminal to read errors.
		pause
		exit /b %errorlevel%
	)
	exit /b 0
) else (
	"%PY_CMD%" rfid_bridge_gui.py %*
	exit /b %errorlevel%
)
