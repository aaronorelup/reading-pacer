"""
generate_screen.py — Generate a new reading passage via LLM.
User picks topic, style, difficulty, word count.
"""

import tkinter as tk

from reading_pacer.services.llm_service import generate_passage
from reading_pacer.themes import BTN_FG, C


class GenerateScreen(tk.Frame):
    """Shown when user clicks 'Generate Passage' from the main screen."""

    def __init__(self, root, on_close, on_passage_ready):
        super().__init__(root, bg=C["base"])
        self.root = root
        self.on_close = on_close
        self.on_passage_ready = on_passage_ready
        self._cancelled = False

        self._build()

    def _build(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=C["mantle"], padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Generate Passage", font=("Helvetica", 18, "bold"),
                 fg=C["lavender"], bg=C["mantle"]).pack(side="left")
        tk.Button(hdr, text="✕ Cancel", font=("Helvetica", 11),
                  bg=C["surface0"], fg=C["text"], relief="flat",
                  padx=14, pady=4, cursor="hand2",
                  command=self._cancel).pack(side="right")

        # ── Form ──
        form = tk.Frame(self, bg=C["base"])
        form.pack(padx=60, pady=(24, 10), fill="x")

        _labelled(form, "Topic", "e.g. The history of black holes, a medieval knight's quest…")
        self.topic_entry = _e(form)

        _labelled(form, "Style", "narrative, expository, persuasive, descriptive")
        self.style_entry = _e(form, "expository")

        _labelled(form, "Difficulty", "easy, medium, hard, college, academic")
        self.diff_entry = _e(form, "medium")

        tk.Label(form, text="Target length (words)", font=("Helvetica", 11),
                 fg=C["subtext0"], bg=C["base"]).pack(anchor="w", pady=(8, 2))
        self.word_var = tk.StringVar(value="300")
        sf = tk.Frame(form, bg=C["base"])
        sf.pack(fill="x")
        tk.Scale(sf, from_=100, to=1500, resolution=50, orient="horizontal",
                 variable=self.word_var, bg=C["base"], fg=C["text"],
                 highlightthickness=0, troughcolor=C["surface0"],
                 activebackground=C["lavender"], length=400, cursor="hand2").pack(side="left")
        tk.Label(sf, textvariable=self.word_var, font=("Helvetica", 12, "bold"),
                 fg=C["lavender"], bg=C["base"], width=6).pack(side="left", padx=10)

        # ── Generate button ──
        tk.Frame(form, bg=C["base"], height=16).pack()
        self.gen_btn = tk.Button(form, text="⚡ Generate Passage", font=("Helvetica", 13, "bold"),
                                 bg=C["lavender"], fg=BTN_FG, relief="flat",
                                 padx=32, pady=10, cursor="hand2", command=self._generate)
        self.gen_btn.pack()

        # ── Loading / result area ──
        self.loading_frame = tk.Frame(self, bg=C["base"])
        self.loading_frame.pack(fill="both", expand=True, padx=60, pady=10)

        self.status_label = tk.Label(self.loading_frame, text="", font=("Helvetica", 12),
                                     fg=C["subtext0"], bg=C["base"])
        self.status_label.pack(pady=10)

        self.result_text = tk.Text(self.loading_frame, wrap="word",
                                   font=("Georgia", 14), bg=C["mantle"], fg=C["text"],
                                   relief="flat", padx=20, pady=16, height=12,
                                   insertbackground=C["text"])
        self.result_text.pack(fill="both", expand=True)

        self.use_btn = tk.Button(self.loading_frame, text="✔ Use This Passage",
                                 font=("Helvetica", 13, "bold"),
                                 bg=C["green"], fg=BTN_FG, relief="flat",
                                 padx=32, pady=10, cursor="hand2",
                                 command=self._use_passage)
        # Hidden until generation completes

    def _cancel(self):
        self._cancelled = True
        self.on_close()

    def _generate(self):
        self._cancelled = False
        topic = self.topic_entry.get().strip()
        if not topic:
            self.status_label.config(text="Please enter a topic.", fg=C["subtext0"])
            return
        self.gen_btn.config(state="disabled")
        self.status_label.config(text="Generating…", fg=C["subtext0"])
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")
        self.use_btn.pack_forget()

        # LLM callbacks arrive on a worker thread — marshal onto the Tk loop.
        generate_passage(
            topic=topic,
            style=self.style_entry.get().strip() or "expository",
            difficulty=self.diff_entry.get().strip() or "medium",
            word_count=int(self.word_var.get()),
            on_done=lambda p: self.after(0, lambda: self._on_done(p)),
            on_error=lambda err: self.after(0, lambda: self._on_error(err)),
            cancelled=lambda: self._cancelled,
            log=lambda msg: self.after(0, lambda: self._set_status(msg)),
        )

    def _set_status(self, msg: str):
        if self.winfo_exists():
            self.status_label.config(text=msg, fg=C["subtext0"])

    def _on_done(self, passage: str):
        if self._cancelled or not self.winfo_exists():
            return
        self.gen_btn.config(state="normal")
        self.status_label.config(text="Done! Review the passage below:", fg=C["subtext0"])
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", passage)
        self.result_text.config(state="disabled")
        self.use_btn.pack(pady=12)

    def _on_error(self, err: str):
        if self._cancelled or not self.winfo_exists():
            return
        self.gen_btn.config(state="normal")
        self.status_label.config(text=f"Error: {err}", fg=C["red"])

    def _use_passage(self):
        passage = self.result_text.get("1.0", "end-1c").strip()
        if passage:
            self.on_passage_ready(passage)


# ── helpers ────────────────────────────────────────────────────────────

def _labelled(parent, label, hint=""):
    tk.Label(parent, text=label, font=("Helvetica", 11, "bold"),
             fg=C["text"], bg=C["base"]).pack(anchor="w", pady=(10, 0))
    if hint:
        tk.Label(parent, text=hint, font=("Helvetica", 9),
                 fg=C["subtext0"], bg=C["base"]).pack(anchor="w")


def _e(parent, default="", width=60) -> tk.Entry:
    e = tk.Entry(parent, font=("Helvetica", 12), bg=C["surface0"], fg=C["text"],
                 insertbackground=C["text"], relief="flat", width=width)
    e.insert(0, default)
    e.pack(fill="x", pady=(2, 0), ipady=6)
    return e
