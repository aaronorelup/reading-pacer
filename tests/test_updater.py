"""Tests for version comparison and GitHub release parsing (no network)."""

from reading_pacer.services import updater


def test_version_comparison():
    assert updater.is_newer("1.1.0", "1.0.0")
    assert updater.is_newer("v1.10.0", "1.9.3")  # numeric, not string, comparison
    assert updater.is_newer("2.0", "1.9.9")
    assert not updater.is_newer("1.0.0", "1.0.0")
    assert not updater.is_newer("0.9.9", "1.0.0")
    assert not updater.is_newer("garbage", "1.0.0")


def test_parse_release_finds_installer_and_digest():
    info = updater.parse_release({
        "tag_name": "v1.2.0",
        "html_url": "https://github.com/x/y/releases/tag/v1.2.0",
        "body": "Notes",
        "assets": [
            {"name": "ReadingPacer-1.2.0-macOS-arm64.dmg",
             "browser_download_url": "https://example.com/a.dmg"},
            {"name": "ReadingPacer-Setup-1.2.0.exe",
             "browser_download_url": "https://example.com/setup.exe",
             "digest": "sha256:ABCDEF"},
        ],
    })
    assert info.version == "1.2.0"
    assert info.notes == "Notes"
    assert info.installer_name == "ReadingPacer-Setup-1.2.0.exe"
    assert info.installer_url == "https://example.com/setup.exe"
    assert info.installer_sha256 == "abcdef"


def test_parse_release_without_installer():
    info = updater.parse_release({"tag_name": "v1.2.0", "assets": []})
    assert info.installer_url == ""
    assert info.page_url == updater.RELEASES_PAGE
    assert not updater.can_self_install(info)
