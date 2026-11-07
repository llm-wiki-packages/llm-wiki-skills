"""What the quiz-show skill's body claims about its own directory."""
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
# The `narrate` engine's script contract: the page's first ```webvtt block,
# one turn per line, `<v Name>` then the words (simple10/llm-wiki-plugins#4108).
TURN = re.compile(r"^<v ([^>]+)>(\S.*)$")


def _section(n: int) -> str:
    return BODY.split(f"\n## {n}. ", 1)[1].split("\n## ", 1)[0]


def test_the_frontmatter_names_this_directory():
    assert BODY.startswith("---\n")
    front = BODY.split("---\n", 2)[1]
    assert f"name: {SKILL.name}\n" in front
    assert "description:" in front


def test_the_body_names_itself_as_a_unit_invocation():
    assert "whereami skill=quiz-show " in BODY
    assert "PLUGIN:quiz-show" not in BODY


def test_the_unit_ships_the_three_references_the_plugin_reads():
    assert {"enable.md", "customize.md", "usage.md"} <= set(LOCAL), LOCAL


def test_the_manifest_serves_the_routine_stage_and_names_its_sandbox_at_the_unit_level():
    assert "routine" in MANIFEST.get("stages", {}), "a unit without stages.routine is one no job can run"
    assert MANIFEST["sandbox_ref"].endswith(":quiz-show"), MANIFEST.get("sandbox_ref")
    assert "sandbox_ref" not in MANIFEST["stages"]["routine"]


def test_the_scope_names_the_scheduled_entry():
    scope = BODY.split("\n## 1. ", 1)[0]
    assert "<args…> ticket=<id> stage=routine" in scope, "the scope names no scheduled entry"


def test_one_op_is_opened_after_the_overlay_read_and_closed_last():
    assert (BODY.count("llm-wiki-ops op open quiz-show"), BODY.count("llm-wiki-ops op close quiz-show ")) == (1, 1)
    assert COMMANDS[:2] == ["llm-wiki-ops policy get", "llm-wiki-ops op open"], COMMANDS[:3]
    assert COMMANDS[-1] == "llm-wiki-ops op close", COMMANDS[-3:]


# What is weak is the quiz's: the same overlay, the same stock rule and the
# same lookup, so the show cannot call weak what the next quiz does not.
def test_the_weak_spot_lookup_is_the_quizs_own():
    assert "llm-wiki-ops policy get quiz-show quiz\n" in BODY
    for line in ("llm-wiki-ops page types log\n", "llm-wiki-ops page ls filter=type:log filter=under:<the log type's dir>\n",
                 "llm-wiki-ops page links id=<document_id>\n"):
        assert line in BODY, line
    assert "newest five sessions whose entries carry `grade=`" in BODY
    assert "latest graded attempt was a `partial` or a `miss`" in BODY
    entry = re.search(r"^- <date> unit=<document_id> \[\[<title>\]\] answer=\"<[^>]+>\" grade=<[a-z|]+>$", BODY, re.M)
    assert entry, "the body names no quiz log entry in the quiz's shape"


def test_an_unresolved_link_row_is_never_given_to_a_verb():
    for hop in ("`relation=tests` row", "`relation=tests` rows are the questions"):
        tail = BODY.split(hop, 1)[1][:300]
        assert "path=none" in tail, hop


def test_the_shows_answer_is_the_questions_own():
    assert "A\nquestion's `answer` field is the answer the show gives" in BODY
    assert "Never create a question page." in BODY


def test_the_episode_is_one_page_written_through_the_page_verbs_asking_for_audio():
    creates = re.findall(r"^llm-wiki-ops page create (.*)$", BODY, re.M)
    assert len(creates) == 1, creates
    for field in ("type=podcast", "dest=wiki/podcasts", "covers=", "narrate.modes=podcast"):
        assert field in creates[0], (field, creates[0])
    edits = re.findall(r"^llm-wiki-ops page edit (.*)$", BODY, re.M)
    assert len(edits) == 1, edits
    for field in ("covers=", "narrate.modes=podcast", "narrate.refresh=podcast"):
        assert field in edits[0], (field, edits[0])
    for verb in ("page edit", "page append"):
        for line in re.findall(rf"^llm-wiki-ops {verb} (.*)$", BODY, re.M):
            assert "research/logs" not in line and "question" not in line.split("covers=")[0], line


def test_narrate_runs_in_one_session_only_section():
    calls = re.findall(r"^llm-wiki-ops narrate .*$", BODY, re.M)
    assert calls == ['llm-wiki-ops narrate "<episode path>" mode=podcast'], calls
    six = _section(6)
    assert "llm-wiki-ops narrate" in six and "Under `ticket=`, skip this section" in six
    assert "Run `narrate` under `ticket=`." in BODY.split("## Never", 1)[1]


def test_the_skill_never_writes_what_narrate_owns():
    never = BODY.split("## Never", 1)[1]
    assert "narrate.render" in never and "Grade, regrade or annotate a quiz log." in never


def test_every_example_script_block_is_one_the_engine_parses():
    blocks = re.findall(r"^```webvtt\n(.*?)^```", BODY, re.M | re.S)
    assert blocks, "the body shows no webvtt script block"
    for block in blocks:
        lines = block.rstrip("\n").split("\n")
        assert all(TURN.match(line) for line in lines), lines
        assert {TURN.match(line)[1] for line in lines} <= {"Alex", "Sam"}, lines
        assert not any(re.search(r"[*_`\[\]#|]", TURN.match(line)[2]) for line in lines), "markdown inside a spoken line"
        # The engine's parser reads `<…>` as a cue tag and `-->` as a timing line.
        assert not any(re.search(r"[<>]|-->", TURN.match(line)[2]) for line in lines), "a cue tag or timing inside a spoken line"


@pytest.mark.parametrize("doc", ["SKILL.md", *(f"references/{n}" for n in LOCAL if n.endswith(".md"))])
def test_no_file_of_the_unit_runs_git_commit(doc):
    assert "llm-wiki-ops git commit" not in _doc(SKILL / doc), doc


def test_the_skill_never_posts_its_own_report():
    for gone in ("tickets update", "written_from=", "written.json"):
        assert gone not in BODY, gone
