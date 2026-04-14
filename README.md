# Name Guard

A lightweight background tool that detects when you mistype a specific word (like your name) and gives you a subtle visual warning.

It runs silently in the background, shows a tray icon, logs activity, and lets you configure everything from the system tray.

## Features
- Detects typos of a chosen word (e.g. <username>)
- Works globally across all applications
- Red screen border flash when a typo is detected
- System tray icon with controls
- Enable / disable monitoring anytime
- Adjustable strictness (Strict / Normal / Relaxed)
- Persistent settings (saved across restarts)
- Logging system with quick access
- Crash logging + heartbeat monitoring
- Auto-recovery (watchdog for input hooks)

## Installation
1. Install Python dependencies

`pip install keyboard rapidfuzz pynput pystray pillow pyinstaller`

## Build the executable

`pyinstaller --noconsole --onefile name_guard.py`

Output will be here:
`dist\name_guard.exe`

## 3. Enable auto-start
1. Press Win + R
2. Enter: `shell:startup`
3. Copy `name_guard.exe` into that folder

Now it will start automatically when you log in.

## Usage
### Tray Icon
After starting, you’ll see a small icon in your system tray:
🟢 Green → Monitoring enabled
⚪ Gray → Monitoring disabled
Right-click the icon for options.

### Menu Options
Enable / Disable
 - Turn detection on or off instantly

Set Target Word
 - Choose the word you want monitored (saved permanently)

Strictness
 - Adjust detection sensitivity:
   - Strict → only very close typos
   - Normal → balanced (recommended)
   - Relaxed → catches more, but more false positives

Open Log
 - Opens the log file

Clear Log
 - Clears all log entries

Open App Folder
 - Opens the folder where logs + settings are stored

Exit
 - Fully stops the app