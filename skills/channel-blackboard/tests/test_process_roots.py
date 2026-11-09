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
