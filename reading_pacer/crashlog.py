"""
crashlog.py — Catch unexpected errors, log them, and tell the user what to do.

Errors are appended to <user data dir>/logs/reading-pacer.log (capped in size).
In the GUI, an error shows a dialog offering to copy the details or open a
pre-filled GitHub issue, so problems on other people's machines get reported
instead of silently failing.
"""

import os
import platform
import sys
import traceback
import urllib.parse
import webbrowser
from datetime import datetime

from reading_pacer import __version__, paths

MAX_LOG_BYTES = 512 * 1024
ISSUES_URL = "https://github.com/aaronorelup/reading-pacer/issues/new"


def log_path() -> str:
    return os.path.join(paths.user_data_dir(), "logs", "reading-pacer.log")


def system_summary() -> str:
    import tkinter

    frozen = "installed app" if getattr(sys, "frozen", False) else "from source"
    return (f"Reading Pacer {__version__} ({frozen}) · "
            f"{platform.system()} {platform.version()} ({platform.machine()}) · "
            f"Python {platform.python_version()} · Tk {tkinter.TkVersion}")


def write(text: str) -> None:
    """Append a timestamped entry to the log. Never raises."""
    try:
        path = log_path()
        paths.ensure_dir(os.path.dirname(path))
        if os.path.isfile(path) and os.path.getsize(path) > MAX_LOG_BYTES:
            os.replace(path, path + ".old")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {text}\n")
    except Exception:
        pass


def format_exception(exc_type, exc, tb) -> str:
    return system_summary() + "\n" + "".join(traceback.format_exception(exc_type, exc, tb))


def issue_url(details: str) -> str:
    body = ("**What were you doing when this happened?**\n\n\n"
            "**Error details**\n```\n" + details[-3000:] + "\n```\n")
    query = urllib.parse.urlencode({"title": "Crash report", "body": body})
    return f"{ISSUES_URL}?{query}"


def show_error_dialog(root, details: str) -> None:
    """A small, non-scary error window with Copy / Report buttons."""
    import tkinter as tk

    from reading_pacer.themes import BTN_FG, C
    from reading_pacer.widgets import Button

    try:
        win = tk.Toplevel(root, bg=C["base"], padx=24, pady=20)
    except tk.TclError:
        return  # root is gone — the log file still has the details
    win.title("Something went wrong")
    win.transient(root)
    tk.Label(win, text="Sorry — something went wrong.", font=("Helvetica", 15, "bold"),
             fg=C["peach"], bg=C["base"]).pack(anchor="w")
    tk.Label(win, text=("Your reading progress is saved. You can usually keep going.\n"
                        "If this keeps happening, please report it so it can be fixed."),
             font=("Helvetica", 11), fg=C["text"], bg=C["base"], justify="left",
             ).pack(anchor="w", pady=(4, 10))
    box = tk.Text(win, height=8, width=70, font=("Courier", 9), bg=C["mantle"],
                  fg=C["subtext0"], relief="flat", padx=8, pady=6)
    box.insert("1.0", details)
    box.config(state="disabled")
    box.pack(fill="both", expand=True)
    tk.Label(win, text=f"Log file: {log_path()}", font=("Helvetica", 9),
             fg=C["overlay0"], bg=C["base"]).pack(anchor="w", pady=(6, 0))

    def _copy():
        win.clipboard_clear()
        win.clipboard_append(details)

    row = tk.Frame(win, bg=C["base"])
    row.pack(fill="x", pady=(12, 0))
    Button(row, text="Close", font=("Helvetica", 11), bg=C["surface0"], fg=C["text"],
           relief="flat", padx=14, pady=5, cursor="hand2",
           command=win.destroy).pack(side="right")
    Button(row, text="Report on GitHub", font=("Helvetica", 11, "bold"), bg=C["blue"],
           fg=BTN_FG, relief="flat", padx=14, pady=5, cursor="hand2",
           command=lambda: webbrowser.open(issue_url(details))).pack(side="right", padx=8)
    Button(row, text="Copy details", font=("Helvetica", 11), bg=C["surface0"],
           fg=C["text"], relief="flat", padx=14, pady=5, cursor="hand2",
           command=_copy).pack(side="left")


def install(root) -> None:
    """Route uncaught errors (startup and Tk callbacks) to the log + dialog."""
    shown = {"count": 0}

    def _report(exc_type, exc, tb):
        details = format_exception(exc_type, exc, tb)
        write(details)
        sys.__stderr__ and sys.__stderr__.write(details)
        if shown["count"] < 3:  # don't bury the user in dialogs if something loops
            shown["count"] += 1
            show_error_dialog(root, details)

    root.report_callback_exception = _report
