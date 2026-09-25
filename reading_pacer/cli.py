"""
cli.py — Command-line entry point (the `reading-pacer` command, `python -m
reading_pacer`, and the packaged app all start here).

    reading-pacer                 start the app
    reading-pacer --version       print the version
    reading-pacer --self-test     run the automated smoke test (see selftest.py)
"""

import os
import sys


def _configure_tls():
    """Give Python a trusted-certificate list on macOS.

    python.org's macOS Python (which the Mac app is built with) does not use the
    system keychain, so HTTPS calls fail with CERTIFICATE_VERIFY_FAILED unless
    OpenSSL is pointed at certifi's bundle. The Mac build ships certifi.
    """
    if sys.platform != "darwin" or os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
    except ImportError:
        return
    os.environ["SSL_CERT_FILE"] = certifi.where()


def main():
    _configure_tls()
    args = sys.argv[1:]
    if "--version" in args:
        from reading_pacer import __version__
        print(f"Reading Pacer {__version__}")
        return
    if "--self-test" in args:
        # Imported lazily: the self-test must set up its data folder before
        # the app's config module reads settings from disk.
        from reading_pacer import selftest
        sys.exit(selftest.main(args))

    from reading_pacer.app import main as run_app
    run_app()


if __name__ == "__main__":
    main()
