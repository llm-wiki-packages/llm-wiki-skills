"""What the daily-report skill's body claims about its own directory."""
import json
import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
# An enabled copy's `*.md` is the source with its `{{@brain-…}}` tokens filled
# in (the `unit-manifest` contract's Tokens section); these tests read the
# source as that copy does.
_TOKENS = {"{{@brain-plugin}}": "brain", "{{@brain-cli}}": "llm-wiki-cli", "{{@brain-cli-ops}}": "llm-wiki-ops", "{{@brain-cli-search}}": "llm-wiki-search"}


def _doc(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for token, name in _TOKENS.items():
        text = text.replace(token, name)
    return text


BODY = _doc(SKILL / "SKILL.md")
SETUP = SKILL / "references" / "setup.md"


def test_the_frontmatter_names_this_directory():
    assert BODY.startswith("---\n")
    front = BODY.split("---\n", 2)[1]
    assert f"name: {SKILL.name}\n" in front
    assert "description:" in front


def test_the_body_names_itself_as_a_unit_invocation():
    assert "whereami skill=daily-report " in BODY
    assert "PLUGIN:daily-report" not in BODY


LOCAL = sorted(p.name for p in (SKILL / "references").glob("*"))

# The plugin reads enable.md, customize.md and usage.md by name (`skills ls`
# carries each as a path), so the body need not mention them.


@pytest.mark.parametrize("local", [n for n in LOCAL if n not in {"enable.md", "customize.md", "usage.md"}])
def test_every_skill_local_reference_it_ships_is_named_in_the_body(local):
    assert local in BODY


def test_the_skill_ships_local_references_to_check():
    assert len(LOCAL) >= 2, LOCAL


# `setup` is a recurring argument, so an unconditional retire refuses on a
# re-run ("carries no 'daily-report-setup' overlay") between the overlay saved
# and the commit that would have kept it.
MARKER_GUARD = "when §1's read returned it"


def test_the_setup_marker_is_retired_only_when_it_was_found():
    setup = _doc(SETUP)
    assert "llm-wiki-ops policy retire daily-report-setup" in setup
    assert MARKER_GUARD in setup, "setup.md retires the marker unconditionally"
    assert MARKER_GUARD in BODY, "the skill body's §8 clause carries no condition"


# The `ops-morning` job runs this unit as `/daily-report ticket=<id>
# stage=routine`; the claim gate admits that job only where the enabled
# manifest serves `routine`.
MANIFEST = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))


def test_the_manifest_serves_the_routine_stage_and_names_its_sandbox_at_the_unit_level():
    assert "routine" in MANIFEST.get("stages", {}), "a unit without stages.routine is one no job can run"
    assert MANIFEST["sandbox_ref"].endswith(":daily-report"), MANIFEST.get("sandbox_ref")
    assert "sandbox_ref" not in MANIFEST["stages"]["routine"]


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
    assert "llm-wiki-ops git commit" not in _doc(SKILL / doc), doc


def test_the_schedule_it_names_is_the_ops_morning_job():
    assert "`ops-morning` job" in BODY
    assert "bundle" not in BODY
