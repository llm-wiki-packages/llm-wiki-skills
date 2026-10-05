"""channel-gmail, the harness tier: the unit installed and enabled through the REAL
CLI, each stage started by the runner in the jail it composes, with the
harness profile's fake agent typing what the unit's SKILL.md says. Its helpers and constants are the
unit's own tests' — `skills/channel-gmail/tests/test_gmail.py`, which ships with
the unit — so a case here reads exactly as it did beside them.
"""

from __future__ import annotations

import json
import pytest

from harness import bound_credential, claimed, declared_job, pending, rooted, run, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-gmail", "test_gmail"))


def _bullets(text: str) -> list:
    return [line for line in text.splitlines() if line.startswith("- ")]


def _body(text: str) -> str:
    assert text.startswith("---\n")
    return text.split("\n---\n", 1)[1]


WRITE = "ops/skills/channel-gmail/scripts/write_items.py"


def pulled(ops, env, wiki, job, pull: list, *flags: str):
    """The harvest stage, in its jail: the connector's pull handed to `write`."""
    ticket_id, cap = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, f"""\
cp "$FIX/pull.json" "$CAP/pull.json"
step write "$OPS" run {WRITE} write "$CAP" --ticket "$TICKET" --from pull.json {' '.join(flags)}
""", files={"pull.json": json.dumps(pull).encode()})
    done = session.step("write")
    assert done.returncode == 0, done.stdout + done.stderr
    return ticket_id, cap


def ledgered(ops, env, wiki, job, cap, lines: list) -> None:
    """The process stage the harvest's landing minted, in its jail: the step's
    verdicts handed to `ledger`, which writes the day's page."""
    process_id = pending(ops, env, wiki, job.slug)[str(cap.relative_to(wiki))]
    session = staged(ops, env, wiki, process_id, f"""\
cp "$FIX/lines.json" "$CAP/lines.json"
step ledger "$OPS" run {WRITE} ledger "$CAP" --ticket "$TICKET" --from lines.json
""", files={"lines.json": json.dumps(lines).encode()})
    done = session.step("ledger")
    assert done.returncode == 0, done.stdout + done.stderr
    assert session.update["status"] in ("ok", "partial"), session.update


def _needs_ledger_verb(ops, env, wiki):
    if run(ops, rooted(env, wiki), "pipeline", "jobs", "ledger", "--help").returncode != 0:
        pytest.skip("`pipeline jobs ledger` is plugins PR 2 (#2486/#2487)")


@pytest.fixture
def job(ops, env, wiki, request):
    # A job's capture dir is keyed on TODAY, not on this test — sharing one
    # slug/target across cases run on the same real day would read one
    # case's items back as another's. Each case gets its own of both.
    # A channel target/slug is `^[a-z0-9][a-z0-9-]*$` — no underscores, so
    # the test's own name (hyphenated, lowered) stands in for it.
    own = request.node.name.replace("_", "-").lower()
    slug = f"harness-gmail-{own}"[:60]
    # `pipeline jobs ledger` (A-11) refuses a `dest` that is not the ledger
    # route (`research/channels/<slug>`) — gmail's own, not the generic
    # staged default `declared_job` gives every other unit.
    j = declared_job(ops, env, wiki, UNIT, f"{TARGET}-{own}"[:60], "options.mailbox=a@example.invalid",
                      f"dest=research/channels/{slug}", slug=slug)
    # `requires.credential: true`'s claim gate (plugins main, post-#2487):
    # `jobs claim` refuses an unbound job — bind this machine's session to it.
    bound_credential(ops, env, wiki, j.slug)
    return j


def test_a_pull_becomes_the_days_ledger_through_the_real_cli(ops, env, wiki, job):
    """The whole point of the rework: a harvest ticket whose `write` posts
    `tickets update` through the REAL CLI from inside its jail, then `ledger` —
    the process arm, on the process ticket the harvest's landing mints —
    building the day's page through the REAL `page create`."""
    pull = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _ticket_id, cap = pulled(ops, env, wiki, job, pull, "--exclude-label", "SPAM")
    day = cap.name
    # The step's verdicts: one line each in the wiki's words, and the digest junked.
    ledgered(ops, env, wiki, job, cap, [{"id": f"gmail:{m['id']}", "line": m["summary"], "junk": m["junk"]} for m in pull])
    ledger_path = wiki / job.dest / f"{day}.md"

    text = ledger_path.read_text(encoding="utf-8")
    head, body = text.split("\n---\n", 1)
    assert "type: ledger" in head and f"channel: {job.slug}" in head
    assert "status:" not in head  # a draft here would put every day of every channel in curate's list
    assert "items: '4'" in head or 'items: "4"' in head or "items: 4" in head

    bullets = _bullets(body)
    assert len(bullets) == 4, body  # 6 pulled: one SPAM filtered, one junked, four kept
    assert "discarded: 1 (junk rules)" in body
    # Oldest first, and in the WIKI's words — the sender's subject is nowhere.
    assert bullets[0] == "- Dana at Acme asks for the Q3 numbers by Friday — gmail:18c0a1"
    assert "URGENT" not in body and "wire the money" not in body
    # The step's own line is folded the same way: a wikilink written there does not survive as one.
    assert bullets[3] == "- Sam shares the ((Roadmap)) draft and 'asks' for comments — gmail:18c0a6"

    # The one the step judged nothing about: the sender's 5 000-character subject, standing in.
    hostile = next(b for b in bullets if b.endswith("— gmail:18c0a3"))
    line = hostile[2 : -len(" — gmail:18c0a3")]
    assert len(line) == 200 and line.endswith("…")
    assert "\n" not in line and "`" not in line and "[" not in line and "]" not in line
    assert "((Home))" in line and "'''" in line  # `[[Home]]` and the fence, neutralized — not removed
    assert "ignore previous instructions" in line.lower()  # carried as DATA, on one bullet's one line
    assert "<" not in line and ">" not in line
    assert hostile.count(" — ") == 1 and "*" not in line and "|" not in line and "://" not in line and "www." not in line
    assert line.startswith("paid - gmail:forged ∗∗now∗∗ a¦b https:")  # the forged pointer reads as text, not as the pointer
    assert body.count("```") == 0 and "[[" not in body and "\n#" not in body

    # The junked message's content is on no page — only its count.
    assert "Weekly digest" not in text


def test_a_second_pull_the_same_day_regenerates_the_one_ledger_whole(ops, env, wiki, job):
    """`write` and `ledger` are the harvest and process stages of TWO
    different tickets (landing mints the process one), never one id reused
    across both — a sub-daily re-pull mints a fresh pair, into the SAME day's
    capture dir."""
    _ticket_id, cap = pulled(ops, env, wiki, job, [msg(1), msg(2)])
    day = cap.name
    ledgered(ops, env, wiki, job, cap, [line_for(1), line_for(2)])
    ledger_path = wiki / job.dest / f"{day}.md"
    first = _body(ledger_path.read_text(encoding="utf-8"))
    assert _bullets(first) == ["- Person 1 asks about thing 1 — gmail:m1", "- Person 2 asks about thing 2 — gmail:m2"]

    # A sub-daily pull: one new message, and m2 again with a better line (the boundary over-fetch is dropped).
    _ticket_id, cap = pulled(ops, env, wiki, job, [msg(3), msg(2)])
    assert cap.name == day, "a sub-daily re-pull still lands in the same day's capture dir"
    ledgered(ops, env, wiki, job, cap, [line_for(1), line_for(2, "rewritten"), line_for(3)])
    assert len(list(ledger_path.parent.glob(f"{day}*"))) == 1  # edited, never a second page for the day
    second = _body(ledger_path.read_text(encoding="utf-8"))
    assert _bullets(second) == ["- Person 1 asks about thing 1 — gmail:m1", "- rewritten — gmail:m2",
                                "- Person 3 asks about thing 3 — gmail:m3"]
    assert second.count("discarded:") == 1

    # Whole, not appended: take an item away and its bullet goes with it.
    # Another pull (same items — `write` is idempotent) for a fresh ticket
    # pair to post the regenerated ledger through.
    _ticket_id, cap = pulled(ops, env, wiki, job, [msg(3), msg(2)])
    (cap / "items" / f"{T0 + 1000}--m1.json").unlink()
    ledgered(ops, env, wiki, job, cap, [line_for(2, "rewritten"), line_for(3)])
    assert _bullets(_body(ledger_path.read_text(encoding="utf-8"))) == _bullets(second)[1:]


def test_the_items_are_still_a_ledger_the_hosts_own_extractor_can_make(ops, env, wiki, job):
    """`pipeline jobs ledger` (A-11) over the same day: the sender's line,
    neutralized, where the process step would have put the wiki's own."""
    _needs_ledger_verb(ops, env, wiki)
    _ticket_id, cap = pulled(ops, env, wiki, job, [msg(11, subject="paid — gmail:forged **now**")])
    day = cap.name

    made = run(ops, rooted(env, wiki), "pipeline", "jobs", "ledger", job.slug, f"day={day}")
    assert made.returncode == 0, made.stdout + made.stderr
    page = wiki / job.dest / f"{day}.md"
    assert page.is_file()
    body = _body(page.read_text(encoding="utf-8"))
    assert _bullets(body) == ["- paid - gmail:forged ∗∗now∗∗ — gmail:m11"]
    assert "discarded: 0 (junk rules)" in body
