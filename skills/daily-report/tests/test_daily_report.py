"""What the daily-report skill's body claims about its own directory."""
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
