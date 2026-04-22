"""
Winget Manager v3
Runs in the system tray, automates 'winget upgrade --all', logs activity, and supports autostart.

Prerequisites:
    pip install pystray Pillow customtkinter requests packaging

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
from tkinter import messagebox
import logging
import winreg
import atexit
import signal
import webbrowser
import socket
import re

APP_VERSION = "2026.04.22.01"

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw, ImageTk
    import customtkinter as ctk
    import requests
    from packaging import version
except ImportError:
    # If modules are missing, we still try to show a basic Tkinter error box
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror("Missing Libraries", "Required libraries not found.\nPlease run: pip install pystray Pillow customtkinter requests packaging")
    sys.exit(1)

# --- Paths & Logging Setup ---
USER_DIR = os.path.expanduser("~")
CONFIG_FILE = os.path.join(USER_DIR, ".winget_manager_config.json")
LOG_FILE = os.path.join(USER_DIR, ".winget_manager.log")
PID_FILE = os.path.join(USER_DIR, ".winget_manager.pid")

class NoLockFileHandler(logging.Handler):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        
    def emit(self, record):
        try:
            with open(self.filename, 'a', encoding="utf-8") as f:
                f.write(self.format(record) + '\n')
        except Exception:
            pass

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
handler = NoLockFileHandler(LOG_FILE)
handler.setFormatter(formatter)
logger.addHandler(handler)

is_graceful_exit = False

def cleanup_pid():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass

def on_system_exit(*args):
    """Logs termination when the OS reboots or shuts down the background process."""
    # Only clean up PID from the main tray process, not UI subprocesses
    if not any(arg in sys.argv for arg in ['--settings', '--logs', '--about']):
        cleanup_pid()
        
    if not is_graceful_exit:
        logging.info("Application is shutting down or terminating (System exit/reboot).")

def register_exit_hooks():
    atexit.register(on_system_exit)
    try:
        signal.signal(signal.SIGTERM, on_system_exit)
        signal.signal(signal.SIGINT, on_system_exit)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, on_system_exit)
    except Exception:
        pass

# --- Configuration Management ---
DEFAULT_CONFIG = {
    "interval_days": 1,
    "trigger": "idle",
    "idle_minutes": 5,
    "last_run": 0,
    "require_ac_power": False,
    "require_network": True,
    "updater_frequency_days": 7,
    "updater_last_check": 0,
    "updater_auto_restart": False
}

def load_config():
    """
    Loads configuration from the JSON file.
    If the file doesn't exist, it creates one with default settings.
    It also fills in any missing keys with their default values to ensure compatibility with updates.
    """
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """
    Saves the provided configuration dictionary to the JSON file.
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")

# --- Autostart Management ---
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WingetManager"

def set_autostart(enable=True):
    """
    Enables or disables autostart on Windows by modifying the CurrentUser Run registry key.
    Points to pythonw.exe to ensure no console window flashes on boot.
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            script_path = os.path.abspath(__file__)
            cmd = f'"{python_exe}" "{script_path}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            logging.info("Autostart enabled in registry.")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logging.info("Autostart disabled in registry.")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logging.error(f"Failed to toggle autostart: {e}")
        return False

def get_autostart_status():
    """
    Checks the registry to see if the application is currently set to run on Windows startup.
    """
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
class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), 
                ("BatteryFlag", ctypes.c_byte), 
                ("BatteryLifePercent", ctypes.c_byte), 
                ("SystemStatusFlag", ctypes.c_byte), 
                ("BatteryLifeTime", ctypes.c_ulong), 
                ("BatteryFullLifeTime", ctypes.c_ulong)]

def is_on_ac_power():
    """Returns True if the system is plugged into AC power or if unable to determine."""
    if sys.platform != "win32":
        return True
    status = SYSTEM_POWER_STATUS()
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return status.ACLineStatus != 0 # 0 means offline (battery)
    return True

def is_network_connected():
    """Check for active internet using the Microsoft NCSI payload over HTTP."""
    try:
        requests.get("http://www.msftconnecttest.com/connecttest.txt", timeout=3)
        return True
    except requests.RequestException:
        return False

def hide_console():
    """
    Attempts to hide the terminal console window on Windows.
    This is useful when the script is run directly via python.exe instead of pythonw.exe,
    or during subprocess creation.
    """
    if sys.platform == "win32":
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception as e:
            logging.error(f"Could not hide console: {e}")

def get_idle_time_seconds():
    """
    Calculates how long the user has been idle (no mouse or keyboard input).
    Uses the Windows GetLastInputInfo API.
    """
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF
        return millis / 1000.0
    return 0

def notify_and_log(icon, message, title, level="info"):
    """
    Helper function to simultaneously write a message to the local .log file 
    and push a system tray notification to the user.
    """
    if level == "error":
        logging.error(message)
    else:
        logging.info(message)
        
    if icon:
        icon.notify(message, title)

def run_winget_upgrade(icon=None):
    """
    Executes the 'winget upgrade --all' command silently.
    Filters out the progress bar elements of stdout, counts successful installs,
    and reports the results via the system tray.
    """
    notify_and_log(icon, "Starting background Winget upgrade...", "Winget Manager")
        
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Removed --silent to parse stdout correctly in case of real setups, but kept prompts auto-accepted
        cmd = [
            "winget", "upgrade", "--all", 
            "--include-unknown", 
            "--accept-package-agreements", 
            "--accept-source-agreements"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)
        
        if "No applicable update found" in result.stdout or "No installed package found matching input criteria" in result.stdout:
            notify_and_log(icon, "All packages are already up to date.", "Winget Manager")
        else:
            # Parse for actual upgrades
            success_count = result.stdout.count("Successfully installed")
            filtered_lines = [line for line in result.stdout.strip().split('\n') if not line.startswith(' ')]
            filtered_output = '\n'.join(filtered_lines)
            logging.info(f"Winget output:\n{filtered_output}")
            
            if success_count > 0:
                notify_and_log(icon, f"Upgrade finished! Successfully updated {success_count} package(s).", "Update Complete")
            else:
                notify_and_log(icon, "Upgrade process finished.", "Winget Manager")
            
        return True
    except Exception as e:
        notify_and_log(icon, f"Error running winget: {e}", "Winget Error", level="error")
        return False

# --- Self Updater ---
def fetch_remote_update():
    """Fetches the latest file from GitHub and returns (remote_version_string, file_content_string)."""
    GITHUB_RAW_URL = "https://raw.githubusercontent.com/sishgupta/Winget-Manager/main/winget_manager.pyw"
    try:
        resp = requests.get(GITHUB_RAW_URL, timeout=10)
        if resp.status_code == 200:
            match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', resp.text)
            if match:
                return match.group(1), resp.text
    except Exception as e:
        logging.error(f"Failed to fetch remote update: {e}")
    return None, None

def apply_update_and_restart(code, icon=None):
    """Writes the given script code to the local file, kills existing tray apps, and restarts."""
    try:
        tmp_file = __file__ + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(code)
            
        # Try to taskkill the main tray app if it exists (and it's not us)
        try:
            if os.path.exists(PID_FILE):
                with open(PID_FILE, 'r') as f:
                    main_pid = int(f.read().strip())
                if main_pid != os.getpid():
                    subprocess.run(['taskkill', '/PID', str(main_pid), '/F'], capture_output=True)
                os.remove(PID_FILE)
        except Exception as e:
            logging.error(f"Failed to kill main tray app during update: {e}")

        time.sleep(1.0) # Give Windows time to release the file lock
        for _ in range(4):
            try:
                os.replace(tmp_file, __file__)
                break
            except Exception:
                time.sleep(1.0)
        
        # Start new instance
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        subprocess.Popen([python_exe, __file__])
        
        # Cleanly shut down current process
        if icon:
            icon.visible = False
            icon.stop()
        os._exit(0)
    except Exception as e:
        logging.error(f"Failed to apply update: {e}")

def check_for_self_updates(icon, auto_apply):
    """
    Checks the GitHub repository for a newer version of winget_manager.pyw.
    Supports checking the remote APP_VERSION string and safely comparing it with the local version.
    Can either notify the user or auto-apply the update and restart the script.
    """
    logging.info("Checking GitHub for self-updates...")
    remote_version, code = fetch_remote_update()
    
    if remote_version:
        if version.parse(remote_version) > version.parse(APP_VERSION):
            if auto_apply:
                notify_and_log(icon, f"Applying new update: v{remote_version}", "Self Updater")
                apply_update_and_restart(code, icon)
            else:
                notify_and_log(icon, f"A new version (v{remote_version}) is available. Pull from GitHub to update.", "Update Available")
        else:
            logging.info("You are running the latest version.")

# --- Background Worker ---
class WorkerThread(threading.Thread):
    def __init__(self, icon, update_icon_callback):
        super().__init__(daemon=True)
        self.icon = icon
        self.update_icon_callback = update_icon_callback
        self.running = True
        self.force_run = False

    def run(self):
        logging.info("Background worker thread started.")
        
        # Initialize previous states for transition-based triggers
        prev_idle_sec = get_idle_time_seconds()
        prev_ac_state = is_on_ac_power()
        prev_net_state = is_network_connected()
        startup_handled = False

        while self.running:
            config = load_config()
            now = time.time()
            interval_seconds = config.get('interval_days', 1) * 86400
            last_run = config.get('last_run', 0)
            idle_minutes = config.get('idle_minutes', 5)

            # UI/Config Triggers (with clean defaults)
            trigger_login = config.get('trigger_login', True)
            trigger_idle = config.get('trigger_return_from_idle', False)
            trigger_ac = config.get('trigger_ac_plugin', False)
            trigger_net = config.get('trigger_network_reconnect', False)

            # Get current states
            curr_idle_sec = get_idle_time_seconds()
            curr_ac_state = is_on_ac_power()
            curr_net_state = is_network_connected()

            # Has enough time passed since the last upgrade?
            time_for_update = (now - last_run) >= interval_seconds
            should_upgrade = False

            if self.force_run:
                logging.info("User requested forced upgrade.")
                should_upgrade = True
                self.force_run = False # Reset flag
            elif time_for_update:
                if trigger_login and not startup_handled:
                    logging.info("Interval met. Trigger: System Startup. Executing upgrade.")
                    should_upgrade = True
                elif trigger_idle and prev_idle_sec >= (idle_minutes * 60) and curr_idle_sec <= 65:
                    logging.info(f"Interval met. Trigger: Return from Idle ({idle_minutes} min). Executing upgrade.")
                    should_upgrade = True
                elif trigger_ac and not prev_ac_state and curr_ac_state:
                    logging.info("Interval met. Trigger: AC Power Plugged In. Executing upgrade.")
                    should_upgrade = True
                elif trigger_net and not prev_net_state and curr_net_state:
                    logging.info("Interval met. Trigger: Network Reconnected. Executing upgrade.")
                    should_upgrade = True

            # Evaluate system readiness inhibitors
            if should_upgrade:
                if config.get("require_ac_power", False) and not curr_ac_state:
                    logging.info("Upgrade postponed: System is currently on battery power.")
                    should_upgrade = False
                elif config.get("require_network", True) and not curr_net_state:
                    logging.info("Upgrade postponed: System has no active internet connection.")
                    should_upgrade = False

            if should_upgrade:
                self.update_icon_callback(state="running")
                success = run_winget_upgrade(self.icon)
                
                if success:
                    self.update_icon_callback(state="normal")
                else:
                    self.update_icon_callback(state="error")
                    
                config['last_run'] = time.time()
                save_config(config)

            # Update previous states at the end of the loop tick
            prev_idle_sec = curr_idle_sec
            prev_ac_state = curr_ac_state
            prev_net_state = curr_net_state
            startup_handled = True

            # Check self-updater
            updater_freq = config.get("updater_frequency_days", 7)
            if updater_freq > 0 and (now - config.get("updater_last_check", 0)) > (updater_freq * 86400):
                check_for_self_updates(self.icon, config.get("updater_auto_restart", False))
                config = load_config() # Reload just in case
                config['updater_last_check'] = time.time()
                save_config(config)

            for _ in range(60):
                if not self.running or self.force_run:
                    break
                time.sleep(1)

    def trigger_force_run(self):
        self.force_run = True

# --- UI Functions ---
def create_image(size=64, state="normal"):
    # Generate icon dynamically so external .ico files aren't required
    image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    
    r = size / 64.0
    color = (0, 120, 215) # Default Blue
    if state == "running":
        color = (255, 140, 0) # Orange
    elif state == "error":
        color = (220, 20, 60) # Red
        
    dc.rounded_rectangle((4*r, 4*r, 60*r, 60*r), radius=10*r, fill=color)
    dc.line([(16*r, 20*r), (26*r, 48*r), (32*r, 30*r), (38*r, 48*r), (48*r, 20*r)], fill="white", width=max(1, int(4*r)), joint="curve")
    return image

def set_tk_icon(window):
    """Sets the dynamic window icon and maintains a reference to prevent garbage collection."""
    try:
        window._icon_ref = ImageTk.PhotoImage(create_image(64, "normal"))
        window.wm_iconphoto(False, window._icon_ref)
        # CustomTkinter on Windows needs slight delays for the HWND to fully absorb icon injections
        window.after(200, lambda: window.wm_iconphoto(False, window._icon_ref))
    except Exception:
        pass

def create_base_window(title, width, height, resizable=False):
    """Creates and centers a CustomTkinter window."""
    # Force Windows Taskbar to use our injected window icon instead of default Python logo
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("wingetmanager.gui.1")
        except Exception:
            pass

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.title(title)
    root.resizable(resizable, resizable)
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    set_tk_icon(root)
    return root

def launch_gui_process(flag):
    """Launches a GUI subprocess so the tray icon doesn't block."""
    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
    subprocess.Popen([python_exe, __file__, flag])

def run_logs_gui():
    """A CustomTkinter GUI to view the log file."""
    root = create_base_window("Winget Manager Logs", 800, 600, resizable=True)

    btn_frame = ctk.CTkFrame(root, fg_color="transparent")
    btn_frame.pack(side="bottom", pady=10)
    
    text_area = ctk.CTkTextbox(root, wrap="word", font=("Cascadia Code", 12))
    text_area.pack(fill="both", expand=True, padx=10, pady=(10, 0))

    last_pos = 0

    def update_log():
        nonlocal last_pos
        current_text = text_area.get('1.0', "end")
        try:
            with open(LOG_FILE, 'r') as f:
                f.seek(last_pos)
                new_text = f.read()
                if new_text:
                    text_area.configure(state='normal')
                    if last_pos == 0 and "does not exist yet" in current_text:
                        text_area.delete('1.0', ctk.END)
                    text_area.insert("end", new_text)
                    text_area.see("end")
                    text_area.configure(state='disabled')
                last_pos = f.tell()
        except FileNotFoundError:
            if last_pos == 0 and "does not exist yet" not in current_text:
                text_area.configure(state='normal')
                text_area.insert("end", "Log file is empty or does not exist yet.")
                text_area.configure(state='disabled')
        
        root.after(1000, update_log)

    def clear_logs():
        nonlocal last_pos
        try:
            open(LOG_FILE, 'w').close()
            text_area.configure(state='normal')
            text_area.delete('1.0', ctk.END)
            text_area.insert("end", "Logs cleared.\n")
            text_area.configure(state='disabled')
            last_pos = 0
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear logs: {e}")

    ctk.CTkButton(btn_frame, text="Clear Logs", font=("Segoe UI", 12), command=clear_logs, fg_color="#8B0000", hover_color="#5C0000").pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="Close", font=("Segoe UI", 12), command=root.destroy).pack(side="left", padx=10)

    text_area.configure(state='disabled')
    update_log()

    root.mainloop()

def run_settings_gui():
    """A CustomTkinter GUI for editing settings."""
    root = create_base_window("Winget Manager Settings", 460, 420)
    config = load_config()

    tabview = ctk.CTkTabview(root)
    tabview.pack(padx=20, pady=10, fill="both", expand=True)

    tab_sched = tabview.add("Schedule")
    tab_conds = tabview.add("Conditions")
    tab_updt = tabview.add("Updates")

    # Dynamic UI Variables mapping using same keys as JSON
    ui_vars = {
        'interval_days': ctk.StringVar(value=str(config.get('interval_days', 1))),
        'trigger_login': ctk.BooleanVar(value=config.get('trigger_login', True)),
        'trigger_return_from_idle': ctk.BooleanVar(value=config.get('trigger_return_from_idle', False)),
        'idle_minutes': ctk.StringVar(value=str(config.get('idle_minutes', 5))),
        'trigger_ac_plugin': ctk.BooleanVar(value=config.get('trigger_ac_plugin', False)),
        'trigger_network_reconnect': ctk.BooleanVar(value=config.get('trigger_network_reconnect', False)),
        'require_ac_power': ctk.BooleanVar(value=config.get('require_ac_power', False)),
        'require_network': ctk.BooleanVar(value=config.get('require_network', True)),
        'updater_frequency_days': ctk.StringVar(value=str(config.get('updater_frequency_days', 7))),
        'updater_auto_restart': ctk.BooleanVar(value=config.get('updater_auto_restart', False))
    }

    # --- Schedule Tab ---
    fnt = ("Segoe UI", 12)
    fnt_b = ("Segoe UI", 14, "bold")
    fnt_s = ("Segoe UI", 11)

    ctk.CTkLabel(tab_sched, text="Check Interval (Days):", font=fnt).grid(row=0, column=0, sticky="w", pady=5)
    ctk.CTkEntry(tab_sched, textvariable=ui_vars['interval_days'], width=80, font=fnt).grid(row=0, column=1, sticky="w", pady=5, padx=10)
    
    ctk.CTkLabel(tab_sched, text="Triggers (When to run updates):", font=fnt_b).grid(row=1, column=0, columnspan=2, sticky="w", pady=(15, 5))
    ctk.CTkCheckBox(tab_sched, text="When I sign into the computer", variable=ui_vars['trigger_login'], font=fnt).grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 5))
    ctk.CTkCheckBox(tab_sched, text="When I return from being idle", variable=ui_vars['trigger_return_from_idle'], font=fnt).grid(row=3, column=0, columnspan=2, sticky="w", pady=(5, 5))

    ctk.CTkLabel(tab_sched, text="  ↳ After this many idle minutes:", font=fnt_s, text_color="gray").grid(row=4, column=0, sticky="w", pady=0)
    ctk.CTkEntry(tab_sched, textvariable=ui_vars['idle_minutes'], width=60, font=fnt).grid(row=4, column=1, sticky="w", pady=0, padx=10)

    ctk.CTkCheckBox(tab_sched, text="When I plug into AC Power", variable=ui_vars['trigger_ac_plugin'], font=fnt).grid(row=5, column=0, columnspan=2, sticky="w", pady=(15, 5))
    ctk.CTkCheckBox(tab_sched, text="When I connect to the Internet", variable=ui_vars['trigger_network_reconnect'], font=fnt).grid(row=6, column=0, columnspan=2, sticky="w", pady=(5, 5))

    # --- Conditions Tab ---
    ctk.CTkLabel(tab_conds, text="Upgrade Restrictions", font=fnt_b).pack(anchor="w", pady=(5, 10))
    
    ctk.CTkSwitch(tab_conds, text="Require AC Power (Do not upgrade on battery)", variable=ui_vars['require_ac_power'], font=fnt).pack(anchor="w", pady=(5, 2))
    ac_stat = "Plugged In" if is_on_ac_power() else "On Battery"
    ctk.CTkLabel(tab_conds, text=f"    Current Status: {ac_stat}", font=fnt_s, text_color="gray").pack(anchor="w", pady=(0, 10))

    ctk.CTkSwitch(tab_conds, text="Require Network Connection (Prevents timeout errors)", variable=ui_vars['require_network'], font=fnt).pack(anchor="w", pady=(5, 2))
    net_stat = "Connected" if is_network_connected() else "Disconnected"
    ctk.CTkLabel(tab_conds, text=f"    Current Status: {net_stat}", font=fnt_s, text_color="gray").pack(anchor="w", pady=(0, 15))
    
    ctk.CTkLabel(tab_conds, text="System Boot", font=fnt_b).pack(anchor="w", pady=(15, 10))
    autostart_var = ctk.BooleanVar(value=get_autostart_status())
    ctk.CTkSwitch(tab_conds, text="Run automatically on Windows start", variable=autostart_var, font=fnt).pack(anchor="w", pady=5)

    # --- Updates Tab ---
    ctk.CTkLabel(tab_updt, text="Winget Manager Updates", font=fnt_b).pack(anchor="w", pady=(5, 10))
    
    ctk.CTkLabel(tab_updt, text="Check Frequency (Days, 0 to disable):", font=fnt).pack(anchor="w", pady=(5, 2))
    ctk.CTkEntry(tab_updt, textvariable=ui_vars['updater_frequency_days'], width=80, font=fnt).pack(anchor="w", pady=(0, 15))

    ctk.CTkSwitch(tab_updt, text="Auto-apply updates and restart (otherwise notify only)", variable=ui_vars['updater_auto_restart'], font=fnt).pack(anchor="w", pady=5)

    status_frame = ctk.CTkFrame(tab_updt, fg_color="transparent")
    status_frame.pack(anchor="w", fill="x", pady=(15, 5))
    
    last_val = config.get('updater_last_check', 0)
    last_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(last_val)) if last_val else "Never"
    status_lbl = ctk.CTkLabel(status_frame, text=f"Last Checked: {last_str}", font=fnt)
    status_lbl.pack(side="left")

    def force_update_check():
        status_lbl.configure(text="Checking for updates...")
        root.update()
        remote_ver, code = fetch_remote_update()
        
        config['updater_last_check'] = time.time()
        save_config(config)
        last_str_new = time.strftime('%Y-%m-%d %H:%M', time.localtime(config['updater_last_check']))
        
        if remote_ver:
            if version.parse(remote_ver) > version.parse(APP_VERSION):
                status_lbl.configure(text=f"Last Check: {last_str_new} (Update Available!)")
                if messagebox.askyesno("Update Available", f"Version {remote_ver} is available!\nDo you want to apply it now and restart?"):
                    apply_update_and_restart(code)
            else:
                status_lbl.configure(text=f"Last Check: {last_str_new} (Up to date)")
                messagebox.showinfo("Updater", "You are running the latest version.")
        else:
            status_lbl.configure(text=f"Last Check: {last_str_new} (Failed)")
            messagebox.showerror("Updater", "Failed to contact GitHub.")

    ctk.CTkButton(status_frame, text="Check Now", width=90, font=fnt, command=force_update_check).pack(side="right")

    # Dynamic Save logic
    def save_and_close():
        try:
            for key, var in ui_vars.items():
                val = var.get()
                if key in ['interval_days', 'idle_minutes', 'updater_frequency_days']:
                    config[key] = int(val)
                else:
                    config[key] = val
            save_config(config)
            
            set_autostart(autostart_var.get())
            
            messagebox.showinfo("Saved", "Settings saved successfully!\nCheck intervals will take effect immediately.")
            root.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values for numeric fields.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")

    btn_frame = ctk.CTkFrame(root, fg_color="transparent")
    btn_frame.pack(pady=(0, 15))
    ctk.CTkButton(btn_frame, text="Save", font=fnt, command=save_and_close, width=100).pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="Cancel", font=fnt, command=root.destroy, width=100, fg_color="gray").pack(side="left", padx=10)

    root.mainloop()

def run_about_gui():
    """A CustomTkinter GUI to show the About box."""
    root = create_base_window("About Winget Manager", 400, 550)

    frame = ctk.CTkFrame(root, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=40, pady=30)

    try:
        big_icon = ctk.CTkImage(light_image=create_image(128), dark_image=create_image(128), size=(128, 128))
        icon_lbl = ctk.CTkLabel(frame, image=big_icon, text="")
        icon_lbl.pack(pady=(0, 15))
    except Exception:
        pass

    fnt_title = ("Segoe UI", 20, "bold")
    fnt = ("Segoe UI", 12)
    fnt_b = ("Segoe UI", 12, "bold")
    fnt_link = ("Segoe UI", 12, "underline")

    ctk.CTkLabel(frame, text="Winget Manager", font=fnt_title).pack()
    ctk.CTkLabel(frame, text=f"Version: {APP_VERSION}", font=fnt).pack(pady=(0, 15))

    repo_link = ctk.CTkLabel(frame, text="GitHub Repository", font=fnt_link, text_color="#1E90FF", cursor="hand2")
    repo_link.pack()
    repo_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/sishgupta/Winget-Manager/"))

    ctk.CTkLabel(frame, text="Open Source Libraries Used:", font=fnt_b).pack(pady=(25, 5))
    
    pystray_link = ctk.CTkLabel(frame, text="pystray (System Tray Icon)", font=fnt_link, text_color="#1E90FF", cursor="hand2")
    pystray_link.pack()
    pystray_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/moses-palmer/pystray"))

    pillow_link = ctk.CTkLabel(frame, text="Pillow (Icon Generation)", font=fnt_link, text_color="#1E90FF", cursor="hand2")
    pillow_link.pack()
    pillow_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://python-pillow.github.io/"))
    
    ctk_link = ctk.CTkLabel(frame, text="CustomTkinter (Modern UI)", font=fnt_link, text_color="#1E90FF", cursor="hand2")
    ctk_link.pack()
    ctk_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/TomSchimansky/CustomTkinter"))

    req_link = ctk.CTkLabel(frame, text="Requests (HTTP Library)", font=fnt_link, text_color="#1E90FF", cursor="hand2")
    req_link.pack()
    req_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://requests.readthedocs.io/"))

    pkg_link = ctk.CTkLabel(frame, text="Packaging (Version Parsing)", font=fnt_link, text_color="#1E90FF", cursor="hand2")
    pkg_link.pack()
    pkg_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://packaging.pypa.io/"))

    ctk.CTkButton(frame, text="Close", font=fnt, command=root.destroy, width=120).pack(pady=(35, 0))

    root.mainloop()

# --- Main App & Menu Routing ---
def run_tray_app():
    # Write PID for update routines to track the main process
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logging.error(f"Failed to write PID file: {e}")

    hide_console()
    logging.info("Starting System Tray Application...")
    worker = None

    def on_setup(icon):
        nonlocal worker
        icon.visible = True
        
        def update_tray_icon(state):
            icon.icon = create_image(size=64, state=state)
            
        worker = WorkerThread(icon, update_tray_icon)
        worker.start()

    def on_quit(icon, item):
        global is_graceful_exit
        is_graceful_exit = True
        logging.info("Application quit by user.")
        if worker:
            worker.running = False
        cleanup_pid()
        icon.stop()

    def on_upgrade_now(icon, item):
        if worker:
            worker.trigger_force_run()

    menu = pystray.Menu(
        item('Upgrade Now', on_upgrade_now, default=True),
        pystray.Menu.SEPARATOR,
        item('Settings', lambda i, it: launch_gui_process('--settings')),
        item('View Logs', lambda i, it: launch_gui_process('--logs')),
        item('About', lambda i, it: launch_gui_process('--about')),
        pystray.Menu.SEPARATOR,
        item('Quit', on_quit)
    )

    icon = pystray.Icon("Winget Manager", create_image(), "Winget Manager", menu)
    icon.run(setup=on_setup)

if __name__ == '__main__':
    if '--settings' in sys.argv:
        hide_console()
        run_settings_gui()
    elif '--logs' in sys.argv:
        hide_console()
        run_logs_gui()
    elif '--about' in sys.argv:
        hide_console()
        run_about_gui()
    else:
        register_exit_hooks()
        run_tray_app()
