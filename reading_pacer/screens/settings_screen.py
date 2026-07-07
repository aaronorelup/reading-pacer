"""
settings_screen.py — Configure LLM providers (API + local), quiz, and appearance.
Full-screen, accessed from the main screen via the ⚙ button.
"""

import tkinter as tk
from tkinter import filedialog

from reading_pacer.config import MAX_QUIZ_QUESTIONS, MIN_QUIZ_QUESTIONS, config
from reading_pacer.services import llm_service
from reading_pacer.themes import BTN_FG, C

# Preset → (base URL, default model). Selecting one fills the URL/model fields.
PROVIDER_PRESETS = {
    "DeepSeek": ("https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
    "OpenAI": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    "OpenRouter": ("https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    "Ollama (local server)": ("http://localhost:11434/v1/chat/completions", "llama3.1"),
    "LM Studio (local server)": ("http://localhost:1234/v1/chat/completions", "local-model"),
    "Custom": None,
}


class SettingsScreen(tk.Frame):
    """Full-screen settings frame with scrolling content."""

    def __init__(self, root, on_close):
        super().__init__(root, bg=C["base"])
        self.root = root
        self.on_close = on_close
        self._build()

    def _build(self):
        pad = {"padx": 40, "pady": 8, "fill": "x"}

        # ── Header ──
        hdr = tk.Frame(self, bg=C["mantle"], padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙ Settings", font=("Helvetica", 18, "bold"),
                 fg=C["lavender"], bg=C["mantle"]).pack(side="left")
        tk.Button(hdr, text="← Back", font=("Helvetica", 11),
                  bg=C["surface0"], fg=C["text"], relief="flat",
                  padx=14, pady=4, cursor="hand2",
                  command=self.on_close).pack(side="right")

        # ── Scrolling content ──
        canvas = tk.Canvas(self, bg=C["base"], highlightthickness=0)
        scroll = tk.Scrollbar(self, command=canvas.yview)
        inner = tk.Frame(canvas, bg=C["base"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=scroll.set)

        def _on_canvas_configure(event):
            canvas.itemconfig("inner", width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # ── Default Provider ──
        tk.Label(inner, text="Default Provider", font=("Helvetica", 14, "bold"),
                 fg=C["text"], bg=C["base"]).pack(anchor="w", **pad)
        self.provider_var = tk.StringVar(value=config.llm_default_provider)
        pf = tk.Frame(inner, bg=C["base"])
        pf.pack(**pad)
        for text, value in [("API (DeepSeek, OpenAI, Ollama, any OpenAI-compatible)", "api"),
                            ("Local GGUF model (llama-cpp-python)", "local")]:
            tk.Radiobutton(pf, text=text, variable=self.provider_var, value=value,
                           font=("Helvetica", 12), fg=C["text"], bg=C["base"],
                           selectcolor=C["surface1"], activebackground=C["base"],
                           activeforeground=C["lavender"], cursor="hand2").pack(anchor="w")
        tk.Label(pf, text="If the default fails, the other is tried automatically.",
                 font=("Helvetica", 10), fg=C["overlay0"], bg=C["base"]).pack(anchor="w")

        # ── API section ──
        _section(inner, "API Model")

        tk.Label(inner, text="Provider preset", font=("Helvetica", 11),
                 fg=C["subtext0"], bg=C["base"]).pack(anchor="w", padx=40, pady=(6, 0))
        self.preset_var = tk.StringVar(value=self._detect_preset())
        preset_menu = tk.OptionMenu(inner, self.preset_var, *PROVIDER_PRESETS.keys(),
                                    command=self._apply_preset)
        preset_menu.configure(font=("Helvetica", 11), bg=C["surface0"], fg=C["text"],
                              relief="flat", cursor="hand2", highlightthickness=0,
                              activebackground=C["surface1"], activeforeground=C["text"])
        preset_menu["menu"].configure(font=("Helvetica", 11), bg=C["surface0"], fg=C["text"])
        preset_menu.pack(anchor="w", padx=40, pady=(2, 0))

        tk.Label(inner, text="API Key   (get one at platform.deepseek.com — "
                             "not needed for local servers)",
                 font=("Helvetica", 11), fg=C["subtext0"], bg=C["base"],
                 ).pack(anchor="w", padx=40, pady=(10, 0))
        key_row = tk.Frame(inner, bg=C["base"])
        key_row.pack(fill="x", padx=40, pady=(2, 0))
        self.api_key_entry = tk.Entry(key_row, font=("Helvetica", 12), bg=C["surface0"],
                                      fg=C["text"], insertbackground=C["text"],
                                      relief="flat", show="•")
        self.api_key_entry.insert(0, config.llm_api_key)
        self.api_key_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self._key_shown = False

        def _toggle_key():
            self._key_shown = not self._key_shown
            self.api_key_entry.config(show="" if self._key_shown else "•")
            show_btn.config(text="Hide" if self._key_shown else "Show")
        show_btn = tk.Button(key_row, text="Show", font=("Helvetica", 10),
                             bg=C["surface0"], fg=C["text"], relief="flat",
                             padx=10, pady=4, cursor="hand2", command=_toggle_key)
        show_btn.pack(side="right", padx=(8, 0))

        tk.Label(inner, text="Model Name", font=("Helvetica", 11),
                 fg=C["subtext0"], bg=C["base"]).pack(anchor="w", padx=40, pady=(10, 0))
        self.api_model_entry = _entry(inner, config.llm_api_model)

        tk.Label(inner, text="API Base URL (chat completions endpoint)",
                 font=("Helvetica", 11),
                 fg=C["subtext0"], bg=C["base"]).pack(anchor="w", padx=40, pady=(10, 0))
        self.api_url_entry = _entry(inner, config.llm_api_base_url)

        # Test connection
        test_row = tk.Frame(inner, bg=C["base"])
        test_row.pack(fill="x", padx=40, pady=(12, 0))
        self.test_btn = tk.Button(test_row, text="⚡ Test Connection",
                                  font=("Helvetica", 11, "bold"),
                                  bg=C["blue"], fg=BTN_FG, relief="flat",
                                  padx=16, pady=6, cursor="hand2", command=self._test_connection)
        self.test_btn.pack(side="left")
        self.test_status = tk.Label(test_row, text="", font=("Helvetica", 11),
                                    fg=C["subtext0"], bg=C["base"], wraplength=460,
                                    justify="left")
        self.test_status.pack(side="left", padx=12)

        # ── Local section ──
        _section(inner, "Local Model")
        tk.Label(inner, text="Model Path (.gguf) — requires: pip install reading-pacer[local]",
                 font=("Helvetica", 11),
                 fg=C["subtext0"], bg=C["base"]).pack(anchor="w", padx=40, pady=(6, 0))
        lf = tk.Frame(inner, bg=C["base"])
        lf.pack(**pad)
        self.local_path_entry = tk.Entry(lf, font=("Helvetica", 12), bg=C["surface0"],
                                         fg=C["text"], insertbackground=C["text"],
                                         relief="flat", width=50)
        self.local_path_entry.insert(0, config.llm_local_path)
        self.local_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        tk.Button(lf, text="Browse…", font=("Helvetica", 10),
                  bg=C["surface0"], fg=C["text"], relief="flat", padx=10, pady=4,
                  cursor="hand2", command=self._browse_local).pack(side="right")

        sf = tk.Frame(inner, bg=C["base"])
        sf.pack(**pad)
        self.ctx_entry = _labelled_num(sf, "Context Size", str(config.llm_local_context_size))
        self.gpu_entry = _labelled_num(sf, "GPU Layers", str(config.llm_local_gpu_layers))

        # ── Quiz section ──
        _section(inner, "Quiz")
        qf = tk.Frame(inner, bg=C["base"])
        qf.pack(**pad)
        tk.Label(qf, text="Questions per quiz", font=("Helvetica", 11),
                 fg=C["subtext0"], bg=C["base"]).pack(side="left", padx=(0, 10))
        self.quiz_n_var = tk.StringVar(value=str(config.quiz_questions))
        tk.Spinbox(qf, from_=MIN_QUIZ_QUESTIONS, to=MAX_QUIZ_QUESTIONS,
                   textvariable=self.quiz_n_var, width=4, font=("Helvetica", 12),
                   bg=C["surface0"], fg=C["text"], relief="flat",
                   buttonbackground=C["surface1"], insertbackground=C["text"],
                   ).pack(side="left")

        # ── Appearance section ──
        _section(inner, "Appearance")
        af = tk.Frame(inner, bg=C["base"])
        af.pack(**pad)
        self.theme_var = tk.StringVar(value=config.theme)
        for text, value in [("Mocha (dark)", "mocha"), ("Latte (light)", "latte")]:
            tk.Radiobutton(af, text=text, variable=self.theme_var, value=value,
                           font=("Helvetica", 12), fg=C["text"], bg=C["base"],
                           selectcolor=C["surface1"], activebackground=C["base"],
                           activeforeground=C["lavender"], cursor="hand2",
                           ).pack(side="left", padx=(0, 16))
        tk.Label(af, text="(restart to apply)", font=("Helvetica", 10),
                 fg=C["overlay0"], bg=C["base"]).pack(side="left")

        # ── Save ──
        tk.Frame(inner, bg=C["base"], height=20).pack()
        tk.Button(inner, text="Save & Close", font=("Helvetica", 13, "bold"),
                  bg=C["green"], fg=BTN_FG, relief="flat", padx=32, pady=10,
                  cursor="hand2", command=self._save).pack(pady=16)

    # ── Presets ────────────────────────────────────────────────────────

    def _detect_preset(self) -> str:
        for name, preset in PROVIDER_PRESETS.items():
            if preset and preset[0] == config.llm_api_base_url:
                return name
        return "Custom"

    def _apply_preset(self, name: str):
        preset = PROVIDER_PRESETS.get(name)
        if not preset:
            return
        url, model = preset
        self.api_url_entry.delete(0, "end")
        self.api_url_entry.insert(0, url)
        self.api_model_entry.delete(0, "end")
        self.api_model_entry.insert(0, model)

    # ── Test connection ────────────────────────────────────────────────

    def _test_connection(self):
        # Apply current field values (without persisting) so the test uses them
        self._apply_fields()
        if not config.has_api():
            self.test_status.config(text="Enter an API key (or a localhost URL) first.",
                                    fg=C["peach"])
            return
        self.test_btn.config(state="disabled")
        self.test_status.config(text="Testing…", fg=C["subtext0"])
        llm_service.test_connection(
            on_done=lambda msg: self.after(0, lambda: self._test_result(msg, ok=True)),
            on_error=lambda msg: self.after(0, lambda: self._test_result(msg, ok=False)),
        )

    def _test_result(self, msg: str, ok: bool):
        if not self.winfo_exists():
            return
        self.test_btn.config(state="normal")
        self.test_status.config(text=("✓ " if ok else "✗ ") + msg,
                                fg=C["green"] if ok else C["red"])

    # ── Save ───────────────────────────────────────────────────────────

    def _browse_local(self):
        path = filedialog.askopenfilename(
            filetypes=[("GGUF files", "*.gguf"), ("All files", "*.*")])
        if path:
            self.local_path_entry.delete(0, "end")
            self.local_path_entry.insert(0, path)

    def _apply_fields(self):
        """Copy widget values into the config object (does not write to disk)."""
        config.llm_default_provider = self.provider_var.get()
        config.llm_api_key = self.api_key_entry.get().strip()
        config.llm_api_model = self.api_model_entry.get().strip()
        config.llm_api_base_url = self.api_url_entry.get().strip()
        config.llm_local_path = self.local_path_entry.get().strip()
        try:
            config.llm_local_context_size = int(self.ctx_entry.get() or 4096)
        except ValueError:
            pass
        try:
            config.llm_local_gpu_layers = int(self.gpu_entry.get() or 0)
        except ValueError:
            pass
        try:
            config.quiz_questions = max(MIN_QUIZ_QUESTIONS,
                                        min(MAX_QUIZ_QUESTIONS, int(self.quiz_n_var.get())))
        except ValueError:
            pass
        config.theme = self.theme_var.get()

    def _save(self):
        self._apply_fields()
        config.save()
        self.on_close()


# ── helpers ────────────────────────────────────────────────────────────

def _section(parent, title):
    sep = tk.Frame(parent, bg=C["surface1"], height=1)
    sep.pack(fill="x", padx=30, pady=(16, 8))
    tk.Label(parent, text=title, font=("Helvetica", 13, "bold"),
             fg=C["lavender"], bg=C["base"]).pack(anchor="w", padx=40, pady=(0, 4))


def _entry(parent, default, show=None, width=60) -> tk.Entry:
    e = tk.Entry(parent, font=("Helvetica", 12), bg=C["surface0"], fg=C["text"],
                 insertbackground=C["text"], relief="flat", show=show, width=width)
    e.insert(0, default)
    e.pack(fill="x", padx=40, pady=(2, 0), ipady=6)
    return e


def _labelled_num(parent, label, default) -> tk.Entry:
    f = tk.Frame(parent, bg=C["base"])
    f.pack(side="left", padx=(0, 16))
    tk.Label(f, text=label, font=("Helvetica", 10), fg=C["subtext0"], bg=C["base"]).pack()
    e = tk.Entry(f, font=("Helvetica", 12), bg=C["surface0"], fg=C["text"],
                 insertbackground=C["text"], relief="flat", width=8)
    e.insert(0, default)
    e.pack(ipady=4)
    return e
