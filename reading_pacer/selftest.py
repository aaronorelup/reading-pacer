"""
selftest.py — Launch the real app, walk through every screen, and report.

    ReadingPacer --self-test --report result.txt --screenshots shots/

Used by CI on clean Windows, macOS and Linux machines to prove that the
*packaged* app (not just the source) starts, renders every screen, paces
text, and can reach the update server. It runs against a throwaway data
folder, so it never touches a real user's settings or reading progress.
Exit code 0 = everything passed.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

SAMPLE = (
    "The lighthouse keepers of the nineteenth century lived by a rhythm few people "
    "today would recognize. Every evening the keeper climbed the tower stairs to "
    "light the lamp, and every morning he climbed them again to put it out.\n\n"
    "Between those two climbs the light could never be allowed to fail, because "
    "somewhere out in the dark a ship was steering by it."
)


class SelfTest:
    def __init__(self, report_path: str | None, shots_dir: str | None, network: bool):
        self.report_path = report_path
        self.shots_dir = shots_dir
        self.network = network
        self.lines: list[str] = []
        self.failed = 0

    def log(self, msg: str):
        self.lines.append(msg)
        if sys.stdout:
            print(msg, flush=True)

    def check(self, name: str, fn):
        try:
            detail = fn()
            self.log(f"PASS  {name}" + (f" — {detail}" if detail else ""))
        except Exception:
            self.failed += 1
            self.log(f"FAIL  {name}\n{traceback.format_exc()}")

    # ── helpers ────────────────────────────────────────────────────────

    def pump(self, seconds: float):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.02)

    def screenshot(self, name: str):
        """Capture just the app window (best effort — never fails the test)."""
        if not self.shots_dir:
            return
        self.root.lift()
        self.pump(0.4)
        os.makedirs(self.shots_dir, exist_ok=True)
        path = os.path.abspath(os.path.join(self.shots_dir, f"{name}.png"))
        r = self.root
        x, y, w, h = r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height()
        try:
            if sys.platform == "darwin":
                # screencapture works in points; Tk reports points on macOS too.
                cmd = ["screencapture", "-x", f"-R{x},{y},{w},{h}", path]
            elif sys.platform == "win32":
                ps = (
                    "Add-Type -AssemblyName System.Drawing;"
                    f"$b=New-Object System.Drawing.Bitmap {w},{h};"
                    "$g=[System.Drawing.Graphics]::FromImage($b);"
                    f"$g.CopyFromScreen({x},{y},0,0,$b.Size);"
                    f"$b.Save('{path}',[System.Drawing.Imaging.ImageFormat]::Png)"
                )
                cmd = ["powershell", "-NoProfile", "-Command", ps]
            else:
                cmd = ["import", "-window", "root", "-crop", f"{w}x{h}+{x}+{y}", path]
            subprocess.run(cmd, timeout=30, check=True, capture_output=True,
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
            self.log(f"      screenshot {name}.png")
        except Exception as e:
            self.log(f"      (screenshot {name} skipped: {e})")

    # ── the test ───────────────────────────────────────────────────────

    def run(self) -> int:
        import tkinter as tk

        from reading_pacer import __version__, crashlog
        from reading_pacer.app import App, _enable_windows_dpi_awareness, _set_window_icon

        self.log(crashlog.system_summary())
        _enable_windows_dpi_awareness()
        self.root = tk.Tk()
        _set_window_icon(self.root)
        errors: list[str] = []
        # Any exception inside a Tk callback is a failure, not a dialog.
        self.root.report_callback_exception = (
            lambda et, e, tb: errors.append("".join(traceback.format_exception(et, e, tb))))

        app = None

        def start():
            nonlocal app
            app = App(self.root)
            self.pump(1.0)
            assert app.main_screen and app.main_screen.winfo_ismapped()
            self.screenshot("1-main")

        def assets():
            from reading_pacer import app as app_mod
            base = os.path.join(os.path.dirname(os.path.abspath(app_mod.__file__)), "assets")
            for f in ("icon.ico", "icon.png"):
                assert os.path.isfile(os.path.join(base, f)), f"missing asset {f}"

        def reading():
            app.main_screen.set_text(SAMPLE)
            app._on_load_text(SAMPLE)
            rs = app.reading_screen
            self.pump(0.5)
            rs._toggle_play()
            self.pump(2.5)
            rs._toggle_play()
            assert rs.current_index > 0, "pacer arrow did not move"
            rs._manual_save()
            self.screenshot("2-reading")
            return f"paced to word {rs.current_index}"

        def settings():
            app._show_settings()
            self.pump(0.6)
            self.screenshot("3-settings")
            app.settings_screen._save()  # exercises writing config
            self.pump(0.2)

        def stats():
            app._show_stats()
            self.pump(0.6)
            self.screenshot("4-stats")
            app._close_stats()

        def generate():
            app.reading_screen._do_new_text()
            self.pump(0.3)
            app._show_generate_screen()
            self.pump(0.6)
            self.screenshot("5-generate")
            app._close_generate()

        def update_dialog():
            from reading_pacer.screens.update_dialog import UpdateDialog
            from reading_pacer.services.updater import UpdateInfo
            dlg = UpdateDialog(self.root, UpdateInfo(
                version="9.9.9", page_url="https://example.invalid",
                notes="### Self-test\n- This dialog is a rendering check."), on_quit=lambda: None)
            self.pump(0.6)
            dlg.destroy()

        def crash_log():
            crashlog.write("self-test entry")
            assert os.path.isfile(crashlog.log_path())

        def update_server():
            import gc
            import threading
            gc.collect()  # free destroyed widgets' Tk variables on the main thread

            from reading_pacer.services import updater
            done = threading.Event()
            result: dict = {}
            updater.check_for_update(
                on_result=lambda info: (result.update(info=info), done.set()),
                on_error=lambda msg: (result.update(error=msg), done.set()))
            assert done.wait(20), "timed out talking to GitHub"
            if "error" in result:
                raise RuntimeError(result["error"])
            info = result.get("info")
            return f"newer release {info.version}" if info else f"{__version__} is current"

        self.check("app starts and shows main screen", start)
        if app:
            self.check("bundled assets present", assets)
            self.check("reading screen paces text + saves", reading)
            self.check("settings screen opens and saves", settings)
            self.check("stats screen opens", stats)
            self.check("generate screen opens", generate)
            self.check("update dialog renders", update_dialog)
            self.check("crash log is writable", crash_log)
            if self.network:
                self.check("update server reachable", update_server)
        for e in errors:
            self.failed += 1
            self.log(f"FAIL  error inside the UI\n{e}")

        try:
            self.root.destroy()
        except tk.TclError:
            pass
        self.log("RESULT: " + ("PASSED" if not self.failed else f"FAILED ({self.failed})"))
        if self.report_path:
            with open(self.report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines) + "\n")
        return 0 if not self.failed else 1


def main(argv: list[str]) -> int:
    def opt(name):
        return argv[argv.index(name) + 1] if name in argv[:-1] else None

    # Isolate BEFORE the app modules load their config from disk: a fresh,
    # empty data folder, so the test never reads or deletes real user data.
    home = tempfile.mkdtemp(prefix="reading-pacer-selftest-")
    os.environ["READING_PACER_HOME"] = home
    with open(os.path.join(home, ".env"), "w", encoding="utf-8") as f:
        f.write("CHECK_FOR_UPDATES=false\n")  # the test checks explicitly instead
    try:
        return SelfTest(opt("--report"), opt("--screenshots"), "--no-network" not in argv).run()
    finally:
        shutil.rmtree(home, ignore_errors=True)
