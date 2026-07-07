"""
reading_screen.py — The core pacer with sliding arrow, stats, save/resume, and
a full-screen comprehension quiz (LLM-generated, with a results review).
"""

import re
import time
import tkinter as tk

from reading_pacer.config import config
from reading_pacer.services import save_manager, stats_manager
from reading_pacer.services.llm_service import generate_questions as llm_generate_questions
from reading_pacer.themes import BTN_FG, C

MIN_STATS_WORDS = 30      # don't record sessions shorter than this
MIN_STATS_SECONDS = 10.0


class ReadingScreen(tk.Frame):
    """Main reading pacer — text with sliding indicator, stats, save/quiz."""

    def __init__(self, root, on_new_text, on_show_main):
        super().__init__(root, bg=C["base"])
        self.root = root
        self.on_new_text = on_new_text
        self.on_show_main = on_show_main

        # ── Reading state ──
        self.words: list[str] = []
        self.word_positions: list[tuple[str, str]] = []
        self.current_index = 0
        self.playing = False
        self.wpm = 250
        self.font_size = 17
        self.timer_id = None
        self._next_tick_time = 0

        # Actual reading speed
        self._actual_start_time = 0.0
        self._actual_elapsed = 0.0
        self._actual_timer_active = False

        # Arrow animation
        self._arrow_x = -1.0
        self._arrow_target_x = -1.0
        self._arrow_y = 0
        self._arrow_anim_id = None

        # Auto-save
        self._save_timer_id = None
        self._last_save_state = None

        # Session stats
        self._session_record_idx = None

        # Quiz state
        self.quiz_questions = []
        self.quiz_index = 0
        self.quiz_correct = 0
        self.quiz_total = 0
        self._quiz_missed = []
        self._quiz_cancelled = False
        self._quiz_spin_id = None
        self._quiz_advance_id = None
        self._quiz_frame = None
        self._quiz_main_area = None   # the reading-content area we hide during quiz

        self._build()
        self._bind_keys()

    def destroy(self):
        """Cancel pending timers so no callback fires on a dead widget."""
        for attr in ("timer_id", "_arrow_anim_id", "_save_timer_id",
                     "_quiz_spin_id", "_quiz_advance_id"):
            tid = getattr(self, attr, None)
            if tid:
                try:
                    self.root.after_cancel(tid)
                except Exception:
                    pass
                setattr(self, attr, None)
        super().destroy()

    # ═══════════════════════════════════════════════════════════════════
    #  BUILD  (bottom bar packed FIRST so it never goes off-screen)
    # ═══════════════════════════════════════════════════════════════════

    def _build(self):
        # ── Top bar ──
        top = tk.Frame(self, bg=C["mantle"], padx=14, pady=9)
        top.pack(fill="x")

        # WPM
        wpm_box = tk.Frame(top, bg=C["mantle"])
        wpm_box.pack(side="left", padx=(0, 18))
        tk.Label(wpm_box, text="WPM", font=("Helvetica", 10),
                 fg=C["subtext0"], bg=C["mantle"]).pack(side="left", padx=(0, 6))
        _sbtn(wpm_box, "−", lambda: self._adj_speed(-25)).pack(side="left")
        self.wpm_label = tk.Label(wpm_box, text="250", font=("Helvetica", 13, "bold"),
                                  fg=C["lavender"], bg=C["mantle"], width=5)
        self.wpm_label.pack(side="left", padx=4)
        _sbtn(wpm_box, "+", lambda: self._adj_speed(25)).pack(side="left")

        # Font
        font_box = tk.Frame(top, bg=C["mantle"])
        font_box.pack(side="left", padx=(0, 18))
        tk.Label(font_box, text="Font", font=("Helvetica", 10),
                 fg=C["subtext0"], bg=C["mantle"]).pack(side="left", padx=(0, 6))
        _sbtn(font_box, "A↓", lambda: self._adj_font(-1)).pack(side="left")
        _sbtn(font_box, "A↑", lambda: self._adj_font(1)).pack(side="left", padx=(4, 0))

        # Right-side buttons
        tk.Button(top, text="💾 Save", font=("Helvetica", 10),
                  bg=C["surface0"], fg=C["text"], relief="flat", padx=12, pady=2,
                  cursor="hand2", command=self._manual_save).pack(side="right", padx=4)
        tk.Button(top, text="New Text", font=("Helvetica", 10),
                  bg=C["surface0"], fg=C["text"], relief="flat", padx=12, pady=2,
                  cursor="hand2", command=self._do_new_text).pack(side="right")

        # ── Bottom bar — packed FIRST with side="bottom" ──
        bot_outer = tk.Frame(self, bg=C["mantle"])
        bot_outer.pack(fill="x", side="bottom")
        tk.Frame(bot_outer, bg=C["surface1"], height=1).pack(fill="x")

        bot = tk.Frame(bot_outer, bg=C["mantle"], padx=20, pady=16)
        bot.pack(fill="x")

        ctrl = tk.Frame(bot, bg=C["mantle"])
        ctrl.pack(side="left")
        self.play_btn = _ctrl(ctrl, "▶", self._toggle_play)
        self.play_btn.pack(side="left", padx=(0, 8))
        _ctrl(ctrl, "⏮", self._restart).pack(side="left", padx=(0, 8))
        _ctrl(ctrl, "⏹", self._stop).pack(side="left")
        tk.Button(ctrl, text="📝 Quiz", font=("Helvetica", 12, "bold"),
                  bg=C["green"], fg=BTN_FG, relief="flat", padx=20, pady=6,
                  cursor="hand2", command=self._start_quiz).pack(side="left", padx=(14, 0))

        # Stats
        stat = tk.Frame(bot, bg=C["mantle"])
        stat.pack(side="right")
        self.actual_wpm_label = tk.Label(stat, text="", font=("Helvetica", 14, "bold"),
                                         fg=C["green"], bg=C["mantle"], anchor="e")
        self.actual_wpm_label.pack(anchor="e", pady=(0, 4))
        self.stats_label = tk.Label(stat, text="", font=("Helvetica", 13),
                                    fg=C["subtext1"], bg=C["mantle"], anchor="e")
        self.stats_label.pack(anchor="e")
        tk.Label(stat, text="Space: play/pause · ← →: skip · ↑ ↓: speed",
                 font=("Helvetica", 10), fg=C["overlay0"], bg=C["mantle"],
                 anchor="e").pack(anchor="e", pady=(4, 0))

        # Progress bar
        prog_box = tk.Frame(bot, bg=C["mantle"])
        prog_box.pack(side="left", fill="x", expand=True, padx=24)
        self.progress_canvas = tk.Canvas(prog_box, height=10, bg=C["mantle"],
                                         highlightthickness=0)
        self.progress_canvas.pack(fill="x", pady=(0, 4))
        self.progress_canvas.bind("<Configure>", self._draw_progress)
        self.progress_canvas.bind("<Button-1>", self._on_progress_click)
        self.progress_pct = tk.Label(prog_box, text="0 %", font=("Helvetica", 12, "bold"),
                                     fg=C["lavender"], bg=C["mantle"])
        self.progress_pct.pack()

        # ── Arrow indicator ──
        self.arrow_canvas = tk.Canvas(self, height=20, bg=C["base"],
                                      highlightthickness=0)
        self.arrow_canvas.pack(fill="x")
        self.arrow_canvas.bind("<Configure>", self._on_arrow_resize)

        # ── Reading content area (text + scrollbar), hidden during quiz ──
        self._quiz_main_area = tk.Frame(self, bg=C["base"])
        self._quiz_main_area.pack(fill="both", expand=True)   # AFTER bottom bar

        txt_box = tk.Frame(self._quiz_main_area, bg=C["base"])
        txt_box.pack(fill="both", expand=True)

        self.text_widget = tk.Text(
            txt_box, wrap="word", state="disabled",
            font=("Georgia", self.font_size),
            bg=C["base"], fg=C["text"],
            relief="flat", padx=44, pady=26,
            spacing1=5, spacing2=3, spacing3=5,
            borderwidth=0, highlightthickness=0, cursor="hand2",
        )
        sb = tk.Scrollbar(txt_box, command=self.text_widget.yview,
                          bg=C["surface0"], troughcolor=C["mantle"],
                          relief="flat", width=10)
        self.text_widget.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text_widget.pack(side="left", fill="both", expand=True)

        self.text_widget.tag_configure("line_hl", background=C["line_hl"])
        self.text_widget.tag_lower("line_hl")
        self.text_widget.bind("<Button-1>", self._on_word_click)
        # Re-anchor arrow + highlight after the text re-wraps on resize
        self.text_widget.bind("<Configure>", lambda e: self.root.after_idle(self._re_anchor))

        # ── Quiz frame (hidden; replaces _quiz_main_area when active) ──
        self._quiz_frame = tk.Frame(self, bg=C["base"])

    # ── Key bindings ────────────────────────────────────────────────────
    # Bound on the root window, so every handler must first check that this
    # screen still exists AND is currently visible — the app swaps screens
    # by pack_forget, and a destroyed screen must never react to keys.

    def _bind_keys(self):
        r = self.root
        r.bind("<space>", self._on_space)
        r.bind("<Left>", self._guarded(lambda: self._skip(-5)))
        r.bind("<Right>", self._guarded(lambda: self._skip(5)))
        r.bind("<Up>", self._guarded(lambda: self._adj_speed(25)))
        r.bind("<Down>", self._guarded(lambda: self._adj_speed(-25)))
        r.bind("<Control-r>", self._guarded(self._restart))
        r.bind("<Control-s>", self._guarded(self._manual_save))
        r.bind("<equal>", self._guarded(lambda: self._adj_font(1)))
        r.bind("<plus>", self._guarded(lambda: self._adj_font(1)))
        r.bind("<minus>", self._guarded(lambda: self._adj_font(-1)))
        for key, letter in [("1", "A"), ("2", "B"), ("3", "C"), ("4", "D"),
                            ("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")]:
            r.bind(key, lambda e, let=letter: self._on_quiz_key(let))

    def _alive_and_visible(self) -> bool:
        try:
            return bool(self.winfo_exists()) and bool(self.winfo_ismapped())
        except tk.TclError:
            return False

    def _guarded(self, fn):
        """Wrap a reading-control handler: only fire when visible and not in quiz."""
        def handler(event=None):
            if not self._alive_and_visible() or self._quiz_frame.winfo_ismapped():
                return None
            fn()
            return "break"
        return handler

    # ═══════════════════════════════════════════════════════════════════
    #  TEXT LOADING
    # ═══════════════════════════════════════════════════════════════════

    def load_text(self, raw: str, word_index: int = 0, wpm: int = 250,
                  actual_elapsed: float = 0.0, font_size: int = 17):
        self._pause()
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        tw = self.text_widget
        tw.configure(state="normal")
        tw.delete("1.0", "end")
        tw.insert("1.0", raw)
        tw.configure(state="disabled")

        # Compute each word's Tk index (line.column) in one O(n) pass.
        self.words = []
        self.word_positions = []
        line_starts = [0]  # char offset of the start of each line
        for m in re.finditer("\n", raw):
            line_starts.append(m.end())

        def _tk_index(offset: int) -> str:
            # Binary search for the line containing this offset
            lo, hi = 0, len(line_starts) - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if line_starts[mid] <= offset:
                    lo = mid
                else:
                    hi = mid - 1
            return f"{lo + 1}.{offset - line_starts[lo]}"

        for m in re.finditer(r"\S+", raw):
            self.words.append(m.group())
            self.word_positions.append((_tk_index(m.start()), _tk_index(m.end())))

        self.current_index = min(word_index, max(len(self.words) - 1, 0))
        self.wpm = wpm
        self.font_size = font_size
        self._actual_elapsed = actual_elapsed
        self._actual_start_time = 0.0
        self._actual_timer_active = False
        self._arrow_x = -1.0
        self._session_record_idx = None

        self.text_widget.configure(font=("Georgia", self.font_size))

        # Ensure we're showing reading content (not stuck on quiz)
        self._show_reading_content()

        self.root.after(50, self._refresh_display)
        self.root.after(70, self._auto_scroll)  # jump to the resume position
        self._update_stats()
        self._update_actual_speed()
        self._draw_progress()
        self._schedule_auto_save()

    def get_raw_text(self) -> str:
        return self.text_widget.get("1.0", "end-1c").strip()

    # ═══════════════════════════════════════════════════════════════════
    #  PLAYBACK
    # ═══════════════════════════════════════════════════════════════════

    def _toggle_play(self):
        if not self.words:
            return
        self._pause() if self.playing else self._play()

    def _play(self):
        if self.current_index >= len(self.words):
            self.current_index = 0
        self.playing = True
        self._next_tick_time = 0
        if not self._actual_timer_active:
            self._actual_start_time = time.monotonic()
            self._actual_timer_active = True
        self.play_btn.configure(text="⏸")
        self._schedule_tick()

    def _pause(self):
        self.playing = False
        if self._actual_timer_active:
            self._actual_elapsed += time.monotonic() - self._actual_start_time
            self._actual_timer_active = False
        if hasattr(self, "play_btn"):
            self.play_btn.configure(text="▶")
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

    def _stop(self):
        self._pause()
        self._actual_elapsed = 0.0
        self.current_index = 0
        self._refresh_display()
        self.text_widget.see("1.0")
        self._schedule_auto_save()

    def _restart(self):
        self._stop()

    def _schedule_tick(self):
        if not self.playing:
            return
        delay = max(int(60_000.0 / max(self.wpm, 1)), 10)
        now_ms = int(time.monotonic() * 1000)
        if self._next_tick_time == 0:
            self._next_tick_time = now_ms + delay
            fire_in = delay
        else:
            self._next_tick_time += delay
            fire_in = max(1, self._next_tick_time - now_ms)
        self.timer_id = self.root.after(fire_in, self._tick)

    def _tick(self):
        if not self.playing:
            return
        self.current_index += 1
        if self.current_index >= len(self.words):
            self.current_index = len(self.words) - 1
            self._pause()
            self._refresh_display()
            self._record_finish()
            return
        self._animate_arrow_to(self.current_index)
        self._update_line_highlight()
        self._auto_scroll()
        if self.current_index % 5 == 0:
            self._update_stats()
            self._update_actual_speed()
            self._draw_progress()
            self._schedule_auto_save()
        self._schedule_tick()

    def _skip(self, delta: int):
        if not self.words:
            return
        self.current_index = max(0, min(len(self.words) - 1, self.current_index + delta))
        self._refresh_display()
        self._auto_scroll()
        self._schedule_auto_save()

    def _adj_speed(self, delta: int):
        self.wpm = max(50, min(1000, self.wpm + delta))
        self._update_stats()

    def _adj_font(self, delta: int):
        self.font_size = max(10, min(36, self.font_size + delta))
        self.text_widget.configure(font=("Georgia", self.font_size))

    # ═══════════════════════════════════════════════════════════════════
    #  ARROW + LINE HIGHLIGHT
    # ═══════════════════════════════════════════════════════════════════

    def _on_arrow_resize(self, event=None):
        self._arrow_y = max(self.arrow_canvas.winfo_height() - 2, 4)
        self._draw_arrow()

    def _draw_arrow(self):
        cv = self.arrow_canvas
        cv.delete("arrow")
        x = self._arrow_x
        if x < 0:
            return
        y, s = self._arrow_y, 7
        cv.create_polygon(x - s, y - s * 2, x + s, y - s * 2, x, y,
                          fill=C["lavender"], outline="", tags="arrow")

    def _word_center_x(self, index: int):
        if index < 0 or index >= len(self.word_positions):
            return None
        tw = self.text_widget
        s, e = self.word_positions[index]
        try:
            bs = tw.bbox(s)
            be = tw.bbox(f"{e}-1c")
        except Exception:
            return None
        if bs is None or be is None:
            return None
        tw_x = tw.winfo_x()
        ax = self.arrow_canvas.winfo_x()
        return (tw_x + bs[0] - ax + tw_x + be[0] + be[2] - ax) / 2.0

    def _snap_arrow_to(self, index):
        x = self._word_center_x(index)
        if x is not None:
            self._arrow_x = self._arrow_target_x = x
            self._draw_arrow()

    def _animate_arrow_to(self, index):
        x = self._word_center_x(index)
        if x is None:
            return
        self._arrow_target_x = x
        if self._arrow_x < 0:
            self._arrow_x = x
        self._cancel_arrow_anim()
        self._arrow_step()

    def _cancel_arrow_anim(self):
        if self._arrow_anim_id:
            self.root.after_cancel(self._arrow_anim_id)
            self._arrow_anim_id = None

    def _arrow_step(self):
        diff = self._arrow_target_x - self._arrow_x
        if abs(diff) < 0.5:
            self._arrow_x = self._arrow_target_x
            self._draw_arrow()
            return
        self._arrow_x += diff * 0.35
        self._draw_arrow()
        self._arrow_anim_id = self.root.after(16, self._arrow_step)

    def _update_line_highlight(self):
        tw = self.text_widget
        tw.tag_remove("line_hl", "1.0", "end")
        if not self.word_positions or self.current_index >= len(self.word_positions):
            return
        s, _ = self.word_positions[self.current_index]
        # "display" = the wrapped visual line, not the whole logical paragraph
        tw.tag_add("line_hl", f"{s} display linestart", f"{s} display lineend +1c")

    # ═══════════════════════════════════════════════════════════════════
    #  DISPLAY
    # ═══════════════════════════════════════════════════════════════════

    def _refresh_display(self):
        self._snap_arrow_to(self.current_index)
        self._update_line_highlight()
        self._update_stats()
        self._update_actual_speed()
        self._draw_progress()

    def _re_anchor(self):
        """After a resize/re-wrap, move the arrow and highlight to the current word."""
        if not self.words or not self.winfo_exists():
            return
        self._snap_arrow_to(self.current_index)
        self._update_line_highlight()

    def _auto_scroll(self):
        if self.word_positions and self.current_index < len(self.word_positions):
            s, _ = self.word_positions[self.current_index]
            self.text_widget.see(s)

    def _update_stats(self):
        total = len(self.words)
        if total == 0:
            return
        cur = self.current_index
        mins = (total - cur) / max(self.wpm, 1)
        if mins >= 1:
            t = f"{int(mins)}:{int((mins % 1) * 60):02d}"
        else:
            t = f"{max(int(mins * 60), 0)}s"
        self.stats_label.configure(
            text=f"{total:,} words  ·  word {cur + 1:,}  ·  ~{t} remaining")
        self.wpm_label.configure(text=str(self.wpm))

    def _current_elapsed(self) -> float:
        elapsed = self._actual_elapsed
        if self._actual_timer_active:
            elapsed += time.monotonic() - self._actual_start_time
        return elapsed

    def _update_actual_speed(self):
        elapsed = self._current_elapsed()
        if elapsed < 1.0 or self.current_index < 3:
            self.actual_wpm_label.configure(text="")
            return
        wpm = self.current_index / (elapsed / 60.0)
        m, s = int(elapsed) // 60, int(elapsed) % 60
        self.actual_wpm_label.configure(text=f"Actual: {wpm:.0f} wpm  ·  {m}:{s:02d} elapsed")

    def _draw_progress(self, _event=None):
        cv = self.progress_canvas
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 4:
            return
        total = max(len(self.words), 1)
        frac = self.current_index / total
        cv.create_rectangle(0, 0, w, h, fill=C["surface0"], outline="")
        fw = max(int(frac * w), 0)
        if fw > 0:
            cv.create_rectangle(0, 0, fw, h, fill=C["lavender"], outline="")
        r = h // 2
        cv.create_oval(max(fw, r) - r, 0, max(fw, r) + r, h, fill=C["lavender"], outline="")
        self.progress_pct.configure(text=f"{int(frac * 100)} %")

    # ═══════════════════════════════════════════════════════════════════
    #  CLICKS
    # ═══════════════════════════════════════════════════════════════════

    def _on_word_click(self, event):
        if not self.word_positions:
            return
        tw = self.text_widget
        idx = tw.index(f"@{event.x},{event.y}")
        for i, (s, e) in enumerate(self.word_positions):
            if tw.compare(idx, ">=", s) and tw.compare(idx, "<=", e):
                self.current_index = i
                self._refresh_display()
                return

    def _on_progress_click(self, event):
        w = self.progress_canvas.winfo_width()
        if w < 1 or not self.words:
            return
        frac = max(0.0, min(1.0, event.x / w))
        self.current_index = min(int(frac * len(self.words)), len(self.words) - 1)
        self._refresh_display()
        self._auto_scroll()

    def _on_space(self, event):
        if not self._alive_and_visible() or self._quiz_frame.winfo_ismapped():
            return None
        self._toggle_play()
        return "break"

    # ═══════════════════════════════════════════════════════════════════
    #  SAVE / NEW TEXT / SESSION STATS
    # ═══════════════════════════════════════════════════════════════════

    def _get_save_state(self) -> tuple:
        return (self.get_raw_text(), self.current_index, self.wpm,
                self._actual_elapsed, self.font_size)

    def _manual_save(self):
        save_manager.save_state(*self._get_save_state())
        self.stats_label.configure(text="✓ Saved")
        self.root.after(1500, self._update_stats)

    def _schedule_auto_save(self):
        if self._save_timer_id:
            self.root.after_cancel(self._save_timer_id)
        self._save_timer_id = self.root.after(5000, self._auto_save)

    def _auto_save(self):
        state = self._get_save_state()
        if state != self._last_save_state:
            save_manager.save_state(*state)
            self._last_save_state = state

    def _do_new_text(self):
        self._pause()
        save_manager.delete_save()
        text = self.get_raw_text()
        self.on_new_text(text)

    def _text_preview(self) -> str:
        return " ".join(self.words[:10])

    def _record_finish(self):
        """Record a session when the pacer reaches the end of the text."""
        elapsed = self._current_elapsed()
        if (self._session_record_idx is not None
                or len(self.words) < MIN_STATS_WORDS or elapsed < MIN_STATS_SECONDS):
            return
        wpm = len(self.words) / (elapsed / 60.0)
        self._session_record_idx = stats_manager.record_session(
            words=len(self.words), seconds=elapsed, wpm=wpm,
            preview=self._text_preview())

    def _record_quiz(self):
        """Record (or amend) a session when a quiz completes."""
        elapsed = self._current_elapsed()
        have_reading = elapsed >= MIN_STATS_SECONDS and self.current_index >= MIN_STATS_WORDS
        wpm = (self.current_index / (elapsed / 60.0)) if have_reading else None
        if self._session_record_idx is not None:
            stats_manager.update_session(self._session_record_idx,
                                         quiz_correct=self.quiz_correct,
                                         quiz_total=self.quiz_total)
        else:
            self._session_record_idx = stats_manager.record_session(
                words=len(self.words), seconds=elapsed, wpm=wpm,
                quiz_correct=self.quiz_correct, quiz_total=self.quiz_total,
                preview=self._text_preview())

    # ═══════════════════════════════════════════════════════════════════
    #  COMPREHENSION QUIZ — full-screen
    # ═══════════════════════════════════════════════════════════════════

    def _start_quiz(self):
        if not self.words:
            return
        self._pause()
        self._quiz_cancelled = False
        self._show_quiz_loading()
        # LLM callbacks arrive on a worker thread — marshal onto the Tk loop.
        llm_generate_questions(
            text=self.get_raw_text(),
            num_questions=config.quiz_questions,
            on_done=lambda qs: self.after(0, lambda: self._on_questions_ready(qs)),
            on_error=lambda err: self.after(0, lambda: self._on_quiz_error(err)),
            cancelled=lambda: self._quiz_cancelled,
            log=lambda msg: self.after(0, lambda: self._set_quiz_loading_text(msg)),
        )

    def _show_quiz_loading(self):
        # Swap: hide reading content, show quiz frame
        self._quiz_main_area.pack_forget()
        self._quiz_frame.pack(fill="both", expand=True)
        # Wipe previous quiz content
        for w in self._quiz_frame.winfo_children():
            w.destroy()

        centre = tk.Frame(self._quiz_frame, bg=C["base"])
        centre.place(relx=0.5, rely=0.5, anchor="center")

        # ── Spinning indicator ──
        self._quiz_spin_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._quiz_spin_idx = 0
        self._quiz_spin_label = tk.Label(centre, text="⠋", font=("Helvetica", 40),
                                         fg=C["lavender"], bg=C["base"])
        self._quiz_spin_label.pack(pady=(0, 10))
        self._spin_quiz_loader()

        self._quiz_loading_text = tk.Label(centre, text="Generating questions…",
                                           font=("Helvetica", 14),
                                           fg=C["text"], bg=C["base"])
        self._quiz_loading_text.pack(pady=4)

        self._quiz_loading_sub = tk.Label(centre, text="",
                                          font=("Helvetica", 11),
                                          fg=C["subtext0"], bg=C["base"])
        self._quiz_loading_sub.pack(pady=4)

        tk.Button(self._quiz_frame, text="Cancel", font=("Helvetica", 11),
                  bg=C["surface0"], fg=C["text"], relief="flat",
                  padx=16, pady=4, cursor="hand2",
                  command=self._cancel_quiz).pack(side="bottom", pady=20)

    def _spin_quiz_loader(self):
        if not self._quiz_frame.winfo_ismapped():
            return
        self._quiz_spin_idx = (self._quiz_spin_idx + 1) % len(self._quiz_spin_chars)
        try:
            self._quiz_spin_label.config(text=self._quiz_spin_chars[self._quiz_spin_idx])
        except tk.TclError:
            return
        self._quiz_spin_id = self.root.after(80, self._spin_quiz_loader)

    def _set_quiz_loading_text(self, msg: str):
        if hasattr(self, "_quiz_loading_sub") and self._quiz_loading_sub.winfo_exists():
            self._quiz_loading_sub.config(text=msg)

    def _stop_quiz_timers(self):
        for attr in ("_quiz_spin_id", "_quiz_advance_id"):
            tid = getattr(self, attr, None)
            if tid:
                self.root.after_cancel(tid)
                setattr(self, attr, None)

    def _cancel_quiz(self):
        self._quiz_cancelled = True
        self._stop_quiz_timers()
        self._show_reading_content()

    def _on_questions_ready(self, questions: list):
        if self._quiz_cancelled or not self.winfo_exists():
            return
        self._stop_quiz_timers()
        self.quiz_questions = questions
        self.quiz_index = 0
        self.quiz_correct = 0
        self.quiz_total = 0
        self._quiz_missed = []
        self._show_quiz_question()

    def _on_quiz_error(self, err: str):
        if self._quiz_cancelled or not self.winfo_exists():
            return
        self._stop_quiz_timers()
        if hasattr(self, "_quiz_loading_text") and self._quiz_loading_text.winfo_exists():
            self._quiz_loading_text.config(text=f"Error: {err[:160]}", fg=C["red"])
            self._quiz_loading_sub.config(text="Check Settings, then try again.")

    def _show_reading_content(self):
        """Restore reading view after quiz."""
        self._quiz_frame.pack_forget()
        self._quiz_main_area.pack(fill="both", expand=True)

    def _show_quiz_question(self):
        if self.quiz_index >= len(self.quiz_questions):
            self._show_quiz_results()
            return

        q = self.quiz_questions[self.quiz_index]
        n = self.quiz_index + 1
        total = len(self.quiz_questions)
        # Difficulty ramps from ★ to ★★★★ across however many questions there are
        level = 1 + round(3 * self.quiz_index / max(total - 1, 1))
        diff = "★" * level + "☆" * (4 - level)

        # Rebuild quiz frame content
        for w in self._quiz_frame.winfo_children():
            w.destroy()

        # Header
        hdr = tk.Frame(self._quiz_frame, bg=C["mantle"], padx=18, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"Q{n}/{total}  {diff}", font=("Helvetica", 13, "bold"),
                 fg=C["lavender"], bg=C["mantle"]).pack(side="left")
        score = f"{self.quiz_correct}/{self.quiz_total} correct" if self.quiz_total else ""
        tk.Label(hdr, text=score, font=("Helvetica", 12),
                 fg=C["subtext1"], bg=C["mantle"]).pack(side="right")

        # Progress bar
        pcv = tk.Canvas(self._quiz_frame, height=6, bg=C["base"], highlightthickness=0)
        pcv.pack(fill="x", padx=40, pady=(10, 4))
        pcv.bind("<Configure>",
                 lambda e, cv=pcv, t=total, i=self.quiz_index: self._quiz_bar(cv, t, i))

        # Question
        tk.Label(self._quiz_frame, text=q["question"], font=("Helvetica", 16),
                 fg=C["text"], bg=C["base"], wraplength=700, justify="left").pack(
                     padx=50, pady=(16, 14), anchor="w")

        # Answers
        ans_frame = tk.Frame(self._quiz_frame, bg=C["base"])
        ans_frame.pack(fill="x", padx=50)
        self._quiz_buttons = []
        for i, choice in enumerate(q["choices"]):
            letter = chr(65 + i)
            btn = tk.Button(ans_frame, text=f"{letter}) {choice}", font=("Helvetica", 13),
                            bg=C["surface0"], fg=C["text"], relief="flat",
                            padx=20, pady=12, anchor="w", cursor="hand2",
                            command=lambda let=letter: self._answer_quiz(let))
            btn.pack(fill="x", pady=3)
            self._quiz_buttons.append(btn)

        # Feedback
        self._quiz_feedback = tk.Label(self._quiz_frame, text="", font=("Helvetica", 13),
                                       fg=C["subtext0"], bg=C["base"])
        self._quiz_feedback.pack(pady=(10, 6))

        # Bottom
        tk.Button(self._quiz_frame, text="✕ Close Quiz", font=("Helvetica", 10),
                  bg=C["surface0"], fg=C["subtext1"], relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  command=self._cancel_quiz).pack(side="bottom", pady=12)

    def _quiz_bar(self, cv, total, idx):
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 4:
            return
        frac = idx / max(total, 1)
        cv.create_rectangle(0, 0, w, h, fill=C["surface0"], outline="")
        fw = max(int(frac * w), 0)
        if fw > 0:
            cv.create_rectangle(0, 0, fw, h, fill=C["green"], outline="")

    def _answer_quiz(self, selected: str):
        q = self.quiz_questions[self.quiz_index]
        correct = (selected == q["correct"])
        self.quiz_total += 1
        if correct:
            self.quiz_correct += 1
        else:
            self._quiz_missed.append({"q": q, "selected": selected})

        for i, btn in enumerate(self._quiz_buttons):
            letter = chr(65 + i)
            btn.config(state="disabled")
            if letter == q["correct"]:
                btn.config(bg=C["green"], fg=BTN_FG)
            elif letter == selected and not correct:
                btn.config(bg=C["red"], fg=BTN_FG)

        self._quiz_feedback.config(
            text="✓ Correct!" if correct else f"✗ Correct answer: {q['correct']}",
            fg=C["green"] if correct else C["red"])

        self.quiz_index += 1
        self._quiz_advance_id = self.root.after(1200, self._show_quiz_question)

    def _show_quiz_results(self):
        self._record_quiz()
        for w in self._quiz_frame.winfo_children():
            w.destroy()

        total = max(self.quiz_total, 1)
        pct = self.quiz_correct / total * 100
        if pct >= 85:
            rating, color = "Excellent comprehension!", C["green"]
        elif pct >= 70:
            rating, color = "Good — slow down for detail-rich passages.", C["peach"]
        else:
            rating, color = "Read slower to retain more details.", C["red"]

        tk.Button(self._quiz_frame, text="← Back to Reading", font=("Helvetica", 12, "bold"),
                  bg=C["lavender"], fg=BTN_FG, relief="flat",
                  padx=24, pady=10, cursor="hand2",
                  command=self._cancel_quiz).pack(side="bottom", pady=16)

        tk.Label(self._quiz_frame, text="Test Complete!", font=("Helvetica", 22, "bold"),
                 fg=C["lavender"], bg=C["base"]).pack(pady=(30, 10))
        tk.Label(self._quiz_frame, text=f"Score: {self.quiz_correct}/{total} ({pct:.0f}%)",
                 font=("Helvetica", 28, "bold"), fg=color, bg=C["base"]).pack(pady=(0, 6))
        tk.Label(self._quiz_frame, text=rating, font=("Helvetica", 14),
                 fg=C["subtext0"], bg=C["base"]).pack(pady=(0, 12))

        # ── Review of missed questions ──
        if self._quiz_missed:
            review = tk.Text(self._quiz_frame, wrap="word", font=("Helvetica", 12),
                             bg=C["mantle"], fg=C["text"], relief="flat",
                             padx=20, pady=14, borderwidth=0, highlightthickness=0)
            review.tag_configure("q", font=("Helvetica", 12, "bold"), spacing1=10)
            review.tag_configure("wrong", foreground=C["red"])
            review.tag_configure("right", foreground=C["green"], spacing3=6)
            review.insert("end", "Review — questions you missed:\n", "q")
            for miss in self._quiz_missed:
                q = miss["q"]
                sel = miss["selected"]
                sel_text = q["choices"][ord(sel) - 65]
                cor = q["correct"]
                cor_text = q["choices"][ord(cor) - 65]
                review.insert("end", f"\n{q['question']}\n", "q")
                review.insert("end", f"  ✗ You answered {sel}) {sel_text}\n", "wrong")
                review.insert("end", f"  ✓ Correct: {cor}) {cor_text}\n", "right")
            review.configure(state="disabled")
            review.pack(fill="both", expand=True, padx=50, pady=(6, 4))
        else:
            tk.Label(self._quiz_frame, text="Perfect score — nothing to review! 🎉",
                     font=("Helvetica", 13), fg=C["green"], bg=C["base"]).pack(pady=8)

    def _on_quiz_key(self, letter: str):
        if not self._alive_and_visible() or not self._quiz_frame.winfo_ismapped():
            return None
        if self.quiz_index >= len(self.quiz_questions):
            return None
        if not hasattr(self, "_quiz_buttons") or not self._quiz_buttons:
            return None
        if self._quiz_buttons[0].cget("state") != "normal":
            return None
        self._answer_quiz(letter)
        return "break"


# ── Widget helpers ─────────────────────────────────────────────────────

def _sbtn(parent, text, cmd):
    return tk.Button(parent, text=text, font=("Helvetica", 11),
                     bg=C["surface0"], fg=C["text"], relief="flat",
                     padx=8, pady=1, cursor="hand2", command=cmd)


def _ctrl(parent, text, cmd):
    return tk.Button(parent, text=text, font=("Helvetica", 20),
                     bg=C["surface0"], fg=C["text"], relief="flat",
                     padx=16, pady=6, cursor="hand2", command=cmd)
