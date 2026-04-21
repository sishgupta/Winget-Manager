"""
Winget Manager v2
Runs in the system tray, automates 'winget upgrade --all', logs activity, and supports autostart.

Prerequisites:
    pip install pystray Pillow

Usage:
    Save as winget_manager.pyw to run natively without a console, or just run normally 
    and it will attempt to hide its own console.
"""

import os
import sys
import time
import json
import threading
import subprocess
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
import winreg

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
except ImportError:
    # If modules are missing, we still try to show a basic Tkinter error box
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror("Missing Libraries", "Required libraries not found.\nPlease run: pip install pystray Pillow")
    sys.exit(1)

# --- Paths & Logging Setup ---
USER_DIR = os.path.expanduser("~")
CONFIG_FILE = os.path.join(USER_DIR, ".winget_manager_config.json")
LOG_FILE = os.path.join(USER_DIR, ".winget_manager.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Configuration Management ---
DEFAULT_CONFIG = {
    "interval_days": 1,
    "trigger": "idle",
    "idle_minutes": 5,
    "last_run": 0
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure all default keys exist in case of updates
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")

# --- Autostart Management ---
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WingetManager"

def set_autostart(enable=True):
    """Enables or disables running the script on Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            # Force usage of pythonw.exe to ensure no console is spawned on startup
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            script_path = os.path.abspath(__file__)
            # Quotes around paths to handle spaces
            cmd = f'"{python_exe}" "{script_path}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            logging.info("Autostart enabled in registry.")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logging.info("Autostart disabled in registry.")
            except FileNotFoundError:
                pass # Already disabled
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logging.error(f"Failed to toggle autostart: {e}")
        return False

def get_autostart_status():
    """Checks if the app is set to run on startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logging.error(f"Error checking autostart status: {e}")
        return False

# --- System Utilities ---
def hide_console():
    """Hides the console window if running directly from python.exe."""
    if sys.platform == "win32":
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0) # 0 = SW_HIDE
        except Exception as e:
            logging.error(f"Could not hide console: {e}")

def get_idle_time_seconds():
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        # GetTickCount returns milliseconds since system start
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    return 0

def notify_and_log(icon, message, title, level="info"):
    """Handles both system tray notifications and logging."""
    if level == "error":
        logging.error(message)
    else:
        logging.info(message)
        
    if icon:
        icon.notify(message, title)

def run_winget_upgrade(icon=None):
    notify_and_log(icon, "Starting background Winget upgrade...", "Winget Manager")
        
    try:
        # Create StartupInfo to hide the console window completely
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Build the command. 
        # --silent tries to prevent package installer GUIs.
        # --accept-package-agreements and --accept-source-agreements bypass prompts.
        cmd = [
            "winget", "upgrade", "--all", 
            "--include-unknown", 
            "--accept-package-agreements", 
            "--accept-source-agreements", 
            "--silent"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)

        # Check if updates were actually installed or if none were found
        if "No applicable update found" in result.stdout or "No installed package found matching input criteria" in result.stdout:
            notify_and_log(icon, "All packages are already up to date.", "Winget Manager")
        else:
            notify_and_log(icon, "Upgrade process finished successfully.", "Winget Manager")
            logging.info(f"Winget output: {result.stdout.strip()}")
            
        return True
    except Exception as e:
        notify_and_log(icon, f"Error running winget: {e}", "Winget Error", level="error")
        return False

# --- Background Worker ---
class WorkerThread(threading.Thread):
    def __init__(self, icon):
        super().__init__(daemon=True)
        self.icon = icon
        self.running = True
        self.force_run = False

    def run(self):
        logging.info("Background worker thread started.")
        while self.running:
            config = load_config()
            now = time.time()
            interval_seconds = config['interval_days'] * 86400
            last_run = config['last_run']
            trigger = config['trigger']
            idle_minutes = config['idle_minutes']

            # Has enough time passed since the last upgrade?
            time_for_update = (now - last_run) >= interval_seconds
            should_upgrade = False

            if self.force_run:
                logging.info("User requested forced upgrade.")
                should_upgrade = True
                self.force_run = False # Reset flag
            elif time_for_update:
                if trigger == 'login':
                    # 'login' means we run immediately once the interval is met
                    # (Assuming the app is placed in the user's Startup folder)
                    logging.info("Interval met. Trigger: Login. Executing upgrade.")
                    should_upgrade = True
                elif trigger == 'idle':
                    # Wait until the user has been away from the keyboard
                    idle_time = get_idle_time_seconds()
                    if idle_time >= (idle_minutes * 60):
                        logging.info(f"Interval met. Trigger: Idle ({idle_minutes} min). Executing upgrade.")
                        should_upgrade = True

            if should_upgrade:
                success = run_winget_upgrade(self.icon)
                if success:
                    # Update the last_run timestamp upon success
                    config['last_run'] = time.time()
                    save_config(config)

            # Sleep for a minute before checking conditions again
            # Using small sleeps to allow quick thread termination if needed
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(1)

    def trigger_force_run(self):
        self.force_run = True

# --- UI Functions ---
def create_image():
    # Generate icon dynamically so external .ico files aren't required
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), color=(0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
     # Draw a blue rounded background
    dc.rounded_rectangle((4, 4, 60, 60), radius=10, fill=(0, 120, 215))
    # Draw a simple 'W'
    dc.line([(16, 20), (26, 48), (32, 30), (38, 48), (48, 20)], fill="white", width=4, joint="curve")
    return image

def run_logs_gui():
    """A standalone Tkinter GUI to view the log file."""
    root = tk.Tk()
    root.title("Winget Manager Logs")
    root.geometry("600x400")
    root.eval('tk::PlaceWindow . center')

    text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
    text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    try:
        with open(LOG_FILE, 'r') as f:
            text_area.insert(tk.INSERT, f.read())
    except FileNotFoundError:
        text_area.insert(tk.INSERT, "Log file is empty or does not exist yet.")

    text_area.configure(state='disabled') # Read-only
    
    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=10)
    ttk.Button(btn_frame, text="Close", command=root.destroy).pack()

    root.mainloop()

def run_settings_gui():
    """A standalone Tkinter GUI for editing settings."""
    root = tk.Tk()
    root.title("Winget Manager Settings")
    root.geometry("360x320")
    root.resizable(False, False)
    root.eval('tk::PlaceWindow . center')

    config = load_config()
    
    # Padding frame
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # --- Schedule Settings ---
    # Interval setting
    ttk.Label(frame, text="Check Interval (Days):").grid(row=0, column=0, sticky=tk.W, pady=5)
    interval_var = tk.IntVar(value=config.get('interval_days', 1))
    ttk.Spinbox(frame, from_=1, to=365, textvariable=interval_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)
    
    # Trigger setting
    ttk.Label(frame, text="Trigger upgrade upon:").grid(row=1, column=0, sticky=tk.W, pady=(15, 0))
    trigger_var = tk.StringVar(value=config.get('trigger', 'idle'))
    ttk.Radiobutton(frame, text="System Startup", variable=trigger_var, value="login").grid(row=2, column=0, columnspan=2, sticky=tk.W)
    ttk.Radiobutton(frame, text="System Idle", variable=trigger_var, value="idle").grid(row=3, column=0, columnspan=2, sticky=tk.W)

    # Idle Time setting
    ttk.Label(frame, text="Idle time required (Minutes):").grid(row=4, column=0, sticky=tk.W, pady=(15, 5))
    idle_var = tk.IntVar(value=config.get('idle_minutes', 5))
    ttk.Spinbox(frame, from_=1, to=1440, textvariable=idle_var, width=10).grid(row=4, column=1, sticky=tk.W, pady=(15, 5))

    # Autostart Setting
    ttk.Separator(frame, orient='horizontal').grid(row=5, column=0, columnspan=2, sticky="ew", pady=15)
    
    autostart_var = tk.BooleanVar(value=get_autostart_status())
    ttk.Checkbutton(frame, text="Run automatically on Windows start", variable=autostart_var).grid(row=6, column=0, columnspan=2, sticky=tk.W)

    def save_and_close():
        try:
            config['interval_days'] = interval_var.get()
            config['trigger'] = trigger_var.get()
            config['idle_minutes'] = idle_var.get()
            save_config(config)
            
            # Handle Autostart toggle
            set_autostart(autostart_var.get())
            
            messagebox.showinfo("Saved", "Settings saved successfully!\nCheck intervals will take effect immediately.")
            root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
    ttk.Button(btn_frame, text="Save", command=save_and_close).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=root.destroy).pack(side=tk.LEFT, padx=5)

    root.mainloop()

# --- Main App & Menu Routing ---
def run_tray_app():
    hide_console() # Attempt to hide the console right away
    logging.info("Starting System Tray Application...")
    worker = None

    def on_setup(icon):
        nonlocal worker
        icon.visible = True
        worker = WorkerThread(icon)
        worker.start()

    def on_quit(icon, item):
        logging.info("Application quit by user.")
        if worker:
            worker.running = False
        icon.stop()

    def on_upgrade_now(icon, item):
        if worker:
            worker.trigger_force_run()

    def on_settings(icon, item):
        # We launch the settings GUI in a separate process to avoid 
        # complex threading conflicts between pystray and tkinter.
        subprocess.Popen([sys.executable, __file__, '--settings'])

    def on_view_logs(icon, item):
        # We launch the logs GUI in a separate process to avoid 
        # complex threading conflicts between pystray and tkinter.
        subprocess.Popen([sys.executable, __file__, '--logs'])

    menu = pystray.Menu(
        item('Upgrade Now', on_upgrade_now),
        pystray.Menu.SEPARATOR,
        item('Settings', on_settings),
        item('View Logs', on_view_logs),
        pystray.Menu.SEPARATOR,
        item('Quit', on_quit)
    )

    icon = pystray.Icon("Winget Manager", create_image(), "Winget Manager", menu)
    icon.run(setup=on_setup)

if __name__ == '__main__':
    # Route logic to avoid pystray and tkinter running in the same thread
    if '--settings' in sys.argv:
        hide_console()
        run_settings_gui()
    elif '--logs' in sys.argv:
        hide_console()
        run_logs_gui()
    else:
        run_tray_app()
