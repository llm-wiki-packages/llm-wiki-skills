"""channel-notion-tasks, the harness tier: the unit installed and enabled through the REAL
CLI, each stage started by the runner in the jail it composes, with the
harness profile's fake agent typing what the unit's SKILL.md says. Its helpers and constants are the
unit's own tests' — `skills/channel-notion-tasks/tests/test_notion.py`, which ships with
the unit — so a case here reads exactly as it did beside them.
"""

from __future__ import annotations

import datetime
import json
import re

import pytest

from harness import ROOT, claimed, declared_job, jsonc, pending, snippet, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-notion-tasks", "test_notion"))

TODAY = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _bullets(text: str) -> list:
    return [line for line in text.splitlines() if line.startswith("- ")]


WRITE = "ops/skills/channel-notion-tasks/scripts/write_items.py"


def pulled(ops, env, wiki, job, pull: list, *flags: str):
    """The harvest stage, in its jail: what `pull.py` left, handed to `write`."""
    ticket_id, cap = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, f"""\
cp "$FIX/pull.json" "$CAP/pull.json"
step write "$OPS" run {WRITE} write "$CAP" --ticket "$TICKET" --from pull.json {' '.join(flags)}
""", files={"pull.json": json.dumps(pull).encode()})
    done = session.step("write")
    assert done.returncode == 0, done.stdout + done.stderr
    return cap


def ledgered(ops, env, wiki, job, cap, rows: list):
    """The process stage the harvest's landing minted, in its jail: the step's
    own words handed to `ledger`, which writes the day's page."""
    process_id = pending(ops, env, wiki, job.slug)[str(cap.relative_to(wiki))]
    session = staged(ops, env, wiki, process_id, f"""\
cp "$FIX/lines.json" "$CAP/lines.json"
step ledger "$OPS" run {WRITE} ledger "$CAP" --ticket "$TICKET" --from lines.json
""", files={"lines.json": json.dumps(rows).encode()})
    done = session.step("ledger")
    assert done.returncode == 0, done.stdout + done.stderr
    assert session.update["status"] in ("ok", "partial"), session.update
    return done


def _machine_fragment(text: str) -> dict:
    """The one fenced json block under `## Machine`: the nono fragment `skills install` writes to `machine.allow`."""
    match = re.search(r"^## Machine\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, "the reference has no `## Machine` block"
    (fence,) = re.findall(r"^```json\n(.*?)^```$", match.group(1), re.M | re.S)
    return json.loads(fence)


def test_the_reference_carries_the_notion_route_the_wikis_vault_resolves():
    text = (ROOT / "references" / "sandboxes" / "notion" / "notion.harvest.md").read_text(encoding="utf-8")
    profile = jsonc(snippet(text))["profile"]
    network = profile["network"]
    assert "api.notion.com" in network["allow_domain"]
    assert not any("notion" in h and h != "api.notion.com" for h in network["allow_domain"])
    assert profile["environment"]["set_vars"]["NOTION_API_VERSION"] == "2025-09-03"
    # The committed `## Profile` is read straight, and refuses every credential key.
    assert set(network) == {"allow_domain"} and "credential" not in json.dumps(profile)
    # A venue route is `credentials` plus `custom_credentials`, nothing else: compose
    # mints `credential_key` and the capture, so a wiki-written one is refused.
    assert _machine_fragment(text) == {"network": {
        "credentials": ["notion"],
        "custom_credentials": {"notion": {
            "upstream": "https://api.notion.com", "env_var": "NOTION_API_TOKEN", "credential_format": "Bearer {}",
        }},
    }}
    # The route is this stage's, resolved from the wiki's vault: no login, no harness-profile route.
    assert "llm-wiki-ops credentials set notion" in text
    assert "never the harness profile's" in " ".join(text.split())
    assert "~/.config/llm-wiki" not in text


def test_enable_md_names_the_vault_not_a_login_or_a_harness_profile():
    enable = (ROOT / "skills" / "channel-notion-tasks" / "references" / "enable.md").read_text(encoding="utf-8")
    flat = " ".join(enable.split())
    assert "llm-wiki-ops credentials set notion" in flat
    assert "No `ntn login`, and no route in a harness profile" in flat
    assert "`ntn login` there" not in flat and "this machine's harness profile" not in flat


@pytest.fixture
def job(ops, env, wiki, request):
    # A job's capture dir is keyed on TODAY: each case gets its own job, or one
    # case's items would read back as another's.
    own = request.node.name.replace("_", "-").lower()
    return declared_job(ops, env, wiki, UNIT, f"{TARGET}-{own}"[:60], "options.workspace=harness",
                        slug=f"harness-notion-{own}"[:60])


def test_the_two_steps_make_the_days_ledger_out_of_what_the_pull_left(ops, env, wiki, job):
    """The whole point of the rework: a harvest ticket whose `write` posts
    `tickets update` through the REAL CLI from inside its jail, then `ledger` —
    the process arm, on the process ticket the harvest's landing mints —
    building the day's page through the REAL `page create`."""
    pull = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cap = pulled(ops, env, wiki, job, pull, "--exclude-status", "Archived")
    day = cap.name
    # The process step's own words, one row per item the day holds. The fixture's
    # hostile task carries none, so its bullet falls back to the task's own title.
    r2 = ledgered(ops, env, wiki, job, cap, [{"id": one["id"], "line": one["summary"], "junk": one["junk"]} for one in pull])
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
    day = None

    def _write(pull):
        nonlocal day
        cap = pulled(ops, env, wiki, job, pull)
        day = day or cap.name
        assert cap.name == day, "a re-pull the same day lands in the same day's capture dir"
        return cap

    cap = _write([task(21, last_edited=f"{TODAY}T09:00:00.000Z")])
    ledgered(ops, env, wiki, job, cap, lines(("0000aaaa-0021", "Task 21 moved to Doing, due 30 Sep")))
    ledger = wiki / job.dest / f"{day}.md"
    assert _bullets(ledger.read_text(encoding="utf-8")) == ["- Task 21 moved to Doing, due 30 Sep — notion:0000aaaa-0021"]

    # Later the same day: the same task edited again, and a new one.
    cap = _write([task(21, last_edited=f"{day}T14:00:00.000Z"), task(22, last_edited=f"{day}T13:00:00.000Z")])
    ledgered(ops, env, wiki, job, cap, lines(("0000aaaa-0021", "Task 21 completed"), ("0000aaaa-0022", "Task 22 moved to Doing, due 30 Sep")))
    assert len(list(ledger.parent.glob(f"{day}*"))) == 1
    body = ledger.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    assert _bullets(body) == [
        "- Task 22 moved to Doing, due 30 Sep — notion:0000aaaa-0022",
        "- Task 21 completed — notion:0000aaaa-0021",
    ]
    assert body.count("discarded:") == 1 and "moved to Doing, due 30 Sep — notion:0000aaaa-0021" not in body
    assert "status:" not in ledger.read_text(encoding="utf-8").split("\n---\n", 1)[0]  # the edit path leaves it unset too
