"""The harness's own seams, where a wrong answer is an opaque fixture error
rather than a red test."""

from __future__ import annotations

import json

import pytest

from harness import NEUTRAL_CWD, ROOT, STEP_MARK, Result, Session, _cli, _cli_python, claimed, declared_job, shown, staged


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


def test_a_step_reports_its_own_exit_code_stdout_and_stderr_from_inside_the_jail(ops, env, wiki):
    """No `tickets update` and no `run`: a plan's step is read back whole however the stage ends."""
    job = declared_job(ops, env, wiki, "channel-frameio", "https://next.frame.io/share/00000000-0000-0000-0000-00000000bbbb",
                       slug="harness-step")
    ticket_id, _capture_dir = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, "step bad sh -c 'echo o; echo e >&2; exit 3'\nstep gone /no/such/command\n"
                                               "step input sh -c 'cat' < /dev/null\n")
    bad = session.step("bad")
    assert (bad.returncode, bad.stdout, bad.stderr) == (3, "o\n", "e\n")
    gone = session.step("gone")
    assert gone.returncode == 127 and "/no/such/command" in gone.stderr
    assert session.step("input") == Result(0, "", "")


def test_a_step_is_read_back_off_the_log_between_the_runtimes_own_lines():
    log = ("nono: Executing\n"
           f'{STEP_MARK}{json.dumps({"name": "a", "rc": 0, "out": chr(123) + chr(34) + "x" + chr(34) + ": 1}", "err": "warn"})}\n'
           "INFO proxy request allowed host=x\n"
           f'{STEP_MARK}{json.dumps({"name": "b", "rc": 2, "out": "", "err": "boom"})}\n')
    session = Session({}, log)
    assert session.step("a").data == {"x": 1} and session.step("a").stderr == "warn"
    assert session.step("b") == Result(2, "", "boom")
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
