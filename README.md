# Winget-Manager
Gemini 3.1 Pro Vibe coded Winget manager

## V2

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

## V1

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
