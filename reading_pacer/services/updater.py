"""
updater.py — Check GitHub Releases for a newer version and (on Windows) install it.

Flow:
  1. check_for_update() asks the GitHub API for the latest release (one small
     HTTPS request, on a daemon thread) and reports an UpdateInfo if its
     version is newer than ours.
  2. On a Windows install made by our installer, download_and_install()
     downloads the new ReadingPacer-Setup-X.Y.Z.exe, verifies its SHA-256
     against the digest GitHub publishes, and runs it silently; the installer
     closes this app, upgrades in place and relaunches it.
  3. Everywhere else (macOS, portable exe, source checkout) the app just opens
     the release page so the user can download it themselves.

Like llm_service, callbacks run on a worker thread — marshal onto Tk with after().
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
import webbrowser
from dataclasses import dataclass

from reading_pacer import __version__

REPO = "aaronorelup/reading-pacer"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
INSTALLER_RE = re.compile(r"^ReadingPacer-Setup-[\d.]+\.exe$")
TIMEOUT = 10


@dataclass
class UpdateInfo:
    version: str             # e.g. "1.2.0"
    page_url: str            # human-readable release page
    notes: str = ""          # release body (markdown)
    installer_url: str = ""  # Windows installer asset, if the release has one
    installer_name: str = ""
    installer_sha256: str = ""  # from GitHub's asset digest, if provided


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.10.2' -> (1, 10, 2). Non-numeric suffixes are ignored."""
    nums = re.findall(r"\d+", text.split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(candidate: str, current: str = __version__) -> bool:
    return parse_version(candidate) > parse_version(current)


def parse_release(data: dict) -> UpdateInfo:
    """Turn a GitHub 'latest release' JSON payload into an UpdateInfo."""
    info = UpdateInfo(
        version=str(data.get("tag_name", "")).lstrip("vV"),
        page_url=data.get("html_url") or RELEASES_PAGE,
        notes=data.get("body") or "",
    )
    for asset in data.get("assets") or []:
        name = asset.get("name", "")
        if INSTALLER_RE.match(name):
            info.installer_name = name
            info.installer_url = asset.get("browser_download_url", "")
            digest = asset.get("digest") or ""
            if digest.startswith("sha256:"):
                info.installer_sha256 = digest.split(":", 1)[1].lower()
            break
    return info


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"ReadingPacer/{__version__}",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_for_update(on_result, on_error=None):
    """Call on_result(UpdateInfo | None) from a worker thread. Never raises."""

    def _work():
        try:
            info = parse_release(_get_json(LATEST_API))
            on_result(info if info.version and is_newer(info.version) else None)
        except Exception as e:  # offline, rate-limited, GitHub down — all non-fatal
            if on_error:
                on_error(str(e))

    threading.Thread(target=_work, daemon=True).start()


# ── Installing ─────────────────────────────────────────────────────────


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def installed_by_installer() -> bool:
    """True when running from a folder our Windows installer created.

    Inno Setup puts its uninstaller (unins000.exe) next to the app, so its
    presence means we can safely upgrade in place.
    """
    if sys.platform != "win32" or not is_frozen():
        return False
    app_dir = os.path.dirname(sys.executable)
    return os.path.isfile(os.path.join(app_dir, "unins000.exe"))


def can_self_install(info: UpdateInfo) -> bool:
    return installed_by_installer() and bool(info.installer_url)


def open_release_page(info: UpdateInfo | None = None):
    webbrowser.open(info.page_url if info else RELEASES_PAGE)


def download_and_install(info: UpdateInfo, on_progress, on_ready, on_error):
    """Download + verify the installer on a worker thread.

    on_progress(fraction 0..1), on_ready(path) and on_error(message) are called
    from the worker thread. After on_ready, call launch_installer(path) on the
    main thread and then quit the app.
    """

    def _work():
        try:
            path = os.path.join(tempfile.gettempdir(), info.installer_name)
            sha = hashlib.sha256()
            req = urllib.request.Request(info.installer_url, headers={
                "User-Agent": f"ReadingPacer/{__version__}",
            })
            with urllib.request.urlopen(req, timeout=30) as resp, open(path, "wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                while chunk := resp.read(64 * 1024):
                    out.write(chunk)
                    sha.update(chunk)
                    done += len(chunk)
                    if total:
                        on_progress(done / total)
            if info.installer_sha256 and sha.hexdigest() != info.installer_sha256:
                os.remove(path)
                raise ValueError("Downloaded file failed its integrity check — "
                                 "please try again or download it from the website.")
            on_ready(path)
        except Exception as e:
            on_error(str(e))

    threading.Thread(target=_work, daemon=True).start()


def launch_installer(path: str):
    """Start the installer detached. It closes this app, upgrades, and relaunches it."""
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
         "/RELAUNCH=1"],
        creationflags=flags, close_fds=True,
    )
