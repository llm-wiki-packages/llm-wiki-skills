"""What the daily-report skill's body claims about its own directory."""
import json
import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
BODY = (SKILL / "SKILL.md").read_text(encoding="utf-8")
SETUP = SKILL / "references" / "setup.md"


def test_the_frontmatter_names_this_directory():
    assert BODY.startswith("---\n")
    front = BODY.split("---\n", 2)[1]
    assert f"name: {SKILL.name}\n" in front
    assert "description:" in front


def test_the_body_names_itself_as_a_unit_invocation():
    assert "whereami skill=daily-report " in BODY
    assert "llm-wiki:daily-report" not in BODY


LOCAL = sorted(p.name for p in (SKILL / "references").glob("*"))


@pytest.mark.parametrize("local", [n for n in LOCAL if n not in {"enable.md", "customize.md"}])
def test_every_skill_local_reference_it_ships_is_named_in_the_body(local):
    assert local in BODY


def test_the_skill_ships_local_references_to_check():
    assert len(LOCAL) >= 2, LOCAL


# `setup` is a recurring argument, so an unconditional retire refuses on a
# re-run ("carries no 'daily-report-setup' overlay") between the overlay saved
# and the commit that would have kept it.
MARKER_GUARD = "when §1's read returned it"


def test_the_setup_marker_is_retired_only_when_it_was_found():
    setup = SETUP.read_text(encoding="utf-8")
    assert "llm-wiki-ops policy retire daily-report-setup" in setup
    assert MARKER_GUARD in setup, "setup.md retires the marker unconditionally"
    assert MARKER_GUARD in BODY, "the skill body's §8 clause carries no condition"


# The `ops-morning` job runs this unit as `/daily-report ticket=<id>
# stage=routine`; the claim gate admits that job only where the enabled
# manifest serves `routine`.
MANIFEST = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))


def test_the_manifest_serves_the_routine_stage_in_its_own_sandbox():
    assert "routine" in MANIFEST.get("stages", {}), "a unit without stages.routine is one no job can run"
    routine = MANIFEST["stages"]["routine"]
    assert routine["sandbox_ref"].endswith(":daily-report/daily-report.routine"), routine


def test_the_scope_names_the_scheduled_entry():
    scope = BODY.split("\n## 1. ", 1)[0]
    assert "<args…> ticket=<id> stage=routine" in scope, "the scope names no scheduled entry"


# The host stamps and the skill reports: one op, opened first and closed last,
# by hand and under a ticket alike. The close commits by hand and reports to
# the ticket under one, so a commit or a report of the skill's own would
# split the run's record.
def test_one_op_is_opened_first_and_closed_last():
    opens = BODY.count("llm-wiki-ops op open daily-report")
    closes = BODY.count("llm-wiki-ops op close daily-report ")
    assert (opens, closes) == (1, 1), (opens, closes)
    commands = re.findall(r"^llm-wiki-ops [a-z]+ [a-z]+", BODY, re.M)
    # The overlay read decides the setup path, which runs under `grill` alone,
    # so it is the one command before the open; it writes nothing.
    assert commands[:2] == ["llm-wiki-ops policy get", "llm-wiki-ops op open"], commands[:3]
    # Only the search index follows the close: it posts nothing and needs no op.
    after = commands[commands.index("llm-wiki-ops op close") + 1:]
    assert set(after) <= {"llm-wiki-ops search index"}, after


def test_the_skill_never_commits_or_posts_its_own_report():
    for gone in ("tickets update", "written_from=", "written.json"):
        assert gone not in BODY, gone


@pytest.mark.parametrize("doc", ["SKILL.md", *(f"references/{n}" for n in LOCAL if n.endswith(".md"))])
def test_no_file_of_the_unit_runs_git_commit(doc):
    """By hand and under a ticket alike, the op's close commits what the run
    wrote; the setup path closes `grill` the same way."""
    assert "llm-wiki-ops git commit" not in (SKILL / doc).read_text(encoding="utf-8"), doc


def test_the_schedule_it_names_is_the_ops_morning_job():
    assert "`ops-morning` job" in BODY
    assert "bundle" not in BODY


# A routine's landing adopts and stamps the pages a `page` verb recorded, so
# the brief, the log and the index go through file tools and stay unstamped.
def test_the_brief_the_log_and_the_index_are_never_written_by_a_page_verb():
    verbs = re.findall(r"^llm-wiki-ops page (?:create|edit) .*$", BODY, re.M)
    for line in verbs:
        assert not re.search(r"wiki/(log|index)\.md|\.html", line), line
    for what in ("`wiki/log.md` bullet, written with\nyour file tools", "written with your file tools: it is no page"):
        assert what in BODY, what
