"""daily-report, the harness tier: the unit installed, bound and enabled
through the REAL CLI, the seeded morning job's routine ticket started by the
runner in the jail its `daily-report.routine` sandbox composes, with the
harness profile's fake agent typing what the unit's SKILL.md says.
"""

from __future__ import annotations

import datetime
import json

from harness import enabled, rooted, run, shown, staged

TODAY = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
REPORT = f"wiki/reports/{TODAY}.md"

# The ticket's own steps (scope, §10) and the writes the sandbox has to
# decide, as the run types them. §1's `op open` and §6's `git commit` and
# `op close` are left out: the commit route is the runner's to grant a slice,
# and no sandbox reference can name `.git` or the wiki's git lock.
PLAN = f"""\
step open "$OPS" --json pipeline tickets open "$TICKET"
step report sh -c 'printf "The lead.\\n" | "$OPS" --json page create title={TODAY} dest=wiki/reports type=report --stdin'
step brief sh -c 'printf "<html></html>\\n" > wiki/reports/{TODAY}.html'
step research sh -c 'printf x > research/daily-report.txt'
step policy sh -c 'mkdir -p .llm-wiki/policy && printf x > .llm-wiki/policy/harness-routine.md'
step listed sh -c 'printf "[\\"{REPORT}\\"]" > "$CAP/written.json"'
step update "$OPS" --json pipeline tickets update "$TICKET" stage=routine status=ok written_from=written.json
"""


def _routine_job(ops, env, wiki) -> str:
    """The seeded job whose routine names this unit, found by its skill so
    the seed's slug is not this file's to know."""
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", "ls")
    assert r.returncode == 0, r.stdout + r.stderr
    slugs = [j["slug"] for j in r.data["jobs"] if j.get("skill") == "daily-report"]
    assert len(slugs) == 1, f"no one seeded job runs daily-report: {[(j['slug'], j.get('skill')) for j in r.data['jobs']]}"
    return slugs[0]


def test_the_seeded_routine_runs_in_its_sandbox_and_lands_the_days_report(ops, env, wiki):
    """The claim gate admits the paused seed once the enabled copy serves
    `routine`; its slice writes `wiki/` and nothing else the sandbox does not
    name, asks the router for the stage's model, and its report lands the
    listed page stamped with the job."""
    enabled(ops, env, wiki, "daily-report")
    slug = _routine_job(ops, env, wiki)
    for verb in ("resume", "claim", "pause"):
        r = run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", verb, slug)
        assert r.returncode == 0, r.stdout + r.stderr
        if verb == "claim":
            mine = [c for c in r.data["claimed"] if c["slug"] == slug]
            assert mine and mine[0]["tickets"], f"{slug}: claim minted no ticket: {r.stdout}"
            ticket_id = mine[0]["tickets"][0]["id"]

    session = staged(ops, env, wiki, ticket_id, PLAN)

    opened = session.step("open")
    assert opened.returncode == 0, opened.stdout + opened.stderr
    assert opened.data["ticket"]["stage"] == "routine", opened.data
    for step in ("report", "brief", "listed", "update"):
        assert session.step(step).returncode == 0, (step, session.step(step))
    for step in ("research", "policy"):
        assert session.step(step).returncode != 0, f"{step}: the routine sandbox let the run write outside `wiki/`"
    assert not (wiki / ".llm-wiki" / "policy" / "harness-routine.md").exists()

    assert session.update["status"] == "ok" and session.update["written"] == [REPORT], session.update
    record = shown(ops, env, wiki, ticket_id)
    assert record["state"] == "done", json.dumps(record)[:800]
    assert "frontier" in (record.get("model_from") or ""), record.get("model_from")
    page = (wiki / REPORT).read_text(encoding="utf-8")
    assert f"\njob: {slug}\n" in page, page[:600]
