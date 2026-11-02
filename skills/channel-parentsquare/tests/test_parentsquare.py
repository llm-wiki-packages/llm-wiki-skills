"""channel-parentsquare's body names only tools the server ships, and none that writes."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

UNIT = Path(__file__).resolve().parents[1]

# An enabled copy's `*.md` is the source with its `{{@brain-…}}` tokens filled
# in (the `unit-manifest` contract's Tokens section); these tests read the
# source as that copy does.
_TOKENS = {"{{@brain-plugin}}": "brain", "{{@brain-cli}}": "llm-wiki-cli", "{{@brain-cli-ops}}": "llm-wiki-ops", "{{@brain-cli-search}}": "llm-wiki-search"}


def _doc(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for token, name in _TOKENS.items():
        text = text.replace(token, name)
    return text.replace("{{@@brain-", "{{@brain-")

# parentsquare-mcp 0.4.0's registered tools that read; every other registered tool adds, edits, invites, links or removes.
READ_TOOLS = {
    "list_schools", "list_school_features", "get_feeds", "get_post", "list_conversations", "get_conversation",
    "get_calendar_events", "list_photos", "list_files", "download_file", "get_directory", "get_staff_member",
    "list_groups", "get_group_feed", "get_student_dashboard", "list_signups", "list_notices", "list_polls",
    "list_links", "list_payments", "list_volunteer_hours", "list_forms", "list_students", "list_parents",
    "list_grades", "get_student", "list_classes", "get_class", "list_staff", "list_class_students",
}
USED = {"list_schools", "get_feeds", "get_post", "list_notices"}


def test_the_body_names_the_read_tools_it_uses_by_their_full_name():
    text = _doc(UNIT / "SKILL.md")
    named = set(re.findall(r"mcp__parentsquare__(\w+)", text))
    assert USED <= named, USED - named
    assert named <= READ_TOOLS, named - READ_TOOLS


def test_the_body_reports_degraded_when_the_server_is_absent():
    text = _doc(UNIT / "SKILL.md")
    assert "DEGRADED" in text and "status=failed" in text


def test_the_manifest_binds_the_login_by_variable():
    import json

    manifest = json.loads((UNIT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["requires"]["credentials"] == {"env": {"PS_PASSWORD": "required", "PS_USERNAME": "required"}}
    assert [b["bin"] for b in manifest["requires"]["bins"]] == ["parentsquare-mcp"]
    assert re.fullmatch(r">=\d+\.\d+\.\d+", manifest["requires"]["ops"]), manifest["requires"].get("ops")  # the unit's own ops floor


def test_the_venue_list_of_read_tools_is_the_whole_list():
    text = _doc(UNIT / "SKILL.md")
    block = text.split("The server's read tools, 0.4.0:", 1)[1].split("This unit uses", 1)[0]
    assert set(re.findall(r"`(\w+)`", block)) == READ_TOOLS


KEYS = UNIT / "scripts" / "keys.py"
HOSTILE = "Picture day $(touch PWNED) `touch PWNED` \"quoted\" 'single' ; touch PWNED"


def _keys(tmp_path, arm, doc, *extra):
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(doc), encoding="utf-8")
    return subprocess.run([sys.executable, str(KEYS), arm, str(draft), *extra], cwd=tmp_path, capture_output=True, text=True, check=False)


def test_a_notice_key_is_the_hash_of_its_content_and_venue_text_runs_nothing(tmp_path):
    doc = {"school_id": 12, "title": HOSTILE, "date": "Oct 3, 2026"}
    done = _keys(tmp_path, "notice", doc)
    want = hashlib.sha1(f"{HOSTILE}|Oct 3, 2026".encode()).hexdigest()[:12]
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == f"ps-notice-12-{want}"
    assert not (tmp_path / "PWNED").exists()
    assert _keys(tmp_path, "notice", doc).stdout == done.stdout
    assert _keys(tmp_path, "notice", {**doc, "date": "Oct 4, 2026"}).stdout != done.stdout


def test_a_stamp_is_thirteen_digits_and_a_hostile_date_runs_nothing(tmp_path):
    ok = _keys(tmp_path, "stamp", {"date": "Oct 3, 2026"}, "--now", "1")
    assert ok.stdout.strip() == "1791028800000", ok.stdout + ok.stderr  # 2026-10-03T12:00:00Z
    bad = _keys(tmp_path, "stamp", {"date": "$(touch PWNED) `touch PWNED`"}, "--now", "1791000000000")
    assert bad.returncode == 0 and bad.stdout.strip() == "1791000000000", bad.stdout + bad.stderr
    assert not (tmp_path / "PWNED").exists()


NOW = "1791028800000"  # 2026-10-03T12:00:00Z, the pull's clock in these cases

# Every shape a served `date` takes: `data-timestamp` verbatim (ISO-8601 or epoch), else the element's own text.
SHAPES = [
    ("iso with an offset", "2026-02-11T14:20:45-08:00", "1770848445000"),
    ("iso with Z", "2026-02-11T22:20:45Z", "1770848445000"),
    ("iso with fractional seconds", "2026-02-11T22:20:45.250Z", "1770848445250"),
    ("iso with no zone, read as UTC", "2026-02-11T22:20:45", "1770848445000"),
    ("epoch seconds", "1770848445", "1770848445000"),
    ("epoch milliseconds", "1770848445492", "1770848445492"),
    ("a date only, noon UTC", "2026-02-11", "1770811200000"),
    ("a month name with a year", "Feb 11, 2026", "1770811200000"),
    ("a month name with no year, the latest one not after the pull", "Feb 11", "1770811200000"),
]


@pytest.mark.parametrize(("shape", "served", "want"), SHAPES, ids=[s[0] for s in SHAPES])
def test_every_served_date_shape_stamps_from_the_post_not_the_clock(tmp_path, shape, served, want):
    done = _keys(tmp_path, "stamp", {"date": served}, "--now", NOW)
    assert done.returncode == 0 and done.stdout.strip() == want, done.stdout + done.stderr


def test_a_repull_of_the_same_post_stamps_the_same(tmp_path):
    doc = {"date": "2026-02-11T14:20:45-08:00"}
    first = _keys(tmp_path, "stamp", doc, "--now", NOW).stdout
    again = _keys(tmp_path, "stamp", doc, "--now", "1791100000000").stdout
    assert first == again


def test_a_date_no_shape_matches_reuses_the_stamp_of_the_posts_own_file(tmp_path):
    items = tmp_path / "day" / "items"
    items.mkdir(parents=True)
    (items / "1791000000000--ps-post-77.json").write_text("{}", encoding="utf-8")
    draft = {"date": "2 hours ago", "id": "ps-post-77"}
    again = _keys(tmp_path, "stamp", draft, "--now", NOW, "--day-dir", str(tmp_path / "day"))
    assert again.stdout.strip() == "1791000000000", again.stdout + again.stderr
    other = _keys(tmp_path, "stamp", {**draft, "id": "ps-post-78"}, "--now", NOW, "--day-dir", str(tmp_path / "day"))
    assert other.stdout.strip() == NOW


def test_a_stamped_file_is_not_the_one_a_parseable_date_reuses(tmp_path):
    items = tmp_path / "day" / "items"
    items.mkdir(parents=True)
    (items / "1791000000000--ps-post-77.json").write_text("{}", encoding="utf-8")
    done = _keys(tmp_path, "stamp", {"date": "2026-02-11T22:20:45Z", "id": "ps-post-77"}, "--now", NOW, "--day-dir", str(tmp_path / "day"))
    assert done.stdout.strip() == "1770848445000"


def test_a_bad_draft_is_refused_with_a_reason(tmp_path):
    done = _keys(tmp_path, "notice", {"school_id": "12; touch PWNED", "title": "t", "date": "d"})
    assert done.returncode == 2 and "school_id" in done.stderr
    assert not (tmp_path / "PWNED").exists()


SERVED = ("title", "date", "subject", "body", "author", "school", "comment")


def test_no_shell_block_in_the_body_carries_served_text():
    """A fenced command or an inline one names a served field as an argument only if the session would type venue text into a shell."""
    text = _doc(UNIT / "SKILL.md")
    shell = re.findall(r"^```sh\n(.*?)^```", text, re.M | re.S) + re.findall(r"`([^`\n]*(?:llm-wiki-ops|sha1sum|date -u)[^`\n]*)`", text)
    assert shell, "the scan found no command at all"
    leaks = [line for block in shell for line in block.splitlines() if re.search(rf"<({'|'.join(SERVED)})>", line)]
    assert not leaks, leaks


# ------------------------------------------------------------------ the ledger script

LEDGER = UNIT / "scripts" / "ledger.py"
DAY = "_raw/ps/2026-10-03"
DEST = "research/channels/ps"


def _stub(tmp_path, *, page_exists=False, capture_dir=DAY, pages=(), held=None):
    """A recording front door: `tickets open` answers the process ticket; `page ls` answers `pages`, `page read` the
    frontmatter `held` (none: a page with no `resource`); `page create` refuses where the day's page exists."""
    stub = tmp_path / "ops_stub.py"
    ticket = {"ticket": "t1", "stage": "process", "slug": "ps", "capture_dir": capture_dir, "dest": DEST}
    stub.write_text(
        "import json, os, sys\n"
        "argv = sys.argv[1:]; verb = [a for a in argv if not a.startswith('--')]\n"
        "open(os.environ['FAKE_CALLS'], 'a').write(json.dumps({'argv': argv, 'stdin': sys.stdin.read() if '--stdin' in argv else None}) + '\\n')\n"
        f"if verb[:2] == ['tickets', 'open']: print(json.dumps({{'ticket': {ticket!r}}})); sys.exit(0)\n"
        f"if verb[:2] == ['page', 'ls']: print(json.dumps({{'pages': json.loads({json.dumps(list(pages))!r})}})); sys.exit(0)\n"
        f"if verb[:2] == ['page', 'read']: print(json.dumps({{'frontmatter': json.loads({json.dumps(held or {})!r})}})); sys.exit(0)\n"
        f"if verb[:2] == ['page', 'create'] and {page_exists!r}: print('exists', file=sys.stderr); sys.exit(2)\n"
        "print('{}')\n"
    )
    return f"{sys.executable} {stub}"


def _item(tmp_path, name, **doc):
    path = tmp_path / DAY / "items" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"v": 1, "attachments": [], "body": "x", **doc}), encoding="utf-8")


def _ledger(tmp_path, *args, page_exists=False, pages=(), held=None):
    stub = _stub(tmp_path, page_exists=page_exists, pages=pages, held=held)
    env = {**__import__("os").environ, "LLM_WIKI_OPS": stub, "FAKE_CALLS": str(tmp_path / "calls.log")}
    done = subprocess.run([sys.executable, str(LEDGER), DAY, "--ticket", "t1", *args], cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
    calls = [json.loads(line) for line in (tmp_path / "calls.log").read_text().splitlines()] if (tmp_path / "calls.log").exists() else []
    return done, calls


def _day(tmp_path):
    _item(tmp_path, "1791028800000--ps-post-2.json", id="parentsquare:ps-post-2", school="Lincoln", subject="Spirit week!")
    _item(tmp_path, "1791000000000--ps-post-1.json", id="parentsquare:ps-post-1", school="Lincoln", subject="Early dismissal Friday")
    _item(tmp_path, "1791030000000--ps-notice-4-0a1b2c3d4e5f.json", id="parentsquare:ps-notice-4-0a1b2c3d4e5f", school="Lincoln",
          subject="Click <b>here</b> — http://evil.example *now* | `x` [[Link]]")


def test_the_ledger_is_built_from_the_items_with_rows_only_where_judged(tmp_path):
    _day(tmp_path)
    (tmp_path / DAY / "lines.json").write_text(json.dumps([
        {"id": "parentsquare:ps-post-2", "junk": "spirit-week chatter"},
        {"id": "parentsquare:ps-notice-4-0a1b2c3d4e5f", "line": "Lincoln: picture day forms due 10/10"},
    ]))
    done, calls = _ledger(tmp_path)
    assert done.returncode == 0, done.stderr
    (create,) = [c for c in calls if c["argv"][:2] == ["page", "create"]]
    assert {"title=2026-10-03", f"dest={DEST}", "type=ledger", "channel=ps", "date=2026-10-03", "items=2", "extracted=true", "status=",
            "resource=parentsquare:ledger", "resource_id=parentsquare:day:2026-10-03"} <= set(create["argv"])
    (lookup,) = [c for c in calls if c["argv"][1:3] == ["page", "ls"]]
    assert lookup["argv"] == ["--json", "page", "ls", "resource=parentsquare:ledger", "resource_id=parentsquare:day:2026-10-03"]
    assert create["stdin"] == (
        "- Lincoln: Early dismissal Friday — parentsquare:ps-post-1\n"
        "- Lincoln: picture day forms due 10/10 — parentsquare:ps-notice-4-0a1b2c3d4e5f\n"
        "\ndiscarded: 1 (junk rules)\n"
    )
    (update,) = [c["argv"] for c in calls if c["argv"][1:3] == ["tickets", "update"]]
    assert "status=ok" in update and "written_from=written.json" in update
    assert json.loads((tmp_path / DAY / "written.json").read_text()) == [f"{DEST}/2026-10-03.md"]
    assert json.loads(done.stdout)["from_subject"] == 1


def test_a_subject_with_no_row_is_neutralized_before_it_is_a_bullet(tmp_path):
    _day(tmp_path)
    _, calls = _ledger(tmp_path)
    (create,) = [c for c in calls if c["argv"][:2] == ["page", "create"]]
    hostile = create["stdin"].splitlines()[2]
    assert hostile.count(" — ") == 1 and hostile.endswith(" — parentsquare:ps-notice-4-0a1b2c3d4e5f")
    for live in ("<b>", "http://", "*now*", "|", "`", "[["):
        assert live not in hostile, live
    assert "items=3" in create["argv"]


def test_a_second_pull_of_the_day_edits_the_page_whole(tmp_path):
    _day(tmp_path)
    done, calls = _ledger(tmp_path, page_exists=True)
    assert done.returncode == 0, done.stderr
    (edit,) = [c for c in calls if c["argv"][:2] == ["page", "edit"]]
    assert edit["argv"][2] == f"{DEST}/2026-10-03.md" and "status=" not in edit["argv"] and edit["stdin"].startswith("- Lincoln")
    assert {"resource=parentsquare:ledger", "resource_id=parentsquare:day:2026-10-03"} <= set(edit["argv"])


def test_a_ledger_a_person_renamed_is_edited_by_its_id(tmp_path):
    _day(tmp_path)
    renamed = f"{DEST}/School week.md"
    done, calls = _ledger(tmp_path, pages=[{"path": renamed, "document_id": "doc-1", "job": "ps"}])
    assert done.returncode == 0, done.stderr
    (edit,) = [c for c in calls if c["argv"][:2] == ["page", "edit"]]
    assert edit["argv"][2] == "id=doc-1" and not [c for c in calls if c["argv"][:2] == ["page", "create"]]
    assert json.loads((tmp_path / DAY / "written.json").read_text()) == [renamed]


def test_two_ledgers_for_one_day_fail_naming_both(tmp_path):
    _day(tmp_path)
    rows = [{"path": f"{DEST}/{n}.md", "document_id": n, "job": "ps"} for n in ("A", "B")]
    done, calls = _ledger(tmp_path, pages=rows)
    (update,) = [c for c in calls if c["argv"][1:3] == ["tickets", "update"]]
    assert "status=failed" in update["argv"] and not [c for c in calls if c["argv"][0] == "page"]
    assert any(f"{DEST}/A.md" in a and f"{DEST}/B.md" in a for a in update["argv"])


def test_a_ledger_a_person_holds_is_left_alone(tmp_path):
    _day(tmp_path)
    done, calls = _ledger(tmp_path, pages=[{"path": f"{DEST}/x.md", "document_id": "doc-1", "job": "ps", "draft": True}])
    (update,) = [c for c in calls if c["argv"][1:3] == ["tickets", "update"]]
    assert done.returncode == 0 and "status=ok" in update["argv"] and not [c for c in calls if c["argv"][0] == "page"]


def test_a_page_at_the_days_path_with_another_resource_is_never_written_over(tmp_path):
    _day(tmp_path)
    done, calls = _ledger(tmp_path, page_exists=True, held={"resource": "https://example.com/x"})
    (update,) = [c for c in calls if c["argv"][1:3] == ["tickets", "update"]]
    assert "status=failed" in update["argv"] and not [c for c in calls if c["argv"][:2] == ["page", "edit"]]


def test_a_day_with_no_items_is_ok_and_writes_no_page(tmp_path):
    (tmp_path / DAY).mkdir(parents=True)
    done, calls = _ledger(tmp_path)
    assert done.returncode == 0 and not [c for c in calls if c["argv"][0] == "page"]
    assert "status=ok" in [c for c in calls if c["argv"][1:3] == ["tickets", "update"]][0]["argv"]


def test_rows_that_do_not_parse_fail_the_step_and_write_no_page(tmp_path):
    _day(tmp_path)
    (tmp_path / DAY / "lines.json").write_text("[{not json")
    done, calls = _ledger(tmp_path)
    assert done.returncode == 1 and not [c for c in calls if c["argv"][0] == "page"]
    assert "status=failed" in [c for c in calls if c["argv"][1:3] == ["tickets", "update"]][0]["argv"]


def test_the_process_step_runs_the_ledger_script_and_writes_no_ledger_by_hand():
    text = _doc(UNIT / "SKILL.md")
    assert "run ops/skills/channel-parentsquare/scripts/ledger.py <capture_dir> --ticket <id>" in text
    assert "ledger.md" not in text and "page create" not in text


def test_an_id_no_item_carries_is_counted_and_named(tmp_path):
    _day(tmp_path)
    (tmp_path / DAY / "lines.json").write_text(json.dumps([{"id": "parentsquare:ps-post-404", "line": "x"},
                                                          {"id": "parentsquare:ps-post-2", "junk": "spirit week"}]))
    done, calls = _ledger(tmp_path)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["unmatched"] == ["parentsquare:ps-post-404"]
    update = [c["argv"] for c in calls if c["argv"][1:3] == ["tickets", "update"]][0]
    assert "status=partial" in update and any("ps-post-404" in a for a in update)


def test_a_ticket_capture_dir_that_is_no_day_is_refused(tmp_path):
    env = {**__import__("os").environ, "LLM_WIKI_OPS": _stub(tmp_path, capture_dir="_raw/ps/latest"), "FAKE_CALLS": str(tmp_path / "calls.log")}
    done = subprocess.run([sys.executable, str(LEDGER), DAY, "--ticket", "t1"], cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 2 and "not a day directory" in done.stderr
