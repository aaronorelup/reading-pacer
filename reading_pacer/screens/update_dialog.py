"""
update_dialog.py — "A new version is available" window.

On a Windows install made by our installer, "Update now" downloads and runs
the new installer, which upgrades in place and relaunches the app. Everywhere
else it opens the release page in the browser.
"""

import tkinter as tk

from reading_pacer import __version__
from reading_pacer.config import config
from reading_pacer.services import updater
from reading_pacer.themes import BTN_FG, C
from reading_pacer.widgets import Button

MAX_NOTES_CHARS = 1500


class UpdateDialog(tk.Toplevel):
    def __init__(self, root: tk.Tk, info: updater.UpdateInfo, on_quit):
        super().__init__(root, bg=C["base"], padx=28, pady=22)
        self.root = root
        self.on_quit = on_quit  # saves reading progress, then closes the app
        self.info = info
        self.self_install = updater.can_self_install(info)
        self.title("Update available")
        self.resizable(False, False)
        self.transient(root)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(10, self._center)

    def _build(self):
        tk.Label(self, text=f"Reading Pacer {self.info.version} is available",
                 font=("Helvetica", 16, "bold"), fg=C["lavender"], bg=C["base"],
                 ).pack(anchor="w")
        tk.Label(self, text=f"You have version {__version__}.", font=("Helvetica", 11),
                 fg=C["subtext0"], bg=C["base"]).pack(anchor="w", pady=(2, 12))

        notes = self.info.notes.strip()
        if notes:
            if len(notes) > MAX_NOTES_CHARS:
                notes = notes[:MAX_NOTES_CHARS].rstrip() + "…"
            box = tk.Text(self, wrap="word", height=10, width=60, font=("Helvetica", 11),
                          bg=C["mantle"], fg=C["text"], relief="flat", padx=12, pady=10,
                          highlightthickness=0, borderwidth=0)
            box.insert("1.0", notes)
            box.config(state="disabled")
            box.pack(fill="x", pady=(0, 12))

        self.status = tk.Label(self, text="", font=("Helvetica", 11),
                               fg=C["subtext0"], bg=C["base"], wraplength=520, justify="left")
        self.status.pack(anchor="w")

        row = tk.Frame(self, bg=C["base"])
        row.pack(fill="x", pady=(10, 0))
        self.update_btn = Button(
            row, text="Update now" if self.self_install else "Download…",
            font=("Helvetica", 12, "bold"), bg=C["green"], fg=BTN_FG, relief="flat",
            padx=20, pady=6, cursor="hand2", command=self._update)
        self.update_btn.pack(side="right")
        self.later_btn = Button(
            row, text="Later", font=("Helvetica", 11), bg=C["surface0"], fg=C["text"],
            relief="flat", padx=14, pady=6, cursor="hand2", command=self.destroy)
        self.later_btn.pack(side="right", padx=8)
        Button(row, text="Skip this version", font=("Helvetica", 11), bg=C["base"],
               fg=C["overlay0"], relief="flat", padx=6, pady=6, cursor="hand2",
               command=self._skip).pack(side="left")

    def _center(self):
        self.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - self.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.lift()
        self.focus_force()

    def _skip(self):
        config.skipped_version = self.info.version
        config.save()
        self.destroy()

    def _update(self):
        if not self.self_install:
            updater.open_release_page(self.info)
            self.destroy()
            return
        self.update_btn.config(state="disabled")
        self.later_btn.config(state="disabled")
        self.status.config(text="Downloading…", fg=C["subtext0"])
        # Worker-thread callbacks — marshal onto the Tk loop.
        updater.download_and_install(
            self.info,
            on_progress=lambda f: self.after(0, lambda: self._progress(f)),
            on_ready=lambda path: self.after(0, lambda: self._install(path)),
            on_error=lambda msg: self.after(0, lambda: self._failed(msg)),
        )

    def _progress(self, fraction: float):
        if self.winfo_exists():
            self.status.config(text=f"Downloading… {fraction:.0%}")

    def _install(self, path: str):
        self.status.config(text="Installing — Reading Pacer will restart in a moment.")
        self.update_idletasks()
        try:
            updater.launch_installer(path)
        except OSError as e:
            self._failed(f"Could not start the installer: {e}")
            return
        # Quit (saving progress) so the installer can replace our files.
        self.root.after(300, self.on_quit)

    def _failed(self, msg: str):
        if not self.winfo_exists():
            return
        self.status.config(text=f"Update failed: {msg}", fg=C["red"])
        self.update_btn.config(state="normal", text="Download…")
        self.later_btn.config(state="normal")
        self.self_install = False  # fall back to the browser on the next click
