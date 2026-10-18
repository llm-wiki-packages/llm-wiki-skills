"""channel-parentsquare's body names only tools the server ships, and none that writes."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

UNIT = Path(__file__).resolve().parents[1]

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
    text = (UNIT / "SKILL.md").read_text(encoding="utf-8")
    named = set(re.findall(r"mcp__parentsquare__(\w+)", text))
    assert USED <= named, USED - named
    assert named <= READ_TOOLS, named - READ_TOOLS


def test_the_body_reports_degraded_when_the_server_is_absent():
    text = (UNIT / "SKILL.md").read_text(encoding="utf-8")
    assert "DEGRADED" in text and "status=failed" in text


def test_the_manifest_binds_the_login_by_variable():
    import json

    manifest = json.loads((UNIT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["requires"]["credentials"] == {"env": {"PS_PASSWORD": "required", "PS_USERNAME": "required"}}
    assert [b["bin"] for b in manifest["requires"]["bins"]] == ["parentsquare-mcp"]
    assert "ops" not in manifest["requires"]


def test_the_venue_list_of_read_tools_is_the_whole_list():
    text = (UNIT / "SKILL.md").read_text(encoding="utf-8")
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
    text = (UNIT / "SKILL.md").read_text(encoding="utf-8")
    shell = re.findall(r"^```sh\n(.*?)^```", text, re.M | re.S) + re.findall(r"`([^`\n]*(?:llm-wiki-ops|sha1sum|date -u)[^`\n]*)`", text)
    assert shell, "the scan found no command at all"
    leaks = [line for block in shell for line in block.splitlines() if re.search(rf"<({'|'.join(SERVED)})>", line)]
    assert not leaks, leaks
