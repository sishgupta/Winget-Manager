"""
Winget Auto Manager
Runs in the system tray and automates 'winget upgrade --all'.

Prerequisites:
    pip install pystray Pillow

Usage:
    Run `python winget_manager.py` to start the tray application.
    Right-click the tray icon to access Settings, upgrade manually, or quit.
"""

import os
import sys
import time
import json
import threading
import subprocess
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Required libraries not found.")
    print("Please run: pip install pystray Pillow")
    sys.exit(1)

# --- Configuration Management ---
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".winget_manager_config.json")

DEFAULT_CONFIG = {
    "interval_days": 1,        # How often to check/upgrade
    "trigger": "idle",         # "idle" or "login"
    "idle_minutes": 5,         # How long to wait before upgrading when idle
    "last_run": 0              # Unix timestamp of the last successful upgrade
}

def load_config():
    """Loads configuration from the JSON file."""
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
        print(f"Failed to load config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Saves configuration to the JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")

# --- System Utilities ---
def get_idle_time_seconds():
    """Returns the system idle time in seconds (Windows only)."""
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        # GetTickCount returns milliseconds since system start
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    return 0

def run_winget_upgrade(icon=None):
    """Executes the winget upgrade command invisibly."""
    if icon:
        icon.notify("Starting background upgrade...", "Winget Auto Manager")
        
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
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            startupinfo=startupinfo
        )
        
        if icon:
            # Check if updates were actually installed or if none were found
            if "No applicable update found" in result.stdout or "No installed package found matching input criteria" in result.stdout:
                icon.notify("All packages are already up to date.", "Winget Auto Manager")
            else:
                icon.notify("Upgrade process finished.", "Winget Auto Manager")
                
        return True
    except Exception as e:
        if icon:
            icon.notify(f"Error running winget: {e}", "Winget Error")
        return False

# --- Background Worker ---
class WorkerThread(threading.Thread):
    def __init__(self, icon):
        super().__init__(daemon=True)
        self.icon = icon
        self.running = True
        self.force_run = False

    def run(self):
        """Main background loop checking for intervals and triggers."""
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
                should_upgrade = True
                self.force_run = False # Reset flag
            elif time_for_update:
                if trigger == 'login':
                    # 'login' means we run immediately once the interval is met
                    # (Assuming the app is placed in the user's Startup folder)
                    should_upgrade = True
                elif trigger == 'idle':
                    # Wait until the user has been away from the keyboard
                    idle_time = get_idle_time_seconds()
                    if idle_time >= (idle_minutes * 60):
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

# --- Tray Icon Application ---
def create_image():
    """Generates an icon dynamically so external .ico files aren't required."""
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), color=(0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    
    # Draw a blue rounded background
    dc.rounded_rectangle((4, 4, 60, 60), radius=10, fill=(0, 120, 215))
    
    # Draw a simple 'W'
    dc.line([(16, 20), (26, 48), (32, 30), (38, 48), (48, 20)], fill="white", width=4, joint="curve")
    return image

def run_tray_app():
    worker = None

    def on_setup(icon):
        nonlocal worker
        icon.visible = True
        worker = WorkerThread(icon)
        worker.start()

    def on_quit(icon, item):
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

    menu = pystray.Menu(
        item('Upgrade Now', on_upgrade_now),
        item('Settings', on_settings),
        pystray.Menu.SEPARATOR,
        item('Quit', on_quit)
    )

    icon = pystray.Icon("Winget Manager", create_image(), "Winget Auto Manager", menu)
    icon.run(setup=on_setup)

# --- Settings GUI ---
def run_settings_gui():
    """A standalone Tkinter GUI for editing settings."""
    root = tk.Tk()
    root.title("Winget Manager Settings")
    root.geometry("340x260")
    root.resizable(False, False)
    
    # Center window on screen
    root.eval('tk::PlaceWindow . center')

    config = load_config()

    # Padding frame
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Interval setting
    ttk.Label(frame, text="Check Interval (Days):").grid(row=0, column=0, sticky=tk.W, pady=5)
    interval_var = tk.IntVar(value=config.get('interval_days', 1))
    interval_spin = ttk.Spinbox(frame, from_=1, to=365, textvariable=interval_var, width=10)
    interval_spin.grid(row=0, column=1, sticky=tk.W, pady=5)

    # Trigger setting
    ttk.Label(frame, text="Trigger upgrade upon:").grid(row=1, column=0, sticky=tk.W, pady=15)
    trigger_var = tk.StringVar(value=config.get('trigger', 'idle'))
    
    ttk.Radiobutton(frame, text="User Login / Startup", variable=trigger_var, value="login").grid(row=2, column=0, columnspan=2, sticky=tk.W)
    ttk.Radiobutton(frame, text="System Idle", variable=trigger_var, value="idle").grid(row=3, column=0, columnspan=2, sticky=tk.W)

    # Idle time setting
    ttk.Label(frame, text="Idle time required (Minutes):").grid(row=4, column=0, sticky=tk.W, pady=(15, 5))
    idle_var = tk.IntVar(value=config.get('idle_minutes', 5))
    idle_spin = ttk.Spinbox(frame, from_=1, to=1440, textvariable=idle_var, width=10)
    idle_spin.grid(row=4, column=1, sticky=tk.W, pady=(15, 5))

    def save_and_close():
        try:
            config['interval_days'] = interval_var.get()
            config['trigger'] = trigger_var.get()
            config['idle_minutes'] = idle_var.get()
            save_config(config)
            messagebox.showinfo("Saved", "Settings saved successfully! They will take effect immediately in the background app.")
            root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")

    # Buttons
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
    
    ttk.Button(btn_frame, text="Save", command=save_and_close).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=root.destroy).pack(side=tk.LEFT, padx=5)

    root.mainloop()

# --- Main Entry Point ---
if __name__ == '__main__':
    # Route logic based on command line arguments
    if '--settings' in sys.argv:
        run_settings_gui()
    else:
        # Prevent multiple instances of the tray app if needed (optional enhancement)
        # Run the standard background tray app
        print("Starting Winget Auto Manager in the system tray...")
        run_tray_app()
