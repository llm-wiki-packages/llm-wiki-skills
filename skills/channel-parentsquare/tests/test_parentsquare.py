"""channel-parentsquare's body names only tools the server ships, and none that writes."""

import re
from pathlib import Path

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


def test_a_notice_is_keyed_by_its_content_never_its_place_in_the_list():
    """0.4.0's `Notice` has no id; an index shifts when one arrives, and a same-day re-pull would file the notice twice."""
    text = (UNIT / "SKILL.md").read_text(encoding="utf-8")
    assert "ps-notice-<school_id>-<n>" not in text
    assert "ps-notice-<school_id>-<12 hex of sha1(title|date)>" in text


def test_the_notices_read_is_bounded_by_the_lookback_like_the_posts():
    text = " ".join((UNIT / "SKILL.md").read_text(encoding="utf-8").split())
    assert re.search(r"`list_notices` once, keeping every notice dated within `options\.lookback_days` days", text)


def test_the_venue_list_of_read_tools_is_the_whole_list():
    text = (UNIT / "SKILL.md").read_text(encoding="utf-8")
    block = text.split("The server's read tools, 0.4.0:", 1)[1].split("This unit uses", 1)[0]
    assert set(re.findall(r"`(\w+)`", block)) == READ_TOOLS
