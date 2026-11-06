"""What the podcast skill's body claims about its own directory."""
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
    assert "whereami skill=podcast " in BODY
    assert "PLUGIN:podcast" not in BODY


def test_the_unit_ships_the_three_references_the_plugin_reads():
    assert {"enable.md", "customize.md", "usage.md"} <= set(LOCAL), LOCAL


def test_the_manifest_serves_the_routine_stage_and_names_its_sandbox_at_the_unit_level():
    assert "routine" in MANIFEST.get("stages", {}), "a unit without stages.routine is one no job can run"
    assert MANIFEST["sandbox_ref"].endswith(":podcast"), MANIFEST.get("sandbox_ref")
    assert "sandbox_ref" not in MANIFEST["stages"]["routine"]


def test_the_scope_names_the_scheduled_entry():
    scope = BODY.split("\n## 1. ", 1)[0]
    assert "<args…> ticket=<id> stage=routine" in scope, "the scope names no scheduled entry"


def test_one_op_is_opened_after_the_overlay_read_and_closed_last():
    assert (BODY.count("llm-wiki-ops op open podcast"), BODY.count("llm-wiki-ops op close podcast ")) == (1, 1)
    assert COMMANDS[:2] == ["llm-wiki-ops policy get", "llm-wiki-ops op open"], COMMANDS[:3]
    assert COMMANDS[-1] == "llm-wiki-ops op close", COMMANDS[-3:]


# The default window opens where the last UNFOCUSED episode's closed, read
# off the episodes themselves: `op latest` would count a focused by-hand
# episode too, and move the weekly window past pages it never covered.
def test_the_default_window_is_read_off_the_last_unfocused_episode():
    assert "op latest" not in BODY
    assert 'llm-wiki-ops page read "<episode path>" fields=window_since,window_until\n' in BODY
    assert "llm-wiki-ops git changed sources filter=since:<the window's start>\n" in BODY
    assert "a focused episode omits both" in BODY
    assert "never a page under\n`wiki/podcasts/`" in BODY, "an episode may feed the next"


# The scheduled run's sandbox reaches no search service: search is a session's.
def test_search_is_a_sessions_only():
    assert "Only a session may also ask" in BODY
    assert not re.search(r"^llm-wiki-ops search ", BODY, re.M), "search as a step every run takes"


def test_the_episode_is_one_page_written_through_the_page_verbs_asking_for_audio():
    creates = re.findall(r"^llm-wiki-ops page create (.*)$", BODY, re.M)
    assert len(creates) == 1, creates
    for field in ("type=podcast", "dest=wiki/podcasts", "covers=", "audio=podcast", "focus=", "window_until="):
        assert field in creates[0], (field, creates[0])
    edits = re.findall(r"^llm-wiki-ops page edit (.*)$", BODY, re.M)
    assert len(edits) == 1, edits
    # A rewritten script is stale audio, and stale audio never re-renders on
    # its own: the edit asks for the render again.
    for field in ("covers=", "audio=podcast", "audio_refresh=podcast", "focus=", "window_until="):
        assert field in edits[0], (field, edits[0])


# The engine is the host's: a scheduled run in its jail hands the page over
# through `audio`, and only a session asked for the audio now runs it.
def test_narrate_runs_in_one_session_only_section():
    calls = re.findall(r"^llm-wiki-ops narrate .*$", BODY, re.M)
    assert calls == ['llm-wiki-ops narrate "<episode path>" mode=podcast'], calls
    six = _section(6)
    assert "llm-wiki-ops narrate" in six and "Under `ticket=`, skip this section" in six
    assert "Run `narrate` under `ticket=`." in BODY.split("## Never", 1)[1]


def test_the_skill_never_writes_what_narrate_owns():
    never = BODY.split("## Never", 1)[1]
    assert "audio_render" in never
    for line in re.findall(r"^llm-wiki-ops page (?:create|edit) (.*)$", BODY, re.M):
        assert "audio_render" not in line, line


def test_every_example_script_block_is_one_the_engine_parses():
    blocks = re.findall(r"^```webvtt\n(.*?)^```", BODY, re.M | re.S)
    assert blocks, "the body shows no webvtt script block"
    hosts = {"Alex", "Sam"}
    for block in blocks:
        lines = block.rstrip("\n").split("\n")
        assert all(TURN.match(line) for line in lines), lines
        assert {TURN.match(line)[1] for line in lines} <= hosts, lines
        assert not any(re.search(r"[*_`\[\]#|]", TURN.match(line)[2]) for line in lines), "markdown inside a spoken line"
        # The engine's parser reads `<…>` as a cue tag and `-->` as a timing line.
        assert not any(re.search(r"[<>]|-->", TURN.match(line)[2]) for line in lines), "a cue tag or timing inside a spoken line"


def test_the_stock_hosts_are_the_ones_the_examples_use():
    stock = _section(1)
    for name in ("**Alex**", "**Sam**"):
        assert name in stock, name
    assert "[narrate.voices]" in stock


@pytest.mark.parametrize("doc", ["SKILL.md", *(f"references/{n}" for n in LOCAL if n.endswith(".md"))])
def test_no_file_of_the_unit_runs_git_commit(doc):
    assert "llm-wiki-ops git commit" not in _doc(SKILL / doc), doc


def test_the_skill_never_posts_its_own_report():
    for gone in ("tickets update", "written_from=", "written.json"):
        assert gone not in BODY, gone
