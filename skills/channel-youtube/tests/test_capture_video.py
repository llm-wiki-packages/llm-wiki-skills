"""The harvest stage's script, run as the runner runs it: `capture_video.py
ticket=<id>` at the wiki root, with a stand-in `yt-dlp` on PATH and a stand-in
front door, so no venue is reached."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

UNIT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = UNIT_DIR / "scripts" / "capture_video.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
META = json.loads((FIXTURES / "metadata.json").read_text(encoding="utf-8"))
ITEM = META["webpage_url"]
TICKET_ID = "8c1d2e3f4a5b"
CAP = "_raw/yt-job/watch--1a2b3c4d"

# Logs every argv; `FAKE_YT_FAIL` is the stderr a failing yt-dlp prints (exit 1).
FAKE_YT_DLP = f"""#!{sys.executable}
import json, os, pathlib, sys
argv = sys.argv[1:]
pathlib.Path(os.environ["FAKE_LOG"]).open("a").write(json.dumps(argv) + "\\n")
if os.environ.get("FAKE_YT_FAIL"):
    print(os.environ["FAKE_YT_FAIL"], file=sys.stderr)
    sys.exit(1)
if "--dump-json" in argv:
    sys.stdout.write(os.environ.get("FAKE_YT_META") or pathlib.Path(os.environ["FAKE_FIXTURES"], "metadata.json").read_text())
else:
    out = pathlib.Path(argv[argv.index("-o") + 1].replace("%(id)s", "dQw4fixture").replace("%(ext)s", "en.vtt"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pathlib.Path(os.environ["FAKE_FIXTURES"], "dQw4fixture.en.vtt").read_text())
"""


def front_door(tmp_path, ticket):
    stub = tmp_path / "ops_stub.py"
    stub.write_text(
        "import json, os, pathlib, sys\n"
        "argv = sys.argv[1:]\n"
        "verb = [a for a in argv if not a.startswith('--')]\n"
        f"TICKET = json.loads({json.dumps(json.dumps(ticket))})\n"
        "if verb[:3] == ['pipeline', 'tickets', 'open']:\n"
        "    print(json.dumps({'ticket': TICKET})); sys.exit(0)\n"
        "if verb[:3] == ['pipeline', 'tickets', 'update']:\n"
        "    pathlib.Path(os.environ['FAKE_UPDATES']).open('a').write(json.dumps(argv) + '\\n'); sys.exit(0)\n"
        "sys.exit(9)\n"
    )
    return shlex.join([sys.executable, str(stub)])


def harvest(tmp_path, *, fail="", meta="", **over):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "yt-dlp"
    fake.write_text(FAKE_YT_DLP, encoding="utf-8")
    fake.chmod(0o755)
    ticket = {"ticket": TICKET_ID, "stage": "harvest", "slug": "yt-job", "item": ITEM, "target": ITEM,
              "capture_dir": CAP, "known": [], "options": {}}
    ticket.update(over)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "LLM_WIKI_OPS": front_door(tmp_path, ticket),
           "FAKE_LOG": str(tmp_path / "yt.log"), "FAKE_UPDATES": str(tmp_path / "updates.log"),
           "FAKE_FIXTURES": str(FIXTURES), "FAKE_YT_FAIL": fail, "FAKE_YT_META": meta}
    cp = subprocess.run([sys.executable, str(SCRIPT), f"ticket={TICKET_ID}"], cwd=tmp_path, env=env, capture_output=True, text=True)
    read = lambda name: [json.loads(line) for line in (tmp_path / name).read_text().splitlines()] if (tmp_path / name).exists() else []  # noqa: E731
    return cp, read("yt.log"), read("updates.log")


def test_a_harvest_leaves_the_bytes_a_record_and_one_ok_update(tmp_path):
    cp, calls, updates = harvest(tmp_path)
    assert cp.returncode == 0, cp.stderr
    cap = tmp_path / CAP
    assert (cap / "metadata.json").is_file() and (cap / "captions" / "dQw4fixture.en.vtt").is_file()
    record = json.loads((cap / "capture.json").read_text())
    assert record["item"] == ITEM and record["body"] == "metadata.json" and record["title"] == META["title"]
    assert len(updates) == 1 and updates[0][-3:] == [TICKET_ID, "stage=harvest", "status=ok"]
    # The item is one argv element, after `--`: a url carrying `&` is never a shell line.
    assert all(c[-2] == "--" and c[-1] == ITEM for c in calls) and len(calls) == 2


def test_a_known_item_is_ok_and_fetches_nothing(tmp_path):
    cp, calls, updates = harvest(tmp_path, known=[{"resource": ITEM}])
    assert cp.returncode == 0 and calls == []
    assert any(a.startswith("reason=known") for a in updates[0]) and "status=ok" in updates[0]


def test_a_refresh_fetches_a_known_item(tmp_path):
    _, calls, _ = harvest(tmp_path, known=[{"resource": ITEM}], refresh=True)
    assert len(calls) == 2


@pytest.mark.parametrize("stderr, why", [
    ("ERROR: Sign in to confirm your age", "auth"),
    ("ERROR: Tunnel connection failed: 403 Forbidden: host x is not in the allowlist", "denied"),
    ("ERROR: HTTP Error 403: Forbidden", "error"),  # YouTube's own 403 is retryable, never `denied`
    ("ERROR: read operation timed out", "timeout"),
    ("ERROR: something else", "error"),
])
def test_a_failed_yt_dlp_is_one_failed_update_naming_the_host_and_why(tmp_path, stderr, why):
    (tmp_path / CAP).mkdir(parents=True)
    (tmp_path / CAP / "capture.json").write_text("{}")  # an earlier run's record must not survive
    cp, _, updates = harvest(tmp_path, fail=stderr)
    assert cp.returncode == 0, cp.stderr
    assert "status=failed" in updates[0] and f"missing=www.youtube.com,{ITEM},{why}" in updates[0]
    assert not (tmp_path / CAP / "metadata.json").exists() and not (tmp_path / CAP / "capture.json").exists()


def test_a_capture_record_that_cannot_be_written_is_a_failed_update_not_an_ok(tmp_path):
    cp, calls, updates = harvest(tmp_path, meta="{not json")
    assert cp.returncode == 0, cp.stderr
    assert len(updates) == 1 and "status=failed" in updates[0] and "status=ok" not in updates[0]


def test_an_item_that_is_no_url_is_failed_and_never_run(tmp_path):
    _, calls, updates = harvest(tmp_path, item="--exec=rm -rf /")
    assert calls == [] and "status=failed" in updates[0]


def test_the_manifest_declares_the_script_beside_the_sandbox():
    manifest = json.loads((UNIT_DIR / "manifest.json").read_text())
    assert manifest["stages"]["harvest"]["script"] == "scripts/capture_video.py"
    assert (UNIT_DIR / "scripts" / "capture_video.py").is_file() and "sandbox_ref" in manifest["stages"]["harvest"]
    assert "# /// script" not in SCRIPT.read_text()  # a block in a script stage is refused at install


# --- a bound `dir` credential: the browser profile, and the cookie jar exported into it once ---

# Stands in for `browser_python` running `export_cookies.py <profile> <jar>`: logs the argv it was
# handed, then writes a jar (`FAKE_EXPORT_FAIL` set: exits 3 with one stderr line, writing nothing).
FAKE_BROWSER_PYTHON = f"""#!{sys.executable}
import json, os, pathlib, sys
pathlib.Path(os.environ["FAKE_EXPORT_LOG"]).open("a").write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("FAKE_EXPORT_FAIL"):
    print("playwright: no cookies for youtube.com in the profile", file=sys.stderr)
    sys.exit(3)
pathlib.Path(sys.argv[3]).write_text("# Netscape HTTP Cookie File\\n")  # argv: <export_cookies.py> <profile> <jar>
if os.environ.get("FAKE_EXPORT_TOUCHES_DB"):
    db = pathlib.Path(sys.argv[2], "Default", "Cookies"); db.parent.mkdir(parents=True, exist_ok=True)
    db.write_text("sqlite"); os.utime(db, ns=(1 << 62, 1 << 62))  # far in the future: strictly newer than the jar
"""


def bound(tmp_path, *, jar=False, export_fails=False, db=None, touches_db=False, **over):
    """A ticket bound to a browser `dir`: `credential_dir` is a profile the slice may write and
    `browser_python` a stand-in that logs every invocation. `db` is the profile cookie DB's age
    relative to the jar: "older" or "newer". Returns (cp, calls, updates, exports, jar)."""
    profile = tmp_path / "profile"
    profile.mkdir(exist_ok=True)
    jar_path = profile / "cookies.txt"
    if jar is not False:  # True: a good jar; a str: that exact body
        jar_path.write_text("# Netscape HTTP Cookie File\n" if jar is True else jar)
        os.utime(jar_path, ns=(1_700_000_000 * 10**9,) * 2)
    if db:
        cookie_db = profile / "Default" / "Cookies"
        cookie_db.parent.mkdir(parents=True, exist_ok=True)
        cookie_db.write_text("sqlite")
        os.utime(cookie_db, ns=((1_700_000_000 + (3600 if db == "newer" else -3600)) * 10**9,) * 2)
    python = tmp_path / "browser_python"
    python.write_text(FAKE_BROWSER_PYTHON, encoding="utf-8")
    python.chmod(0o755)
    os.environ["FAKE_EXPORT_LOG"] = str(tmp_path / "export.log")
    os.environ["FAKE_EXPORT_FAIL"] = "1" if export_fails else ""
    os.environ["FAKE_EXPORT_TOUCHES_DB"] = "1" if touches_db else ""
    try:
        cp, calls, updates = harvest(tmp_path, credential="youtube", credential_dir=str(profile), browser_python=str(python), **over)
    finally:
        del os.environ["FAKE_EXPORT_LOG"], os.environ["FAKE_EXPORT_FAIL"], os.environ["FAKE_EXPORT_TOUCHES_DB"]
    log = tmp_path / "export.log"
    exports = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return cp, calls, updates, exports, jar_path


def test_an_unbound_ticket_runs_yt_dlp_without_cookies(tmp_path):
    cp, calls, _ = harvest(tmp_path)
    assert cp.returncode == 0 and len(calls) == 2
    assert all("--cookies" not in c for c in calls)


def test_a_jar_already_in_the_profile_rides_both_calls_and_is_not_re_exported(tmp_path):
    cp, calls, updates, exports, jar = bound(tmp_path, jar=True)
    assert cp.returncode == 0, cp.stderr
    assert len(calls) == 2 and all(c[c.index("--cookies") + 1] == str(jar) for c in calls)
    assert exports == [] and "status=ok" in updates[0]


def test_a_profile_with_no_jar_exports_one_through_browser_python_then_spends_it(tmp_path):
    cp, calls, updates, exports, jar = bound(tmp_path)
    assert cp.returncode == 0, cp.stderr
    assert len(exports) == 1 and exports[0][0].endswith("scripts/export_cookies.py") and exports[0][1:] == [str(jar.parent), str(jar)]
    assert jar.is_file()
    assert len(calls) == 2 and all(c[c.index("--cookies") + 1] == str(jar) for c in calls)
    assert "status=ok" in updates[0]


def test_an_export_that_fails_is_a_credential_store_error_and_no_yt_dlp_call(tmp_path):
    cp, calls, updates, exports, jar = bound(tmp_path, export_fails=True)
    assert cp.returncode == 0, cp.stderr
    assert len(exports) == 1 and calls == [] and not jar.exists()
    assert len(updates) == 1 and "status=failed" in updates[0]
    reason = next(a for a in updates[0] if a.startswith("reason="))
    assert reason.startswith("reason=credential_store_error: ") and "no cookies for youtube.com" in reason
    assert f"missing=www.youtube.com,{ITEM},error" in updates[0]
    assert not any("auth" in a for a in updates[0] if a.startswith("missing="))


def test_a_bound_dir_with_no_jar_and_no_browser_python_is_a_credential_store_error(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    cp, calls, updates = harvest(tmp_path, credential="youtube", credential_dir=str(profile))
    assert cp.returncode == 0 and calls == []
    assert "status=failed" in updates[0] and any(a.startswith("reason=credential_store_error") for a in updates[0])


def test_an_auth_wall_with_a_jar_present_keeps_the_jar_and_reports_auth(tmp_path):
    # The jar is the live session after yt-dlp's first write-back; only a fresh login replaces it.
    cp, calls, updates, exports, jar = bound(tmp_path, jar=True, db="older", fail="ERROR: Sign in to confirm your age")
    assert cp.returncode == 0, cp.stderr
    assert jar.exists() and exports == []
    assert "status=failed" in updates[0] and f"missing=www.youtube.com,{ITEM},auth" in updates[0]


def test_a_login_newer_than_the_jar_re_exports_it_once(tmp_path):
    cp, calls, updates, exports, jar = bound(tmp_path, jar="# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tOLD\told\n", db="newer")
    assert cp.returncode == 0, cp.stderr
    assert len(exports) == 1 and exports[0][1:] == [str(jar.parent), str(jar)]
    assert "OLD" not in jar.read_text()
    assert len(calls) == 2 and all(c[c.index("--cookies") + 1] == str(jar) for c in calls) and "status=ok" in updates[0]


def test_a_jar_newer_than_the_login_is_spent_as_is(tmp_path):
    cp, calls, updates, exports, jar = bound(tmp_path, jar=True, db="older")
    assert cp.returncode == 0 and exports == [] and len(calls) == 2


def test_the_export_s_own_touch_of_the_profile_does_not_re_export_next_run(tmp_path):
    # Opening the profile headless makes Chromium write its cookie DB on close; that write is not a login.
    _, _, _, exports, jar = bound(tmp_path, touches_db=True)
    assert len(exports) == 1
    _, calls, updates, exports, _ = bound(tmp_path, jar=False, touches_db=True)
    assert len(exports) == 1, "the second run re-exported: the jar must be stamped newer than the DB after an export"
    assert len(calls) == 4 and "status=ok" in updates[-1]


def test_a_plain_error_with_a_jar_present_keeps_the_jar(tmp_path):
    _, _, updates, _, jar = bound(tmp_path, jar=True, fail="ERROR: read operation timed out")
    assert jar.exists() and f"missing=www.youtube.com,{ITEM},timeout" in updates[0]


def test_nothing_from_the_profile_lands_in_the_capture_dir(tmp_path):
    cp, _, _, _, _ = bound(tmp_path, jar=True)
    assert cp.returncode == 0
    names = {p.name for p in (tmp_path / CAP).rglob("*")}
    assert "cookies.txt" not in names


def test_a_bot_check_with_a_jar_present_keeps_the_jar_and_is_retryable(tmp_path):
    # YouTube's IP-reputation wall carries the words "sign in", but a logged-in jar hits it too;
    # after the first run the jar, not the profile, holds the live (rotated) session.
    _, _, updates, _, jar = bound(tmp_path, jar=True, fail="ERROR: Sign in to confirm you’re not a bot. Use --cookies-from-browser or --cookies")
    assert jar.exists()
    assert "status=failed" in updates[0] and f"missing=www.youtube.com,{ITEM},error" in updates[0]


def test_a_bot_check_with_no_jar_is_still_auth(tmp_path):
    _, _, updates = harvest(tmp_path, fail="ERROR: Sign in to confirm you’re not a bot")
    assert f"missing=www.youtube.com,{ITEM},auth" in updates[0]


def test_a_jar_without_the_netscape_header_is_dropped_and_re_exported(tmp_path):
    cp, calls, updates, exports, jar = bound(tmp_path, jar="")  # a save yt-dlp was killed in the middle of
    assert cp.returncode == 0, cp.stderr
    assert len(exports) == 1 and jar.read_text().startswith("# Netscape HTTP Cookie File")
    assert len(calls) == 2 and "status=ok" in updates[0]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any directory")
def test_a_credential_dir_that_cannot_be_read_is_a_credential_store_error_not_a_traceback(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    profile.chmod(0)
    try:
        cp, calls, updates = harvest(tmp_path, credential="youtube", credential_dir=str(profile), browser_python=sys.executable)
    finally:
        profile.chmod(0o700)
    assert cp.returncode == 0 and "Traceback" not in cp.stderr and calls == []
    assert len(updates) == 1 and "status=failed" in updates[0] and any(a.startswith("reason=credential_store_error") for a in updates[0])
