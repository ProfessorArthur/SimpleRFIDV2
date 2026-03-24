# SimpleRFIDV2

SimpleRFIDV2 reads RFID tag UIDs from an RC522 reader over serial and types the UID into the currently focused text field on Windows.

This repository includes:
- Arduino firmware: `SimpleRFIDV2.ino`
- Python GUI controller: `rfid_bridge_gui.py`
- Packaged Windows app: `dist/RFIDBridgeControl.exe`
- Optional autostart scripts:
	- `install_autostart_task.bat`
	- `remove_autostart_task.bat`

## What You Need

- Windows PC
- Arduino Uno (or compatible)
- RC522 RFID reader module
- RFID tags/cards
- USB cable for Arduino

## RC522 Wiring (Arduino Uno)

- VCC -> 3.3V (do not use 5V)
- GND -> GND
- RST -> D9
- SDA/SS -> D10
- MOSI -> D11
- MISO -> D12
- SCK -> D13

## Installation Guide (Non-Technical)

Use this if you want the easiest setup with minimal terminal usage.

### 1) Install Arduino IDE

Download and install Arduino IDE:
https://www.arduino.cc/en/software

### 2) Install USB Driver (if Arduino is not detected)

If your board uses CH340/CH341 and is not detected, run:
- `CH34x_Install_Windows_v3_4.EXE`

### 3) Upload the RFID Firmware

1. Open Arduino IDE.
2. Open `SimpleRFIDV2.ino` from this folder.
3. In Arduino IDE:
	 - Set Board to Arduino Uno.
	 - Select the correct COM port.
4. Install library if prompted: `MFRC522` by GithubCommunity.
5. Click Upload.

### 4) Start the Desktop App

Use one of these:
- Double-click `start_rfid_gui.bat` (recommended)
- Or run `dist/RFIDBridgeControl.exe` directly

### 5) Use It

1. In the app, pick the same COM port as your Arduino.
2. Keep default settings first:
	 - Baud: `115200`
	 - Backend: `pyautogui`
3. Click Start.
4. Click into any text box where you want UID text typed.
5. Scan an RFID tag.

If enabled, Enter is pressed automatically after each UID.

### 6) Optional: Start Automatically on Login

Run:
- `install_autostart_task.bat`

To remove autostart later:
- `remove_autostart_task.bat`

## Installation Guide (Technical)

Use this if you want to run from source, tune settings, or debug.

### 1) Prerequisites

- Python 3.10+
- Arduino IDE

### 2) Create and Activate Virtual Environment

From project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install Python Dependencies

```powershell
pip install -r requirements.txt
```

### 4) Flash Arduino Firmware

Upload `SimpleRFIDV2.ino` after wiring the RC522 module.

### 5) Run GUI Bridge

```powershell
python rfid_bridge_gui.py
```

Or start minimized to tray:

```powershell
python rfid_bridge_gui.py --tray
```

### 6) Run CLI Bridge (Alternative)

List serial ports:

```powershell
python rfid_serial_bridge.py --list-ports
```

Run bridge:

```powershell
python rfid_serial_bridge.py --port COM3 --baud 115200 --append-enter
```

## Configuration Notes

- UID output format is uppercase hex, one UID per line.
- Arduino firmware baud is `115200` and should match desktop app settings.
- Duplicate reads are filtered in firmware and Python bridge cooldown logic.
- If typing is blocked in a specific app/game, switch backend from `pyautogui` to `pydirectinput`.

## Troubleshooting

- App opens then closes immediately:
	- Launch via `start_rfid_gui.bat` to get fallback Python error output.
- No COM ports appear:
	- Reconnect USB cable.
	- Reinstall CH34x driver.
	- Check Device Manager for serial device status.
- Tags are detected in Serial Monitor but not typed:
	- Ensure target text field is focused.
	- Increase Focus Delay.
	- Try `pydirectinput` backend.
- Wrong or no UID output:
	- Confirm RC522 wiring and 3.3V power.
	- Re-upload `SimpleRFIDV2.ino`.
