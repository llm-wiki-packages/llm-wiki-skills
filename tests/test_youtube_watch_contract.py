"""The files an enrich unit leaves and the reader that folds them into the page
are three scripts in three units that install on their own, so nothing but
this file holds them to one contract: the names agree, and what each writer
leaves is what `channel-youtube`'s reader accepts."""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from harness import ROOT


def _load(unit: str, script: str):
    here = str(ROOT / "skills" / unit / "scripts")
    sys.path.insert(0, here)
    try:
        spec = importlib.util.spec_from_file_location(f"_contract_{unit}_{script}", ROOT / "skills" / unit / "scripts" / f"{script}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(here)


@pytest.fixture(scope="module")
def reader():
    return _load("channel-youtube", "watch_notes")


@pytest.fixture(scope="module")
def gemini():
    return _load("channel-youtube-watch-gemini", "watch_gemini")


@pytest.fixture(scope="module")
def local():
    return _load("channel-youtube-watch-local", "watch_frames")


def test_the_three_scripts_agree_on_the_names_the_reader_looks_for(reader, gemini, local):
    for writer in (gemini, local):
        assert (writer.NOTES_DIR, writer.NOTES_NAME, writer.META_NAME) == (reader.NOTES_DIR, reader.NOTES_NAME, reader.META_NAME)
        assert writer.MAX_NOTES_CHARS == reader.MAX_CHARS


def test_what_the_gemini_unit_writes_is_what_the_page_reader_accepts(reader, gemini, tmp_path):
    gemini.write_notes(tmp_path, "- [00:10] A point.", model="gemini-x", tokens=7)
    assert reader.load(tmp_path) == {"engine": "gemini", "model": "gemini-x", "text": "- [00:10] A point."}
    meta = json.loads((tmp_path / "enrich" / "watch.json").read_text())
    assert meta["engine"] in reader.ENGINES and meta["unit"] == gemini.UNIT


def test_what_the_local_unit_seals_is_what_the_page_reader_accepts(reader, local, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cap" / "enrich").mkdir(parents=True)
    (tmp_path / "cap" / "enrich" / "watch.md").write_text("- [00:10] A point.\n")
    assert local.main(["seal", "--capture-dir", "cap", "--model", "m-1"]) == 0
    assert reader.load(tmp_path / "cap") == {"engine": "local", "model": "m-1", "text": "- [00:10] A point."}
    assert json.loads((tmp_path / "cap" / "enrich" / "watch.json").read_text())["unit"] == local.UNIT


def test_both_writers_name_the_unit_that_carries_them(gemini, local):
    assert (gemini.UNIT, local.UNIT) == ("channel-youtube-watch-gemini", "channel-youtube-watch-local")
    assert (ROOT / "skills" / gemini.UNIT).is_dir() and (ROOT / "skills" / local.UNIT).is_dir()
