"""Every `{{@brain-…}}` token the package ships is one `skills enable` and
`reference` can fill in (the `unit-manifest` contract's Tokens section).

A bad key in a unit's `*.md` refuses at enable, on an operator's machine;
here it reddens in CI first. Only `*.md` is filled in, so a token anywhere
else would ship as literal text.
"""

from __future__ import annotations

import re

import pytest

from harness import ROOT, TOKENS, render

TREES = ("skills", "sandboxes")
SHIPPED = sorted(p for tree in TREES for p in (ROOT / tree).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
DOCS = [p for p in SHIPPED if p.suffix == ".md"]
# A unit's own tests name the tokens to fill them, as an enabled copy reads.
OTHERS = [p for p in SHIPPED if p.suffix != ".md" and "tests" not in p.relative_to(ROOT).parts]
# What the tokens replaced: a doc that spells one of these again is one the
# next rename misses.
LITERAL = re.compile(r"/llm-wiki:|llm-wiki-(?:cli|ops|search)(?![-/_a-z0-9])")


def _id(path):
    return str(path.relative_to(ROOT))


def test_the_scan_reads_the_docs_and_finds_tokens():
    assert len(DOCS) >= 50 and OTHERS, (len(DOCS), len(OTHERS))
    assert sum(p.read_text(encoding="utf-8").count("{{@brain-") for p in DOCS) >= 300


@pytest.mark.parametrize("path", DOCS, ids=_id)
def test_every_token_in_a_doc_is_a_known_key(path):
    render(path.read_text(encoding="utf-8"), where=_id(path))


@pytest.mark.parametrize("path", DOCS, ids=_id)
def test_a_doc_spells_no_literal_namespace_or_cli_name(path):
    text = path.read_text(encoding="utf-8")
    found = [f"{_id(path)}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0)}" for m in LITERAL.finditer(text)]
    assert not found, "write the token: " + ", ".join(f"{{{{@{k}}}}}" for k in TOKENS) + "\n" + "\n".join(found)


@pytest.mark.parametrize("path", OTHERS, ids=_id)
def test_a_token_appears_only_where_it_is_filled_in(path):
    assert "{{@brain-" not in path.read_text(encoding="utf-8", errors="replace").replace("{{@@brain-", ""), _id(path)


@pytest.mark.parametrize(("text", "rendered"), [
    ("/{{@brain-plugin}}:enable x", "/brain:enable x"),
    ("`{{@brain-cli-ops}} tickets open <id>` and {{@brain-cli}}", "`llm-wiki-ops tickets open <id>` and llm-wiki-cli"),
    ("{{@brain-cli-search}}", "llm-wiki-search"),
    ("{{@@brain-cli-ops}} shows the token", "{{@brain-cli-ops}} shows the token"),
    ("{{@index}} {{@root}} {{title}}", "{{@index}} {{@root}} {{title}}"),
    ("a\n{{@brain-cli}}\nb\n", "a\nllm-wiki-cli\nb\n"),
])
def test_render_fills_known_keys_and_passes_the_rest_through(text, rendered):
    assert render(text) == rendered


@pytest.mark.parametrize("text", [
    "one\n`{{@brain-cli-op}} run`",   # an unknown key
    "one\n{{@brain-cli }}",          # malformed
    "one\n{{@brain-cli",             # unclosed
    "one\n{{@brain-}}",              # no key
])
def test_render_refuses_a_bad_token_by_line(text):
    with pytest.raises(ValueError, match=r"^doc\.md:2: "):
        render(text, where="doc.md")


def test_the_literal_scan_finds_what_it_was_written_for():
    assert LITERAL.search("run `/llm-wiki:enable x`") and LITERAL.search("`llm-wiki-ops tickets open`")
    assert not LITERAL.search("/llm-wiki-server:reindex, llm-wiki-ops-v1, .llm-wiki.toml, llm-wiki-ops/v1/plugin")
