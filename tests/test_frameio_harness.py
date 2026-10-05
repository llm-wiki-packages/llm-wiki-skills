"""channel-frameio, the harness tier: the unit installed and enabled through
the REAL CLI, its harvest stage started by the runner in the jail it composes,
with the harness profile's fake agent typing what the unit's SKILL.md says.
Its helpers and constants are the unit's own tests' —
`skills/channel-frameio/tests/test_frameio.py`, which ships with the unit —
so a case here reads exactly as it did beside them.

Rich behavior (title settling, `reference`, video stubs, `bundle_media`, PDF
extraction) is the unit's own tests'; this file proves the front door
plumbing through a real jail.
"""

from __future__ import annotations

import json

from harness import claimed, declared_job, shown, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-frameio", "test_frameio"))

DRIVER = "ops/skills/channel-frameio/scripts/harvest_share.py"

# The venue's bytes for every planned leaf, written where the plan put it:
# what a capture would have fetched.
CAPTURE_LEAVES = """python3 - "$CAP" <<'PY'
import json, os, sys
for leaf in json.load(open(os.path.join(sys.argv[1], "plan.json")))["leaves"]:
    os.makedirs(leaf["dir"], exist_ok=True)
    open(os.path.join(leaf["dir"], "document.pdf"), "wb").write(b"%PDF-1.4 fake")
    json.dump({"item": leaf["item"], "title": "T", "body": "document.pdf", "content_type": "application/pdf"},
              open(os.path.join(leaf["dir"], "capture.json"), "w"))
PY
"""


def test_a_live_harvest_ticket_plans_and_captures_through_the_real_cli(ops, env, wiki):
    """`harvest_share.py`, run in the stage's jail, opens its ticket through
    `tickets open` and posts `tickets update`, and the runner lands what it posted."""
    job = declared_job(ops, env, wiki, UNIT, SHARE, "dest=sources/scrapes/harness-frameio", slug="harness-frameio")
    ticket_id, cap = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, f"""\
cp "$FIX/tree.json" "$CAP/tree.json"
step plan "$OPS" run {DRIVER} "$CAP" --ticket "$TICKET" --plan-only
{CAPTURE_LEAVES}step report "$OPS" run {DRIVER} "$CAP" --ticket "$TICKET" --budget-seconds -1
""", files={"tree.json": json.dumps({"leaves": [_leaf(1)]}).encode()})

    planned = session.step("plan")
    assert planned.returncode == 0, planned.stdout + planned.stderr
    assert json.loads(planned.stdout)["planned"] == 1
    (leaf,) = json.loads((cap / "plan.json").read_text(encoding="utf-8"))["leaves"]
    assert (wiki / leaf["dir"] / "document.pdf").is_file()
    reported = session.step("report")
    assert reported.returncode == 0, reported.stdout + reported.stderr
    assert json.loads(reported.stdout)["captured"] == 1

    assert session.update["status"] == "ok", session.update
    assert shown(ops, env, wiki, ticket_id)["state"] == "done"


def test_an_explicit_reference_on_the_job_reaches_the_plan(ops, env, wiki):
    """The operator's `harvest.assets=reference` rides the job record into the
    ticket, and the driver's `--plan-only` leaves the media leaf out of
    `plan.json` — named under `unplanned` — while the document is planned."""
    job = declared_job(ops, env, wiki, UNIT, FOLDER, "dest=sources/scrapes/harness-frameio-ref",
                       "harvest.assets=reference", slug="harness-frameio-reference")
    assert job.record["harvest"]["assets"] == "reference"
    ticket_id, cap = claimed(ops, env, wiki, job)
    video, deck = _leaf(1, name="Keynote.mov"), _leaf(2, name="Deck.pdf")
    session = staged(ops, env, wiki, ticket_id, f"""\
cp "$FIX/tree.json" "$CAP/tree.json"
step plan "$OPS" run {DRIVER} "$CAP" --ticket "$TICKET" --plan-only
""", files={"tree.json": json.dumps({"leaves": [video, deck]}).encode()})

    planned = session.step("plan")
    assert planned.returncode == 0, planned.stdout + planned.stderr
    summary = json.loads(planned.stdout)
    assert (summary["planned"], summary["skipped"]["reference"]) == (1, 1), summary
    plan = json.loads((cap / "plan.json").read_text(encoding="utf-8"))
    assert [leaf["item"] for leaf in plan["leaves"]] == [deck["view_url"]]
    assert plan["unplanned"] == [{"item": video["view_url"], "name": "Keynote.mov", "why": "reference"}]
