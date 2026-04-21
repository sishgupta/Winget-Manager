# Winget-Manager
Gemini 3.1 Pro Vibe coded Winget manager

### Prompt:
Create a Python application to control Winget. It needs to run in the system tray, check for updates in Winget, and then run upgrade all when the user configures an interval like 1 day or 1 week and after an action like user login or idle

I will build a self-contained Python application that runs in your system tray to manage `winget` auto-updates. 

To make the application robust and prevent GUI-related threading freezes, I have designed it using a multi-process approach within a single file. The main process handles the system tray and background checking, and when you click "Settings," it seamlessly spawns a secondary process to show the configuration dialog.

### Prerequisites
Before running the code, you will need to install the two lightweight dependencies used for the system tray icon and image generation. Open your terminal or command prompt and run:
```bash
pip install pystray Pillow
```

### The Code

http://googleusercontent.com/immersive_entry_chip/0

### How It Works:
1. **Background Loop:** When you launch the script, it creates a tray icon and spawns a daemon thread. This thread wakes up every minute to check if the timeframe has passed (e.g., 1 day or 7 days).
2. **Idle Detection:** If you selected the "Idle" trigger, it hooks directly into the Windows `user32.dll` to check how long your mouse and keyboard have been untouched. Once it crosses your set threshold (e.g., 5 minutes), it executes the update.
3. **Login Detection:** If you select the "Login" trigger, it will simply run as soon as the timer limit is reached. To utilize this effectively, you should place a shortcut to this script in your `shell:startup` folder.
4. **Stealth Upgrades:** The script explicitly forces Winget to suppress console windows (`CREATE_NO_WINDOW`) and silently accepts source/package agreements so you aren't interrupted by command prompts.
5. **Dynamic Icon:** It uses Pillow (PIL) to draw a blue icon dynamically on launch, removing the need for you to download and manage separate `.ico` files.
