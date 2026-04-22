# Winget-Manager
Gemini 3.1 Pro Vibe coded Winget Manager written in Python

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

## Features
- System Tray Application - for quick access and minimal ui.
  - Icon is a dynamic vector, changes colour based on state of the program (red for error, orange for working, blue for idle). Icon is used throughout the program.
  - Windows 11 notifications/toasts
- Upgrade Now Action - bypass the timers and run a check now
- Settings Dialog 
  - Scheduling
    - Check Interval
    - Trigger (Startup/Idle)
    - Idle Time
  - Conditions
    - AC Power
    - Network Connectivity
    - Run at Boot
  - Auto Updater
    - Update Check Frequency
    - Auto apply and restart
    - Check now with Status
- Live Log Viewer - view what is happening in real time and clear log button
- About Dialog - credits/references to other libraries used
