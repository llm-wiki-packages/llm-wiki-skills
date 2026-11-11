"""podcast, the harness tier: the unit installed and enabled through the
REAL CLI, a routines job's ticket started by the runner in the jail its
`sandbox.jsonc` routine stage composes, with the harness profile's fake agent
typing what the unit's SKILL.md says.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from harness import enabled, rooted, run, shown, staged

SLUG = "harness-podcast"
# What §2–§3 read, put there on the host before the claim: two lectures of a
# course, new in the window the first episode covers.
LECTURE_1 = "sources/documents/courses/Harness 101/Lecture 1 — Light.md"
LECTURE_2 = "sources/documents/courses/Harness 101/Lecture 2 — Sugar.md"
TITLE = "2026-01-08 Light into sugar"
EPISODE = f"wiki/podcasts/{TITLE}.md"
SUMMARY = "harness podcast"
# The last unfocused episode, which §2 opens the window at, and a later
# focused one, which must not move it.
EARLIER = "wiki/podcasts/2026-01-01 Week one.md"
FOCUSED = "wiki/podcasts/2026-01-04 Harness 101 deep dive.md"

# The body arrives as a file the fake agent pipes in: a fenced block's
# backticks inside an `sh -c` string would be command substitution.
BODY = (
    "Two lectures on how light becomes sugar.\n\n"
    "## Show notes\n- [[Lecture 1 — Light]]: where the energy comes from.\n- [[Lecture 2 — Sugar]]: where it goes.\n\n"
    "## Script\n\n"
    "```webvtt\n"
    "<v Alex>Welcome to The Margin. Two lectures, one trick: light into sugar.\n"
    "<v Sam>The cell runs on sunshine, slowly.\n"
    "```\n"
).encode()
COVERS = "[[Lecture 1 — Light]],[[Lecture 2 — Sugar]]"


def _plan() -> str:
    """The order SKILL.md gives: §1's overlay read and `op open`, §2's
    window, §3's reads, §5's episode created then refreshed through the page
    verbs, the writes the sandbox has to refuse, and §7's `op close` last.
    §6 is a session's only, so a ticketed run never types `narrate`. The
    `git commit` is the step the skill never takes, typed here to show it is
    refused by name."""
    return f"""\
step overlay "$OPS" --json policy get podcast
step op-open "$OPS" --json op open podcast
step today date -u +%Y-%m-%d
step episodes "$OPS" --json page list filter=under:wiki/podcasts
step last "$OPS" --json page read "{EARLIER}" fields=window_since,window_until
step changed "$OPS" --json git changed sources filter=since:2026-01-01
step lecture1 "$OPS" --json page read "{LECTURE_1}"
step lecture2 "$OPS" --json page read "{LECTURE_2}"
step create sh -c '"$OPS" --json page create type=podcast dest=wiki/podcasts "title={TITLE}" "description=Two lectures on light and sugar." focus=none window_since=2026-01-01 window_until=2026-01-08 "covers={COVERS}" narrate.modes=podcast --stdin < "$FIX/episode.md"'
step refresh sh -c '"$OPS" --json page edit "{EPISODE}" "description=Two lectures on light and sugar, refreshed." focus=none window_since=2026-01-01 window_until=2026-01-08 "covers={COVERS}" narrate.modes=podcast narrate.refresh=podcast --stdin < "$FIX/episode.md"'
step write-sources sh -c 'printf x >> "{LECTURE_1}"'
step commit "$OPS" --json git commit message=harness
step op-close "$OPS" --json op close podcast outcome=ok "summary={SUMMARY}"
"""


@pytest.fixture(scope="module")
def ran(ops, env, wiki) -> dict:
    """A routines job for the unit, claimed and run once for this module's cases."""
    enabled(ops, env, wiki, "podcast")
    for rel, body in ((LECTURE_1, "Light is absorbed by chlorophyll.\n"), (LECTURE_2, "The Calvin cycle fixes carbon into sugar.\n")):
        where, name = rel.rsplit("/", 1)
        r = run(ops, rooted(env, wiki), "--json", "page", "create", f"title={name.removesuffix('.md')}", f"dest={where}", "--stdin", input=body)
        assert r.returncode == 0 and (wiki / rel).is_file(), r.stdout + r.stderr
    for rel, fields in ((EARLIER, ("focus=none", "window_since=2025-12-25", "window_until=2026-01-01")), (FOCUSED, ("focus=Harness 101",))):
        where, name = rel.rsplit("/", 1)
        r = run(ops, rooted(env, wiki), "--json", "page", "create", f"title={name.removesuffix('.md')}", f"dest={where}", "type=podcast",
                *fields, "--stdin", input="An earlier episode.\n")
        assert r.returncode == 0 and (wiki / rel).is_file(), r.stdout + r.stderr
    r = run(ops, rooted(env, wiki), "--json", "git", "commit", LECTURE_1, LECTURE_2, EARLIER, FOCUSED, "message=harness: what podcast reads")
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, rooted(env, wiki), "--json", "jobs", "add", SLUG, "routines=podcast", "every=7d", "description=harness: podcast")
    assert r.returncode == 0, r.stdout + r.stderr
    for verb in ("resume", "claim", "pause"):
        r = run(ops, rooted(env, wiki), "--json", "jobs", verb, SLUG)
        assert r.returncode == 0, r.stdout + r.stderr
        if verb == "claim":
            mine = [c for c in r.data["claimed"] if c["slug"] == SLUG]
            assert mine and mine[0]["tickets"], f"{SLUG}: claim minted no ticket: {r.stdout}"
            ticket_id = mine[0]["tickets"][0]["id"]
    return {"session": staged(ops, env, wiki, ticket_id, _plan(), files={"episode.md": BODY}), "ticket": ticket_id}


def test_the_routine_runs_in_its_sandbox_and_lands_the_episode(ops, env, wiki, ran):
    """The claim gate admits the job once the enabled copy serves `routine`;
    its slice reads the window off `.git` and the lectures under `sources/`,
    writes the episode under `wiki/` and nothing the sandbox does not name,
    and its `op close` is the report the landing commits under the skill's
    own op."""
    session = ran["session"]
    for step in ("overlay", "op-open", "today", "episodes", "last", "changed", "lecture1", "lecture2", "create", "refresh", "op-close"):
        assert session.step(step).returncode == 0, (step, session.step(step))
    listed = [p["path"] for p in session.step("episodes").data["pages"]]
    assert {EARLIER, FOCUSED} <= set(listed), session.step("episodes").stdout
    # The focused episode carries no window; the unfocused one opens it.
    assert session.step("last").data["frontmatter"]["window_until"] == "2026-01-01", session.step("last").stdout
    assert {LECTURE_1, LECTURE_2} <= set(session.step("changed").data["files"]), session.step("changed").stdout
    assert "chlorophyll" in session.step("lecture1").data["body"], session.step("lecture1").stdout
    assert session.step("write-sources").returncode != 0, "the routine sandbox let the run write under `sources/`"
    commit = session.step("commit")
    assert commit.returncode != 0 and "a ticketed run commits nothing" in commit.stdout + commit.stderr, commit

    assert session.update["status"] == "ok", session.update
    record = shown(ops, env, wiki, ran["ticket"])
    assert record["state"] == "done", json.dumps(record)[:800]
    assert EPISODE in record["written"], (session.update, record.get("written"))  # the landing joins the verbs' record (plugin #4333); the report's own written[] no longer carries it
    assert "frontier" in (record.get("model_from") or ""), record.get("model_from")


def test_the_episode_asks_for_its_audio_and_links_back_to_what_it_covers(ops, env, wiki, ran):
    """The page `narrate` renders: `narrate: {modes: podcast}`, a refresh asked for on
    the rewrite, the script in its `webvtt` block, and `covers` rows that
    resolve to the lectures, so each lecture's backlinks lead to it."""
    page = run(ops, rooted(env, wiki), "--json", "page", "read", EPISODE, "--frontmatter")
    assert page.returncode == 0, page.stdout + page.stderr
    front = page.data["frontmatter"]
    assert front["type"] == "podcast" and front["description"].endswith("refreshed."), front
    assert (front["focus"], front["window_since"], front["window_until"]) == ("none", "2026-01-01", "2026-01-08"), front
    # A string until the plugins declare `narrate.modes` a list field (#4102); then a list.
    narrate = front["narrate"]
    assert narrate["modes"] in ("podcast", ["podcast"]) and narrate["refresh"] in ("podcast", ["podcast"]), front
    assert "render" not in narrate, front
    assert front["covers"] == ["[[Lecture 1 — Light]]", "[[Lecture 2 — Sugar]]"], front["covers"]
    body = (wiki / EPISODE).read_text(encoding="utf-8")
    assert "```webvtt\n<v Alex>Welcome to The Margin." in body, body

    links = run(ops, rooted(env, wiki), "--json", "page", "links", EPISODE)
    assert links.returncode == 0, links.stdout + links.stderr
    covered = {link["path"] for link in links.data["links"] if link["relation"] == "covers"}
    assert covered == {LECTURE_1, LECTURE_2}, links.stdout
    back = run(ops, rooted(env, wiki), "--json", "page", "backlinks", LECTURE_1)
    assert back.returncode == 0, back.stdout + back.stderr
    assert EPISODE in {link["path"] for link in back.data["links"]}, back.stdout


def test_the_landing_commits_under_the_skills_own_op(ops, env, wiki, ran):
    latest = run(ops, rooted(env, wiki), "--json", "op", "latest", "podcast", "filter=outcome:ok")
    assert latest.returncode == 0 and latest.data["found"] is True, latest.stdout + latest.stderr
    close = subprocess.run(["git", "-C", str(wiki), "log", "--format=%H", f"--grep=^{SUMMARY}$", "-n", "1"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert close, f"no landing commit carries the summary {SUMMARY!r}"
    trailers = subprocess.run(["git", "-C", str(wiki), "log", "-1", "--format=%B", close], capture_output=True, text=True, check=True).stdout
    assert "Op: podcast" in trailers and "Outcome: ok" in trailers, trailers
