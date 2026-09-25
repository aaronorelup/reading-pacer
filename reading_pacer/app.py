"""
app.py — Main application entry point.
Orchestrates screens: main → reading/generate/settings/stats, save/resume.
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

from reading_pacer import crashlog
from reading_pacer.config import config
from reading_pacer.screens.generate_screen import GenerateScreen
from reading_pacer.screens.main_screen import MainScreen
from reading_pacer.screens.reading_screen import ReadingScreen
from reading_pacer.screens.settings_screen import SettingsScreen
from reading_pacer.screens.stats_screen import StatsScreen
from reading_pacer.screens.update_dialog import UpdateDialog
from reading_pacer.services import save_manager, updater
from reading_pacer.themes import C


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Reading Pacer")
        # Being DPI-aware means sizes are physical pixels — scale the window
        # so it has the same on-screen size regardless of display scaling.
        scale = max(root.winfo_fpixels("1i") / 96.0, 1.0)
        self.root.geometry(f"{int(960 * scale)}x{int(720 * scale)}")
        self.root.minsize(int(660 * scale), int(460 * scale))
        self.root.configure(bg=C["base"])

        # Screens
        self.main_screen = None
        self.reading_screen = None
        self.settings_screen = None
        self.generate_screen = None
        self.stats_screen = None

        # Resume a saved session if one exists
        saved = save_manager.load_state()
        if saved:
            self._init_reading_screen()
            self.reading_screen.load_text(
                raw=saved["text"],
                word_index=saved.get("word_index", 0),
                wpm=saved.get("wpm", 250),
                actual_elapsed=saved.get("actual_elapsed", 0.0),
                font_size=saved.get("font_size", 17),
            )
            self.reading_screen.pack(fill="both", expand=True)
        else:
            self._init_main_screen()
            self.main_screen.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self._update_dialog = None
        if config.check_for_updates:
            self.root.after(2500, lambda: self.check_for_updates(manual=False))

    # ── Quit / updates ─────────────────────────────────────────────────

    def quit(self):
        """Save reading progress, then close the app."""
        if self.reading_screen:
            try:
                self.reading_screen._auto_save()
            except Exception as e:  # never block closing the window
                crashlog.write(f"save on quit failed: {e!r}")
        self.root.destroy()

    def check_for_updates(self, manual: bool):
        """Ask GitHub for a newer release. `manual` = the user clicked "Check now"."""

        def _result(info):
            if info is None:
                if manual:
                    messagebox.showinfo("Up to date",
                                        "You have the latest version of Reading Pacer.",
                                        parent=self.root)
                return
            if not manual and info.version == config.skipped_version:
                return
            self._show_update(info)

        def _error(msg):
            crashlog.write(f"update check failed: {msg}")
            if manual:
                messagebox.showwarning("Couldn't check for updates",
                                       "Couldn't reach the update server. "
                                       "Check your internet connection and try again.",
                                       parent=self.root)

        # Worker-thread callbacks — marshal onto the Tk loop.
        updater.check_for_update(
            on_result=lambda info: self.root.after(0, lambda: _result(info)),
            on_error=lambda msg: self.root.after(0, lambda: _error(msg)),
        )

    def _show_update(self, info):
        if self._update_dialog and self._update_dialog.winfo_exists():
            return
        self._update_dialog = UpdateDialog(self.root, info, on_quit=self.quit)

    # ── Screen initialisation ──────────────────────────────────────────

    def _init_main_screen(self, initial_text=""):
        if self.main_screen:
            self.main_screen.destroy()
        self.main_screen = MainScreen(
            self.root,
            on_load_text=self._on_load_text,
            on_generate_passage=self._show_generate_screen,
            on_open_settings=self._show_settings,
            on_open_stats=self._show_stats,
            initial_text=initial_text,
        )

    def _init_reading_screen(self):
        if self.reading_screen:
            self.reading_screen.destroy()
        self.reading_screen = ReadingScreen(
            self.root,
            on_new_text=self._on_new_text,
            on_show_main=self._show_main,
        )

    # ── Navigation ─────────────────────────────────────────────────────

    def _show_main(self):
        """Show main screen, hiding all others."""
        for s in [self.reading_screen, self.settings_screen,
                  self.generate_screen, self.stats_screen]:
            if s:
                s.pack_forget()
        if not self.main_screen:
            self._init_main_screen()
        self.main_screen.pack(fill="both", expand=True)
        self.root.focus_set()

    def _on_load_text(self, raw: str, start_quiz: bool = False):
        """Load text into reading screen from main; optionally jump into quiz."""
        self._init_reading_screen()
        self.main_screen.pack_forget()
        self.reading_screen.pack(fill="both", expand=True)
        self.reading_screen.load_text(raw)
        if start_quiz:
            self.reading_screen.after(300, self.reading_screen._start_quiz)

    def _on_new_text(self, text: str):
        """Called when 'New Text' clicked in reading screen."""
        save_manager.delete_save()
        self.reading_screen.destroy()
        self.reading_screen = None
        self._init_main_screen(initial_text=text)
        self.main_screen.pack(fill="both", expand=True)

    # ── Generate screen ────────────────────────────────────────────────

    def _show_generate_screen(self):
        self.main_screen.pack_forget()
        if self.reading_screen:
            self.reading_screen.pack_forget()
        self.generate_screen = GenerateScreen(
            self.root,
            on_close=self._close_generate,
            on_passage_ready=self._on_passage_ready,
        )
        self.generate_screen.pack(fill="both", expand=True)

    def _close_generate(self):
        if self.generate_screen:
            self.generate_screen.destroy()
            self.generate_screen = None
        self._show_main()

    def _on_passage_ready(self, passage: str):
        """Generated passage ready — update main text and load reading screen."""
        self.generate_screen.destroy()
        self.generate_screen = None
        # Update the main screen's text box so it's there when they go back
        if self.main_screen:
            self.main_screen.set_text(passage)
        self._init_reading_screen()
        self.reading_screen.pack(fill="both", expand=True)
        self.reading_screen.load_text(passage)
        # Delete any prior save — this is a fresh passage
        save_manager.delete_save()

    # ── Settings screen ────────────────────────────────────────────────

    def _show_settings(self):
        self._hide_current()
        self.settings_screen = SettingsScreen(
            self.root, on_close=self._close_settings,
            on_check_updates=lambda: self.check_for_updates(manual=True))
        self.settings_screen.pack(fill="both", expand=True)

    def _close_settings(self):
        if self.settings_screen:
            self.settings_screen.destroy()
            self.settings_screen = None
        self._restore_previous()
        if self.main_screen:
            self.main_screen.set_status(
                "✓ LLM configured" if config.has_any_llm() else
                "No LLM configured — quiz and generation need one (Settings)")

    # ── Stats screen ───────────────────────────────────────────────────

    def _show_stats(self):
        self._hide_current()
        self.stats_screen = StatsScreen(self.root, on_close=self._close_stats)
        self.stats_screen.pack(fill="both", expand=True)

    def _close_stats(self):
        if self.stats_screen:
            self.stats_screen.destroy()
            self.stats_screen = None
        self._restore_previous()

    # ── Shared helpers ─────────────────────────────────────────────────

    def _hide_current(self):
        if self.reading_screen and self.reading_screen.winfo_ismapped():
            self.reading_screen.pack_forget()
        elif self.main_screen and self.main_screen.winfo_ismapped():
            self.main_screen.pack_forget()

    def _restore_previous(self):
        if self.reading_screen and not self.reading_screen.winfo_ismapped():
            self.reading_screen.pack(fill="both", expand=True)
        elif self.main_screen and not self.main_screen.winfo_ismapped():
            self.main_screen.pack(fill="both", expand=True)
        elif not self.main_screen:
            self._show_main()


def _enable_windows_dpi_awareness():
    """Render at native resolution on high-DPI Windows displays (sharp text).

    Tk picks up the real DPI and scales point-based fonts accordingly.
    """
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll
        try:
            windll.shcore.SetProcessDpiAwareness(1)
        except OSError:
            windll.user32.SetProcessDPIAware()
    except Exception:
        pass  # never let DPI setup stop the app


def _set_window_icon(root: tk.Tk):
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    try:
        if sys.platform == "win32":
            root.iconbitmap(os.path.join(assets, "icon.ico"))
        else:
            root.iconphoto(True, tk.PhotoImage(file=os.path.join(assets, "icon.png")))
    except Exception:
        pass  # a missing icon should never stop the app


def main():
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    _set_window_icon(root)
    crashlog.install(root)
    try:
        App(root)
    except Exception:
        # Startup failed (e.g. a corrupt save file): log it and say so plainly
        # instead of a window that silently never appears.
        details = crashlog.format_exception(*sys.exc_info())
        crashlog.write(details)
        messagebox.showerror(
            "Reading Pacer couldn't start",
            "Sorry — Reading Pacer hit an error while starting.\n\n"
            f"Details were saved to:\n{crashlog.log_path()}\n\n"
            "Please report it at github.com/Bloodtailor/reading-pacer/issues",
            parent=root)
        root.destroy()
        sys.exit(1)
    root.mainloop()


if __name__ == "__main__":
    main()
