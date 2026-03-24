import argparse
import re
import sys
import time
from typing import Optional

import serial
from serial.tools import list_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read RFID UIDs from serial and type them into the active window."
    )
    parser.add_argument("--port", help="Serial port, e.g. COM3", default=None)
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument(
        "--append-enter",
        action="store_true",
        help="Press Enter after typing each UID",
    )
    parser.add_argument(
        "--backend",
        choices=["pyautogui", "pydirectinput"],
        default="pyautogui",
        help="Typing backend library",
    )
    parser.add_argument(
        "--key-interval",
        type=float,
        default=0.0,
        help="Delay between typed characters",
    )
    parser.add_argument(
        "--cooldown-ms",
        type=int,
        default=300,
        help="Ignore duplicate UID during this cooldown window",
    )
    parser.add_argument(
        "--focus-delay",
        type=float,
        default=3.0,
        help="Seconds to wait so you can focus the target input field",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List available serial ports and exit",
    )
    return parser.parse_args()


def print_ports() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return

    print("Available serial ports:")
    for p in ports:
        desc = f" - {p.description}" if p.description else ""
        print(f"  {p.device}{desc}")


def normalize_uid(line: str) -> Optional[str]:
    line = line.strip().upper()
    if not line:
        return None

    if line.startswith("TAG:"):
        line = line[4:].strip()
    if line.startswith("UID:"):
        line = line[4:].strip()

    line = line.replace(" ", "")

    if re.fullmatch(r"[0-9A-F]{8,20}", line):
        return line
    return None


def load_backend(name: str):
    if name == "pyautogui":
        import pyautogui

        return pyautogui

    import pydirectinput

    return pydirectinput


def type_uid(backend_name: str, backend, uid: str, append_enter: bool, key_interval: float) -> None:
    backend.typewrite(uid, interval=key_interval)
    if append_enter:
        backend.press("enter")


def main() -> int:
    args = parse_args()

    if args.list_ports:
        print_ports()
        return 0

    if not args.port:
        print("Error: --port is required unless --list-ports is used.")
        return 1

    backend = load_backend(args.backend)

    print(f"Connecting to {args.port} @ {args.baud}...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as exc:
        print(f"Failed to open serial port: {exc}")
        return 1

    # Allow board reset and serial stabilization.
    time.sleep(2.0)
    ser.reset_input_buffer()

    if args.focus_delay > 0:
        print(f"Focus your target field now. Starting in {args.focus_delay:.1f}s...")
        time.sleep(args.focus_delay)

    print("Bridge running. Press Ctrl+C to stop.")

    last_uid = ""
    last_ms = 0

    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="ignore").strip()
            uid = normalize_uid(line)
            if not uid:
                continue

            now_ms = int(time.time() * 1000)
            if uid == last_uid and (now_ms - last_ms) < args.cooldown_ms:
                continue

            print(f"UID: {uid}")
            type_uid(args.backend, backend, uid, args.append_enter, args.key_interval)

            last_uid = uid
            last_ms = now_ms

    except KeyboardInterrupt:
        print("\nStopping bridge.")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    sys.exit(main())
