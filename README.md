# Winget-Manager
Gemini 3.1 Pro Vibe coded Winget Manager written in Python

The purpose of the application is to be an extremely lightweight and extremely readable and maintainable script that automatically executes a ```winget upgrade --all``` at a time when the user is present to accept UAC prompts but still convenient or as unobtrusive to the user as possible.

A log provides maximum transprarency for the actions of the tool.

![System Tray Menu](screenshots/System%20Tray%20Menu.png)

![About Dialog](screenshots/About%20Dialog.png)

![Settings Dialog Schedule](screenshots/Settings%20Dialog%20Schedule.png)

![Settings Dialog Conditions](screenshots/Settings%20Dialog%20Conditions.png)

![Settings Dialog Updates](screenshots/Settings%20Dialog%20Updates.png)

![Log Viewer](screenshots/Log%20Viewer.png)
   
## Features

### Unobtrusive System Tray Agent
* **Minimal Footprint:** Runs silently in the system tray, out of your way until needed.
* **At-a-Glance Status:** The tray icon changes color dynamically so you always know what it's doing (🔵 Idle, 🟠 Upgrading, 🔴 Error).
* **Quick Upgrade:** Just double-click the tray icon to bypass all schedules and force an update check immediately.
* **Native Notifications:** Uses standard Windows 11 toast notifications to tell you when updates are finished or if self-updates are available.

### Smart, Presence-Aware Scheduling
*Upgrades happen when it makes sense for you, completely avoiding workflow interruptions while ensuring you are present for UAC prompts.*
* **Behavioral Triggers:** Tell the app to logically start upgrading based on your actions:
  * **Return from Idle:** *(Perfect for desktops)* Triggers immediately when you return to your computer after a set time away.
  * **AC Power Plug-in:** *(Perfect for laptops)* Triggers the moment you plug your laptop into the wall.
  * **Network Reconnect:** Triggers as soon as network connectivity resumes.
  * **System Startup:** Triggers shortly after you log into Windows.
* **Check Interval:** Set how many days to wait before looking for updates again.

### Safety Conditions & System Checks
* **Battery Saver:** Can block updates from running if your device is running on battery power.
* **Smart Network Check:** Ensures you have true internet access (bypassing captive hotel/cafe Wi-Fi portals) before attempting to download updates.
* **Run at Boot:** Automatically starts the background agent every time you turn on your PC.

### Auto-Updater
* **Set It and Forget It:** Configurable to automatically check GitHub for new versions of Winget Manager, apply the update, and restart silently in the background.

### System Tools
* **Settings Menu:** A clean, modern Windows 11 style interface to manage all of the application's timing and triggers.
* **Live Log Viewer:** A dedicated window using the modern 'Cascadia Code' terminal font to watch Winget install text in real-time or troubleshoot errors.

## Installation and Use
1. **Install Python:** Download and install [Python 3.8+](https://www.python.org/downloads/) for Windows. 
   > **⚠️ Important:** Make sure to check the box for **"Add python.exe to PATH"** during the installation process.
2. **Install Dependencies:** Open Command Prompt or PowerShell and install the required libraries:
   ```bash
   pip install pystray Pillow customtkinter requests packaging
   ```
3. **Download:** Download `winget_manager.pyw` from this repository and place it in a permanent folder (e.g., `C:\Tools\WingetManager\`).
4. **Run the App:** Double-click `winget_manager.pyw` to launch it. 
   > **Note:** This is a background process. No window will pop up. Instead, look for the blue Winget Manager icon in your Windows System Tray (next to the clock).
5. **Configure:** Right-click the tray icon and open **Settings** to define your automated upgrade triggers.
   > **💡 Tips:** 
   > * Turn on **"Run automatically on Windows start"** in the Conditions tab for a completely hands-off experience.
   > * Double-click the tray icon at any time to bypass the schedule and force an immediate update check.

## Why not Task Scheduler?
Many winget packages require UAC Prompts to be accepted but running winget AS admin results in inconsistencies as many packages won't upgrade from elevated winget. Thus a solution that serves the user installations when they are present but in a non-intrusive manner is needed.
Task scheduler doesn't really offer this kind of *anti*-anti-intrusive action as the default is to work with methods that *DON'T* interupt the user. In this case we **do** want to interupt the user, just at the best time possible.
