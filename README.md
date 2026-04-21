# Winget-Manager
Gemini 3.1 Pro Vibe coded Winget manager

![System Tray Menu](screenshots/System%20Tray%20Menu.png)

![About Dialog](screenshots/About%20Dialog.png)

![Settings Dialog Schedule](screenshots/Settings%20Dialog%20Schedule.png)

![Settings Dialog Conditions](screenshots/Settings%20Dialog%20Conditions.png)

![Settings Dialog Updates](screenshots/Settings%20Dialog%20Updates.png)

![Log Viewer](screenshots/Log%20Viewer.png)

## Installation and Use
1. Install Python
2. Install Dependencies ```pip install pystray Pillow customtkinter requests packaging```
3. Download and place winget_manager.pyw somewhere useful
4. Double click to run or launch with pythonw
5. Use system tray to configure via settings menu

## V3 - Enhancements
### Prompt:
Recommend some potential enhancements without actually making them - this is just a discussion

### Response:
This is a great application to build upon! Since the core loop of trigger -> wait -> execute is very stable now, there are a lot of fun directions you could take it.

Here are some potential enhancements just for brainstorming, ranging from easy quality-of-life tweaks to "power user" features:

1. **Exclusion List (Blacklist):** Sometimes an update breaks a specific app, or you want to keep an older version of a tool. You could add a UI in Settings to manage a list of Package IDs to ignore (passing --exact --id "AppName" --version "old" or just managing an exclusion list before formulating the winget command).
2. **Dry-Run / Preview:** Right now, it blindly updates everything. You could add an "Updates Available" tray menu item that parses the output of winget upgrade (without --all) to show the user exactly which apps have pending updates before they click "Upgrade Now".
3. **Update Notifications:** Currently, you get system tray tooltips. You could integrate native Windows 10/11 Toast Notifications (using a fast library like win11toast) to pop up a message saying "Winget Manager: Successfully updated 3 packages" when the background worker finishes.
4. **Dynamic Tray Icon State:** You could modify your create_image() function to draw different icons based on the app's state. For example: a blue "W" normally, an orange "W" with a little play button when an update is actively running, and a red "W" if the last update threw an error.
5. **Clear Logs Button:** Your log file will eventually get quite long. Adding a simple "Clear Logs" button inside your Log UI to wipe the .winget_manager.log file would be handy.
6. **Modernize Tkinter (customtkinter):** Standard tkinter looks a bit "Windows 95". If you ever wanted to make the settings and log windows look like native Windows 11 dark-mode apps with smooth rounded buttons, swapping tkinter for the customtkinter library is a surprisingly easy drop-in replacement.
7. **Network & Battery Awareness:** For laptop users, doing heavy package installations on battery power isn't ideal. You could add a check using ctypes to skip the idle trigger if the laptop is discharging, or skip if the system isn't connected to the internet (preventing timeout errors in the log).
8. **Self-Updater:** Since you have the code on GitHub, you could add an "Update Winget Manager" button that fetches the raw winget_manager.pyw from your repo and overwrites itself if a newer version is found.

### Prompt:
As suggested Please implement the following subset of items
1. update notifications
2. dynamic tray icon state
3. clear logs button
4. modernize tkinter
5. network and battery awareness - also add options to settings
6. self updater - with settings to enable/disable a frequency check, select a frequency and to either notify or auto update directly and restart

### Response:
What was implemented:
1. **Update Notifications:** Integrated parsing logic for Winget. If it upgrades packages successfully, it reads how many were installed and you'll get a Windows notification (e.g., "Successfully updated 3 package(s)"). It uses the tray's native .notify behavior.
2. **Dynamic Tray Icon State:** The tray icon changes color! Default Blue = monitoring, Orange = currently running upgrades, Red = error.
3. **Clear Logs Button:** Easily accessible inside the Logs GUI (--logs flag), backed by error-catching.
4. **Modernize Tkinter:** Shifted all GUIs (Settings, Logs, About) over to use customtkinter for a polished, dark/light-mode respecting modern feel.
5. **Network and Battery Awareness:** Utilized ctypes.windll to detect if the laptop is plugged into the wall and socket to check network vitality. This effectively stops upgrades from draining your battery or timing out without internet. These defaults are toggleable in the settings ui!
6. **Self-Updater Mechanism:** Reaches out to the GitHub repository file to detect if APP_VERSION is higher. Options were added for checking frequency and picking between purely notifying you vs auto-downloading, applying the code, and cleanly restarting the app behind the scenes.

Prerequisites to test the new code:
Be sure to install the new requirements in your terminal if you haven't recently locally:

 ```pip install pystray Pillow customtkinter requests packaging```

### Prompt:
some fixes: the settings, about and log ui dont use the icon for the windows titlebar anymore. also the settings window is about twice as tall as it needs to be and definitely a bit too wide. finally, the auto update doesnt have a force update button or any kind of status on the last update or if there is an update. please add these things. is it possible to present the status of network and battery in their settings aswell?

### Response:
1. **Titlebar Icons Realized:** The customtkinter framework has a notorious quirk on Windows where pushing dynamic icons inside the module constructor drops them immediately (thanks to internal C garbage collection). I created a clever helper tool (set_tk_icon) that grabs the freshly painted tray image, anchors it into memory with an internal variable reference, and pushes it using Native Tk window bindings on a slight .after(200...) millisecond delay. This correctly bypasses the framework quirk, restoring the Winget Manager icon inside your Windows Titlebars without an external .ico file!
2. **Settings Window Trimmed:** As requested, the "Settings" and "About" windows had explicit parameters dropped or recalculated (480x520 -> 460x420, etc.). The tabs will now correctly self-wrap their inner content rather than stretching.
3. **Power/Network Status Injections:** Real-time statuses (e.g. Current Status: Plugged In, Current Status: Connected) are now anchored directly beneath your battery and internet toggles on that tab.
4. **Interactive Auto-Update:** The "Updates" tab now boasts a dedicated "Check Now" button. Surrounding it are labels detailing exactly what occurred during the last check and displaying any status strings interactively. Pressing "Check Now" triggers the requests lookup, evaluates if a newer match exists, writes a log item, and prompts you to safely reboot into the newly pulled code!
 
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
```python
root.geometry("800x600") # Changed from 600x400
```

Fixing the Pushed-Off Close Button:

In Tkinter, widgets pushed to the screen earlier get display priority. If a large textbox appears, it eagerly claims space, so the Close button sometimes gets pushed below the bottom edge. By creating and anchoring the button frame before packing the ScrolledText widget, it gets properly docked to the bottom.
```python
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
The vector icon in the systray - can that also be used for the icon used by the gui and log ui? it's part of the windows ui in the title bar.

#### Response: 
I have updated both the Logs UI and Settings UI to use the dynamically generated "W" icon for their windows!

I fetched the ImageTk module provided by the Pillow library and used ```root.iconphoto(True, ImageTk.PhotoImage(image))``` to apply your existing create_image() asset so it correctly bridges into Tkinter's native titlebars/taskbar buttons without needing a physical .ico file on your device.


### Add an About Menu:
#### Prompt: 
I want to add an about box, that you can open from the systray menu.
It should have a bigger version of the icon top and center.
A version number that is just the date in yyyy.mm.dd.xx where xx is for multiple builds in a single day.
It should link to the github repo https://github.com/sishgupta/Winget-Manager/
it should credit and reference any libraries used with links to the libraries where appropriate.

#### Response: 
I have built out the new About dialog into the system tray!

Here's a breakdown of the modifications made to support this cleanly:
1. **Dynamic Vector Scaling:** I refactored your create_image() drawing utility to take an optional size parameter (with a default fallback of 64). I dynamically calculated a multiplier scale down the math constants (radius, bounding lines, coordinates) so it perfectly recreates your "W" icon natively at any resolution. The About Box uses a crisp 128x128 generated version centered at the top.
2. **About Gui Integration:** I built run_about_gui(). Added the modern yyyy.mm.dd.xx timestamp marker (2026.04.21.01).
3. **Python webbrowser Hooking:** Bound click events to native clickable links highlighting in blue with standard finger-cursor pointers for your requested github repo, as well as the repos for pystray and pillow.
4. **App Routing Framework:** Linked the new subprocess (--about via sys.argv) and added it tightly into pystray.Menu just underneath "View Logs".
    
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
- **Recommended file extension:** You can rename this file to winget_manager.pyw. Windows natively treats .pyw files as "GUI/Windowless" scripts and will never flash a terminal when you click it. Even if you don't rename it, the code includes an API call to manually hide the window immediately upon launching.
- **Logs are in:** ```C:\Users\<YourUsername>\.winget_manager.log.```
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
