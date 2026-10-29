"""study-plan, the harness tier: the unit installed and enabled through the
REAL CLI, a routines job's ticket started by the runner in the jail its
`sandbox.jsonc` routine stage composes, with the harness profile's fake agent
typing what the unit's SKILL.md says.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from harness import _ops_python, enabled, rooted, run, shown, staged

SLUG = "harness-study-plan"
# What §2–§4 read, put there on the host before the claim: a syllabus, two
# concepts one the other's prereq, a question testing the second, and one quiz
# session that missed it, in the entry shape the quiz writes.
SYLLABUS = "sources/playbooks/Harness syllabus.md"
BASE = "wiki/concepts/Harness base idea.md"
BUILT = "wiki/concepts/Harness built idea.md"
QUESTION = "wiki/questions/Harness built question.md"
LOG = "research/logs/Quiz harness session.md"
PLAN_PAGE = "wiki/guides/Study plan.md"
SUMMARY = "harness study plan"


def _plan(question_id: str) -> str:
    """The order SKILL.md gives: §1's overlay read and `op open`, the reads
    §2–§5 make, the plan created then refreshed through the page verbs, the
    writes the sandbox has to refuse, and §7's `op close` last. A read the
    sandbox does not reach answers empty or refuses, so each is checked for
    its data. The `git commit` is the step the skill never takes, typed here
    to show it is refused by name."""
    body = "Harness lead.\\n\\n## Built idea\\n![[Harness base idea]]\\n![[Harness built idea]]\\nPractice: ![[Harness built question]]\\n"
    covers = "[[Harness built idea]],[[Harness base idea]]"
    return f"""\
step overlay "$OPS" --json policy get study-plan quiz
step op-open "$OPS" --json op open study-plan
step today date -u +%Y-%m-%d
step playbooks "$OPS" --json page ls filter=type:playbook
step syllabus "$OPS" --json page read "{SYLLABUS}"
step logs "$OPS" --json page ls filter=under:research/logs
step log "$OPS" --json page read "{LOG}"
step tests "$OPS" --json page read id={question_id} fields=tests
step prereqs "$OPS" --json page read "{BUILT}" fields=prereqs
step questions "$OPS" --json page backlinks "{BUILT}"
step guides "$OPS" --json page ls filter=type:guide
step create sh -c 'printf "{body}" | "$OPS" --json page create type=guide title="Study plan" "description=Harness plan." "covers={covers}" --stdin'
step refresh sh -c 'printf "{body}Refreshed.\\n" | "$OPS" --json page edit "{PLAN_PAGE}" "description=Harness plan, refreshed." "covers={covers}" --stdin'
step write-sources sh -c 'printf x >> "{SYLLABUS}"'
step write-research sh -c 'printf x >> "{LOG}"'
step commit "$OPS" --json git commit message=harness
step op-close "$OPS" --json op close study-plan outcome=ok "summary={SUMMARY}"
"""


def _create(ops, env, wiki, rel: str, kind: str, body: str, *fields: str) -> str:
    where, name = rel.rsplit("/", 1)
    r = run(ops, rooted(env, wiki), "--json", "page", "create", f"title={name.removesuffix('.md')}", f"dest={where}",
            f"type={kind}", *fields, "--stdin", input=body)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (wiki / rel).is_file(), (rel, r.stdout)
    r = run(ops, rooted(env, wiki), "--json", "page", "read", rel, "fields=document_id")
    assert r.returncode == 0, r.stdout + r.stderr
    return r.data["frontmatter"]["document_id"]


@pytest.fixture(scope="module")
def ran(ops, env, wiki) -> dict:
    """A routines job for the unit, claimed and run once for this module's cases."""
    enabled(ops, env, wiki, "study-plan")
    _create(ops, env, wiki, SYLLABUS, "playbook", "First the base idea, then the built idea; a test on both next week.\n")
    _create(ops, env, wiki, BASE, "concept", "The base idea.\n", "description=The base idea.")
    _create(ops, env, wiki, BUILT, "concept", "Builds on the base idea.\n", "description=Builds on the base idea.",
            "prereqs=[[Harness base idea]]")
    question_id = _create(ops, env, wiki, QUESTION, "question", "What does the built idea build on?\n",
                          "description=What does the built idea build on?", "answer=The base idea.", "tests=[[Harness built idea]]")
    entry = f'- 2026-01-01 unit={question_id} [[Harness built question]] answer="no idea" grade=miss\n'
    _create(ops, env, wiki, LOG, "log", entry, "description=A harness quiz.", "covers=[[Harness built idea]]")
    r = run(ops, rooted(env, wiki), "--json", "git", "commit", SYLLABUS, BASE, BUILT, QUESTION, LOG, "message=harness: what study-plan reads")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, rooted(env, wiki), "--json", "jobs", "add", SLUG, "routines=study-plan", "every=1d", "description=harness: study-plan")
    assert r.returncode == 0, r.stdout + r.stderr
    for verb in ("resume", "claim", "pause"):
        r = run(ops, rooted(env, wiki), "--json", "jobs", verb, SLUG)
        assert r.returncode == 0, r.stdout + r.stderr
        if verb == "claim":
            mine = [c for c in r.data["claimed"] if c["slug"] == SLUG]
            assert mine and mine[0]["tickets"], f"{SLUG}: claim minted no ticket: {r.stdout}"
            ticket_id = mine[0]["tickets"][0]["id"]
    return {"session": staged(ops, env, wiki, ticket_id, _plan(question_id)), "ticket": ticket_id, "question": question_id}


def test_the_routine_runs_in_its_sandbox_and_lands_the_plan(ops, env, wiki, ran):
    """The claim gate admits the job once the enabled copy serves `routine`;
    its slice reads the overlays, the syllabus under `sources/`, the logs
    under `research/` and the units under `wiki/`, writes the plan under
    `wiki/` and nothing the sandbox does not name, and its `op close` is the
    report the landing commits under the skill's own op."""
    session = ran["session"]
    for step in ("overlay", "op-open", "today", "playbooks", "syllabus", "logs", "log", "tests", "prereqs", "questions", "guides",
                 "create", "refresh", "op-close"):
        assert session.step(step).returncode == 0, (step, session.step(step))
    assert SYLLABUS in [p["path"] for p in session.step("playbooks").data["pages"]], session.step("playbooks").stdout
    assert "a test on both next week" in session.step("syllabus").data["body"], session.step("syllabus").stdout
    assert LOG in [p["path"] for p in session.step("logs").data["pages"]], session.step("logs").stdout
    assert f"unit={ran['question']}" in session.step("log").data["body"], session.step("log").stdout
    assert "Harness built idea" in json.dumps(session.step("tests").data["frontmatter"]), session.step("tests").stdout
    assert "Harness base idea" in json.dumps(session.step("prereqs").data["frontmatter"]), session.step("prereqs").stdout
    assert QUESTION in [link["path"] for link in session.step("questions").data["links"] if link["relation"] == "tests"], session.step("questions").stdout
    for step in ("write-sources", "write-research"):
        assert session.step(step).returncode != 0, f"{step}: the routine sandbox let the run write outside `wiki/`"
    commit = session.step("commit")
    assert commit.returncode != 0 and "a ticketed run commits nothing" in commit.stdout + commit.stderr, commit

    assert session.update["status"] == "ok", session.update
    assert PLAN_PAGE in session.update["written"], session.update
    record = shown(ops, env, wiki, ran["ticket"])
    assert record["state"] == "done", json.dumps(record)[:800]
    assert "frontier" in (record.get("model_from") or ""), record.get("model_from")

    plan = run(ops, rooted(env, wiki), "--json", "page", "read", PLAN_PAGE, "--frontmatter")
    assert plan.returncode == 0, plan.stdout + plan.stderr
    front = plan.data["frontmatter"]
    assert front["type"] == "guide" and front["description"] == "Harness plan, refreshed.", front
    assert front["covers"] == ["[[Harness built idea]]", "[[Harness base idea]]"], front["covers"]
    links = run(ops, rooted(env, wiki), "--json", "page", "links", PLAN_PAGE)
    assert links.returncode == 0, links.stdout + links.stderr
    embedded = {link["path"] for link in links.data["links"] if link["relation"] == "embeds"}
    assert embedded == {BASE, BUILT, QUESTION}, links.stdout

    latest = run(ops, rooted(env, wiki), "--json", "op", "latest", "study-plan", "filter=outcome:ok")
    assert latest.returncode == 0 and latest.data["found"] is True, latest.stdout + latest.stderr
    close = subprocess.run(["git", "-C", str(wiki), "log", "--format=%H", f"--grep=^{SUMMARY}$", "-n", "1"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert close, f"no landing commit carries the summary {SUMMARY!r}"
    trailers = subprocess.run(["git", "-C", str(wiki), "log", "-1", "--format=%B", close], capture_output=True, text=True, check=True).stdout
    assert "Op: study-plan" in trailers and "Outcome: ok" in trailers, trailers


_STARTER = """
import json, importlib.resources
print((importlib.resources.files("llm_wiki_ops") / "presets" / "student" / "jobs" / "study-plan.json").read_text())
"""


def test_the_student_presets_starter_job_runs_this_unit_as_a_routine(ops, env):
    """The preset seeds the job and this catalog ships the unit; a rename on
    either side is a starter the claim gate skips forever."""
    r = run(_ops_python(ops), env, "-c", _STARTER)
    assert r.returncode == 0, r.stderr
    job = r.data
    assert job["routines"] == [{"skill": "study-plan"}], job["routines"]
