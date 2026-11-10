"""The harvest stage's script, run as the runner runs it: `capture_video.py
ticket=<id>` at the wiki root, with a stand-in `yt-dlp` on PATH and a stand-in
front door, so no venue is reached."""

from __future__ import annotations

import json
import os
import shlex
import stat
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
if "--cookies" in argv and os.environ.get("FAKE_ROTATE"):
    jar = pathlib.Path(argv[argv.index("--cookies") + 1])
    jar.write_text(jar.read_text().replace("\\tSID\\tsid-value", "\\tSID\\t" + os.environ["FAKE_ROTATE"]))
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


# `credentials browser-state get|put` over `FAKE_STATE`, the slot's state file: `put` merges by (name, domain, path)
# and logs what it was given; `FAKE_GET_FAIL` makes `get` refuse.
STATE_VERBS = (
    "if verb[:3] == ['credentials', 'browser-state', 'get']:\n"
    "    if os.environ.get('FAKE_GET_FAIL'):\n"
    "        print('no such credential directory', file=sys.stderr); sys.exit(1)\n"
    "    path = pathlib.Path(os.environ['FAKE_STATE'])\n"
    "    state = json.loads(path.read_text()) if path.exists() else {'cookies': [], 'origins': []}\n"
    "    print(json.dumps({'path': str(path), 'format': 'json', 'state': state})); sys.exit(0)\n"
    "if verb[:3] == ['credentials', 'browser-state', 'put']:\n"
    "    path = pathlib.Path(os.environ['FAKE_STATE'])\n"
    "    new = json.loads(sys.stdin.read())\n"
    "    pathlib.Path(os.environ['FAKE_STATE'] + '.puts').open('a').write(json.dumps(new) + '\\n')\n"
    "    state = json.loads(path.read_text()) if path.exists() else {'cookies': [], 'origins': []}\n"
    "    key = lambda c: (c['name'], c['domain'], c['path'])\n"
    "    merged = {key(c): c for c in state['cookies']}; merged.update((key(c), c) for c in new['cookies'])\n"
    "    path.write_text(json.dumps({'cookies': list(merged.values()), 'origins': state['origins']})); print('{}'); sys.exit(0)\n"
)


def front_door(tmp_path, ticket):
    stub = tmp_path / "ops_stub.py"
    stub.write_text(
        "import json, os, pathlib, sys\n"
        "argv = sys.argv[1:]\n"
        "verb = [a for a in argv if not a.startswith('--')]\n"
        f"TICKET = json.loads({json.dumps(json.dumps(ticket))})\n"
        "if verb[:2] == ['tickets', 'open']:\n"
        "    print(json.dumps({'ticket': TICKET})); sys.exit(0)\n"
        "if verb[:2] == ['tickets', 'update']:\n"
        "    pathlib.Path(os.environ['FAKE_UPDATES']).open('a').write(json.dumps(argv) + '\\n'); sys.exit(0)\n"
        + STATE_VERBS +
        "sys.exit(9)\n"
    )
    return shlex.join([sys.executable, str(stub)])


# Runs a script with `sys.executable` set to argv[1]: the cookie export runs on the script's own interpreter.
ON_PYTHON = "import runpy, sys; sys.executable = sys.argv.pop(1); sys.argv.pop(0); runpy.run_path(sys.argv[0], run_name='__main__')"


def harvest(tmp_path, *, fail="", meta="", python=None, **over):
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
    on = ["-c", ON_PYTHON, python] if python else []
    cp = subprocess.run([sys.executable, *on, str(SCRIPT), f"ticket={TICKET_ID}"], cwd=tmp_path, env=env, capture_output=True, text=True)
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


def test_a_pull_drops_the_notes_an_enrich_unit_made_of_the_old_bytes(tmp_path):
    (tmp_path / CAP / "enrich").mkdir(parents=True)
    (tmp_path / CAP / "enrich" / "watch.md").write_text("old notes")
    harvest(tmp_path, fail="ERROR: something else")  # a failed pull never reaches `--record`, so this step's own clear is what runs
    assert not (tmp_path / CAP / "enrich").exists()


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
    assert (UNIT_DIR / "scripts" / "capture_video.py").is_file() and "sandbox_ref" in manifest and "sandbox_ref" not in manifest["stages"]["harvest"]
    assert "# /// script" not in SCRIPT.read_text()  # standard library only: no browser, so no env to build


# --- a bound `dir` credential: its browser state, spent as a cookie jar and saved back ---

COOKIES = [
    {"name": "SID", "value": "sid-value", "domain": ".youtube.com", "path": "/", "expires": 1900000000.5, "secure": True, "httpOnly": True, "sameSite": "None"},
    {"name": "YSC", "value": "session-value", "domain": ".youtube.com", "path": "/", "expires": -1, "secure": True, "httpOnly": False, "sameSite": "Lax"},
    {"name": "NID", "value": "nid-value", "domain": ".google.com", "path": "/", "expires": 1900000001, "secure": False, "httpOnly": False, "sameSite": "Lax"},
    {"name": "gv", "value": "gv-value", "domain": "r1---sn.googlevideo.com", "path": "/", "expires": 1900000002, "secure": True, "httpOnly": False, "sameSite": "Lax"},
    {"name": "other", "value": "other-value", "domain": "example.com", "path": "/x", "expires": 1900000003, "secure": True, "httpOnly": False, "sameSite": "Lax"},
    {"name": "lookalike", "value": "x", "domain": "notyoutube.com", "path": "/", "expires": 1900000004, "secure": True, "httpOnly": False, "sameSite": "Lax"},
]
OLD = 1_700_000_000 * 10**9


def bound(tmp_path, *, cookies=COOKIES, state=True, jar=None, jar_newer=False, rotate="", get_fails=False, **over):
    """A ticket bound to a browser `dir`: `credential_dir` holds the state the stand-in verbs serve (`state=False`:
    none saved yet) and, given `jar`, a jar an earlier run left, older than the state unless `jar_newer`. Returns
    (cp, calls, updates, jar, state path, the states `put` was given)."""
    profile = tmp_path / "profile"
    profile.mkdir(exist_ok=True)
    state_path = profile / ".llm-wiki-browser-state.json"
    if state:
        state_path.write_text(json.dumps({"cookies": cookies, "origins": []}))
        os.utime(state_path, ns=(OLD, OLD))
    jar_path = profile / "cookies.txt"
    if jar is not None:
        jar_path.write_text(jar)
        stamp = OLD + (3600 if jar_newer else -3600) * 10**9
        os.utime(jar_path, ns=(stamp, stamp))
    os.environ.update(FAKE_STATE=str(state_path), FAKE_ROTATE=rotate, FAKE_GET_FAIL="1" if get_fails else "")
    try:
        cp, calls, updates = harvest(tmp_path, credential="youtube", credential_dir=str(profile), **over)
    finally:
        for name in ("FAKE_STATE", "FAKE_ROTATE", "FAKE_GET_FAIL"):
            del os.environ[name]
    puts_log = Path(f"{state_path}.puts")
    puts = [json.loads(line) for line in puts_log.read_text().splitlines()] if puts_log.exists() else []
    return cp, calls, updates, jar_path, state_path, puts


def jar_rows(jar):
    return [line.split("\t") for line in jar.read_text().splitlines() if line and not line.startswith("# ")]


def test_an_unbound_ticket_runs_yt_dlp_without_cookies(tmp_path):
    cp, calls, _ = harvest(tmp_path)
    assert cp.returncode == 0 and len(calls) == 2
    assert all("--cookies" not in c for c in calls)


def test_the_jar_is_the_venue_cookies_of_the_state_and_rides_both_calls(tmp_path):
    cp, calls, updates, jar, _, _ = bound(tmp_path)
    assert cp.returncode == 0, cp.stderr
    assert len(calls) == 2 and all(c[c.index("--cookies") + 1] == str(jar) for c in calls) and "status=ok" in updates[0]
    raw = jar.read_bytes()
    assert raw.startswith(b"# Netscape HTTP Cookie File\n") and b"\r" not in raw
    assert stat.S_IMODE(jar.stat().st_mode) == 0o600
    sid, ysc, nid, gv = jar_rows(jar)  # example.com and notyoutube.com are filtered
    assert sid == ["#HttpOnly_.youtube.com", "TRUE", "/", "TRUE", "1900000000", "SID", "sid-value"]
    assert ysc[4] == "0" and ysc[5] == "YSC"  # a session cookie's expiry is 0
    assert nid[3] == "FALSE" and gv[:2] == ["r1---sn.googlevideo.com", "FALSE"]  # no leading dot: host-only


def test_the_cookies_yt_dlp_rotated_are_saved_back_with_what_the_jar_cannot_carry(tmp_path):
    cp, _, _, _, state_path, puts = bound(tmp_path, rotate="sid-rotated")
    assert cp.returncode == 0, cp.stderr
    (put,) = puts
    assert {c["name"] for c in put["cookies"]} == {"SID", "YSC", "NID", "gv"} and put["origins"] == []
    saved = {c["name"]: c for c in json.loads(state_path.read_text())["cookies"]}
    assert saved["SID"]["value"] == "sid-rotated" and saved["SID"]["sameSite"] == "None" and saved["SID"]["httpOnly"] is True
    assert saved["YSC"]["expires"] == -1 and saved["other"]["value"] == "other-value"


def test_a_failed_call_still_saves_the_rotation_back(tmp_path):
    _, _, updates, _, state_path, puts = bound(tmp_path, rotate="sid-rotated", fail="ERROR: Sign in to confirm your age")
    assert f"missing=www.youtube.com,{ITEM},auth" in updates[0] and len(puts) == 1
    assert [c["value"] for c in json.loads(state_path.read_text())["cookies"] if c["name"] == "SID"] == ["sid-rotated"]


def test_a_jar_newer_than_the_state_is_a_killed_runs_rotation_and_is_saved_first(tmp_path):
    left = "# Netscape HTTP Cookie File\n#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1900000000\tSID\tsid-from-a-killed-run\n"
    cp, calls, _, jar, _, puts = bound(tmp_path, jar=left, jar_newer=True)
    assert cp.returncode == 0, cp.stderr
    assert [c["value"] for c in puts[0]["cookies"]] == ["sid-from-a-killed-run"] and puts[0]["cookies"][0]["sameSite"] == "None"
    assert [r[6] for r in jar_rows(jar) if r[5] == "SID"] == ["sid-from-a-killed-run"] and len(calls) == 2


def test_a_state_newer_than_the_jar_is_a_login_and_wins(tmp_path):
    left = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tstale\n"
    _, _, _, jar, _, puts = bound(tmp_path, jar=left)
    assert [r[6] for r in jar_rows(jar) if r[5] == "SID"] == ["sid-value"]
    assert len(puts) == 1 and "stale" not in json.dumps(puts)  # the one put is this run's own, after the calls


def test_an_old_jar_with_no_state_yet_becomes_the_state(tmp_path):
    left = "# Netscape HTTP Cookie File\n#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1900000000\tSID\tsid-before-the-state\n"
    cp, calls, _, jar, state_path, _ = bound(tmp_path, state=False, jar=left)
    assert cp.returncode == 0 and len(calls) == 2, cp.stderr
    assert [c["value"] for c in json.loads(state_path.read_text())["cookies"]] == ["sid-before-the-state"]


def test_a_jar_without_the_netscape_header_is_not_saved_back_first(tmp_path):
    _, calls, _, jar, _, puts = bound(tmp_path, jar="", jar_newer=True)  # a save yt-dlp was killed in the middle of
    assert len(calls) == 2 and len(puts) == 1 and jar.read_text().startswith("# Netscape HTTP Cookie File")


def test_a_state_with_no_venue_cookie_is_a_credential_store_error_and_no_yt_dlp_call(tmp_path):
    cp, calls, updates, jar, _, puts = bound(tmp_path, cookies=[c for c in COOKIES if c["domain"] in ("example.com", "notyoutube.com")])
    assert cp.returncode == 0, cp.stderr
    assert calls == [] and not jar.exists() and puts == []
    assert len(updates) == 1 and "status=failed" in updates[0]
    reason = next(a for a in updates[0] if a.startswith("reason="))
    assert reason.startswith("reason=credential_store_error: ") and "not logged in to youtube.com" in reason
    assert f"missing=www.youtube.com,{ITEM},error" in updates[0]


def test_a_state_verb_that_refuses_is_a_credential_store_error(tmp_path):
    _, calls, updates, _, _, _ = bound(tmp_path, get_fails=True)
    assert calls == [] and any(a.startswith("reason=credential_store_error: ") and "no such credential directory" in a for a in updates[0])


def test_a_cookie_value_never_reaches_stdout_or_stderr(tmp_path):
    cp, _, _, _, _, _ = bound(tmp_path, rotate="sid-rotated")
    assert "sid-value" not in cp.stdout + cp.stderr and "sid-rotated" not in cp.stdout + cp.stderr


def test_nothing_from_the_credential_lands_in_the_capture_dir(tmp_path):
    cp, _, _, _, _, _ = bound(tmp_path)
    assert cp.returncode == 0
    names = {p.name for p in (tmp_path / CAP).rglob("*")}
    assert "cookies.txt" not in names and not any(n.startswith(".cookies") for n in names)


def test_a_bot_check_with_a_jar_is_retryable(tmp_path):
    # YouTube's IP-reputation wall carries the words "sign in", but a logged-in jar hits it too.
    _, _, updates, _, _, _ = bound(tmp_path, fail="ERROR: Sign in to confirm you’re not a bot. Use --cookies-from-browser or --cookies")
    assert "status=failed" in updates[0] and f"missing=www.youtube.com,{ITEM},error" in updates[0]


def test_a_bot_check_with_no_jar_is_still_auth(tmp_path):
    _, _, updates = harvest(tmp_path, fail="ERROR: Sign in to confirm you’re not a bot")
    assert f"missing=www.youtube.com,{ITEM},auth" in updates[0]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_a_jar_that_cannot_be_read_is_a_credential_store_error_not_a_traceback(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    jar = profile / "cookies.txt"
    jar.write_text("# Netscape HTTP Cookie File\n")
    jar.chmod(0)
    try:
        cp, calls, updates, _, _, _ = bound(tmp_path)
    finally:
        jar.chmod(0o600)
    assert cp.returncode == 0 and "Traceback" not in cp.stderr and calls == []
    assert len(updates) == 1 and "status=failed" in updates[0] and any(a.startswith("reason=credential_store_error") for a in updates[0])


def test_a_pull_unlinks_a_symlinked_enrich_and_leaves_its_target(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "keep.txt").write_text("keep")
    (tmp_path / CAP).mkdir(parents=True)
    (tmp_path / CAP / "enrich").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    harvest(tmp_path, fail="ERROR: something else")  # a failed pull never reaches `--record`, so this step's own clear is what runs
    assert not (tmp_path / CAP / "enrich").exists() and (tmp_path / "elsewhere" / "keep.txt").is_file()
