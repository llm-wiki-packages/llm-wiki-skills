"""channel-notion-tasks, the harness tier: the unit installed and enabled through the REAL
CLI, landing pages in the session wiki. Its helpers and constants are the
unit's own tests' — `skills/channel-notion-tasks/tests/test_notion.py`, which ships with
the unit — so a case here reads exactly as it did beside them.
"""

from __future__ import annotations

import json
import re

import pytest

from harness import ROOT, declared_job, jsonc, landed, live_ticket, rooted, run, snippet, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-notion-tasks", "test_notion"))


def _bullets(text: str) -> list:
    return [line for line in text.splitlines() if line.startswith("- ")]


def _needs_run_verb(ops, env, wiki):
    if run(ops, rooted(env, wiki), "pipeline", "tickets", "run", "--help").returncode != 0:
        pytest.skip("`pipeline tickets run` (spawn=self) is plugins PR 2 (#2486)")


def _closing_the_process_ticket_discards_the_scripts_own_ledger():
    """Same finding as `test_gmail_harness.py`'s: `tickets_close.py`
    (~line 479-486), unconditionally, for any job whose `dest` is the
    ledger route, regenerates the day's page straight from the raw
    `items/*.json` files' own `subject`/`title` field — in-process, after
    and OVER whatever this unit's own `ledger` subcommand, built from the
    process step's judged `lines.json`, just wrote through `page create`.
    Reported to the coordinator, not a harness gap to paper over."""
    pytest.skip("plugins main c284c4839: tickets_close.py's extract_ledger overwrites a ledger job's page on close, discarding write_items.py ledger's own lines.json curation — reported, not a harness gap")


def _credential_keys(node) -> set:
    """Every `credentials`/`custom_credentials`/`credential_capture` key at
    any depth of a parsed document — the real invariant a wiki's own
    template must never carry, not just the `## Machine`/`## Probe` headings
    that happen to be how this reference used to spell one."""
    found: set = set()
    if isinstance(node, dict):
        found |= {"credentials", "custom_credentials", "credential_capture"} & node.keys()
        for value in node.values():
            found |= _credential_keys(value)
    elif isinstance(node, list):
        for item in node:
            found |= _credential_keys(item)
    return found


def test_the_reference_carries_no_notion_route_and_the_profile_reaches_only_the_api():
    text = (ROOT / "references" / "sandboxes" / "notion" / "notion.harvest.md").read_text(encoding="utf-8")
    profile = jsonc(snippet(text))["profile"]
    assert "api.notion.com" in profile["network"]["allow_domain"]
    assert not any("notion" in h and h != "api.notion.com" for h in profile["network"]["allow_domain"])
    assert profile["environment"]["set_vars"]["NOTION_API_VERSION"] == "2025-09-03"
    # The wiki-writable `## Profile` block is the real invariant: it must
    # carry no credential key at all, whatever depth or heading a route
    # might otherwise hide behind.
    assert not _credential_keys(profile)
    # ntn owns its own login (spec §8): no venue route, no wiki-writable
    # capture. A machine-owned block here would refuse at `skills install`
    # under the compose-mints-every-capture rule (llm-wiki-plugins#2646) —
    # `install.py` only ever reads a JSON fence under these two headings.
    assert "## Machine" not in text and "## Probe" not in text
    # The route lives in the harness profile, named in prose only, no path spelled.
    assert "harness profile" in text and "~/.config/llm-wiki" not in text
    # The admin's hand-written harness-profile route, shown as an example
    # only — a plain fenced block, never under a `## Machine`/`## Probe`
    # heading `skills install` would read — carries everything a route
    # nothing mints for it needs.
    example = json.loads(re.search(r"```json\n(.*?)^```$", text, re.M | re.S).group(1))
    assert example["network"]["credentials"] == ["notion"]
    assert example["network"]["custom_credentials"]["notion"] == {
        "upstream": "https://api.notion.com", "credential_key": "cmd://notion",
        "env_var": "NOTION_API_TOKEN", "credential_format": "Bearer {}",
    }
    assert example["credential_capture"]["notion"]["command"] == ["ntn", "auth", "token"]


def test_a_captured_token_reaches_a_spawned_harvest_session():
    pytest.skip(
        "the composer does not yet merge a harness profile's routes into a "
        "spawned session jail: plugins #2657 (harness profiles, part B)"
    )


@pytest.fixture
def job(ops, env, wiki):
    return declared_job(ops, env, wiki, UNIT, TARGET, "options.workspace=harness")


def test_the_two_steps_make_the_days_ledger_out_of_what_the_pull_left(ops, env, wiki, job):
    """The whole point of the rework: a live harvest ticket, `write` posting
    `tickets update` through the REAL CLI (no stub — `run` exports
    `LLM_WIKI_OPS`), then `ledger` — the process arm, on the SAME ticket, as
    `channel-youtube`'s own `--record`-then-process reuse does — building the
    day's page through the REAL `page create`."""
    _closing_the_process_ticket_discards_the_scripts_own_ledger()
    _needs_run_verb(ops, env, wiki)
    ticket_id, cap = live_ticket(ops, env, wiki, job)
    rel = str(cap.relative_to(wiki))
    day = cap.name
    pull = json.loads(FIXTURE.read_text(encoding="utf-8"))
    (cap / "pull.json").write_text(json.dumps(pull), encoding="utf-8")
    r = run(ops, rooted(env, wiki), "run", "ops/skills/channel-notion-tasks/scripts/write_items.py", "write",
            rel, "--ticket", ticket_id, "--from", "pull.json", "--exclude-status", "Archived", cwd=wiki)
    assert r.returncode == 0, r.stdout + r.stderr

    # The process step's own words, one row per item the day holds. The fixture's
    # hostile task carries none, so its bullet falls back to the task's own title.
    (cap / "lines.json").write_text(
        json.dumps([{"id": one["id"], "line": one["summary"], "junk": one["junk"]} for one in pull]), encoding="utf-8"
    )
    r2 = run(ops, rooted(env, wiki), "run", "ops/skills/channel-notion-tasks/scripts/write_items.py", "ledger",
             rel, "--ticket", ticket_id, "--dest", job.dest, "--from", "lines.json", cwd=wiki)
    assert r2.returncode == 0, r2.stdout + r2.stderr

    closed = landed(ops, env, wiki, ticket_id)
    assert closed.get("status") in ("ok", "partial", None), closed
    ledger = wiki / job.dest / f"{day}.md"
    assert json.loads(r2.stdout)["written"] == [f"{job.dest}/{day}.md"] and ledger.is_file()

    head, body = ledger.read_text(encoding="utf-8").split("\n---\n", 1)
    assert "type: ledger" in head and f"channel: {job.slug}" in head and "items: '3'" in head
    # No status: a ledger is outside the lifecycle, and a draft a day would put
    # every day of every channel in curate's list.
    assert "status:" not in head

    bullets = _bullets(body)
    assert len(bullets) == 3, body  # 5 pulled: one Archived filtered at harvest, one junked at process, three kept
    assert "discarded: 1 (junk rules)" in body
    assert bullets[0] == "- Launch checklist moved to Doing, due 30 Sep, owner Operator — https://www.notion.so/0a1b2c3d00004000800000000000b001"

    hostile = bullets[1]
    line, pointer = hostile[2:].rsplit(" — ", 1)
    assert len(line) == 200 and line.endswith("…")
    assert "`" not in hostile and "[" not in hostile and "]" not in hostile and "<" not in hostile
    assert "((Home))" in line and "'''" in line and "ignore previous instructions" in line.lower()
    assert pointer == "notion:0000bbbb-0002"  # from the id: the venue's url carried the title, and lost its id at the cap
    assert hostile.count(" — ") == 1 and "*" not in line and "|" not in line and "://" not in line and "www." not in line
    assert body.count("```") == 0 and "[[" not in body and "\n#" not in body

    assert "Reordered backlog" not in ledger.read_text(encoding="utf-8")  # the junked task: counted, never rendered


def test_a_second_pull_the_same_day_regenerates_the_one_ledger_whole(ops, env, wiki, job):
    _closing_the_process_ticket_discards_the_scripts_own_ledger()
    _needs_run_verb(ops, env, wiki)
    ticket_id, cap = live_ticket(ops, env, wiki, job)
    rel = str(cap.relative_to(wiki))
    day = cap.name

    def _write(pull):
        (cap / "pull.json").write_text(json.dumps(pull), encoding="utf-8")
        r = run(ops, rooted(env, wiki), "run", "ops/skills/channel-notion-tasks/scripts/write_items.py", "write",
                rel, "--ticket", ticket_id, "--from", "pull.json", cwd=wiki)
        assert r.returncode == 0, r.stdout + r.stderr

    def _ledger(rows):
        (cap / "lines.json").write_text(json.dumps(rows), encoding="utf-8")
        r = run(ops, rooted(env, wiki), "run", "ops/skills/channel-notion-tasks/scripts/write_items.py", "ledger",
                rel, "--ticket", ticket_id, "--dest", job.dest, "--from", "lines.json", cwd=wiki)
        assert r.returncode == 0, r.stdout + r.stderr

    _write([task(21, last_edited=f"{day}T09:00:00.000Z")])
    _ledger(lines(("0000aaaa-0021", "Task 21 moved to Doing, due 30 Sep")))
    ledger = wiki / job.dest / f"{day}.md"
    assert _bullets(ledger.read_text(encoding="utf-8")) == ["- Task 21 moved to Doing, due 30 Sep — notion:0000aaaa-0021"]

    # Later the same day: the same task edited again, and a new one.
    _write([task(21, last_edited=f"{day}T14:00:00.000Z"), task(22, last_edited=f"{day}T13:00:00.000Z")])
    _ledger(lines(("0000aaaa-0021", "Task 21 completed"), ("0000aaaa-0022", "Task 22 moved to Doing, due 30 Sep")))
    assert len(list(ledger.parent.glob(f"{day}*"))) == 1
    body = ledger.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    assert _bullets(body) == [
        "- Task 22 moved to Doing, due 30 Sep — notion:0000aaaa-0022",
        "- Task 21 completed — notion:0000aaaa-0021",
    ]
    assert body.count("discarded:") == 1 and "moved to Doing, due 30 Sep — notion:0000aaaa-0021" not in body
    assert "status:" not in ledger.read_text(encoding="utf-8").split("\n---\n", 1)[0]  # the edit path leaves it unset too
