"""`export_cookies.py`, the helper `browser_python` runs over the bound browser
profile: a fake `playwright` package ahead on `sys.path` answers a canned
cookie list, so no browser is launched."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

UNIT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = UNIT_DIR / "scripts" / "export_cookies.py"

COOKIES = [
    {"name": "SID", "value": "sid-value", "domain": ".youtube.com", "path": "/", "expires": 1900000000.5, "secure": True, "httpOnly": True},
    {"name": "YSC", "value": "session-value", "domain": ".youtube.com", "path": "/", "expires": -1, "secure": True},
    {"name": "NID", "value": "nid-value", "domain": ".google.com", "path": "/", "expires": 1900000001, "secure": False},
    {"name": "gv", "value": "gv-value", "domain": "r1---sn.googlevideo.com", "path": "/", "expires": 1900000002, "secure": True},
    {"name": "other", "value": "other-value", "domain": "example.com", "path": "/x", "expires": 1900000003, "secure": True},
    {"name": "lookalike", "value": "x", "domain": "notyoutube.com", "path": "/", "expires": 1900000004, "secure": True},
]

FAKE_PLAYWRIGHT = """
import json, os, pathlib
class _Context:
    def __init__(self):
        self.closed = False
    def cookies(self):
        return json.loads(os.environ["FAKE_COOKIES"])
    def close(self):
        self.closed = True
        pathlib.Path(os.environ["FAKE_CLOSED"]).write_text("closed")
class _Chromium:
    def launch_persistent_context(self, directory, **kwargs):
        pathlib.Path(os.environ["FAKE_LAUNCH"]).write_text(json.dumps({"directory": str(directory), **kwargs}))
        return _Context()
class _PW:
    chromium = _Chromium()
class sync_playwright:
    def __enter__(self):
        return _PW()
    def __exit__(self, *a):
        return False
"""


def export(tmp_path, cookies, *, out_name="cookies.txt"):
    pkg = tmp_path / "site" / "playwright"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "sync_api.py").write_text(FAKE_PLAYWRIGHT)
    profile = tmp_path / "profile"
    profile.mkdir()
    out = profile / out_name
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "site"), "FAKE_COOKIES": json.dumps(cookies),
           "FAKE_LAUNCH": str(tmp_path / "launch.json"), "FAKE_CLOSED": str(tmp_path / "closed")}
    cp = subprocess.run([sys.executable, str(SCRIPT), str(profile), str(out)], env=env, capture_output=True, text=True)
    launch = json.loads((tmp_path / "launch.json").read_text()) if (tmp_path / "launch.json").exists() else None
    return cp, out, launch, (tmp_path / "closed").exists()


def test_the_jar_is_a_netscape_file_of_the_venue_cookies_only(tmp_path):
    cp, out, launch, closed = export(tmp_path, COOKIES)
    assert cp.returncode == 0, cp.stderr
    raw = out.read_bytes()
    assert raw.startswith(b"# Netscape HTTP Cookie File\n") and b"\r" not in raw
    rows = [line.split("\t") for line in raw.decode().splitlines() if line and not line.startswith("#")]
    assert [r[5] for r in rows] == ["SID", "YSC", "NID", "gv"]  # example.com and notyoutube.com are filtered
    assert all(len(r) == 7 for r in rows)
    sid, ysc, nid, gv = rows
    assert sid == [".youtube.com", "TRUE", "/", "TRUE", "1900000000", "SID", "sid-value"]
    assert ysc[4] == "0"  # a session cookie's expiry is 0
    assert nid[3] == "FALSE"
    assert gv[:2] == ["r1---sn.googlevideo.com", "FALSE"]  # no leading dot: host-only


def test_the_jar_is_private_and_the_profile_was_opened_headless_then_closed(tmp_path):
    cp, out, launch, closed = export(tmp_path, COOKIES)
    assert cp.returncode == 0
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    assert launch["directory"] == str(out.parent) and launch["headless"] is True and "channel" not in launch
    assert launch["args"] == ["--disable-blink-features=AutomationControlled"] and launch["ignore_default_args"] == ["--enable-automation"]
    assert closed


def test_no_venue_cookies_is_exit_2_with_one_stderr_line_and_no_file(tmp_path):
    cp, out, _, closed = export(tmp_path, [c for c in COOKIES if c["domain"] in ("example.com", "notyoutube.com")])
    assert cp.returncode == 2
    assert len(cp.stderr.strip().splitlines()) == 1 and "youtube.com" in cp.stderr
    assert not out.exists() and closed
    assert not list(out.parent.glob("*.tmp*")) and not list(out.parent.glob(".cookies*"))


def test_a_cookie_value_never_reaches_stdout_or_stderr(tmp_path):
    cp, _, _, _ = export(tmp_path, COOKIES)
    assert "sid-value" not in cp.stdout + cp.stderr


def test_the_wrong_argv_is_usage(tmp_path):
    cp = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert cp.returncode == 2 and "usage" in cp.stderr
