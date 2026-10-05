"""channel-hubspot-video, the harness tier: the unit installed and enabled
through the REAL CLI, each stage started by the runner in the jail it
composes, with the harness profile's fake agent typing what the unit's
SKILL.md says.
Its helpers and constants are the unit's own tests' —
`skills/channel-hubspot-video/tests/test_hubspot.py`, which ships with the
unit — so a case here reads exactly as it did beside them.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess

import pytest

from harness import RESOLVABLE_TEST_HOST, claimed, declared_job, pending, rooted, run, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-hubspot-video", "test_hubspot"))


LEAVES = "ops/skills/channel-hubspot-video/scripts/leaves.py"


def _needs_retry_verb(ops, env, wiki):
    if run(ops, rooted(env, wiki), "pipeline", "tickets", "retry", "--help").returncode != 0:
        pytest.skip("`pipeline tickets retry` is plugins PR 2 (#2486)")


def test_a_cadence_change_and_a_retry_refusal_are_real(ops, env, wiki):
    """`every` is not an identity key, so a `once` job can be given a period
    while a section fills, and back — and `tickets retry` refuses a ticket
    that never ran, naming it (G3 side note: the refusal text is re-read
    from the new verb)."""
    job = declared_job(ops, env, wiki, UNIT, "https://www.example-hubspot.invalid/continue", slug="port-channel-hubspot-continue")
    assert job.record["every"] == "once"
    for cadence in ("1h", "once"):
        done = run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", "edit", job.slug, f"every={cadence}")
        assert done.returncode == 0, done.stdout + done.stderr
        assert run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", "show", job.slug).data["job"]["every"] == cadence
    _needs_retry_verb(ops, env, wiki)
    refused = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "retry", "0123456789ab")
    assert refused.returncode != 0 and "no ticket" in refused.stdout + refused.stderr  # never minted, never active


def test_a_title_with_an_apostrophe_survives_the_documented_shell_line(ops, env, wiki):
    """The process step is a shell line a worker TYPES, single-quoting the title
    off `capture.json`. `safe_title` maps BOTH quote forms to U+2019, so no
    title it can produce breaks out of those quotes and loses its page."""
    dest = "sources/courses/port-hubspot-apostrophe"
    for venue in ("Don't Panic", 'He said "no" twice'):
        title = leaves.safe_title(venue)
        assert "'" not in title, title
        line = (
            "printf '%s' 'body' | "
            + shlex.join([*ops, "--json", "page", "create"])
            + f" 'title={title}' 'dest={dest}' 'resource=https://example.invalid/x'"
            + f" 'extracted=true' 'type=video' --stdin"
        )
        done = subprocess.run(["/bin/sh", "-c", line], env=rooted(env, wiki), capture_output=True, text=True, check=False)
        assert done.returncode == 0, line + "\n" + done.stdout + done.stderr
        assert (wiki / json.loads(done.stdout)["path"]).is_file()


def test_a_harvested_lesson_becomes_the_staged_page(ops, env, wiki):
    """The whole point of the rework: a harvest ticket whose session, in its
    jail, runs `leaves.py plan`/`record`/`report` posting `tickets update`
    through the REAL CLI, and a process ticket whose session runs
    `to_markdown.py` and `page create` — no `ticket.json`, no `report.json`
    anywhere on disk."""
    # The runner refuses a ticket whose target host does not resolve to a public
    # address; `SECTION`'s own (`www.example-hubspot.invalid`) never does. Nothing
    # here fetches the target — `plan` reads the fixture `urls.json`/`sites.json` —
    # so `RESOLVABLE_TEST_HOST` stands in for it everywhere the fixtures name it.
    old_host = "www.example-hubspot.invalid"
    host = RESOLVABLE_TEST_HOST
    section = SECTION.replace(old_host, host)
    lesson = LESSON.replace(old_host, host)
    job = declared_job(ops, env, wiki, UNIT, section, slug="harness-hubspot")
    shutil.rmtree(wiki / "_raw" / job.slug, ignore_errors=True)
    shutil.rmtree(wiki / job.dest, ignore_errors=True)
    ticket_id, cap = claimed(ops, env, wiki, job)
    sites = json.loads((FIX / "sites.json").read_text(encoding="utf-8"))
    sites["sites"] = {(host if k == old_host else k): v for k, v in sites["sites"].items()}
    session = staged(ops, env, wiki, ticket_id, f"""\
cp "$FIX/urls.json" "$FIX/sites.json" "$CAP/"
step plan "$OPS" run {LEAVES} plan "$CAP" --urls "$CAP/urls.json" --sites "$CAP/sites.json" --ticket "$TICKET"
leaf=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["leaves"][0]["dir"])' "$CAP/plan.json")
mkdir -p "$leaf" && cp "$FIX/page.html" "$FIX/meta.json" "$leaf/"
step record "$OPS" run {LEAVES} record "$CAP" --leaf 0
step report "$OPS" run {LEAVES} report "$CAP" --ticket "$TICKET"
""", files={"urls.json": json.dumps([{"url": lesson, "lastmod": "2026-07-15"}]).encode(),
            "sites.json": json.dumps(sites).encode(),
            "page.html": (FIX / "page.html").read_bytes(), "meta.json": (FIX / "meta.json").read_bytes()})
    for name in ("plan", "record", "report"):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    (leaf_row,) = json.loads((cap / "plan.json").read_text(encoding="utf-8"))["leaves"]
    leaf_dir = wiki / leaf_row["dir"]
    assert json.loads((leaf_dir / "capture.json").read_text(encoding="utf-8"))["title"] == "Pricing the offer"
    assert json.loads(session.step("report").stdout)["status"] == "ok"

    # Landing the harvest mints a NEW process ticket, keyed to the leaf's own
    # captured directory; the process arm's `report` posts on THAT ticket.
    process_id = pending(ops, env, wiki, job.slug)[leaf_row["dir"]]

    # The process arm: no network, no credential — `to_markdown.py` off the
    # site's own selectors, then the REAL `page create` through the front door.
    expected = f"{job.dest}/Pricing the offer.md"
    create = (f"""cat "$CAP/page.md" | "$OPS" --json page create 'title=Pricing the offer' 'dest={job.dest}' """
              f"""'resource={lesson}' 'extracted=true' 'type=video' 'venue=hubspot-cms' --stdin""")
    session = staged(ops, env, wiki, process_id, f"""\
step md "$OPS" run ops/skills/channel-hubspot-video/scripts/to_markdown.py "$CAP/page.html" --selector main#main-content \
    --drop-selector "main#main-content h1" --title-selector "main#main-content h2" --base-url {shlex.quote(lesson)}
step create sh -c {shlex.quote(create)}
printf '%s' {shlex.quote(json.dumps([expected]))} > "$CAP/written.json"
step report "$OPS" run {LEAVES} report "$CAP" --ticket "$TICKET" --written-from written.json
""")
    for name in ("md", "create", "report"):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    assert session.step("create").data["path"] == expected
    # The frontmatter block `page create` writes precedes the body, so the body
    # itself is what starts with the true title's H1, not the whole file.
    _front, body = (wiki / expected).read_text(encoding="utf-8").split("---\n", 2)[1:]
    assert body.lstrip().startswith("# Pricing the offer")
    assert json.loads(session.step("report").stdout)["status"] == "ok"
    assert session.update["status"] == "ok", session.update
