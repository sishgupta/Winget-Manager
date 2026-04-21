# Winget-Manager
Gemini 3.1 Pro Vibe coded Winget manager

![System Tray Menu](screenshots/System%20Tray%20Menu.png) ![Settings Menu](screenshots/Settings%20Menu.png) 
![Log Viewer](screenshots/Log%20Viewer.png)

## V2.1 - Fixing what AI can't See
### Filtering winget logging to remove winget status bar output:
#### Prompt: 
I want to modify it to remove logging from the winget output when the log starts with a space character. This is usually a status bar ui update and not a real status from the application. So it can be ignored. Other output lines from winget should be kept.

#### Response: 
Filtered Winget Logging: I updated the run_winget_upgrade method to split the standard output of winget by lines and ignore any lines that begin with a space character. This ensures status-bar updates and progress lines aren't printed randomly into your logs, keeping it clean with only the valid package information.

### Fixing UI Padding on Settings:
#### Prompt: 
I want to fix is the UI box for the settings has too much padding to the bottom and right. The UI box for the log is good.

#### Response: 
Fixed Settings UI Padding: Inside run_settings_gui, I removed the hardcoded window sizing (root.geometry("360x320")). Doing this—along with adjusting the bottom pady of the button frame—allows Tkinter to auto-shrink perfectly to the dimensions of the inner components. This entirely clears out the awkward empty padding you were experiencing at the bottom and right. I also kept the auto-centering logic so it always opens neatly in the middle of your screen!

### Fixing UI Element Runoff on the Log:
#### Prompt: 
Can you tell me what to change to make the log window wider by default? and taller? as the close button has run off the screen.

#### Response: 
Here are the specific lines that fix this in run_logs_gui():

Adjusting the Window Size:
```bash
root.geometry("800x600") # Changed from 600x400
```

Fixing the Pushed-Off Close Button:

In Tkinter, widgets pushed to the screen earlier get display priority. If a large textbox appears, it eagerly claims space, so the Close button sometimes gets pushed below the bottom edge. By creating and anchoring the button frame before packing the ScrolledText widget, it gets properly docked to the bottom.
```bash
# Before
text_area.pack(...)
# ...
btn_frame.pack(pady=10) # Packed second, gets pushed down

# Now
btn_frame.pack(side=tk.BOTTOM, pady=10) # Anchored to the bottom first
# ...
text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0)) # Fills available remaining space
```

### Missing Log Entry During Reboot:
#### Prompt: 
When my computer rebooted, i didnt see a log entry for that close. Any thoughts about how to cover that situation? Maybe because it wasnt an exit from the user per the system tray menu?

#### Response: 
I added standard Python atexit and signal hooks to the top of the file to gracefully capture terminal exits. When Windows reboots or forcefully asks the background application to close (e.g., via a SIGTERM signal or exiting the program lifecycle naturally), it will now trap that event and write "Application is shutting down or terminating (System exit/reboot)." to your log.

### 60-Second Delay on Manual Updates:
#### Prompt: 
When launching a manual update, there is a 60 second delay. Can we remove that for the manual update?

#### Response: 
The background worker was previously sleeping in 1-second ticks strictly for 60 seconds at a time (for _ in range(60)), and only checking if the app was physically closed before skipping the wait. I've updated this loop break condition so that it will immediately skip the remainder of the 60-second delay the absolute second self.force_run is flagged (which happens instantly when you hit "Upgrade Now" in the UI). Your manual upgrades will now start immediately.

### Process Termination Logs for closing UI elements and for graceful exit from the UI:
#### Prompt: 
for the logs - now there is a log saying terminated every time i close the settings or the logs ui. additionally when i exit via the menu it shows two logs - one for user exited and one for terminated by system. please fix.

#### Response: 
I've successfully updated the script to fix the duplicate and erroneous logging you were seeing.

Here is what I changed:

1. **Isolated The Hooks to Only the Background Service:** The atexit log hook previously was set right when the Python module was requested. Since your UI (--settings and --logs) executes by spawning a separate python subprocess for itself using the same script, it was mistakenly attaching that system shutdown handler locally and writing to the log when it closed. I moved the hook initialization (register_exit_hooks()) down to the bottom where sys.argv confirms it is ONLY running run_tray_app().

2. **Flagged Graceful Exits:** To fix you seeing double logs on user exits (the "Quit" button event vs the process system-death event), I set a global flag called is_graceful_exit = True inside on_quit(). When the background process closes, your application will now only log the "terminating (System exit/reboot)" event if it wasn't already deliberately quit by the user via the UI.

### Live Log:
#### Prompt: 
I want to make the log "live" - is this feasible? is it easy to do without adding a lot of libraries?

#### Response: 
I've updated the GUI logic to make the log window "live".

Here's how I did this using only the native tkinter methods without importing any new libraries:
I replaced the single static file read with an update_log() function that gets recursively scheduled every 1000 milliseconds using root.after(). On each tick, it jumps to the last read position in the file and only append new changes (auto-scrolling to the bottom as it does). If the file resets or doesn't exist yet, it handles showing your initial placeholder message dynamically until it appears.

### Vector Icon used Everywhere:
#### Prompt: 
the vector icon in the systray - can that also be used for the icon used by the gui and log ui? it's part of the windows ui in the title bar.

#### Response: 
I have updated both the Logs UI and Settings UI to use the dynamically generated "W" icon for their windows!

I fetched the ImageTk module provided by the Pillow library and used root.iconphoto(True, ImageTk.PhotoImage(image)) to apply your existing create_image() asset so it correctly bridges into Tkinter's native titlebars/taskbar buttons without needing a physical .ico file on your device.

## V2 - Adding in obvious things we missed.

### Prompt: 
cool so we're going to make v2 now. The code before is great but we need to try to implement some features.

The first feature is that when i run the python script, a console window opens with log output. Lets make sure the console is hidden. Everything should get output to a log file in the same directory as the configuratoin. create a ui to view the log file, add a way to get to that ui from the systray icon menu. in addition all icon.notify should also create a log entry. I notice at this time only errors are logged, but lets log the actions. Please add timestamps to all logs.

The second feature to implement, is some sort of autostart. I don't know if that is possible with python, but i would like for the script it'sself to install it'sself with some sort of auto run feature. Preferably a windows task scheduler task to start it - as i believe this is the most modern method of auto starting a program, however, registry based autostart is also acceptable. This autostart feature should be on the settings menu, and should be optional. The disable needs to work well. 

### Response:
I have implemented all of your requested features in v2.

#### Here are a few technical notes on how the new features were integrated:
1. **Console Hiding:** I added a Windows API call (GetConsoleWindow and ShowWindow) that automatically hides the console right when the script starts. Additionally, for the autostart feature, it uses pythonw.exe (the windowless Python executable) to ensure a console never even flashes on boot.
2. **Logging:** I swapped basic print() statements for Python's built-in logging module. It includes precise timestamps and logs all application lifecycle events, background checks, and upgrade results.
3. **Log Viewer UI:** A clean, scrollable text interface has been added to view the log file directly.
4. **Autostart:** I went with the Registry-based approach (HKCU\Software\Microsoft\Windows\CurrentVersion\Run). While Task Scheduler is modern, creating and deleting scheduled tasks requires Administrator (UAC) elevation. Using the Current User registry key allows the script to toggle autostart seamlessly from the 5. Settings menu without constantly prompting you for Admin permissions, which is standard practice for system tray apps.

#### Notes for V2:
- **Recommended file extension:** You can rename this file to winget_updater.pyw. Windows natively treats .pyw files as "GUI/Windowless" scripts and will never flash a terminal when you click it. Even if you don't rename it, the code includes an API call to manually hide the window immediately upon launching.
- **Logs are in:** C:\Users\<YourUsername>\.winget_updater.log.
- **Testing Autostart:** Once you open the script, right-click the icon > Settings > Check "Run automatically on Windows start" and click Save. You can verify it applied correctly by checking the Startup Apps tab in your Windows Task Manager.

## V1 - Can it even be done?

### Prompt:
Create a Python application to control Winget. It needs to run in the system tray, check for updates in Winget, and then run upgrade all when the user configures an interval like 1 day or 1 week and after an action like user login or idle

### Response:
I will build a self-contained Python application that runs in your system tray to manage `winget` auto-updates. 

To make the application robust and prevent GUI-related threading freezes, I have designed it using a multi-process approach within a single file. The main process handles the system tray and background checking, and when you click "Settings," it seamlessly spawns a secondary process to show the configuration dialog.

#### Prerequisites:
Before running the code, you will need to install the two lightweight dependencies used for the system tray icon and image generation. Open your terminal or command prompt and run:
```bash
pip install pystray Pillow
```

#### How It Works:
1. **Background Loop:** When you launch the script, it creates a tray icon and spawns a daemon thread. This thread wakes up every minute to check if the timeframe has passed (e.g., 1 day or 7 days).
2. **Idle Detection:** If you selected the "Idle" trigger, it hooks directly into the Windows `user32.dll` to check how long your mouse and keyboard have been untouched. Once it crosses your set threshold (e.g., 5 minutes), it executes the update.
3. **Login Detection:** If you select the "Login" trigger, it will simply run as soon as the timer limit is reached. To utilize this effectively, you should place a shortcut to this script in your `shell:startup` folder.
4. **Stealth Upgrades:** The script explicitly forces Winget to suppress console windows (`CREATE_NO_WINDOW`) and silently accepts source/package agreements so you aren't interrupted by command prompts.
5. **Dynamic Icon:** It uses Pillow (PIL) to draw a blue icon dynamically on launch, removing the need for you to download and manage separate `.ico` files.
