"""
PyInstaller runtime hook for certifi.

Ensures certifi can locate its cacert.pem certificate bundle when the
application is running from a PyInstaller bundle (sys.frozen = True).

Without this hook, HTTPS requests to api.deepseek.com will fail with
SSL certificate verification errors because certifi cannot find the
bundled cacert.pem via importlib.resources.
"""

import os
import sys


def _patch_certifi():
    """Help certifi find cacert.pem inside the PyInstaller bundle."""
    import certifi.core as _core

    # In a PyInstaller one-file or one-dir bundle, data files are
    # extracted to sys._MEIPASS.
    bundle_root = sys._MEIPASS if getattr(sys, 'frozen', False) else None
    if not bundle_root:
        return  # not inside a PyInstaller bundle — nothing to do

    # Try the most common locations inside the bundle
    candidates = [
        os.path.join(bundle_root, 'certifi', 'cacert.pem'),
        os.path.join(bundle_root, 'cacert.pem'),
    ]
    cert_path = None
    for candidate in candidates:
        if os.path.isfile(candidate):
            cert_path = candidate
            break

    if not cert_path:
        # cacert.pem not found — certifi's built-in logic may still work
        return

    # Monkey-patch certifi's where() so it returns the correct path
    # inside the bundle on the very first call.
    _original_where = _core.where

    def _patched_where() -> str:
        """Return the correct cacert.pem path inside the PyInstaller bundle."""
        # Return our known-good path; certifi caches the result internally
        # so subsequent calls hit _CACERT_PATH.
        if _core._CACERT_PATH is None:
            _core._CACERT_PATH = cert_path
        return _core._CACERT_PATH

    _core.where = _patched_where


_patch_certifi()
