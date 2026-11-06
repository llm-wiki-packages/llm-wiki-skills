"""study-plan and quiz-show both name what is weak by the quiz's own rule
and lookup. Units ship self-contained, so each carries its own copy; this
holds the copies to each other, so the plan and the show cannot call weak
what the other does not."""

from __future__ import annotations

import pytest

from harness import ROOT, doc

UNITS = ("study-plan", "quiz-show")
# The lines the lookup is made of, as the enabled copies read them.
SHARED = (
    "{cli} policy get {unit} quiz\n",
    "{cli} page types log\n",
    "{cli} page ls filter=type:log filter=under:<the log type's dir>\n",
    "- <date> unit=<document_id> [[<title>]] answer=\"<the reply>\" grade=<correct|partial|miss>\n",
    "{cli} page links id=<document_id>\n",
    "{cli} page backlinks \"<tested concept path>\"\n",
    "Read the newest five sessions whose entries carry `grade=`, newest by the\ndate each entry opens with",
    "latest graded attempt was a `partial` or a `miss`",
    "a unit with no such row tested itself",
    "Its `relation=covers` rows under the log type's directory are every session\nthat tested it",
)


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("line", SHARED)
def test_each_unit_carries_the_quizs_lookup(unit, line):
    body = doc(ROOT / "skills" / unit / "SKILL.md")
    want = line.format(cli="llm-wiki-ops", unit=unit)
    assert want in body, f"{unit}: {want!r}"
