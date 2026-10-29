"""What the study-plan skill's body claims about its own directory."""
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
    return text.replace("{{@@brain-", "{{@brain-")


BODY = _doc(SKILL / "SKILL.md")
MANIFEST = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))
LOCAL = sorted(p.name for p in (SKILL / "references").glob("*"))
COMMANDS = re.findall(r"^llm-wiki-ops [a-z]+ [a-z]+", BODY, re.M)


def test_the_frontmatter_names_this_directory():
    assert BODY.startswith("---\n")
    front = BODY.split("---\n", 2)[1]
    assert f"name: {SKILL.name}\n" in front
    assert "description:" in front


def test_the_body_names_itself_as_a_unit_invocation():
    assert "whereami skill=study-plan " in BODY
    assert "PLUGIN:study-plan" not in BODY


# The plugin reads enable.md, customize.md and usage.md by name (`skills ls`
# carries each as a path), so the body need not mention them.
def test_the_unit_ships_the_three_references_the_plugin_reads():
    assert {"enable.md", "customize.md", "usage.md"} <= set(LOCAL), LOCAL


# The student preset's `study-plan` job runs this unit as `/study-plan
# ticket=<id> stage=routine`; the claim gate admits that job only where the
# enabled manifest serves `routine`.
def test_the_manifest_serves_the_routine_stage_and_names_its_sandbox_at_the_unit_level():
    assert "routine" in MANIFEST.get("stages", {}), "a unit without stages.routine is one no job can run"
    assert MANIFEST["sandbox_ref"].endswith(":study-plan"), MANIFEST.get("sandbox_ref")
    assert "sandbox_ref" not in MANIFEST["stages"]["routine"]


def test_the_scope_names_the_scheduled_entry():
    scope = BODY.split("\n## 1. ", 1)[0]
    assert "<args…> ticket=<id> stage=routine" in scope, "the scope names no scheduled entry"


def test_one_op_is_opened_after_the_overlay_read_and_closed_last():
    assert (BODY.count("llm-wiki-ops op open study-plan"), BODY.count("llm-wiki-ops op close study-plan ")) == (1, 1)
    # The overlay read writes nothing, so it may precede the open.
    assert COMMANDS[:2] == ["llm-wiki-ops policy get", "llm-wiki-ops op open"], COMMANDS[:3]
    assert COMMANDS[-1] == "llm-wiki-ops op close", COMMANDS[-3:]


def test_the_overlay_read_takes_the_quiz_weak_spot_rule_too():
    assert "llm-wiki-ops policy get study-plan quiz\n" in BODY


# The quiz skill writes one `log` page per session, one entry per graded
# answer; this unit reads those entries back, so the fields it names are the
# quiz's, in the quiz's order.
def test_the_log_entry_it_reads_is_the_one_the_quiz_writes():
    entry = re.search(r"^- <date> unit=<document_id> \[\[<title>\]\] answer=\"<[^>]+>\" grade=<[a-z|]+>$", BODY, re.M)
    assert entry, "the body names no quiz log entry in the quiz's shape"
    assert "llm-wiki-ops page ls filter=under:research/logs" in BODY
    assert "llm-wiki-ops page read id=<document_id> fields=tests" in BODY
    assert 'fields=prereqs' in BODY


def test_the_plan_is_one_guide_written_through_the_page_verbs():
    creates = re.findall(r"^llm-wiki-ops page create (.*)$", BODY, re.M)
    assert len(creates) == 1 and "type=guide" in creates[0] and "covers=" in creates[0], creates
    edits = re.findall(r"^llm-wiki-ops page edit (.*)$", BODY, re.M)
    assert len(edits) == 1 and "covers=" in edits[0], edits
    assert "![[<concept>]]" in BODY and "![[<question>]]" in BODY


def test_the_syllabus_is_read_never_parsed_or_written():
    assert "llm-wiki-ops page ls filter=type:playbook" in BODY
    assert "Never assume a layout" in BODY
    for verb in ("page edit", "page append"):
        for line in re.findall(rf"^llm-wiki-ops {verb} (.*)$", BODY, re.M):
            assert "playbook" not in line and "research/logs" not in line, line


@pytest.mark.parametrize("doc", ["SKILL.md", *(f"references/{n}" for n in LOCAL if n.endswith(".md"))])
def test_no_file_of_the_unit_runs_git_commit(doc):
    assert "llm-wiki-ops git commit" not in _doc(SKILL / doc), doc


def test_the_skill_never_posts_its_own_report():
    for gone in ("tickets update", "written_from=", "written.json"):
        assert gone not in BODY, gone
