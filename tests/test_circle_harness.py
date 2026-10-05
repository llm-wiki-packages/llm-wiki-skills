"""channel-circle, the harness tier: the unit installed and enabled through
the REAL CLI, each stage started by the runner in the jail it composes, with
the harness profile's fake agent typing what the unit's SKILL.md says. Its
helpers and constants are the unit's own tests' —
`skills/channel-circle/tests/test_circle.py`, which ships with the unit —
so a case here reads exactly as it did beside them.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess

from pathlib import Path

from harness import claimed, declared_job, pending, rooted, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-circle", "test_circle"))


SCRIPT = "ops/skills/channel-circle/scripts"

# `capture_lesson.py --leaf <n>`'s stand-in: the venue's bytes for each planned
# lesson, in the directory the plan gave it, and lesson 1's caption track.
CAPTURED = """python3 - "$CAP" "$FIX" <<'PY'
import json, os, shutil, sys
cap, fix = sys.argv[1:]
for leaf in json.load(open(os.path.join(cap, "plan.json")))["leaves"]:
    os.makedirs(leaf["dir"], exist_ok=True)
    for name in ("page.html", "meta.json"):
        shutil.copy(os.path.join(fix, f"lesson-{leaf['order']}", name), os.path.join(leaf["dir"], name))
    if leaf["order"] == 1:
        os.makedirs(os.path.join(leaf["dir"], "captions"), exist_ok=True)
        shutil.copy(os.path.join(fix, "en.vtt"), os.path.join(leaf["dir"], "captions", "en.vtt"))
PY
"""


def fixtures() -> dict:
    files = {f"{d}/{n}": (FIX / d / n).read_bytes() for d in ("root", "lesson-1", "lesson-2") for n in ("page.html", "meta.json")}
    return {**files, "en.vtt": VTT.encode()}


def page_lines(cap: Path, dest: str, verb: str = "create") -> str:
    """SKILL.md's process step 3, as the shell line a worker TYPES: the title
    and the url off `capture.json`, each single-quoted as the documented line
    has them, the body on stdin — so every content case is a quoting case."""
    record = json.loads((cap / "capture.json").read_text(encoding="utf-8"))
    where = f"'title={record['title']}' 'dest={dest}'" if verb == "create" else f"'{dest}/{record['title']}.md'"
    return f"""cat "$CAP/page.md" | "$OPS" --json page {verb} {where} 'resource={record['item']}' type=lesson extracted=true --stdin"""


def processed(ops, env, wiki, ticket: str, cap: Path, dest: str, again: bool = False):
    """The process stage, in its jail: convert, write the page (`create`, or
    `edit` on the host's `already exists`), report what it wrote."""
    title = json.loads((cap / "capture.json").read_text(encoding="utf-8"))["title"]
    second = f"step again sh -c {shlex.quote(page_lines(cap, dest))}\nstep edit sh -c {shlex.quote(page_lines(cap, dest, 'edit'))}\n" if again else ""
    return staged(ops, env, wiki, ticket, f"""\
step md "$OPS" run {SCRIPT}/to_markdown.py "$CAP/page.html" --out "$CAP/page.md"
step create sh -c {shlex.quote(page_lines(cap, dest))}
{second}printf '%s' {shlex.quote(json.dumps([f"{dest}/{title}.md"]))} > "$CAP/written.json"
step report "$OPS" run {SCRIPT}/section_plan.py report "$CAP" --ticket "$TICKET" --stage process --written-from written.json
""")


def test_one_ticket_walks_the_section_and_every_lesson_becomes_a_page(ops, env, wiki):
    """The whole point of the rework: a harvest ticket whose session, in its
    jail, runs `section_plan.py plan`/`record`/`report` posting `tickets
    update` through the REAL CLI, and a process ticket per lesson whose
    session runs `to_markdown.py` and `page create` — no `ticket.json`, no
    `report.json` anywhere on disk."""
    # `TARGET`'s host is `example.com` (RFC 2606): the runner refuses a ticket
    # whose target does not resolve to a public address, and `test_circle.py`'s
    # fixtures are keyed to that host, so `harvest.scope=section` keeps the leaves.
    job = declared_job(ops, env, wiki, UNIT, TARGET, slug="harness-circle")
    ticket_id, cap = claimed(ops, env, wiki, job)
    records = "".join(f'step record-{n}-{i} "$OPS" run {SCRIPT}/section_plan.py record "$CAP" --leaf {n}\n'
                      for n in (1, 2) for i in (1, 2))  # a respawned worker records again: nothing may stack
    session = staged(ops, env, wiki, ticket_id, f"""\
cp "$FIX/root/page.html" "$FIX/root/meta.json" "$CAP/"
step plan "$OPS" run {SCRIPT}/section_plan.py plan "$CAP" --ticket "$TICKET"
{CAPTURED}{records}step report "$OPS" run {SCRIPT}/section_plan.py report "$CAP" --ticket "$TICKET"
""", files=fixtures())

    planned = session.step("plan")
    assert planned.returncode == 0, planned.stdout + planned.stderr
    plan = json.loads((cap / "plan.json").read_text(encoding="utf-8"))
    assert [leaf["url"] for leaf in plan["leaves"]] == [L1, L2]
    for leaf in plan["leaves"]:
        assert leaf["dir"].startswith(f"_raw/{job.slug}/") and len(leaf["dir"].split("/")) == 3
        for i in (1, 2):
            done = session.step(f"record-{leaf['order']}-{i}")
            assert done.returncode == 0, done.stdout + done.stderr
        directory = wiki / leaf["dir"]
        record = json.loads((directory / "capture.json").read_text(encoding="utf-8"))
        assert (record["slug"], record["item"], record["body"], record["content_type"]) == (
            job.slug, leaf["url"], "page.html", "text/html")
        assert "frontmatter" not in record and not set(record) & set(HOST_KEYS)
        assert not (directory / "page.md").exists(), "harvest renders no page"
    assert json.loads((wiki / plan["leaves"][1]["dir"] / "facts.json").read_text(encoding="utf-8")) == {
        "course": "Course One | Example Community", "space": "course-one", "section": "Section One",
        "duration": "12:30", "source_title": "Reading the Room"}
    reported = session.step("report")
    assert reported.returncode == 0, reported.stdout + reported.stderr
    assert json.loads(reported.stdout)["status"] == "ok"

    assert session.update["status"] == "ok", session.update

    # Landing the harvest mints one process ticket per captured directory.
    by_dir = pending(ops, env, wiki, job.slug)
    assert sorted(by_dir) == sorted(leaf["dir"] for leaf in plan["leaves"])

    texts = []
    for leaf in plan["leaves"]:
        directory = wiki / leaf["dir"]
        facts = json.loads((directory / "facts.json").read_text(encoding="utf-8"))
        assert facts["course"] == "Course One | Example Community" and facts["section"] == "Section One"
        first = leaf["order"] == 1
        session = processed(ops, env, wiki, by_dir[leaf["dir"]], directory, job.dest, again=first)
        for name in ("md", "create", "report", *(("again", "edit") if first else ())):
            done = session.step(name)
            assert done.returncode == (2 if name == "again" else 0), (name, done.stdout + done.stderr)
        if first:  # a second process run for one lesson EDITS the page the first one wrote
            assert "already exists" in session.step("again").stdout
        page = wiki / session.step("create").data["path"]
        assert page.is_relative_to(wiki / job.dest)
        texts.append(page.read_text(encoding="utf-8"))
        assert session.update["status"] == "ok", session.update
    first, second = texts
    assert "title: Getting the Frame Right" in first and f"resource: {L1}" in first and "status: draft" in first
    assert "extracted: 'true'" in first
    assert "marmalade-sandwich rule" in first and "> A frame is a promise about what matters." in first
    assert "Topic 1 of 2" in first and "heliotrope question" in second
    assert "https://assets-v2.circle.so/abc123def" in second  # the extensionless Resources link survives
    for text in texts:
        assert len(re.findall(r"^---$", text, flags=re.M)) == 2, "one frontmatter block, the host's own"
        assert "Powered by a community platform" not in text and "logo123" not in text  # chrome stripped
    assert sorted(page.name for page in (wiki / job.dest).glob("*.md")) == [
        "Getting the Frame Right.md", "Reading the Room.md"]


def test_a_title_with_an_apostrophe_survives_the_documented_shell_line(ops, env, wiki):
    """The process step is a shell line a worker TYPES, single-quoting the title
    off `capture.json`. `safe_title` maps BOTH quote forms to U+2019, so no
    title it can produce breaks out of those quotes and loses its page."""
    dest = "sources/courses/port-circle-apostrophe"
    for venue in ("Don't Panic", 'He said "no" twice'):
        title = mod.safe_title(venue)
        assert "'" not in title, title
        line = (
            "printf '%s' 'body' | "
            + shlex.join([*ops, "--json", "page", "create"])
            + f" 'title={title}' 'dest={dest}' 'resource=https://example.invalid/x'"
            + f" 'extracted=true' 'type=lesson' --stdin"
        )
        done = subprocess.run(["/bin/sh", "-c", line], env=rooted(env, wiki), capture_output=True, text=True, check=False)
        assert done.returncode == 0, line + "\n" + done.stdout + done.stderr
        assert (wiki / json.loads(done.stdout)["path"]).is_file()
