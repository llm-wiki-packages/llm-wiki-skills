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
    sys.stdout.write(pathlib.Path(os.environ["FAKE_FIXTURES"], "metadata.json").read_text())
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


def harvest(tmp_path, *, fail="", **over):
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
           "FAKE_FIXTURES": str(FIXTURES), "FAKE_YT_FAIL": fail}
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


def test_an_item_that_is_no_url_is_failed_and_never_run(tmp_path):
    _, calls, updates = harvest(tmp_path, item="--exec=rm -rf /")
    assert calls == [] and "status=failed" in updates[0]


def test_the_manifest_declares_the_script_beside_the_sandbox():
    manifest = json.loads((UNIT_DIR / "manifest.json").read_text())
    assert manifest["stages"]["harvest"]["script"] == "scripts/capture_video.py"
    assert (UNIT_DIR / "scripts" / "capture_video.py").is_file() and "sandbox_ref" in manifest["stages"]["harvest"]
    assert "# /// script" not in SCRIPT.read_text()  # a block in a script stage is refused at install
