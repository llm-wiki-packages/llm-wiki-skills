"""The portal job's decisions and the file reuse: pure helpers, no browser and no CLI."""
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


harvest = load("harvest")
bb = load("bb")
NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def row(**kw):
    return {"available": "Yes", "member_available": "Yes", "duration": {"type": "Continuous"}, **kw}


def test_portal_target_names_no_course():
    assert harvest.is_portal("https://learn.example.edu/ultra/course")
    assert harvest.is_portal("https://learn.example.edu/ultra/courses/")
    assert not harvest.is_portal("https://learn.example.edu/ultra/courses/_123_1/outline")
    assert not harvest.is_portal("https://learn.example.edu#_123_1")


def test_a_course_with_no_dates_is_active():
    assert harvest.course_status(row(), NOW) == "active"


def test_a_course_is_finished_only_after_the_grace_period():
    just_ended = row(duration={"type": "DateRange", "start": "2026-08-01T00:00:00Z", "end": "2026-11-01T00:00:00Z"})
    long_ended = row(duration={"type": "DateRange", "start": "2026-01-01T00:00:00Z", "end": "2026-03-01T00:00:00Z"})
    assert harvest.course_status(just_ended, NOW) == "active"
    assert harvest.course_status(long_ended, NOW) == "finished"


def test_a_future_course_waits():
    assert harvest.course_status(row(duration={"type": "DateRange", "start": "2027-01-05T00:00:00Z"}), NOW) == "upcoming"


def test_a_term_course_reads_the_terms_dates():
    r = row(available="Term", duration={"type": "Term"}, term_duration={"type": "DateRange", "end": "2026-01-01T00:00:00Z"})
    assert harvest.course_status(r, NOW) == "finished"


def test_closed_courses_and_organizations_are_not_courses_to_pull():
    assert harvest.course_status(row(member_available="No"), NOW) == "closed"
    assert harvest.course_status(row(available="Disabled"), NOW) == "closed"
    assert harvest.course_status(row(organization=True), NOW) == "organization"


def test_a_finished_course_is_pulled_until_a_clean_pull_or_its_tries_run_out():
    assert harvest.should_pull("active", {"final_done": True})
    assert harvest.should_pull("finished", {})
    assert not harvest.should_pull("finished", {"final_done": True})
    assert not harvest.should_pull("finished", {"final_tries": harvest.FINAL_TRIES})
    assert not harvest.should_pull("upcoming", {})
    assert not harvest.should_pull("closed", {})


def test_course_folders_are_one_component_and_unique():
    taken = set()
    assert harvest.course_folder({"courseId": "PSY/2301: Intro"}, taken) == "PSY-2301- Intro"
    assert harvest.course_folder({"courseId": "psy/2301: intro"}, taken) == "psy-2301- intro-2"


def test_a_file_is_reused_only_when_its_owner_is_unchanged(tmp_path):
    dest = tmp_path / "files" / "Unit 1"
    dest.mkdir(parents=True)
    (dest / "a.pdf").write_bytes(b"x")
    r = {"path": "files/Unit 1/a.pdf"}
    assert bb.reusable(r, "_1_1", tmp_path, dest, {"_1_1": "t1"}, {"_1_1": "t1"}) == dest / "a.pdf"
    assert bb.reusable(r, "_1_1", tmp_path, dest, {"_1_1": "t1"}, {"_1_1": "t2"}) is None


def test_a_file_owned_by_a_post_stands_on_its_path(tmp_path):
    dest = tmp_path / "files"
    dest.mkdir()
    (dest / "a.pdf").write_bytes(b"x")
    assert bb.reusable({"path": "files/a.pdf"}, "post-9", tmp_path, dest, {}, {"_1_1": "t1"}) == dest / "a.pdf"


def test_a_missing_or_moved_file_is_fetched_again(tmp_path):
    dest = tmp_path / "files"
    dest.mkdir()
    assert bb.reusable({"path": "files/gone.pdf"}, "x", tmp_path, dest, {}, {}) is None
    assert bb.reusable(None, "x", tmp_path, dest, {}, {}) is None
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "a.pdf").write_bytes(b"x")
    assert bb.reusable({"path": "other/a.pdf"}, "x", tmp_path, dest, {}, {}) is None


def test_the_jails_proxy_reaches_playwright_with_its_credentials_apart():
    env = {"HTTPS_PROXY": "http://nono:tok%2Fen@127.0.0.1:49419", "NO_PROXY": "localhost,127.0.0.1"}
    assert bb.proxy_from_env(env) == {"server": "http://127.0.0.1:49419", "username": "nono", "password": "tok/en", "bypass": "localhost,127.0.0.1"}


def test_outside_a_jail_there_is_no_proxy():
    assert bb.proxy_from_env({}) is None


def test_a_course_folder_is_its_short_code():
    taken = set()
    assert harvest.course_folder({"courseId": "PSY2301-21.01.01-2B27-S3"}, taken) == "PSY2301"
    assert harvest.course_folder({"courseId": "CareerServicesResourceCenter"}, taken) == "CareerServicesResourceCenter"
    assert harvest.course_folder({"courseId": "PSY2301-22.01.01-2B28-S1"}, taken) == "PSY2301-2"


def test_subject_tags_come_from_the_code_prefix():
    mapping = harvest.subject_map("PSY=psychology, lss=study-skills,bad")
    assert mapping == {"PSY": "psychology", "LSS": "study-skills"}
    assert harvest.subject_tags({"courseId": "PSY2301-21.01.01"}, mapping) == ["psychology"]
    assert harvest.subject_tags({"courseId": "LSS1301-24"}, mapping) == ["study-skills"]
    assert harvest.subject_tags({"courseId": "ENG1301-1"}, mapping) == []
    assert harvest.subject_tags({"courseId": "CareerServicesResourceCenter"}, mapping) == []


def test_a_course_quiet_for_six_weeks_rests_and_is_checked_weekly():
    assert not harvest.quiet({}, NOW)
    assert not harvest.quiet({"last_change": "2026-10-01T00:00:00Z"}, NOW)
    assert harvest.quiet({"last_change": "2026-09-01T00:00:00Z"}, NOW)
    assert harvest.should_pull("dormant", {"last_pull": "2026-10-30T00:00:00Z"}, NOW)
    assert not harvest.should_pull("dormant", {"last_pull": "2026-11-05T00:00:00Z"}, NOW)
    assert harvest.should_pull("dormant", {}, NOW)
