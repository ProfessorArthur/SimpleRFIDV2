import argparse
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional, Tuple

import serial
from serial.tools import list_ports

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


TASK_NAME = "SimpleRFIDBridge"
STARTUP_FILE_NAME = "SimpleRFIDBridge.cmd"


class BridgeGuiApp:
    def __init__(self, root: tk.Tk, start_minimized: bool = False, auto_install_autostart: bool = True) -> None:
        self.root = root
        self.root.title("RFID Bridge Control")
        self.root.geometry("700x520")
        self.root.minsize(560, 430)
        self.root.resizable(True, True)
        self.start_minimized = start_minimized
        self.auto_install_autostart = auto_install_autostart

        icon_path = os.path.join(os.path.dirname(__file__), "rfid.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.bridge_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.running = False
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.last_error: Optional[str] = None
        self.log_file_path = os.path.join(os.path.dirname(__file__), "rfid_bridge.log")
        self.tray_icon = None
        self.tray_thread: Optional[threading.Thread] = None

        self.port_var = tk.StringVar()
        self.backend_var = tk.StringVar(value="pyautogui")
        self.append_enter_var = tk.BooleanVar(value=True)
        self.focus_delay_var = tk.StringVar(value="3.0")
        self.baud_var = tk.StringVar(value="115200")
        self.cooldown_var = tk.StringVar(value="300")
        self.key_interval_var = tk.StringVar(value="0.0")

        self._build_ui()
        self.refresh_ports()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.auto_install_autostart:
            # Register autostart in the background of first launch; no user action needed.
            self.root.after(300, self.ensure_autostart_registered)

        if self.start_minimized and self._tray_supported():
            self.root.after(200, self.hide_to_tray)

    def _startup_file_path(self) -> str:
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
            "Startup",
        )
        return os.path.join(startup_dir, STARTUP_FILE_NAME)

    def _autostart_runner_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{os.path.abspath(sys.executable)}" --tray'

        base_dir = os.path.dirname(os.path.abspath(__file__))
        launcher_bat = os.path.join(base_dir, "start_rfid_gui.bat")
        if os.path.exists(launcher_bat):
            return f'"{launcher_bat}" --tray'

        python_exe = os.path.abspath(sys.executable)
        script_path = os.path.abspath(__file__)
        return f'"{python_exe}" "{script_path}" --tray'

    def _autostart_working_dir(self) -> str:
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))

    def _startup_file_content(self) -> str:
        runner_cmd = self._autostart_runner_command()
        working_dir = self._autostart_working_dir()
        return "\n".join(
            [
                "@echo off",
                f'cd /d "{working_dir}"',
                f"start \"\" {runner_cmd}",
                "exit /b 0",
            ]
        ) + "\n"

    def _startup_file_is_current(self) -> bool:
        startup_file = self._startup_file_path()
        if not os.path.exists(startup_file):
            return False

        expected = self._startup_file_content().replace("\r\n", "\n")
        try:
            with open(startup_file, "r", encoding="utf-8") as fh:
                current = fh.read().replace("\r\n", "\n")
        except Exception:
            return False

        return current == expected

    def _autostart_already_registered(self) -> bool:
        return self._startup_file_is_current()

    def _install_autostart(self) -> Tuple[bool, str]:
        startup_file = self._startup_file_path()
        try:
            os.makedirs(os.path.dirname(startup_file), exist_ok=True)
            with open(startup_file, "w", encoding="utf-8") as fh:
                fh.write(self._startup_file_content())
        except Exception as exc:
            return False, f"Autostart setup failed: {exc}"

        task_registered = False
        try:
            task_runner = f'cmd /c "\"{startup_file}\""'
            create = subprocess.run(
                ["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "ONLOGON", "/TR", task_runner, "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            task_registered = create.returncode == 0
        except Exception:
            task_registered = False

        if os.path.exists(startup_file):
            if task_registered:
                return True, f"Autostart enabled via Startup folder and Task Scheduler: {startup_file}"
            return True, f"Autostart enabled via Startup folder: {startup_file}"

        return False, "Autostart setup failed: could not create Startup launcher."

    def _remove_autostart(self) -> Tuple[bool, str]:
        removed_any = False

        try:
            delete = subprocess.run(
                ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            if delete.returncode == 0:
                removed_any = True
        except Exception:
            pass

        startup_file = self._startup_file_path()
        try:
            if os.path.exists(startup_file):
                os.remove(startup_file)
                removed_any = True
        except Exception as exc:
            return False, f"Could not remove Startup launcher: {exc}"

        if removed_any:
            return True, "Autostart removed."
        return True, "Autostart was not configured."

    def ensure_autostart_registered(self) -> None:
        if self._autostart_already_registered():
            return

        success, details = self._install_autostart()
        self.append_log(details)

    def on_enable_autostart(self) -> None:
        if self._autostart_already_registered():
            self.append_log("Autostart is already configured.")
            messagebox.showinfo("Autostart", "Autostart is already configured.")
            return

        self._run_with_loading_modal(
            title="Autostart",
            message="Enabling autostart. Please wait...",
            work=self._install_autostart,
            on_complete=self._finish_autostart_action,
        )

    def on_remove_autostart(self) -> None:
        self._run_with_loading_modal(
            title="Autostart",
            message="Removing autostart. Please wait...",
            work=self._remove_autostart,
            on_complete=self._finish_autostart_action,
        )

    def _finish_autostart_action(self, result: Tuple[bool, str]) -> None:
        success, details = result
        self.append_log(details)
        if success:
            messagebox.showinfo("Autostart", details)
        else:
            messagebox.showerror("Autostart", details)

    def _build_uninstall_script(self, exe_path: str) -> Tuple[bool, str]:
        startup_file = self._startup_file_path()
        script_path = os.path.join(tempfile.gettempdir(), "SimpleRFIDBridge_uninstall.cmd")

        lines = [
            "@echo off",
            "setlocal",
            f'set "TASK_NAME={TASK_NAME}"',
            f'set "STARTUP_FILE={startup_file}"',
            f'set "APP_EXE={exe_path}"',
            "schtasks /Delete /TN \"%TASK_NAME%\" /F >nul 2>nul",
            "if exist \"%STARTUP_FILE%\" del /f /q \"%STARTUP_FILE%\" >nul 2>nul",
            "timeout /t 2 /nobreak >nul",
            "del /f /q \"%APP_EXE%\" >nul 2>nul",
            "for %%I in (\"%APP_EXE%\") do set \"APP_DIR=%%~dpI\"",
            "rd \"%APP_DIR%\" >nul 2>nul",
            "exit /b 0",
        ]

        try:
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        except Exception as exc:
            return False, f"Could not create uninstall script: {exc}"

        return True, script_path

    def on_uninstall_app(self) -> None:
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Uninstall",
                "Uninstall is available only in the packaged EXE build."
                "\n\nYou are running from source, so just delete the project folder when not needed.",
            )
            return

        confirmed = messagebox.askyesno(
            "Uninstall",
            "This will remove autostart and delete this EXE after the app closes. Continue?",
        )
        if not confirmed:
            return

        def uninstall_work() -> Tuple[bool, str]:
            exe_path = os.path.abspath(sys.executable)
            script_ok, script_or_error = self._build_uninstall_script(exe_path)
            if not script_ok:
                return False, script_or_error

            try:
                creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                    subprocess, "DETACHED_PROCESS", 0
                )
                subprocess.Popen(
                    ["cmd", "/c", script_or_error],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags,
                )
            except Exception as exc:
                return False, f"Failed to start uninstall script: {exc}"

            return True, "Uninstall started. The app will close now."

        def on_uninstall_complete(result: Tuple[bool, str]) -> None:
            success, details = result
            self.append_log(details)
            if not success:
                messagebox.showerror("Uninstall", details)
                return

            self.stop_bridge()
            self._stop_tray()
            self.root.after(250, self.root.destroy)

        self._run_with_loading_modal(
            title="Uninstall",
            message="Preparing uninstall. Please wait...",
            work=uninstall_work,
            on_complete=on_uninstall_complete,
        )

    def _run_with_loading_modal(
        self,
        title: str,
        message: str,
        work: Callable[[], Any],
        on_complete: Callable[[Any], None],
    ) -> None:
        modal = tk.Toplevel(self.root)
        modal.title(title)
        modal.transient(self.root)
        modal.resizable(False, False)
        modal.grab_set()
        modal.protocol("WM_DELETE_WINDOW", lambda: None)

        body = ttk.Frame(modal, padding=14)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text=message, justify=tk.LEFT).pack(anchor="w")
        progress = ttk.Progressbar(body, mode="indeterminate", length=250)
        progress.pack(fill=tk.X, pady=(10, 0))
        progress.start(10)

        modal.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - modal.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - modal.winfo_height()) // 2
        modal.geometry(f"+{max(0, x)}+{max(0, y)}")

        result_queue: queue.Queue[Tuple[bool, Any]] = queue.Queue()

        def worker() -> None:
            try:
                result_queue.put((True, work()))
            except Exception as exc:
                result_queue.put((False, exc))

        threading.Thread(target=worker, daemon=True).start()

        def poll_result() -> None:
            try:
                success, payload = result_queue.get_nowait()
            except queue.Empty:
                self.root.after(100, poll_result)
                return

            progress.stop()
            try:
                modal.grab_release()
            except Exception:
                pass
            modal.destroy()

            if success:
                on_complete(payload)
                return

            details = f"{type(payload).__name__}: {payload}"
            self.append_log(f"{title} failed: {details}")
            messagebox.showerror(title, f"{title} failed.\n\n{details}")

        self.root.after(100, poll_result)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(frame, text="RFID Serial Bridge", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="COM Port").grid(row=1, column=0, sticky="w", pady=4)
        self.port_box = ttk.Combobox(frame, textvariable=self.port_var, state="readonly", width=28)
        self.port_box.grid(row=1, column=1, sticky="w", pady=4)
        ttk.Button(frame, text="Refresh", command=self.refresh_ports).grid(row=1, column=2, sticky="w", padx=(8, 0))

        ttk.Label(frame, text="Baud").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.baud_var, width=12).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Backend").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frame,
            textvariable=self.backend_var,
            values=["pyautogui", "pydirectinput"],
            state="readonly",
            width=20,
        ).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Focus Delay (s)").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.focus_delay_var, width=12).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Cooldown (ms)").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.cooldown_var, width=12).grid(row=5, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Key Interval (s)").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.key_interval_var, width=12).grid(row=6, column=1, sticky="w", pady=4)

        ttk.Checkbutton(frame, text="Append Enter after UID", variable=self.append_enter_var).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(8, 6)
        )

        button_row = ttk.Frame(frame)
        button_row.grid(row=8, column=0, columnspan=3, sticky="w", pady=(6, 10))

        self.start_btn = ttk.Button(button_row, text="Start", command=self.start_bridge)
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(button_row, text="Stop", command=self.stop_bridge, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.tray_btn = ttk.Button(button_row, text="Tray", command=self.hide_to_tray)
        self.tray_btn.pack(side=tk.LEFT, padx=(8, 0))

        maintenance_row = ttk.Frame(frame)
        maintenance_row.grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.enable_autostart_btn = ttk.Button(
            maintenance_row,
            text="Enable Autostart",
            command=self.on_enable_autostart,
        )
        self.enable_autostart_btn.pack(side=tk.LEFT)

        self.remove_autostart_btn = ttk.Button(
            maintenance_row,
            text="Remove Autostart",
            command=self.on_remove_autostart,
        )
        self.remove_autostart_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.uninstall_btn = ttk.Button(
            maintenance_row,
            text="Uninstall App",
            command=self.on_uninstall_app,
        )
        self.uninstall_btn.pack(side=tk.LEFT, padx=(8, 0))
        if not getattr(sys, "frozen", False):
            self.uninstall_btn.configure(state=tk.DISABLED)

        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(frame, textvariable=self.status_var, foreground="#0c5").grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(2, 8)
        )

        ttk.Label(frame, text="Bridge Output").grid(row=11, column=0, sticky="w")
        log_frame = ttk.Frame(frame)
        log_frame.grid(row=12, column=0, columnspan=3, sticky="nsew", pady=(4, 0))

        self.log = tk.Text(log_frame, height=10, width=62, wrap=tk.NONE, state=tk.DISABLED)
        self.log.grid(row=0, column=0, sticky="nsew")

        log_scroll_y = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log.yview)
        log_scroll_y.grid(row=0, column=1, sticky="ns")
        log_scroll_x = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.log.xview)
        log_scroll_x.grid(row=1, column=0, sticky="ew")

        self.log.configure(yscrollcommand=log_scroll_y.set, xscrollcommand=log_scroll_x.set)

        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(12, weight=1)

    def refresh_ports(self) -> None:
        ports = [p.device for p in list_ports.comports()]
        self.port_box["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])

    def append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + " | " + text + "\n")
        except Exception:
            pass

    def validate_inputs(self) -> Tuple[bool, str]:
        if not self.port_var.get():
            return False, "Please select a COM port."

        try:
            int(self.baud_var.get())
        except ValueError:
            return False, "Baud must be a number."

        try:
            float(self.focus_delay_var.get())
        except ValueError:
            return False, "Focus Delay must be a number."

        try:
            int(self.cooldown_var.get())
        except ValueError:
            return False, "Cooldown must be a number."

        try:
            float(self.key_interval_var.get())
        except ValueError:
            return False, "Key Interval must be a number."

        return True, ""

    def normalize_uid(self, line: str) -> Optional[str]:
        cleaned = line.strip().upper()
        if not cleaned:
            return None

        if cleaned.startswith("TAG:"):
            cleaned = cleaned[4:].strip()
        if cleaned.startswith("UID:"):
            cleaned = cleaned[4:].strip()

        cleaned = cleaned.replace(" ", "")

        if 8 <= len(cleaned) <= 20 and all(c in "0123456789ABCDEF" for c in cleaned):
            return cleaned

        return None

    def _tray_supported(self) -> bool:
        return pystray is not None and Image is not None

    def _create_tray_image(self):
        icon_path = os.path.join(os.path.dirname(__file__), "rfid.ico")
        if Image is not None and os.path.exists(icon_path):
            try:
                return Image.open(icon_path)
            except Exception:
                pass

        if Image is None or ImageDraw is None:
            return None

        image = Image.new("RGB", (64, 64), color=(24, 130, 96))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 54, 54), outline=(255, 255, 255), width=3)
        draw.rectangle((20, 20, 44, 44), outline=(255, 255, 255), width=2)
        return image

    def _ensure_tray(self) -> None:
        if not self._tray_supported() or self.tray_icon is not None:
            return

        tray_mod = pystray
        if tray_mod is None:
            return

        def on_show(icon, item) -> None:
            self.root.after(0, self.show_from_tray)

        def on_exit(icon, item) -> None:
            self.root.after(0, self.quit_from_tray)

        menu = tray_mod.Menu(
            tray_mod.MenuItem("Show", on_show),
            tray_mod.MenuItem("Exit", on_exit),
        )

        self.tray_icon = tray_mod.Icon(
            "SimpleRFIDBridge",
            self._create_tray_image(),
            "RFID Bridge Control",
            menu,
        )
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()

    def _stop_tray(self) -> None:
        if self.tray_icon is None:
            return
        try:
            self.tray_icon.stop()
        except Exception:
            pass
        self.tray_icon = None

    def hide_to_tray(self) -> None:
        if not self._tray_supported():
            messagebox.showwarning(
                "Tray Not Available",
                "Tray mode is unavailable because pystray is not installed in this build.",
            )
            return

        self._ensure_tray()
        self.root.withdraw()
        self.append_log("Window minimized to tray.")

    def show_from_tray(self) -> None:
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass

    def quit_from_tray(self) -> None:
        self.stop_bridge()
        self._stop_tray()
        self.root.after(350, self.root.destroy)

    def type_uid(self, backend, uid: str, append_enter: bool, key_interval: float) -> None:
        backend.typewrite(uid, interval=key_interval)
        if append_enter:
            backend.press("enter")

    def bridge_worker(
        self,
        port: str,
        baud: int,
        backend_name: str,
        append_enter: bool,
        focus_delay: float,
        cooldown_ms: int,
        key_interval: float,
    ) -> None:
        try:
            if backend_name == "pyautogui":
                import pyautogui as backend
            else:
                import pydirectinput as backend

            self.output_queue.put(f"Connecting to {port} @ {baud}...")
            ser = serial.Serial(port, baud, timeout=1)
        except Exception as exc:
            self.output_queue.put(f"Start failed ({type(exc).__name__}): {exc}")
            self.output_queue.put(traceback.format_exc().strip())
            self.running = False
            return

        try:
            time.sleep(2.0)
            ser.reset_input_buffer()

            if focus_delay > 0:
                self.output_queue.put(f"Focus target field. Starting in {focus_delay:.1f}s...")
                end_at = time.time() + focus_delay
                while time.time() < end_at:
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.05)

            self.output_queue.put("Bridge running.")

            last_uid = ""
            last_ms = 0

            while not self.stop_event.is_set():
                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                uid = self.normalize_uid(line)
                if not uid:
                    continue

                now_ms = int(time.time() * 1000)
                if uid == last_uid and (now_ms - last_ms) < cooldown_ms:
                    continue

                self.output_queue.put(f"UID: {uid}")
                self.type_uid(backend, uid, append_enter, key_interval)
                last_uid = uid
                last_ms = now_ms

        except Exception as exc:
            self.output_queue.put(f"Runtime error ({type(exc).__name__}): {exc}")
            self.output_queue.put(traceback.format_exc().strip())
        finally:
            try:
                ser.close()
            except Exception:
                pass
            self.running = False
            self.output_queue.put("Bridge stopped.")

    def start_bridge(self) -> None:
        if self.running:
            return

        is_valid, err = self.validate_inputs()
        if not is_valid:
            messagebox.showerror("Invalid Settings", err)
            return

        self.append_log("Starting bridge...")
        self.stop_event.clear()
        self.running = True

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.status_var.set("Running")
        self.append_log(f"Running on {self.port_var.get()}")

        self.bridge_thread = threading.Thread(
            target=self.bridge_worker,
            args=(
                self.port_var.get(),
                int(self.baud_var.get()),
                self.backend_var.get(),
                self.append_enter_var.get(),
                float(self.focus_delay_var.get()),
                int(self.cooldown_var.get()),
                float(self.key_interval_var.get()),
            ),
            daemon=True,
        )
        self.bridge_thread.start()

        self.root.after(150, self.poll_output)
        self.root.after(1000, self.poll_process)

    def poll_output(self) -> None:
        drained = 0
        while drained < 60:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            self.append_log(line)
            if line.startswith("Start failed") or line.startswith("Runtime error"):
                self.last_error = line
            drained += 1

        if self.running:
            self.root.after(150, self.poll_output)

    def poll_process(self) -> None:
        if self.running:
            self.root.after(1000, self.poll_process)
            return

        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.status_var.set("Stopped")
        if self.last_error:
            messagebox.showerror("Bridge Error", self.last_error)
            self.last_error = None

    def stop_bridge(self) -> None:
        if not self.running:
            return

        self.append_log("Stopping bridge...")
        self.stop_event.set()

    def on_close(self) -> None:
        if self._tray_supported():
            self.hide_to_tray()
            return

        self.stop_bridge()
        self.root.after(350, self.root.destroy)


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--skip-autostart-install", action="store_true")
    args, _ = parser.parse_known_args()

    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")

    app = BridgeGuiApp(
        root,
        start_minimized=args.tray,
        auto_install_autostart=not args.skip_autostart_install,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
