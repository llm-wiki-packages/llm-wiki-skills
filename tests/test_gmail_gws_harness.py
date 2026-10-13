"""channel-gmail-gws, the harness tier: the unit installed and enabled through
the REAL CLI, its harvest script started by the runner in the jail it
composes — with the job's `dir` slot granting a stand-in gws login — and its
process stage typed by the harness profile's fake agent. Its helpers and
constants are the unit's own tests' (`skills/channel-gmail-gws/tests/test_gmail_gws.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import SCRATCH, claimed, declared_job, pending, rooted, run, staged, unit_tests

globals().update(unit_tests("channel-gmail-gws", "test_gmail_gws"))

WRITE = "ops/skills/channel-gmail-gws/scripts/write_items.py"


def _bullets(text: str) -> list:
    return [line for line in text.split("\n---\n", 1)[1].splitlines() if line.startswith("- ")]


@pytest.fixture
def login(request) -> Path:
    """A login directory the stand-in gws answers out of, outside the wiki."""
    own = request.node.name.replace("_", "-").lower()[:40]
    directory = SCRATCH / "gws-logins" / own
    directory.mkdir(parents=True)
    messages = [raw_message(n) for n in (1, 2, 3)]
    (directory / "profile.json").write_text(json.dumps({"emailAddress": MAILBOX}), encoding="utf-8")
    newest_first = sorted(messages, key=lambda m: -int(m["internalDate"]))
    (directory / "list.json").write_text(json.dumps({"messages": [{"id": m["id"]} for m in newest_first]}), encoding="utf-8")
    for m in messages:
        (directory / f"msg-{m['id']}.json").write_text(json.dumps(m), encoding="utf-8")
    return directory


@pytest.fixture
def job(ops, env, wiki, login, request):
    own = request.node.name.replace("_", "-").lower()
    slug = f"harness-gws-{own}"[:60]
    j = declared_job(ops, env, wiki, UNIT, f"{TARGET}-{own}"[:60], f"options.mailbox={MAILBOX}", "options.lookback_days=36500",
                     f"dest=research/channels/{slug}", slug=slug)
    attended = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    name = f"gws-{slug}"[:60]
    r = run(ops, attended, "--json", "credentials", "set", name, "kind=dir", "login=none", f"path={login}")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, attended, "--json", "credentials", "bind", "job", j.slug, f"dir={name}")
    assert r.returncode == 0, r.stdout + r.stderr
    return j


def test_the_harvest_script_pulls_through_the_granted_login_and_the_day_becomes_an_actionable_ledger(ops, env, wiki, job):
    ticket_id, cap = claimed(ops, env, wiki, job)
    harvest = staged(ops, env, wiki, ticket_id, "")  # a script stage: the runner starts harvest.py, no plan is typed
    assert harvest.update and harvest.update["status"] == "ok", harvest.log[-3000:]
    assert sorted(p.name.split("--")[1] for p in (cap / "items").iterdir()) == ["m1.json", "m2.json", "m3.json"]

    process_id = pending(ops, env, wiki, job.slug)[str(cap.relative_to(wiki))]
    lines = [verdict(1, "fyi"), verdict(2, "action", due="2026-10-16"), verdict(3, "needs-reply")]
    session = staged(ops, env, wiki, process_id, f"""\
cp "$FIX/lines.json" "$CAP/lines.json"
step ledger "$OPS" run {WRITE} ledger "$CAP" --ticket "$TICKET" --from lines.json
""", files={"lines.json": json.dumps(lines).encode()})
    done = session.step("ledger")
    assert done.returncode == 0, done.stdout + done.stderr
    assert session.update["status"] == "ok", session.update

    text = (wiki / job.dest / f"{cap.name}.md").read_text(encoding="utf-8")
    head = text.split("\n---\n", 1)[0]
    assert "type: ledger" in head and f"channel: {job.slug}" in head and "status:" not in head
    assert any(f"needs_reply: {q}1{q}" in head for q in ("", "'", '"')), head
    assert any(f"actions: {q}1{q}" in head for q in ("", "'", '"')), head
    assert _bullets(text) == [
        "- [needs-reply] Person 3 asks about thing 3 — gmail:m3",
        "- [action] Person 2 asks about thing 2 (due 2026-10-16) — gmail:m2",
        "- [fyi] Person 1 asks about thing 1 — gmail:m1",
    ]
