"""The unit scripts that ask the front door a question read its ANSWER, not
just its exit code.

`llm-wiki-ops tickets open` prints prose for a person unless asked for
`--json`. A caller that trusts the exit code and takes stdout for a path
launches a browser on a directory named after a line of prose — silently
logged out. Each stub below answers in the shape the real CLI's verb answers,
prose included, so a caller that forgets `--json` fails here instead of on a
wiki.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import stat
import sys
import types
from pathlib import Path

import pytest

from harness import rooted, run

SKILLS = Path(__file__).resolve().parents[1] / "skills"

PROFILE = "/home/u/.local/share/llm-wiki/credentials/community.example"
# The CLI's own no-wiki `error` (1.97.0 prints it on stdout under `--json`,
# beside a `_cmd_` block, and exits 2). The scripts read the no-wiki arm off a
# non-zero exit, so what this stub has to get right is refusing.
NO_WIKI = {"error": "no wiki here — run `llm-wiki-cli wiki <key> ...` to reach one, or `llm-wiki-cli init <dir>` to make one"}


def _load(unit: str, script: str, *stubbed: str):
    """Import a unit script in-process, satisfying the PEP 723 dependencies
    the test venv does not carry. Removes exactly the stubs it inserted."""
    inserted = [n for n in stubbed if n not in sys.modules]
    for name in inserted:
        sys.modules[name] = types.ModuleType(name)
    try:
        spec = importlib.util.spec_from_file_location(f"_front_door_{unit}_{script}", SKILLS / unit / "scripts" / script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for name in inserted:
            sys.modules.pop(name, None)


@pytest.fixture
def front_door(tmp_path, monkeypatch):
    """`answer(rc, json_answer, prose)` puts a recording `llm-wiki-ops` first
    on PATH. It answers `json_answer` when asked `--json` and `prose`
    otherwise — the real CLI's two voices; `honors_json=False` is a CLI that
    only has the one — and records what it was handed at `answer.seen`. The
    ambient env carries what a hosted script really inherits."""
    bin_dir, seen = tmp_path / "stub-bin", tmp_path / "seen.json"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    # What a hosted run exports: the front door it was itself reached by. A
    # script that honors it must reach THIS stub, not whatever the suite runs.
    monkeypatch.setenv("LLM_WIKI_OPS", str(bin_dir / "llm-wiki-ops"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "some-other-wiki"))

    def answer(rc: int, json_answer: dict, prose: str = "prose for a person\n", honors_json: bool = True):
        stub = bin_dir / "llm-wiki-ops"
        stub.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            f"json.dump({{'argv': sys.argv[1:], 'cwd': os.getcwd(), 'stdin': sys.stdin.read() if not sys.stdin.isatty() else '',\n"
            f"           'inherited': sorted(k for k in ('CLAUDE_PROJECT_DIR',) if k in os.environ)}},\n"
            f"          open({str(seen)!r}, 'w'))\n"
            f"sys.stdout.write({json.dumps(json_answer)!r} if {honors_json!r} and '--json' in sys.argv else {prose!r})\n"
            f"sys.exit({rc})\n"
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        return lambda: json.loads(seen.read_text())

    answer.seen = seen
    return answer


# --- channel-circle: both scripts carry the same `profile_dir` -----------------

TICKET_ID = "0123456789ab"


def circle_ticket(**over) -> dict:
    """`tickets open`'s answer: the ticket, with `credential_dir` where the host granted a profile."""
    return {"ticket": {"ticket": TICKET_ID, "slug": "course", "credential": {}, "credential_mode": "none", **over}}


@pytest.fixture(params=["capture_lesson.py", "outage_probe.py"])
def circle(request):
    return _load("channel-circle", request.param)


def test_a_granted_profile_is_the_tickets_credential_dir(circle, front_door, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    seen = front_door(0, circle_ticket(credential_mode="dir", credential_dir=str(profile)), "ticket: …\n")
    path, refused = circle.profile_dir(tmp_path, TICKET_ID, "community.example")
    assert (path, refused) == (profile, None)
    got = seen()
    assert got["argv"] == ["--json", "tickets", "open", TICKET_ID], got
    assert Path(got["cwd"]) == tmp_path.resolve(), got
    # CLAUDE_PROJECT_DIR is the harness's project dir, never a wiki root; the
    # CLI does not read it, and the unit drops it so the nested call carries
    # nothing but the cwd
    assert got["inherited"] == [], got


def test_a_ticket_granting_no_profile_is_absent_and_names_the_bind(circle, front_door, tmp_path):
    front_door(0, circle_ticket())
    path, refused = circle.profile_dir(tmp_path, TICKET_ID, "community.example")
    assert path is None and refused[0] == "absent", (path, refused)
    for line in ("llm-wiki-ops credentials set community.example kind=dir login=browser host=community.example",
                 "llm-wiki-ops credentials login community.example",
                 "llm-wiki-ops credentials bind job course dir=community.example"):
        assert line in refused[1], refused


def test_a_granted_directory_that_is_gone_is_unreachable(circle, front_door, tmp_path):
    """No login fixes a grant this run cannot read: never `absent`."""
    front_door(0, circle_ticket(credential_mode="dir", credential_dir=str(tmp_path / "gone")))
    path, refused = circle.profile_dir(tmp_path, TICKET_ID, "community.example")
    assert path is None and refused[0] == "unreachable", (path, refused)


def test_a_cli_that_could_not_answer_is_unreachable_not_absent(circle, front_door, tmp_path):
    """Exit 1 is every "could not answer". Reading it as "no auth profile"
    sends an operator to log in to fix a wiki that is not there."""
    front_door(1, NO_WIKI)
    path, refused = circle.profile_dir(tmp_path, TICKET_ID, "community.example")
    assert path is None and refused[0] == "unreachable" and "no wiki here" in refused[1], refused


def test_prose_on_stdout_is_never_taken_for_a_path(circle, front_door, tmp_path):
    """A CLI that answers prose even to `--json` — an older one — is an
    unreadable ticket, never `Path("credential_dir: …")`."""
    front_door(0, {}, f"credential_dir: {PROFILE}\n", honors_json=False)
    path, refused = circle.profile_dir(tmp_path, TICKET_ID, "community.example")
    assert path is None and refused[0] == "unreachable", (path, refused)


def test_the_real_cli_answers_what_circle_reads(circle, wiki, env, ops, monkeypatch):
    """No stub: `tickets open` of a ticket that is not there is a refusal the
    unit reads as unreachable, never as a missing login."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LLM_WIKI_ROOT", raising=False)
    path, refused = circle.profile_dir(wiki, "ffffffffffff", "circle-probe.example")
    assert path is None and refused[0] == "unreachable", (path, refused)


def test_no_circle_hint_names_a_login_script_the_unit_does_not_ship():
    """The re-login step is `credentials login <domain>`; a hint naming a
    script nobody ships sends an operator nowhere."""
    for script in ("capture_lesson.py", "outage_probe.py"):
        text = (SKILLS / "channel-circle" / "scripts" / script).read_text(encoding="utf-8")
        assert "scripts/login.py" not in text, script
    capture = (SKILLS / "channel-circle" / "scripts" / "capture_lesson.py").read_text(encoding="utf-8")
    assert capture.count("credentials login") >= 3, "auth_expired, cloudflare_challenge and the absent hint"


# --- every unit reaches the front door a hosted run NAMES ----------------------


def _named_only(tmp_path, monkeypatch):
    """A recording `llm-wiki-ops` reachable ONLY through `LLM_WIKI_OPS`: the
    bare name is on no PATH the script can see. Returns a reader of the calls."""
    bin_dir, seen = tmp_path / "named-bin", tmp_path / "named.jsonl"
    bin_dir.mkdir()
    stub = bin_dir / "llm-wiki-ops"
    stub.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        f"open({str(seen)!r}, 'a').write(json.dumps({{'argv': sys.argv[1:], 'cwd': os.getcwd()}}) + '\\n')\n"
        "print('{}')\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tmp_path / "no-bare-name-here"))
    monkeypatch.setenv("LLM_WIKI_OPS", str(stub))

    def calls():
        return [json.loads(line) for line in seen.read_text().splitlines()] if seen.exists() else []

    return calls


def _load_spawner(unit: str, script: str):
    """`_load`, with the unit's own `scripts/` on `sys.path`: a unit ships
    siblings that import each other."""
    here = str(SKILLS / unit / "scripts")
    sys.path.insert(0, here)
    try:
        return _load(unit, script, "requests")
    finally:
        sys.path.remove(here)


def _reach_ops(mod, tmp_path, monkeypatch):
    mod._ops(tmp_path, "credentials", "info", "example.test")


def _reach_section_plan(mod, tmp_path, monkeypatch):
    leaf = {"url": "https://example.invalid/lesson", "dir": "d"}
    monkeypatch.setattr(mod, "_plan_and_leaf", lambda args: (tmp_path, {}, leaf))
    monkeypatch.setattr(mod, "leaf_path", lambda capture_dir, one: tmp_path)
    mod.cmd_detect(types.SimpleNamespace())


def _reach_gmail(mod, tmp_path, monkeypatch):
    mod._ops(["--json", "page", "create"], "body")


def _reach_leaves(mod, tmp_path, monkeypatch):
    mod._spawn(tmp_path, "run", "scripts/assets.py")


def _reach_notion(mod, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with contextlib.suppress(Exception):
        mod.write_page("research/channels/tasks", "2026-01-01", {}, "body")


def _reach_frameio(mod, tmp_path, monkeypatch):
    with contextlib.suppress(SystemExit):
        mod.write_page(tmp_path, "sources/scrapes/x", "Title", [], "body")


def _reach_youtube(mod, tmp_path, monkeypatch):
    with contextlib.suppress(SystemExit):
        mod.write_page(tmp_path, "sources/youtube/x", "Title", {}, "body")


SPAWNERS = [
    ("channel-circle", "capture_lesson.py", _reach_ops),
    ("channel-circle", "outage_probe.py", _reach_ops),
    ("channel-circle", "section_plan.py", _reach_section_plan),
    ("channel-frameio", "frameio_doc_note.py", _reach_frameio),
    ("channel-gmail", "write_items.py", _reach_gmail),
    ("channel-hubspot-video", "leaves.py", _reach_leaves),
    ("channel-notion-tasks", "write_items.py", _reach_notion),
    ("channel-spotify", "spotify.py", _reach_ops),
    ("channel-youtube", "youtube_note.py", _reach_youtube),
]


@pytest.mark.parametrize(("unit", "script", "reach"), SPAWNERS, ids=[f"{u}-{s}" for u, s, _ in SPAWNERS])
def test_every_unit_reaches_the_front_door_a_hosted_run_names(unit, script, reach, tmp_path, monkeypatch):
    """`llm-wiki-ops run` exports `LLM_WIKI_OPS`, naming the CLI it was itself
    reached by. A jail is not promised the `~/.local/bin` entry the bare name
    is, so a unit that reads PATH alone is the one that dies in a slice."""
    calls = _named_only(tmp_path, monkeypatch)
    mod = _load_spawner(unit, script)
    reach(mod, tmp_path, monkeypatch)
    assert calls(), f"{unit}/{script} never reached the front door `LLM_WIKI_OPS` names"
