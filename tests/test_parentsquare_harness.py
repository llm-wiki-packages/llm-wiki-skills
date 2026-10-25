"""channel-parentsquare, the harness tier: the unit's sandbox installed and enabled through the REAL CLI,
and the stdio MCP server it declares reaching the operator's review. The bin is
`tests/fake_parentsquare_mcp.sh`, first on the harness's PATH: nothing here starts the real server or reaches
ParentSquare.
"""

from __future__ import annotations

import json

from harness import SOURCE, enabled, installed_sandbox, rooted, run, template

UNIT = "channel-parentsquare"
TEMPLATE = "parentsquare"


def _mcp_block() -> list:
    """The template's harvest stage `mcp` block, as the catalog ships it."""
    return template(TEMPLATE)["stages"]["harvest"]["mcp"]


def _installed(ops, env, wiki) -> dict:
    """The unit installed, and the `sandbox.jsonc` install wrote beside it, parsed."""
    r = run(ops, rooted(env, wiki), "--json", "skills", "install", UNIT)
    assert r.returncode == 0, r.stdout + r.stderr
    return installed_sandbox(ops, env, wiki, UNIT)


def test_install_writes_the_sandbox_with_the_servers_the_template_declares(ops, env, wiki):
    written = _installed(ops, env, wiki)
    assert written["stages"]["harvest"]["mcp"] == _mcp_block()
    assert [one["name"] for one in written["stages"]["harvest"]["mcp"]] == ["parentsquare"]
    assert written["source"]["ref"] == f"{SOURCE}:{TEMPLATE}"


def test_skills_enable_answers_with_the_stages_mcp_row(ops, env, wiki):
    """The sandbox `skills install` wrote, then the unit enabled: the review row names the server and the `env` names, never a value."""
    _installed(ops, env, wiki)
    attended = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    done = run(ops, attended, "--json", "skills", "enable", UNIT, "--confirm")
    assert done.returncode == 0, done.stdout + done.stderr
    answer = done.data
    stages = [one for one in answer["stages"] if one["stage"] == "harvest"]
    assert len(stages) == 1, answer
    (block,) = _mcp_block()
    assert stages[0]["reach"]["mcp"] == [
        {"name": block["name"], "command": block["command"], "args": block["args"], "env": sorted(block["env"])},
    ], stages[0]["reach"]
    assert "cookies.json" not in json.dumps(stages[0]["reach"]["mcp"])
    assert any(w.startswith("env: PS_PASSWORD, PS_USERNAME") for w in answer["warnings"]), answer["warnings"]


def test_the_unit_enables_on_the_sandbox_install_wrote(ops, env, wiki):
    enabled(ops, env, wiki, UNIT)
    assert (wiki / run(ops, rooted(env, wiki), "--json", "whereami").data["wiki"]["ops_dir"] / "skills" / UNIT / "sandbox.jsonc").is_file()


def test_the_template_asks_for_no_machine_grant():
    """The slice floor grants a declared bin's toolchain reads, console script included; a server bin needs no `machine_reads`."""
    assert "machine_reads" not in template(TEMPLATE)["stages"]["harvest"]
