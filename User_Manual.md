## SimpleRFID User Manual (Quick Start)

### 1) What You Need
- Windows 10 or 11 PC
- USB RFID reader (serial/COM type)
- One app file: `RFIDBridgeControl.exe` (main app)

Internet is **not required** to use the app.

### 2) What To Download
For non-technical users, download only these files:

Required:
- `RFIDBridgeControl.exe`

Required only if device is not detected in Windows:
- `CH34x driver installer` (CH340/CH341 USB-Serial driver)

Optional (quality-of-life):
- `install_autostart_task.bat` (start app automatically when Windows logs in)
- `remove_autostart_task.bat` (remove autostart)
- `start_rfid_gui.bat` (helper launcher used by autostart)

You do **not** need Python files if you are using the EXE.

### 3) First-Time Setup (Onboarding)
1. Plug the RFID reader into USB.
2. Wait 5-10 seconds for Windows to detect it.
3. Open Device Manager and find the COM port (example: `COM3`).
  - If no COM port appears or device shows a yellow warning icon, install the CH34x driver, reconnect USB, then check Device Manager again.
4. Run `RFIDBridgeControl.exe`.
5. In the app:
   - Select your COM port
   - Keep Baud at `115200` (unless your hardware uses another value)
   - Keep Backend as `pyautogui`
   - Keep Focus Delay at `3.0`
   - Enable "Append Enter" if you want Enter key after each scan
6. Click **Start**.
7. Click inside your target text box before countdown ends.
8. Scan a card/tag. UID should appear in that text box.

### 4) Daily Use
1. Plug reader in.
2. Open app.
3. Select COM port.
4. Click **Start**.
5. Scan tags.
6. Click **Stop** when done.

### 5) Optional: Auto Start With Windows
1. Right-click `install_autostart_task.bat`.
2. Run as Administrator.
3. Log out and log back in to verify auto start.

To disable auto start, run `remove_autostart_task.bat` as Administrator.

### 6) If Something Does Not Work
- COM port not showing:
  - Reconnect USB
  - Try another USB cable/port
  - Install `CH34x driver installer` (for CH340/CH341 devices) or the driver from your hardware vendor
  - Click Refresh in app
- Scans not typing:
  - Make sure target text field is selected
  - Increase Focus Delay to `5.0`
  - Try Backend `pydirectinput`
- App closes or errors:
  - Check `rfid_bridge.log` in the same folder and send it to support

### 7) Support Info To Share
When asking for help, share:
- Screenshot of app settings
- COM port name from Device Manager
- `rfid_bridge.log` file