"""The harness's own seams, where a wrong answer is an opaque fixture error
rather than a red test."""

from __future__ import annotations

import pytest

from harness import NEUTRAL_CWD, ROOT, Session, _cli, _cli_python, claimed, declared_job, shown, staged


def test_a_claimed_ticket_runs_in_the_jail_the_runner_composes(ops, env, wiki):
    """`staged`: `tickets run <id> wait=` starts the stage behind its jail and the
    fake agent types the plan there, as the ticket's own worker."""
    job = declared_job(ops, env, wiki, "channel-frameio", "https://next.frame.io/share/00000000-0000-0000-0000-00000000aaaa",
                       slug="harness-staged")
    ticket_id, capture_dir = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, 'step jail printenv LLM_WIKI_JAIL\nstep open "$OPS" --json pipeline tickets open "$TICKET"\n'
                     'step update "$OPS" --json pipeline tickets update "$TICKET" stage=harvest status=ok\n')
    assert session.step("jail").stdout.strip() == "nono"
    opened = session.step("open")
    assert opened.returncode == 0, opened.stdout + opened.stderr
    assert opened.data["ticket"]["capture_dir"] == str(capture_dir.relative_to(wiki))
    assert shown(ops, env, wiki, ticket_id)["state"] == "done"  # the pass the slice's exit runs landed it


def test_a_step_is_read_back_off_the_log_between_the_runtimes_own_lines():
    log = "nono: Executing\n@@out a\n{\"x\": 1}\n\n@@err a\nwarn\n@@rc a 0\nINFO proxy\n@@out b\n\n@@err b\nboom\n@@rc b 2\n"
    session = Session({}, log)
    assert session.step("a").data == {"x": 1} and session.step("a").stderr.strip() == "warn"
    assert session.step("b").returncode == 2 and session.step("b").stderr.strip() == "boom"
    with pytest.raises(AssertionError):
        session.step("c")


def test_the_cli_interpreter_is_found_beside_its_console_script(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "llm-wiki-ops").touch()
    assert _cli_python([str(tmp_path / "bin" / "llm-wiki-ops")]) == [str(tmp_path.resolve() / "bin" / "python")]
    assert _cli_python(["uv", "run", "--project", "/p", "llm-wiki-ops"]) == ["uv", "run", "--project", "/p", "python"]


def test_the_machine_cli_is_found_beside_a_path_spelled_ops():
    """`LLM_WIKI_OPS` is the console script by absolute path (the dispatch's
    contract, and `which`'s answer): its directory need not be on PATH, so the
    machine CLI is the sibling file, not a bare name."""
    assert _cli(["/opt/ops/bin/llm-wiki-ops"]) == ["/opt/ops/bin/llm-wiki-cli"]
    assert _cli(["llm-wiki-ops"]) == ["llm-wiki-cli"]
    assert _cli(["uv", "run", "--project", "/p", "llm-wiki-ops"]) == ["uv", "run", "--project", "/p", "llm-wiki-cli"]


def test_the_harness_runs_nothing_from_the_checkout():
    """A checkout inside a wiki would bind every call to that wiki; what the
    neutral directory needs is that no wiki owns it."""
    assert NEUTRAL_CWD.is_dir() and not NEUTRAL_CWD.is_relative_to(ROOT) and not ROOT.is_relative_to(NEUTRAL_CWD)
    assert not any((p / ".llm-wiki.toml").exists() for p in (NEUTRAL_CWD, *NEUTRAL_CWD.parents))
