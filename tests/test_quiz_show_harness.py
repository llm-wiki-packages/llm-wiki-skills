"""quiz-show, the harness tier: the unit installed and enabled through the
REAL CLI, a routines job's ticket started by the runner in the jail its
`sandbox.jsonc` routine stage composes, with the harness profile's fake agent
typing what the unit's SKILL.md says.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from harness import enabled, rooted, run, shown, staged

SLUG = "harness-quiz-show"
# What §2–§3 read, put there on the host before the claim: a concept, a
# question testing it, and one quiz session that missed it, in the entry
# shape the quiz writes.
CONCEPT = "wiki/concepts/Harness show idea.md"
QUESTION = "wiki/questions/Harness show question.md"
LOG = "research/logs/Quiz harness show session.md"
TITLE = "2026-01-08 Pop Quiz — weak spots"
EPISODE = f"wiki/podcasts/{TITLE}.md"
SUMMARY = "harness quiz show"
COVERS = "[[Harness show question]],[[Harness show idea]]"
# The body arrives as a file the fake agent pipes in: a fenced block's
# backticks inside an `sh -c` string would be command substitution.
BODY = (
    "One question the last quiz missed.\n\n"
    "## Show notes\n- [[Harness show question]] — [[Harness show idea]], weak\n\n"
    "## Script\n\n"
    "```narrate\n"
    "<v Alex>Welcome to Pop Quiz. One question, no pressure.\n"
    "<v Sam>Some pressure.\n"
    "```\n"
).encode()
# The unit's id, off the log's own entry, and the page it names, as a
# session types them: never from link text.
PICK = b'''import json, re, sys
d = json.load(sys.stdin)
print(re.search(r"unit=(\\S+)", d["body"]).group(1))
'''


def _plan() -> str:
    """The order SKILL.md gives: §1's overlay read and `op open`, §2's
    weak-spot lookup, §3's reads, §5's episode created then refreshed
    through the page verbs, the writes the sandbox has to refuse, and §7's
    `op close` last. §6 is a session's only, so a ticketed run never types
    `narrate`. The `git commit` is the step the skill never takes, typed
    here to show it is refused by name."""
    return f"""\
step overlay "$OPS" --json policy get quiz-show quiz
step op-open "$OPS" --json op open quiz-show
step logtype "$OPS" --json page types log
step logs "$OPS" --json page ls filter=type:log filter=under:research/logs
step log "$OPS" --json page read "{LOG}"
step unit sh -c '"$OPS" --json page links id="$("$OPS" --json page read "{LOG}" | "$PY" "$FIX/pick.py")"'
step concepts "$OPS" --json page ls filter=type:concept
step backlinks "$OPS" --json page backlinks "{CONCEPT}"
step question "$OPS" --json page read "{QUESTION}"
step concept "$OPS" --json page read "{CONCEPT}"
step episodes "$OPS" --json page ls filter=under:wiki/podcasts
step create sh -c '"$OPS" --json page create type=podcast dest=wiki/podcasts "title={TITLE}" "description=The question the last quiz missed." "covers={COVERS}" audio=podcast --stdin < "$FIX/episode.md"'
step refresh sh -c '"$OPS" --json page edit "{EPISODE}" "description=The question the last quiz missed, refreshed." "covers={COVERS}" audio=podcast audio_refresh=podcast --stdin < "$FIX/episode.md"'
step write-research sh -c 'printf x >> "{LOG}"'
step commit "$OPS" --json git commit message=harness
step op-close "$OPS" --json op close quiz-show outcome=ok "summary={SUMMARY}"
"""


def _create(ops, env, wiki, rel: str, kind: str, body: str, *fields: str) -> str:
    where, name = rel.rsplit("/", 1)
    r = run(ops, rooted(env, wiki), "--json", "page", "create", f"title={name.removesuffix('.md')}", f"dest={where}",
            f"type={kind}", *fields, "--stdin", input=body)
    assert r.returncode == 0 and (wiki / rel).is_file(), r.stdout + r.stderr
    r = run(ops, rooted(env, wiki), "--json", "page", "read", rel, "fields=document_id")
    assert r.returncode == 0, r.stdout + r.stderr
    return r.data["frontmatter"]["document_id"]


@pytest.fixture(scope="module")
def ran(ops, env, wiki) -> dict:
    """A routines job for the unit, claimed and run once for this module's cases."""
    enabled(ops, env, wiki, "quiz-show")
    _create(ops, env, wiki, CONCEPT, "concept", "Light becomes sugar in two steps.\n", "description=Light becomes sugar in two steps.")
    question_id = _create(ops, env, wiki, QUESTION, "question", "How many steps turn light into sugar?\n",
                          "description=How many steps turn light into sugar?", "answer=Two.", "tests=[[Harness show idea]]")
    entry = f'- 2026-01-01 unit={question_id} [[Harness show question]] answer="three" grade=miss\n'
    _create(ops, env, wiki, LOG, "log", entry, "description=A harness quiz.", "covers=[[Harness show idea]]")
    r = run(ops, rooted(env, wiki), "--json", "git", "commit", CONCEPT, QUESTION, LOG, "message=harness: what quiz-show reads")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, rooted(env, wiki), "--json", "jobs", "add", SLUG, "routines=quiz-show", "every=1d", "description=harness: quiz-show")
    assert r.returncode == 0, r.stdout + r.stderr
    for verb in ("resume", "claim", "pause"):
        r = run(ops, rooted(env, wiki), "--json", "jobs", verb, SLUG)
        assert r.returncode == 0, r.stdout + r.stderr
        if verb == "claim":
            mine = [c for c in r.data["claimed"] if c["slug"] == SLUG]
            assert mine and mine[0]["tickets"], f"{SLUG}: claim minted no ticket: {r.stdout}"
            ticket_id = mine[0]["tickets"][0]["id"]
    session = staged(ops, env, wiki, ticket_id, _plan(), files={"pick.py": PICK, "episode.md": BODY})
    return {"session": session, "ticket": ticket_id, "question": question_id}


def test_the_routine_runs_in_its_sandbox_and_lands_the_episode(ops, env, wiki, ran):
    """The claim gate admits the job once the enabled copy serves `routine`;
    its slice reads the overlays and the logs under `research/`, reaches the
    missed question by its id, reads the questions and concepts under
    `wiki/`, writes the episode there and nothing the sandbox does not name,
    and its `op close` is the report the landing commits under the skill's
    own op."""
    session = ran["session"]
    for step in ("overlay", "op-open", "logtype", "logs", "log", "unit", "concepts", "backlinks", "question", "concept", "episodes",
                 "create", "refresh", "op-close"):
        assert session.step(step).returncode == 0, (step, session.step(step))
    assert LOG in [p["path"] for p in session.step("logs").data["pages"]], session.step("logs").stdout
    unit = session.step("unit").data
    assert unit["path"] == QUESTION, session.step("unit").stdout
    assert [link["path"] for link in unit["links"] if link["relation"] == "tests"] == [CONCEPT], session.step("unit").stdout
    tests = [link["path"] for link in session.step("backlinks").data["links"] if link["relation"] == "tests"]
    assert tests == [QUESTION], session.step("backlinks").stdout
    assert session.step("write-research").returncode != 0, "the routine sandbox let the run write under `research/`"
    commit = session.step("commit")
    assert commit.returncode != 0 and "a ticketed run commits nothing" in commit.stdout + commit.stderr, commit

    assert session.update["status"] == "ok", session.update
    assert EPISODE in session.update["written"], session.update
    record = shown(ops, env, wiki, ran["ticket"])
    assert record["state"] == "done", json.dumps(record)[:800]
    assert "frontier" in (record.get("model_from") or ""), record.get("model_from")


def test_the_episode_asks_for_its_audio_and_links_back_to_what_it_asks(ops, env, wiki, ran):
    page = run(ops, rooted(env, wiki), "--json", "page", "read", EPISODE, "--frontmatter")
    assert page.returncode == 0, page.stdout + page.stderr
    front = page.data["frontmatter"]
    assert front["type"] == "podcast" and front["description"].endswith("refreshed."), front
    # A string until the plugins declare `audio` a list field (#4102); then a list.
    assert front["audio"] in ("podcast", ["podcast"]) and front["audio_refresh"] in ("podcast", ["podcast"]), front
    assert "audio_render" not in front, front
    body = (wiki / EPISODE).read_text(encoding="utf-8")
    assert "```narrate\n<v Alex>Welcome to Pop Quiz." in body, body
    links = run(ops, rooted(env, wiki), "--json", "page", "links", EPISODE)
    assert links.returncode == 0, links.stdout + links.stderr
    covered = {link["path"] for link in links.data["links"] if link["relation"] == "covers"}
    assert covered == {QUESTION, CONCEPT}, links.stdout


def test_the_landing_commits_under_the_skills_own_op(ops, env, wiki, ran):
    latest = run(ops, rooted(env, wiki), "--json", "op", "latest", "quiz-show", "filter=outcome:ok")
    assert latest.returncode == 0 and latest.data["found"] is True, latest.stdout + latest.stderr
    close = subprocess.run(["git", "-C", str(wiki), "log", "--format=%H", f"--grep=^{SUMMARY}$", "-n", "1"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert close, f"no landing commit carries the summary {SUMMARY!r}"
    trailers = subprocess.run(["git", "-C", str(wiki), "log", "-1", "--format=%B", close], capture_output=True, text=True, check=True).stdout
    assert "Op: quiz-show" in trailers and "Outcome: ok" in trailers, trailers
