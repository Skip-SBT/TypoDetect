from __future__ import annotations

import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from dataclasses import dataclass, field
import tkinter as tk
from tkinter import simpledialog

import keyboard
from rapidfuzz.distance import Levenshtein
import pystray
from PIL import Image, ImageDraw

try:
    from pynput import mouse
except ImportError:
    mouse = None


APP_NAME = "Name Guard"
APP_DIRNAME = "NameGuard"
LOG_FILENAME = "name_guard_log.txt"
SETTINGS_FILENAME = "settings.json"
HEARTBEAT_FILENAME = "heartbeat.txt"

DEFAULT_TARGET_WORD = "mhubrath"
DEFAULT_STRICTNESS = "normal"

STRICTNESS_PRESETS = {
    "strict": {"max_edit_distance": 1, "min_similarity": 0.88},
    "normal": {"max_edit_distance": 2, "min_similarity": 0.75},
    "relaxed": {"max_edit_distance": 3, "min_similarity": 0.65},
}

MIN_WORD_LENGTH = 3
FLASH_DURATION_MS = 700
BORDER_THICKNESS = 12
HEARTBEAT_INTERVAL_SECONDS = 10
MAX_LOG_LINES = 500


@dataclass
class DetectorState:
    current_word_chars: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


running = True
monitoring_enabled = True
tray_icon: pystray.Icon | None = None
state: DetectorState | None = None
flasher = None
mouse_listener = None
last_input_activity = time.time()

settings_lock = threading.Lock()
log_lock = threading.Lock()

# Completed words go here for background processing
word_queue: queue.Queue[str] = queue.Queue(maxsize=1000)


def get_app_dir() -> str:
    path = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), APP_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_log_path() -> str:
    return os.path.join(get_app_dir(), LOG_FILENAME)


def get_settings_path() -> str:
    return os.path.join(get_app_dir(), SETTINGS_FILENAME)


def get_heartbeat_path() -> str:
    return os.path.join(get_app_dir(), HEARTBEAT_FILENAME)


def default_settings() -> dict:
    return {
        "target_word": DEFAULT_TARGET_WORD,
        "strictness": DEFAULT_STRICTNESS,
    }


def normalize_word(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalpha())


def save_settings(settings_data: dict) -> None:
    try:
        with open(get_settings_path(), "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=2)
    except Exception:
        pass


def load_settings() -> dict:
    path = get_settings_path()
    data = default_settings()

    if not os.path.exists(path):
        save_settings(data)
        return data

    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        if isinstance(loaded, dict):
            target_word = normalize_word(str(loaded.get("target_word", DEFAULT_TARGET_WORD)))
            strictness = str(loaded.get("strictness", DEFAULT_STRICTNESS)).strip().lower()

            if not target_word:
                target_word = DEFAULT_TARGET_WORD

            if strictness not in STRICTNESS_PRESETS:
                strictness = DEFAULT_STRICTNESS

            data["target_word"] = target_word
            data["strictness"] = strictness
    except Exception:
        save_settings(data)

    return data


settings = load_settings()


def get_target_word() -> str:
    with settings_lock:
        return settings["target_word"]


def get_strictness() -> str:
    with settings_lock:
        return settings["strictness"]


def get_strictness_values() -> dict:
    return STRICTNESS_PRESETS[get_strictness()]


def trim_log_if_needed() -> None:
    path = get_log_path()
    try:
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) <= MAX_LOG_LINES:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines[-MAX_LOG_LINES:])
    except Exception:
        pass


def write_log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"

    with log_lock:
        try:
            with open(get_log_path(), "a", encoding="utf-8") as f:
                f.write(line)
            trim_log_if_needed()
        except Exception:
            pass


def write_crash_log(prefix: str, exc_type, exc_value, exc_traceback) -> None:
    with log_lock:
        try:
            with open(get_log_path(), "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {prefix}\n")
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
                f.write("\n")
            trim_log_if_needed()
        except Exception:
            pass


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        return
    write_crash_log("UNCAUGHT EXCEPTION", exc_type, exc_value, exc_traceback)


def handle_thread_exception(args) -> None:
    write_crash_log("THREAD EXCEPTION", args.exc_type, args.exc_value, args.exc_traceback)


sys.excepthook = handle_uncaught_exception
threading.excepthook = handle_thread_exception


def clear_log() -> None:
    try:
        with open(get_log_path(), "w", encoding="utf-8") as f:
            f.write("")
        write_log("Log cleared.")
    except Exception:
        pass


def open_log() -> None:
    path = get_log_path()

    if not os.path.exists(path):
        with open(path, "a", encoding="utf-8"):
            pass

    try:
        os.startfile(path)
    except Exception:
        try:
            subprocess.Popen(["notepad.exe", path])
        except Exception:
            pass


def open_app_folder() -> None:
    try:
        os.startfile(get_app_dir())
    except Exception:
        pass


def update_heartbeat() -> None:
    try:
        with open(get_heartbeat_path(), "w", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass


def heartbeat_worker() -> None:
    while running:
        update_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)


def hide_console_window() -> None:
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def looks_like_wrong_word(word: str, target: str) -> bool:
    word = normalize_word(word)
    target = normalize_word(target)

    if not word or word == target:
        return False

    if len(word) < MIN_WORD_LENGTH:
        return False

    values = get_strictness_values()
    distance = Levenshtein.distance(word, target)
    similarity = Levenshtein.normalized_similarity(word, target)

    return distance <= values["max_edit_distance"] and similarity >= values["min_similarity"]


class ScreenBorderFlasher:
    def __init__(self, border_thickness: int = BORDER_THICKNESS) -> None:
        self.border_thickness = border_thickness
        self.root: tk.Tk | None = None
        self.ready = threading.Event()
        self.hide_job = None

        self.thread = threading.Thread(target=self._ui_thread, daemon=True)
        self.thread.start()
        self.ready.wait(timeout=5)

    def _ui_thread(self) -> None:
        root = tk.Tk()
        self.root = root
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)

        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()

        canvas = tk.Canvas(root, width=width, height=height, highlightthickness=0, bg="black")
        canvas.pack()

        try:
            root.wm_attributes("-transparentcolor", "black")
        except tk.TclError:
            pass

        canvas.create_rectangle(0, 0, width, height, outline="red", width=self.border_thickness)

        self.ready.set()
        root.mainloop()

    def flash(self, duration_ms: int = FLASH_DURATION_MS) -> None:
        if self.root is None:
            return

        def show_border() -> None:
            if self.root is None:
                return

            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            self.root.geometry(f"{width}x{height}+0+0")
            self.root.deiconify()
            self.root.lift()

            if self.hide_job is not None:
                self.root.after_cancel(self.hide_job)

            self.hide_job = self.root.after(duration_ms, hide_border)

        def hide_border() -> None:
            if self.root is None:
                return
            self.root.withdraw()
            self.hide_job = None

        self.root.after(0, show_border)


def create_tray_image(enabled: bool = True) -> Image.Image:
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    fill = (40, 200, 80, 255) if enabled else (180, 180, 180, 255)
    draw.ellipse((14, 14, 50, 50), fill=fill, outline=(20, 20, 20, 255), width=3)
    return image


def refresh_tray_icon() -> None:
    global tray_icon
    if tray_icon is None:
        return

    enabled_text = "Enabled" if monitoring_enabled else "Disabled"
    tray_icon.icon = create_tray_image(monitoring_enabled)
    tray_icon.title = (
        f"{APP_NAME} - {enabled_text} - Word: {get_target_word()} - {get_strictness().capitalize()}"
    )
    try:
        tray_icon.update_menu()
    except Exception:
        pass


def enable_monitoring(icon=None, item=None) -> None:
    global monitoring_enabled
    monitoring_enabled = True
    write_log("Monitoring enabled.")
    refresh_tray_icon()


def disable_monitoring(icon=None, item=None) -> None:
    global monitoring_enabled
    monitoring_enabled = False
    write_log("Monitoring disabled.")
    refresh_tray_icon()


def set_strictness(value: str) -> None:
    value = value.lower().strip()
    if value not in STRICTNESS_PRESETS:
        return

    with settings_lock:
        settings["strictness"] = value
        save_settings(settings)

    write_log(f"Strictness changed to: {value}")
    refresh_tray_icon()


def set_strictness_strict(icon=None, item=None) -> None:
    set_strictness("strict")


def set_strictness_normal(icon=None, item=None) -> None:
    set_strictness("normal")


def set_strictness_relaxed(icon=None, item=None) -> None:
    set_strictness("relaxed")


def prompt_set_target_word(icon=None, item=None) -> None:
    def ask() -> None:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            value = simpledialog.askstring(
                APP_NAME,
                "Enter the word to monitor:",
                initialvalue=get_target_word(),
                parent=root,
            )
        finally:
            root.destroy()

        if value is None:
            return

        cleaned = normalize_word(value)
        if not cleaned:
            write_log("Invalid target word rejected.")
            return

        old_value = get_target_word()
        with settings_lock:
            settings["target_word"] = cleaned
            save_settings(settings)

        write_log(f"Target word changed from '{old_value}' to '{cleaned}'")
        refresh_tray_icon()

    threading.Thread(target=ask, daemon=True).start()


def stop_program(icon: pystray.Icon | None = None, item=None) -> None:
    global running, mouse_listener
    running = False
    write_log("Application exited.")

    try:
        keyboard.unhook_all()
    except Exception:
        pass

    try:
        if mouse_listener is not None:
            mouse_listener.stop()
    except Exception:
        pass

    if icon is not None:
        try:
            icon.stop()
        except Exception:
            pass


def enqueue_finished_word(word: str) -> None:
    if not word:
        return

    try:
        word_queue.put_nowait(word)
    except queue.Full:
        # Drop the oldest item and keep the newest one
        try:
            _ = word_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            word_queue.put_nowait(word)
        except queue.Full:
            pass


def finalize_current_word() -> None:
    global state
    if not monitoring_enabled or state is None:
        return

    with state.lock:
        if not state.current_word_chars:
            return
        word = "".join(state.current_word_chars)
        state.current_word_chars.clear()

    enqueue_finished_word(word)


def worker_process_words() -> None:
    while running:
        try:
            word = word_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        try:
            target = get_target_word()
            if looks_like_wrong_word(word, target):
                write_log(
                    f"Possible typo detected: typed='{word}' target='{target}' strictness='{get_strictness()}'"
                )
                if flasher is not None:
                    flasher.flash()
        except Exception:
            write_crash_log("WORD PROCESSOR ERROR", *sys.exc_info())
        finally:
            word_queue.task_done()


def on_key(event: keyboard.KeyboardEvent) -> None:
    global last_input_activity, state

    if not running or not monitoring_enabled or state is None:
        return
    if event.event_type != "down":
        return

    last_input_activity = time.time()
    key = event.name

    # Keep this hot path very small and cheap
    with state.lock:
        if key == "backspace":
            if state.current_word_chars:
                state.current_word_chars.pop()
            return

        if len(key) == 1 and key.isprintable():
            if key.isalpha():
                state.current_word_chars.append(key.lower())
            else:
                if state.current_word_chars:
                    word = "".join(state.current_word_chars)
                    state.current_word_chars.clear()
                    enqueue_finished_word(word)
            return

        if key in {"space", "enter", "tab"}:
            if state.current_word_chars:
                word = "".join(state.current_word_chars)
                state.current_word_chars.clear()
                enqueue_finished_word(word)
            return

        # For other keys like ctrl, alt, arrows, shift:
        # do not force-finalize, because it creates noise and extra work.


def on_click(x, y, button, pressed) -> None:
    global last_input_activity
    if running and monitoring_enabled and pressed:
        last_input_activity = time.time()
        finalize_current_word()


def rebuild_listeners() -> None:
    global mouse_listener

    try:
        keyboard.unhook_all()
    except Exception:
        pass

    keyboard.hook(on_key)

    if mouse is not None:
        try:
            if mouse_listener is not None:
                mouse_listener.stop()
        except Exception:
            pass

        mouse_listener = mouse.Listener(on_click=on_click, daemon=True)
        mouse_listener.start()


def watchdog_worker() -> None:
    last_refresh = time.time()

    while running:
        now = time.time()
        if now - last_refresh > 300:
            try:
                rebuild_listeners()
                write_log("Watchdog refreshed input listeners.")
            except Exception:
                write_crash_log("WATCHDOG REFRESH FAILED", *sys.exc_info())
            last_refresh = now
        time.sleep(5)


def build_menu() -> pystray.Menu:
    return pystray.Menu(
        pystray.MenuItem(
            lambda item: f"Status: {'Enabled' if monitoring_enabled else 'Disabled'}",
            lambda icon, item: None,
            enabled=False,
        ),
        pystray.MenuItem(
            lambda item: f"Word: {get_target_word()}",
            lambda icon, item: None,
            enabled=False,
        ),
        pystray.MenuItem(
            lambda item: f"Strictness: {get_strictness().capitalize()}",
            lambda icon, item: None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Enable", enable_monitoring, checked=lambda item: monitoring_enabled),
        pystray.MenuItem("Disable", disable_monitoring, checked=lambda item: not monitoring_enabled),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Set Target Word...", prompt_set_target_word),
        pystray.MenuItem(
            "Strictness",
            pystray.Menu(
                pystray.MenuItem("Strict", set_strictness_strict, checked=lambda item: get_strictness() == "strict"),
                pystray.MenuItem("Normal", set_strictness_normal, checked=lambda item: get_strictness() == "normal"),
                pystray.MenuItem("Relaxed", set_strictness_relaxed, checked=lambda item: get_strictness() == "relaxed"),
            ),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Log", lambda icon, item: open_log()),
        pystray.MenuItem("Open App Folder", lambda icon, item: open_app_folder()),
        pystray.MenuItem("Clear Log", lambda icon, item: clear_log()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", stop_program),
    )


def setup_tray() -> pystray.Icon:
    return pystray.Icon(
        "name_guard",
        create_tray_image(monitoring_enabled),
        APP_NAME,
        menu=build_menu(),
    )


def main() -> None:
    global tray_icon, state, flasher

    hide_console_window()
    write_log(
        f"Application started. target='{get_target_word()}' strictness='{get_strictness()}'"
    )

    state = DetectorState()
    flasher = ScreenBorderFlasher()

    rebuild_listeners()

    if mouse is None:
        write_log("Mouse click detection unavailable: pynput not installed.")

    threading.Thread(target=heartbeat_worker, daemon=True).start()
    threading.Thread(target=watchdog_worker, daemon=True).start()
    threading.Thread(target=worker_process_words, daemon=True).start()

    tray_icon = setup_tray()
    refresh_tray_icon()
    tray_icon.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        write_crash_log("FATAL MAIN EXCEPTION", *sys.exc_info())
        raise