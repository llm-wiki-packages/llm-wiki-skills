"""daily-report, the harness tier: the unit installed, bound and enabled
through the REAL CLI, the seeded morning job's routine ticket started by the
runner in the jail its `daily-report.routine` sandbox composes, with the
harness profile's fake agent typing what the unit's SKILL.md says.
"""

from __future__ import annotations

import datetime
import json
import shlex
import subprocess

import pytest

from harness import enabled, rooted, run, shown, staged

TODAY = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
REPORT = f"wiki/reports/{TODAY}.md"
BRIEF = f"wiki/reports/{TODAY}.html"
LOG = "wiki/log.md"
# What §3 reads, put there on the host before the claim: the day's ops digest
# and one channel's ledger page.
DIGEST = f"research/reports/{TODAY}.md"
LEDGER = f"research/channels/harness-daily-report/{TODAY}.md"
# A `sources/` page `page lint` flags: the sweep skips a tree it cannot read
# without a word, so only a finding there shows the jail reaches it.
UNDATED = "sources/harness-daily-report/undated.md"
SUMMARY = f"harness daily report {TODAY}"


def _hooked(name: str, tool: str, rel: str, write: str) -> str:
    """One plan step for a raw Write or Edit: the bytes land, then the wiki's
    `PostToolUse` hook records them, as `op record` with the harness's
    payload on stdin naming the file by its absolute path."""
    payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": "%s"}})
    script = f'{write} && printf {shlex.quote(payload)} "$LLM_WIKI_ROOT/{rel}" | "$OPS" --json op record'
    return f"step {name} sh -c {shlex.quote(script)}\n"


# The order SKILL.md gives: §1's overlay read, then `op open`, the reads
# §2–§3 make, the writes the sandbox has to decide — the report through a
# verb, the brief and a log line as a session's Write and Edit, each recorded
# by the hook — and §7's `op close` last. A read the sandbox does not reach
# answers empty or refuses, so each is checked for its data. The `git commit`
# is the step the skill never takes, typed here to show it is refused by name.
PLAN = f"""\
step overlay "$OPS" --json policy get daily-report daily-report-setup
step op-open "$OPS" --json op open daily-report
step latest "$OPS" --json op latest daily-report
step changed "$OPS" --json git changed research sources filter=since:3d
step ledgers "$OPS" --json page ls filter=under:research/channels
step digest "$OPS" --json page read {DIGEST}
step lint "$OPS" --json page lint
step report sh -c 'printf "The lead.\\n" | "$OPS" --json page create title={TODAY} dest=wiki/reports type=report --stdin'
{_hooked("brief", "Write", BRIEF, f"printf '<html></html>\\n' > {BRIEF}")}\
{_hooked("log", "Edit", LOG, f"printf '\\n- report: harness {TODAY}\\n' >> {LOG}")}\
step write-research sh -c 'printf x > research/daily-report.txt'
step write-policy sh -c 'mkdir -p .llm-wiki/policy && printf x > .llm-wiki/policy/harness-routine.md'
step commit "$OPS" --json git commit message=harness
step op-close "$OPS" --json op close daily-report outcome=ok "summary={SUMMARY}"
"""


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    return text.split("\n---\n", 1)[0]


def _routine_job(ops, env, wiki) -> str:
    """The seeded job whose routine names this unit, found by its skill so
    the seed's slug is not this file's to know."""
    r = run(ops, rooted(env, wiki), "--json", "jobs", "ls")
    assert r.returncode == 0, r.stdout + r.stderr
    slugs = [j["slug"] for j in r.data["jobs"] if j.get("skill") == "daily-report"]
    assert len(slugs) == 1, f"no one seeded job runs daily-report: {[(j['slug'], j.get('skill')) for j in r.data['jobs']]}"
    return slugs[0]


@pytest.fixture(scope="module")
def ran(ops, env, wiki) -> dict:
    """The seeded routine, claimed and run once for this module's cases."""
    enabled(ops, env, wiki, "daily-report")
    for rel, body in ((DIGEST, "The digest.\n"), (LEDGER, "- a line\n")):
        where, name = rel.rsplit("/", 1)
        r = run(ops, rooted(env, wiki), "--json", "page", "create", f"title={name.removesuffix('.md')}", f"dest={where}",
                "type=report", "--stdin", input=body)
        assert r.returncode == 0, r.stdout + r.stderr
    (wiki / UNDATED).parent.mkdir(parents=True, exist_ok=True)
    (wiki / UNDATED).write_text("---\ntitle: undated\ntype: note\npublished: someday\n---\nBody.\n", encoding="utf-8")
    r = run(ops, rooted(env, wiki), "--json", "git", "commit", DIGEST, LEDGER, UNDATED, "message=harness: what daily-report reads")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (wiki / LOG).is_file(), "the wiki has no log for §5 to append to"
    log_before = _frontmatter((wiki / LOG).read_text(encoding="utf-8"))
    slug = _routine_job(ops, env, wiki)
    for verb in ("resume", "claim", "pause"):
        r = run(ops, rooted(env, wiki), "--json", "jobs", verb, slug)
        assert r.returncode == 0, r.stdout + r.stderr
        if verb == "claim":
            mine = [c for c in r.data["claimed"] if c["slug"] == slug]
            assert mine and mine[0]["tickets"], f"{slug}: claim minted no ticket: {r.stdout}"
            ticket_id = mine[0]["tickets"][0]["id"]
    return {"session": staged(ops, env, wiki, ticket_id, PLAN), "slug": slug, "ticket": ticket_id, "log_before": log_before}


def test_the_seeded_routine_runs_in_its_sandbox_and_lands_the_days_report(ops, env, wiki, ran):
    """The claim gate admits the paused seed once the enabled copy serves
    `routine`; its slice writes `wiki/` and nothing else the sandbox does not
    name, reads the overlay, the op log, `research/` and `sources/`, asks the
    router for the stage's model, and its `op close` is the report: the
    landing commits the page it wrote under the skill's own op, so `op
    latest` reads the scheduled run as it reads a hand run."""
    session, slug = ran["session"], ran["slug"]
    for step in ("overlay", "op-open", "latest", "changed", "ledgers", "digest", "lint", "report", "brief", "log", "op-close"):
        assert session.step(step).returncode == 0, (step, session.step(step))
    assert "daily-report" in [o["name"] for o in session.step("overlay").data["overlays"]], session.step("overlay").stdout
    assert {DIGEST, LEDGER} <= set(session.step("changed").data["files"]), session.step("changed").stdout
    assert LEDGER in [p["path"] for p in session.step("ledgers").data["pages"]], session.step("ledgers").stdout
    assert session.step("digest").data["body"] == "The digest.\n", session.step("digest").stdout
    assert UNDATED in [f["path"] for f in session.step("lint").data["findings"]], session.step("lint").stdout
    assert session.step("brief").data["recorded"] == [BRIEF], session.step("brief").stdout
    assert session.step("log").data["recorded"] == [LOG], session.step("log").stdout
    for step in ("write-research", "write-policy"):
        assert session.step(step).returncode != 0, f"{step}: the routine sandbox let the run write outside `wiki/`"
    assert not (wiki / ".llm-wiki" / "policy" / "harness-routine.md").exists()
    commit = session.step("commit")
    assert commit.returncode != 0 and "a ticketed run commits nothing" in commit.stdout + commit.stderr, commit

    assert session.update["status"] == "ok", session.update
    assert {REPORT, BRIEF, LOG} <= set(session.update["written"]), session.update
    record = shown(ops, env, wiki, ran["ticket"])
    assert record["state"] == "done", json.dumps(record)[:800]
    assert "frontier" in (record.get("model_from") or ""), record.get("model_from")
    page = (wiki / REPORT).read_text(encoding="utf-8")
    assert f"\njob: {slug}\n" in page, page[:600]

    latest = run(ops, rooted(env, wiki), "--json", "op", "latest", "daily-report", "filter=outcome:ok")
    assert latest.returncode == 0 and latest.data["found"] is True, latest.stdout + latest.stderr

    def message(rev: str) -> str:
        return subprocess.run(["git", "-C", str(wiki), "log", "-1", "--format=%B", rev], capture_output=True, text=True, check=True).stdout

    close = subprocess.run(["git", "-C", str(wiki), "log", "--format=%H", f"--grep=^{SUMMARY}$", "-n", "1"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert close, f"no landing commit carries the summary {SUMMARY!r}"
    trailers = message(close)
    assert "Op: daily-report" in trailers and "Outcome: ok" in trailers and "Op: pass" not in trailers, trailers
    pages = subprocess.run(["git", "-C", str(wiki), "log", "--format=%H", "-n", "1", "--", REPORT], capture_output=True, text=True, check=True).stdout.strip()
    assert "Op: daily-report" in message(pages) and "Op: pass" not in message(pages), message(pages)


@pytest.mark.xfail(strict=True, reason=(
    "simple10/llm-wiki-plugins#3284: the routine landing runs `landing.adopt` and `stamp_meta` over every "
    "path `op close` posts, so the brief gets an `.html.md` adopt stub and `wiki/log.md` is restamped"
))
def test_the_landing_leaves_the_brief_and_the_log_as_the_run_wrote_them(wiki, ran):
    """A routine's Write and Edit are committed under its op and nothing
    more: no adopt stub beside the HTML, and the log keeps its frontmatter."""
    assert not (wiki / f"{BRIEF}.md").exists(), f"{BRIEF}.md: the landing adopted the brief"
    assert _frontmatter((wiki / LOG).read_text(encoding="utf-8")) == ran["log_before"], "the landing restamped wiki/log.md"
