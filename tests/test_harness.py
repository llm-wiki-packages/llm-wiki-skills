"""The harness's own seams, where a wrong answer is an opaque fixture error
rather than a red test."""

from __future__ import annotations

import pytest

from harness import NEUTRAL_CWD, ROOT, _cli, declared_job, landed, live_ticket, rooted, run


def test_a_live_ticket_is_minted_and_moved_to_active_by_the_cli(ops, env, wiki):
    """`live_ticket` (A-8, A-9): `jobs claim` mints the harvest ticket, and
    `tickets run <id> spawn=self` moves it to `active/` under this session's
    own worker id — never a hand-written `ticket.json` (side note)."""
    if run(ops, rooted(env, wiki), "pipeline", "tickets", "run", "--help").returncode != 0:
        pytest.skip("`pipeline tickets run` is plugins PR 2 (#2486)")
    # A resolvable host: `spawn=self` refuses a ticket whose target host does
    # not resolve to a public address (plugins main, post-#2487), before this
    # case ever reaches the script that would fetch it.
    job = declared_job(ops, env, wiki, "web-page", "https://example.com/harness/live-ticket", slug="harness-live-ticket")
    ticket_id, capture_dir = live_ticket(ops, env, wiki, job)
    shown = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "show", ticket_id).data["tickets"][0]
    assert shown["state"] == "active" and shown["worker"] == "harness-session"
    assert capture_dir.relative_to(wiki)
    landed(ops, env, wiki, ticket_id)  # frees the harvest cap slot for every later case in this session


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


class _Answer:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


REFUSAL = "refused: runs only in its jail; run `pipeline tickets run <id> wait=<s>` instead"


@pytest.mark.parametrize("args", [
    ("--json", "pipeline", "tickets", "run", "t1", "spawn=self"),
    ("run", "ops/skills/channel-gmail/scripts/write_items.py", "write", "_raw/x/y"),
])
def test_a_stage_driven_by_hand_and_refused_for_the_jail_is_a_skip_not_a_failure(args):
    from harness import _refused_for_the_jail

    assert _refused_for_the_jail(args, _Answer(2, stderr=REFUSAL))


@pytest.mark.parametrize("args, answer", [
    (("run", "ops/skills/x/scripts/y.py"), _Answer(2, stderr="usage: y.py")),  # a refusal that is not the jail's stays a failure
    (("run", "ops/skills/x/scripts/y.py"), _Answer(0, stdout=REFUSAL)),
    (("pipeline", "tickets", "close", "t1"), _Answer(2, stderr=REFUSAL)),  # not a hand-driven stage
])
def test_every_other_answer_is_the_cases_to_judge(args, answer):
    from harness import _refused_for_the_jail

    assert _refused_for_the_jail(args, answer) is None
