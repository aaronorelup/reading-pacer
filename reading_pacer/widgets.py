"""
widgets.py — Small cross-platform widget shims.

On macOS, Tk's native (Aqua) buttons ignore the `bg` option, so our flat
coloured buttons would render as grey system buttons with unreadable pastel
text. `Button` is a drop-in replacement: a real `tk.Button` on Windows/Linux,
and a Label that behaves like a flat button on macOS.
"""

import sys
import tkinter as tk

IS_MAC = sys.platform == "darwin"


class _LabelButton(tk.Label):
    """A Label that looks and acts like a flat tk.Button (click, hover, disable)."""

    def __init__(self, master=None, command=None, relief="flat", **kw):
        kw.pop("activebackground", None)
        kw.pop("activeforeground", None)
        kw.setdefault("cursor", "hand2")
        super().__init__(master, relief=relief, **kw)
        self._command = command
        self._pressed = False
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _enabled(self) -> bool:
        return str(self.cget("state")) != "disabled"

    def _on_press(self, _event):
        self._pressed = self._enabled()

    def _on_release(self, event):
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if self._pressed and inside and self._enabled() and self._command:
            self._command()
        self._pressed = False

    def configure(self, cnf=None, **kw):
        if "command" in kw:
            self._command = kw.pop("command")
        kw.pop("activebackground", None)
        kw.pop("activeforeground", None)
        return super().configure(cnf, **kw)

    config = configure

    def invoke(self):
        if self._enabled() and self._command:
            return self._command()


Button = _LabelButton if IS_MAC else tk.Button


def bind_mousewheel(widget: tk.Widget, scroll_target) -> None:
    """Scroll `scroll_target` (anything with yview_scroll) while the mouse is over `widget`.

    Handles all three platforms: Windows wheel deltas come in multiples of 120,
    macOS sends small raw deltas, and X11 sends Button-4/Button-5 instead.
    """

    def _wheel(event):
        if sys.platform == "win32":
            steps = -int(event.delta / 120)
        else:  # macOS
            steps = -event.delta
        if steps:
            scroll_target.yview_scroll(steps, "units")

    def _enter(_e):
        widget.bind_all("<MouseWheel>", _wheel)
        widget.bind_all("<Button-4>", lambda e: scroll_target.yview_scroll(-1, "units"))
        widget.bind_all("<Button-5>", lambda e: scroll_target.yview_scroll(1, "units"))

    def _leave(_e):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.unbind_all(seq)

    widget.bind("<Enter>", _enter)
    widget.bind("<Leave>", _leave)
