import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("process", SCRIPTS / "process.py")
process = importlib.util.module_from_spec(spec)
spec.loader.exec_module(process)


def calls(monkeypatch):
    seen = []

    def fake(*args, stdin=None):
        seen.append(args)
        return 0, {"path": "sources/c/x.md"}

    monkeypatch.setattr(process, "ops_json", fake)
    return seen


def test_a_root_names_its_keys_but_not_its_settings_in_ops_lends(monkeypatch):
    seen = calls(monkeypatch)
    keys = {"ops.root": "true", "current": "true", "course": "PSY 2301", "ops.extract": "light"}
    assert process.create_root("sources/c", {"title": "PSY", "abstract": "a", "body": "b"}, keys) is None
    create = seen[0]
    assert create[:2] == ("page", "create") and "ops.lends=current,course" in create
    assert "--inherit" not in create


def test_a_new_page_copies_its_roots_keys_and_a_re_pull_does_not(monkeypatch, tmp_path):
    seen = calls(monkeypatch)
    page = {"title": "Lecture", "type": "document", "body": "b"}
    process.write_page(page, "bb:1", "sources/c", None)
    process.write_page(page, "bb:1", "sources/c", "sources/c/Lecture.md")
    assert "--inherit" in seen[0] and seen[0][:2] == ("page", "create")
    assert seen[-1][:2] == ("page", "edit") and "--inherit" not in seen[-1]


def test_a_portal_courses_subject_tags_are_lent_from_its_root(monkeypatch):
    seen = calls(monkeypatch)
    keys = {"current": "true", "course": "PSY 2301", "tags": "psychology"}
    assert process.create_root("sources/courses/school/PSY2301", {"title": "PSY", "abstract": "a", "body": "b"}, keys) is None
    create = seen[0]
    assert "tags=psychology" in create and "ops.lends=current,course,tags" in create
    assert "dest=sources/courses/school/PSY2301" in create


def test_a_new_root_fills_the_pages_already_below_it(monkeypatch):
    # The pass lands a course's captures in any order: most of its pages can be written before its root.
    seen = calls(monkeypatch)
    assert process.create_root("sources/c", {"title": "PSY", "abstract": "a", "body": "b"}, {"current": "true"}) is None
    assert seen[-1] == ("page", "root", "apply", "sources/c")


def test_a_root_whose_fill_is_refused_says_so(monkeypatch):
    def fake(*args, stdin=None):
        return (2, {"error": "refused"}) if args[:3] == ("page", "root", "apply") else (0, {"path": "sources/c/README.md"})

    monkeypatch.setattr(process, "ops_json", fake)
    assert "refused" in process.create_root("sources/c", {"title": "PSY", "abstract": "a", "body": "b"}, {"current": "true"})


def test_written_from_names_the_file_inside_the_capture_not_a_wiki_path():
    # `tickets update` reads `written_from=` against the ticket's capture directory: a wiki-relative path doubles.
    import inspect

    source = inspect.getsource(process)
    assert "/" not in process.WRITTEN
    assert source.count("written_from=WRITTEN") == 3 and "capture / WRITTEN).as_posix()" not in source
