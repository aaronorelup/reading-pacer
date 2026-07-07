"""
main_screen.py — Landing screen with text input, load/generate/quiz buttons.
"""

import os
import tkinter as tk
from tkinter import filedialog

from reading_pacer.themes import BTN_FG, C


class MainScreen(tk.Frame):
    """Input screen — paste or open text, load pacer, generate passage, or quiz."""

    def __init__(self, root, on_load_text, on_generate_passage, on_open_settings,
                 on_open_stats, initial_text=""):
        super().__init__(root, bg=C["base"])
        self.root = root
        self.on_load_text = on_load_text
        self.on_generate_passage = on_generate_passage
        self.on_open_settings = on_open_settings
        self.on_open_stats = on_open_stats

        self._build()
        if initial_text:
            self.input_text.insert("1.0", initial_text)
            self._update_word_count()

    def _build(self):
        # ── Title + Stats/Settings ──
        title_row = tk.Frame(self, bg=C["base"])
        title_row.pack(fill="x", padx=44, pady=(36, 4))

        tk.Label(title_row, text="Reading Pacer",
                 font=("Helvetica", 26, "bold"),
                 fg=C["lavender"], bg=C["base"]).pack(side="left")

        tk.Button(title_row, text="⚙ Settings", font=("Helvetica", 10),
                  bg=C["surface0"], fg=C["text"], relief="flat",
                  padx=14, pady=4, cursor="hand2",
                  command=self.on_open_settings).pack(side="right")
        tk.Button(title_row, text="📊 Stats", font=("Helvetica", 10),
                  bg=C["surface0"], fg=C["text"], relief="flat",
                  padx=14, pady=4, cursor="hand2",
                  command=self.on_open_stats).pack(side="right", padx=(0, 8))

        # ── Subtitle + open-file ──
        sub_row = tk.Frame(self, bg=C["base"])
        sub_row.pack(fill="x", padx=44, pady=(0, 14))
        tk.Label(sub_row, text="Paste your text below — or open a file — then press Load.",
                 font=("Helvetica", 13), fg=C["subtext0"], bg=C["base"]).pack(side="left")
        tk.Button(sub_row, text="📂 Open File…", font=("Helvetica", 10),
                  bg=C["surface0"], fg=C["text"], relief="flat",
                  padx=12, pady=3, cursor="hand2",
                  command=self._open_file).pack(side="right")

        # ── Buttons (centred, packed bottom-first so they never clip) ──
        btn_row = tk.Frame(self, bg=C["base"])
        btn_row.pack(side="bottom", pady=18, fill="x")
        btn_inner = tk.Frame(btn_row, bg=C["base"])
        btn_inner.pack()

        def _btn(text, color, cmd):
            tk.Button(btn_inner, text=text, font=("Helvetica", 12, "bold"),
                      bg=color, fg=BTN_FG, relief="flat",
                      padx=24, pady=8, cursor="hand2", command=cmd).pack(side="left", padx=5)

        _btn("Load Text", C["lavender"], self._on_load)
        _btn("Generate Passage", C["blue"], self.on_generate_passage)
        _btn("Test Comprehension", C["green"], self._on_test)

        self.quiz_status_label = tk.Label(btn_row, text="", font=("Helvetica", 10),
                                          fg=C["subtext0"], bg=C["base"])
        self.quiz_status_label.pack(pady=(6, 0))

        # ── Text area ──
        border = tk.Frame(self, bg=C["surface0"])
        border.pack(padx=44, fill="both", expand=True)

        self.input_text = tk.Text(
            border, wrap="word", font=("Helvetica", 14),
            bg=C["mantle"], fg=C["text"], insertbackground=C["text"],
            selectbackground=C["surface1"], selectforeground=C["text"],
            relief="flat", padx=18, pady=14,
            spacing1=2, spacing3=2, borderwidth=0,
            highlightthickness=1, highlightbackground=C["surface0"],
            highlightcolor=C["lavender"], undo=True,
        )
        self.input_text.pack(fill="both", expand=True, padx=2, pady=2)
        self.input_text.bind("<KeyRelease>", lambda e: self._update_word_count())

        # Word count
        self.wc_label = tk.Label(self, text="Words: 0", font=("Helvetica", 11),
                                 fg=C["subtext0"], bg=C["base"])
        self.wc_label.pack(side="bottom", pady=(0, 8))

    # ── File loading ───────────────────────────────────────────────────

    def _open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt *.md *.markdown"), ("All files", "*.*")])
        if not path:
            return
        try:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                with open(path, encoding="cp1252", errors="replace") as f:
                    text = f.read()
        except OSError as e:
            self.set_status(f"Could not open file: {e}")
            return
        self.set_text(text.strip())
        self.set_status(f"Loaded {os.path.basename(path)}")

    # ── Actions ────────────────────────────────────────────────────────

    def _update_word_count(self):
        text = self.input_text.get("1.0", "end-1c").strip()
        wc = len(text.split()) if text else 0
        self.wc_label.config(text=f"Words: {wc:,}")

    def _on_load(self):
        raw = self.input_text.get("1.0", "end-1c").strip()
        if raw:
            self.quiz_status_label.config(text="")
            self.on_load_text(raw)

    def _on_test(self):
        raw = self.input_text.get("1.0", "end-1c").strip()
        if not raw:
            self.quiz_status_label.config(text="Paste text first")
            return
        self.quiz_status_label.config(text="")
        self.on_load_text(raw, start_quiz=True)

    def get_text(self) -> str:
        return self.input_text.get("1.0", "end-1c").strip()

    def set_text(self, text: str):
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", text)
        self._update_word_count()

    def set_status(self, msg: str):
        self.quiz_status_label.config(text=msg)
