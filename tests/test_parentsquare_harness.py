"""channel-parentsquare, the harness tier: the unit's sandbox reference installed, checked and enabled
through the REAL CLI, and the stdio MCP server it declares reaching the operator's review. The bin is
`tests/fake_parentsquare_mcp.sh`, first on the harness's PATH: nothing here starts the real server or reaches
ParentSquare.
"""

from __future__ import annotations

import json
import re

from harness import ROOT, enabled, jsonc, rooted, run

UNIT = "channel-parentsquare"
TEMPLATE = "parentsquare-harvest"
REFERENCE = ROOT / "references" / "sandboxes" / "parentsquare" / "parentsquare.harvest.md"


def _mcp_block() -> list:
    """The reference's `## MCP` block, parsed."""
    text = REFERENCE.read_text(encoding="utf-8")
    section = re.search(r"^## MCP\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert section, "the reference has no ## MCP"
    (fence,) = re.findall(r"^```json\n(.*?)^```$", section.group(1), re.M | re.S)
    return json.loads(fence)


def _installed(ops, env, wiki) -> dict:
    """The unit installed, and the template install wrote for its venue's harvest, parsed."""
    r = run(ops, rooted(env, wiki), "--json", "skills", "install", UNIT)
    assert r.returncode == 0, r.stdout + r.stderr
    ops_dir = run(ops, rooted(env, wiki), "--json", "whereami").data["wiki"]["ops_dir"]
    return jsonc((wiki / ops_dir / "sandboxes" / f"{TEMPLATE}.jsonc").read_text(encoding="utf-8"))


def test_install_writes_the_template_with_the_servers_the_reference_declares(ops, env, wiki):
    template = _installed(ops, env, wiki)
    assert template["mcp"] == _mcp_block()
    assert [one["name"] for one in template["mcp"]] == ["parentsquare"]
    assert template["source"]["ref"] == "llm-wiki-packages/llm-wiki-skills:references/sandboxes/parentsquare/parentsquare.harvest.md"


def test_sandboxes_check_accepts_the_installed_template(ops, env, wiki):
    _installed(ops, env, wiki)
    r = run(ops, rooted(env, wiki), "--json", "sandboxes", "check", TEMPLATE)
    assert r.returncode == 0, r.stdout + r.stderr


def test_skills_enable_answers_with_the_stages_mcp_row(ops, env, wiki):
    """The template `skills install` wrote, enabled and bound, then the unit enabled: the review row names the server and the `env` names, never a value."""
    enabled(ops, env, wiki, UNIT)  # the harness's own sandbox is bound first, and put back at the end
    _installed(ops, env, wiki)
    ops_dir = run(ops, rooted(env, wiki), "--json", "whereami").data["wiki"]["ops_dir"]
    attended = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}

    def bind(sandbox: str) -> dict:
        for verb in (["skills", "bind", UNIT, "stage=harvest", f"sandbox={sandbox}", "--confirm"],
                     ["git", "commit", f"{ops_dir}/skills/{UNIT}/manifest.json", f"message=harness: harvest on {sandbox}"]):
            done = run(ops, attended, "--json", *verb)
            assert done.returncode == 0, (verb, done.stdout + done.stderr)
        done = run(ops, attended, "--json", "skills", "enable", UNIT, "--confirm")
        assert done.returncode == 0, done.stdout + done.stderr
        return done.data

    done = run(ops, attended, "--json", "sandboxes", "enable", TEMPLATE, "--confirm")
    assert done.returncode == 0, done.stdout + done.stderr
    try:
        answer = bind(TEMPLATE)
    finally:
        bind(f"{UNIT}-harvest")  # every other case here runs on the harness's own sandbox
    stages = [one for one in answer["stages"] if one["stage"] == "harvest"]
    assert len(stages) == 1, answer
    (block,) = _mcp_block()
    assert stages[0]["reach"]["mcp"] == [
        {"name": block["name"], "command": block["command"], "args": block["args"], "env": sorted(block["env"])},
    ], stages[0]["reach"]
    assert "cookies.json" not in json.dumps(stages[0]["reach"]["mcp"])
    assert any(w.startswith("env: PS_PASSWORD, PS_USERNAME") for w in answer["warnings"]), answer["warnings"]
