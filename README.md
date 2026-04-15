# TypoDetect

A lightweight background tool that detects when you mistype a specific word (like your name) and gives you a subtle visual warning.

It runs silently in the background, shows a tray icon, logs activity, and lets you configure everything from the system tray.

## Features

- 🔍 Detects typos of a chosen word in real time
- 🌐 Works globally across all applications
- 🔴 Red screen-border flash when a typo is detected
- 🖥️ System tray icon with full controls
- ⏸️ Enable / disable monitoring anytime
- 🎚️ Adjustable strictness (Strict / Normal / Relaxed)
- 💾 Persistent settings saved across restarts
- 📝 Built-in logging with quick access
- 🛡️ Crash logging and heartbeat monitoring
- 🔄 Auto-recovery watchdog for input hooks

## Installation

### Install from source (pip)

```bash
pip install .
```

This installs TypoDetect and all its dependencies. After installation you can launch it with:

```bash
typodetect
```

### Install in development mode

```bash
pip install -e .
```

### Build a standalone executable

If you prefer a single `.exe` that doesn't require Python:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile typodetect/name_guard.py
```

The executable will be in `dist/name_guard.exe`.

## Auto-start on Windows

1. Press <kbd>Win</kbd> + <kbd>R</kbd>
2. Enter: `shell:startup`
3. Copy the executable (or a shortcut) into that folder

## Usage

### Tray Icon

After starting, a small icon appears in your system tray:

| Icon | Meaning |
|------|---------|
| 🟢 Green | Monitoring enabled |
| ⚪ Grey  | Monitoring disabled |

Right-click the icon to open the menu.

### Menu Options

| Option | Description |
|--------|-------------|
| **Enable / Disable** | Turn detection on or off instantly |
| **Set Target Word** | Choose the word you want monitored (saved permanently) |
| **Strictness** | Adjust sensitivity — *Strict*, *Normal* (recommended), or *Relaxed* |
| **Open Log** | Opens the log file |
| **Clear Log** | Clears all log entries |
| **Open App Folder** | Opens the folder where logs and settings are stored |
| **Exit** | Fully stops the app |

## License

This project is licensed under the [MIT License](LICENSE).
