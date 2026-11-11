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
    keys = {"ops.root": "true", "current": "true", "course": "PSY 2301", "ops.mine": "light"}
    assert process.create_root("sources/c", {"title": "PSY", "abstract": "a", "body": "b"}, keys) is None
    create = seen[0]
    assert create[:2] == ("page", "create") and "ops.lends=current,course" in create
    assert "--inherit" not in create


def test_no_write_asks_for_its_roots_keys(monkeypatch, tmp_path):
    # The plugin applies a root's lent keys on every write (llm-wiki-plugins#4434): `--inherit` is gone.
    seen = calls(monkeypatch)
    page = {"title": "Lecture", "type": "document", "body": "b"}
    process.write_page(page, "bb:1", "sources/c", None)
    process.write_page(page, "bb:1", "sources/c", "sources/c/Lecture.md")
    assert seen[0][:2] == ("page", "create") and seen[-1][:2] == ("page", "edit")
    assert not any("--inherit" in call for call in seen)


def test_a_portal_courses_subject_tags_are_lent_from_its_root(monkeypatch):
    seen = calls(monkeypatch)
    keys = {"current": "true", "course": "PSY 2301", "tags": "psychology"}
    assert process.create_root("sources/courses/school/PSY2301", {"title": "PSY", "abstract": "a", "body": "b"}, keys) is None
    create = seen[0]
    assert "tags=psychology" in create and "ops.lends=current,course,tags" in create
    assert "dest=sources/courses/school/PSY2301" in create


def test_a_new_root_is_made_and_titled_and_nothing_else(monkeypatch):
    # The pages already below a new root get its keys in the root's own write (the plugin's fan-out): no `page root`.
    seen = calls(monkeypatch)
    assert process.create_root("sources/c", {"title": "PSY", "abstract": "a", "body": "b"}, {"current": "true"}) is None
    assert [call[:2] for call in seen] == [("page", "create"), ("page", "edit")]
    assert seen[-1] == ("page", "edit", "sources/c/x.md", "title=PSY")


def test_a_root_whose_title_edit_is_refused_says_so(monkeypatch):
    def fake(*args, stdin=None):
        return (2, {"error": "refused"}) if args[:2] == ("page", "edit") else (0, {"path": "sources/c/README.md"})

    monkeypatch.setattr(process, "ops_json", fake)
    assert "refused" in process.create_root("sources/c", {"title": "PSY", "abstract": "a", "body": "b"}, {"current": "true"})


def test_written_from_names_the_file_inside_the_capture_not_a_wiki_path():
    # `tickets update` reads `written_from=` against the ticket's capture directory: a wiki-relative path doubles.
    import inspect

    source = inspect.getsource(process)
    assert "/" not in process.WRITTEN
    assert source.count("written_from=WRITTEN") == 3 and "capture / WRITTEN).as_posix()" not in source
