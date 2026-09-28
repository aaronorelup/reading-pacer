"""
stats_screen.py — Reading history: totals, a WPM/comprehension trend chart,
and recent sessions. Data comes from services.stats_manager.
"""

import tkinter as tk
from datetime import datetime

from reading_pacer.services import stats_manager
from reading_pacer.themes import C
from reading_pacer.widgets import Button

CHART_SESSIONS = 30  # most recent sessions shown in the trend chart


class StatsScreen(tk.Frame):
    """Full-screen reading-history view, accessed from the main screen."""

    def __init__(self, root, on_close):
        super().__init__(root, bg=C["base"])
        self.root = root
        self.on_close = on_close
        self.sessions = stats_manager.load_sessions()
        self.summary = stats_manager.summary()
        self._build()

    def _build(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=C["mantle"], padx=18, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📊 Reading Stats", font=("Helvetica", 18, "bold"),
                 fg=C["lavender"], bg=C["mantle"]).pack(side="left")
        Button(hdr, text="← Back", font=("Helvetica", 11),
                  bg=C["surface0"], fg=C["text"], relief="flat",
                  padx=14, pady=4, cursor="hand2",
                  command=self.on_close).pack(side="right")

        if not self.sessions:
            centre = tk.Frame(self, bg=C["base"])
            centre.place(relx=0.5, rely=0.45, anchor="center")
            tk.Label(centre, text="No sessions yet", font=("Helvetica", 18, "bold"),
                     fg=C["text"], bg=C["base"]).pack(pady=(0, 8))
            tk.Label(centre,
                     text="Finish a text or complete a comprehension quiz\n"
                          "and your progress will show up here.",
                     font=("Helvetica", 12), fg=C["subtext0"], bg=C["base"],
                     justify="center").pack()
            return

        # ── Summary chips ──
        s = self.summary
        chips = tk.Frame(self, bg=C["base"])
        chips.pack(pady=(20, 6))
        secs = s["total_seconds"]
        time_str = f"{int(secs // 3600)}h {int(secs % 3600 // 60)}m" if secs >= 3600 \
            else f"{int(secs // 60)}m {int(secs % 60)}s"
        self._chip(chips, f"{s['total_words']:,}", "words read")
        self._chip(chips, time_str, "time reading")
        self._chip(chips, str(s["sessions"]), "sessions")
        if s["avg_wpm"]:
            self._chip(chips, f"{s['avg_wpm']:.0f}", "avg wpm")
        if s["avg_score"] is not None:
            self._chip(chips, f"{s['avg_score']:.0f}%", "comprehension")

        # ── Trend chart ──
        chart_box = tk.Frame(self, bg=C["base"])
        chart_box.pack(fill="x", padx=44, pady=(14, 4))
        legend = tk.Frame(chart_box, bg=C["base"])
        legend.pack(anchor="e")
        tk.Label(legend, text="● speed (wpm)", font=("Helvetica", 10),
                 fg=C["lavender"], bg=C["base"]).pack(side="left", padx=6)
        tk.Label(legend, text="● comprehension (%)", font=("Helvetica", 10),
                 fg=C["green"], bg=C["base"]).pack(side="left", padx=6)
        self.chart = tk.Canvas(chart_box, height=180, bg=C["mantle"],
                               highlightthickness=0)
        self.chart.pack(fill="x")
        self.chart.bind("<Configure>", self._draw_chart)

        # ── Recent sessions ──
        tk.Label(self, text="Recent sessions", font=("Helvetica", 13, "bold"),
                 fg=C["text"], bg=C["base"]).pack(anchor="w", padx=44, pady=(16, 4))
        table = tk.Text(self, wrap="none", font=("Consolas", 11),
                        bg=C["mantle"], fg=C["subtext1"], relief="flat",
                        padx=18, pady=12, borderwidth=0, highlightthickness=0)
        table.tag_configure("head", foreground=C["subtext0"])
        table.tag_configure("wpm", foreground=C["lavender"])
        table.tag_configure("score", foreground=C["green"])
        table.insert("end", f"{'date':<14}{'words':>8}{'time':>9}{'wpm':>7}"
                            f"{'quiz':>8}   passage\n", "head")
        for sess in reversed(self.sessions[-10:]):
            date = self._fmt_date(sess.get("ts", ""))
            words = f"{sess.get('words', 0):,}"
            secs = sess.get("seconds", 0)
            dur = f"{int(secs // 60)}:{int(secs % 60):02d}"
            wpm = f"{sess['wpm']:.0f}" if sess.get("wpm") else "–"
            quiz = (f"{sess['quiz_correct']}/{sess['quiz_total']}"
                    if sess.get("quiz_total") else "–")
            preview = (sess.get("preview") or "")[:36]
            table.insert("end", f"{date:<14}{words:>8}{dur:>9}")
            table.insert("end", f"{wpm:>7}", "wpm")
            table.insert("end", f"{quiz:>8}", "score")
            table.insert("end", f"   {preview}\n")
        table.configure(state="disabled", height=min(len(self.sessions), 10) + 1)
        table.pack(fill="x", padx=44, pady=(0, 20))

    def _chip(self, parent, value, label):
        f = tk.Frame(parent, bg=C["surface0"], padx=18, pady=10)
        f.pack(side="left", padx=6)
        tk.Label(f, text=value, font=("Helvetica", 17, "bold"),
                 fg=C["lavender"], bg=C["surface0"]).pack()
        tk.Label(f, text=label, font=("Helvetica", 10),
                 fg=C["subtext0"], bg=C["surface0"]).pack()

    @staticmethod
    def _fmt_date(ts: str) -> str:
        try:
            return datetime.fromisoformat(ts).strftime("%b %d %H:%M")
        except ValueError:
            return ts[:12]

    # ── Chart ──────────────────────────────────────────────────────────

    def _draw_chart(self, _event=None):
        cv = self.chart
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 60:
            return
        data = self.sessions[-CHART_SESSIONS:]
        pad_l, pad_r, pad_t, pad_b = 46, 46, 16, 22
        iw, ih = w - pad_l - pad_r, h - pad_t - pad_b

        wpms = [(i, s["wpm"]) for i, s in enumerate(data) if s.get("wpm")]
        scores = [(i, s["quiz_correct"] / s["quiz_total"] * 100)
                  for i, s in enumerate(data) if s.get("quiz_total")]

        if len(data) < 2 or (len(wpms) < 2 and len(scores) < 2):
            cv.create_text(w / 2, h / 2, text="Complete a few more sessions to see trends",
                           font=("Helvetica", 11), fill=C["overlay0"])
            return

        # Grid lines
        for frac in (0.0, 0.5, 1.0):
            y = pad_t + ih * (1 - frac)
            cv.create_line(pad_l, y, w - pad_r, y, fill=C["surface0"])

        def x_at(i):
            return pad_l + (i / max(len(data) - 1, 1)) * iw

        # WPM series (own scale, left labels)
        if len(wpms) >= 2:
            vals = [v for _, v in wpms]
            lo, hi = min(vals), max(vals)
            span = max(hi - lo, 1.0)
            lo, hi = lo - span * 0.1, hi + span * 0.1
            pts = [(x_at(i), pad_t + ih * (1 - (v - lo) / (hi - lo))) for i, v in wpms]
            for a, b in zip(pts, pts[1:], strict=False):
                cv.create_line(*a, *b, fill=C["lavender"], width=2, smooth=True)
            for x, y in pts:
                cv.create_oval(x - 3, y - 3, x + 3, y + 3, fill=C["lavender"], outline="")
            cv.create_text(pad_l - 8, pad_t + 6, text=f"{hi:.0f}", anchor="e",
                           font=("Helvetica", 9), fill=C["lavender"])
            cv.create_text(pad_l - 8, pad_t + ih - 6, text=f"{lo:.0f}", anchor="e",
                           font=("Helvetica", 9), fill=C["lavender"])

        # Comprehension series (fixed 0–100 scale, right labels)
        if len(scores) >= 1:
            pts = [(x_at(i), pad_t + ih * (1 - v / 100)) for i, v in scores]
            for a, b in zip(pts, pts[1:], strict=False):
                cv.create_line(*a, *b, fill=C["green"], width=2, smooth=True)
            for x, y in pts:
                cv.create_oval(x - 3, y - 3, x + 3, y + 3, fill=C["green"], outline="")
            cv.create_text(w - pad_r + 8, pad_t + 6, text="100%", anchor="w",
                           font=("Helvetica", 9), fill=C["green"])
            cv.create_text(w - pad_r + 8, pad_t + ih - 6, text="0%", anchor="w",
                           font=("Helvetica", 9), fill=C["green"])

        cv.create_text(pad_l, h - 8, text="older", anchor="w",
                       font=("Helvetica", 9), fill=C["overlay0"])
        cv.create_text(w - pad_r, h - 8, text="recent", anchor="e",
                       font=("Helvetica", 9), fill=C["overlay0"])
