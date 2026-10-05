"""The enrich unit's notes, as `youtube_note.py`'s process arm folds them into
the page: what `watch_notes.load` accepts, where the block sits, and that
nothing in a model's notes can forge page structure."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

UNIT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = UNIT_DIR / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
META = json.loads((FIXTURES / "metadata.json").read_text(encoding="utf-8"))
ITEM = META["webpage_url"]
CAP = "_raw/yt-job/leaf"
TRANSCRIPT = "#### [00:00] What overload is\n\nWords."
NOTES = "**Overview** A lesson.\n- [00:10] Overload is defined.\n- [01:30] Progression is covered."


def _load(name):
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.fixture(scope="module")
def note():
    return _load("youtube_note")


@pytest.fixture(scope="module")
def notes():
    return _load("watch_notes")


def put(cap, text=NOTES, **meta):
    enrich = cap / "enrich"
    enrich.mkdir(parents=True, exist_ok=True)
    if text is not None:
        (enrich / "watch.md").write_text(text, encoding="utf-8")
    doc = {"v": 1, "engine": "gemini", "unit": "an-enrich-unit", "model": "gemini-x", **meta}
    (enrich / "watch.json").write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return enrich


# ------------------------------------------------------------------------ load


def test_a_valid_pair_loads_with_what_the_page_needs(notes, tmp_path):
    put(tmp_path)
    assert notes.load(tmp_path) == {"engine": "gemini", "model": "gemini-x", "text": NOTES}


def test_the_local_engine_loads_with_no_model(notes, tmp_path):
    put(tmp_path, engine="local", model=None)
    assert notes.load(tmp_path) == {"engine": "local", "model": None, "text": NOTES}


@pytest.mark.parametrize("breakage", [
    lambda e: (e / "watch.md").unlink(),
    lambda e: (e / "watch.json").unlink(),
    lambda e: (e / "watch.json").write_text("{not json"),
    lambda e: (e / "watch.json").write_text("[1, 2]"),
    lambda e: (e / "watch.json").write_text(json.dumps({"v": 2, "engine": "gemini"})),
    lambda e: (e / "watch.json").write_text(json.dumps({"v": 1, "engine": "other"})),
    lambda e: (e / "watch.json").write_text(json.dumps({"v": 1})),
    lambda e: (e / "watch.md").write_text("  \n\n"),
])
def test_anything_short_of_a_whole_pair_is_no_notes(notes, tmp_path, breakage):
    breakage(put(tmp_path))
    assert notes.load(tmp_path) is None


def test_no_enrich_directory_is_no_notes(notes, tmp_path):
    assert notes.load(tmp_path) is None


def test_a_model_that_is_not_a_short_string_is_dropped_or_cut(notes, tmp_path):
    put(tmp_path, model=["gemini"])
    assert notes.load(tmp_path)["model"] is None
    put(tmp_path, model="m" * 500)
    assert len(notes.load(tmp_path)["model"]) == notes.MODEL_MAX


def test_the_notes_are_cut_at_the_ceiling(notes, tmp_path):
    put(tmp_path, text="x" * (notes.MAX_CHARS + 100))
    assert len(notes.load(tmp_path)["text"]) == notes.MAX_CHARS


# ------------------------------------------------------------------------ page


def body_of(note, watch):
    front = note.frontmatter_for(META)
    return note.build_body(META, front, ITEM, TRANSCRIPT, watch=watch)[0]


def test_the_notes_sit_between_the_description_and_the_transcript(note):
    body = body_of(note, {"engine": "gemini", "model": "gemini-x", "text": NOTES})
    heads = re.findall(r"^## .*$", body, re.M)
    assert heads == ["## Description", "## Watch notes", "## Transcript"]
    section = body.split("## Watch notes\n\n", 1)[1].split("\n## ", 1)[0]
    assert section.startswith("*Google's Gemini watched the video (gemini-x). Its timestamps are its own")
    assert "> - [00:10] Overload is defined." in section and "> **Overview** A lesson." in section


def test_the_local_engine_says_what_it_read(note):
    body = body_of(note, {"engine": "local", "model": None, "text": NOTES})
    assert "*A model read sampled frames and the captions. Its timestamps" in body


def test_no_notes_leave_the_page_as_harvest_alone_built_it(note):
    body = body_of(note, None)
    assert "Watch notes" not in body and body == note.build_body(META, note.frontmatter_for(META), ITEM, TRANSCRIPT)[0]


HOSTILE = "\n".join([
    "# A forged heading",
    "```",
    "rm -rf /",
    "---",
    "Setext",
    "======",
    "> nested [!warning] callout",
    "[[Some Page]] and ![[Embed]] and %% hide $$",
    "<script>alert(1)</script> [x](javascript:alert(1))",
    "see https://example.com/a for more",
    "tab\tand\x1b[31m escape and a\u2028line separator",
])


def test_nothing_in_a_models_notes_can_forge_page_structure(note):
    body = body_of(note, {"engine": "gemini", "model": "gemini-x", "text": HOSTILE})
    section = body.split("## Watch notes\n\n", 1)[1].split("\n## Transcript", 1)[0]
    provenance, quoted = section.split("\n\n", 1)
    assert "\n" not in provenance
    assert all(line.startswith(">") for line in quoted.rstrip("\n").split("\n")), quoted
    assert not re.search(r"^---$", body, re.M), "no bare rule can open a frontmatter fence"
    assert re.findall(r"^## ", body, re.M) == ["## "] * 3, "only this unit's own headings"
    # Inside the quote too, so a fence the notes open cannot swallow the notes after it.
    for escaped in ("> \\# A forged heading", "> \\```", "> \\> nested [!warning] callout", "> \\======"):
        assert escaped in quoted, escaped
    for forged in ("<script", "[[Some Page]]", "![[", "%% hide", "$$", "](javascript:"):
        assert forged not in quoted, forged
    assert "<https://example.com/a>" in quoted and "\x1b" not in quoted and "\u2028" not in quoted


def test_a_model_name_cannot_write_a_line_of_its_own(note):
    body = body_of(note, {"engine": "gemini", "model": "x\n## Injected\n[[Page]]", "text": NOTES})
    (provenance,) = [line for line in body.split("\n") if line.startswith("*Google's Gemini")]
    assert "x ## Injected" in provenance and "[[Page]]" not in provenance
    assert re.findall(r"^## .*$", body, re.M) == ["## Description", "## Watch notes", "## Transcript"]


# ------------------------------------------------------------------ the two arms


@pytest.fixture
def wiki(note, tmp_path, monkeypatch):
    """A wiki with one capture. The front door's two calls are the test's: the
    ticket and the page write, whose body is what the page would carry."""
    cap = tmp_path / CAP
    cap.mkdir(parents=True)
    (cap / "metadata.json").write_text(json.dumps(META))
    written = {}
    monkeypatch.setattr(note, "open_ticket", lambda ticket, stage=None: {"slug": "yt-job", "item": ITEM, "process": {}})
    monkeypatch.setattr(note, "write_page", lambda wiki, dest, title, front, body, ops=None: written.update(body=body) or f"{dest}/{title}.md")

    def arm(*flags):
        monkeypatch.setattr(sys, "argv", ["youtube_note.py", str(tmp_path), "--capture-dir", CAP, "--ticket", "abc", *flags])
        return note.main()

    return cap, arm, written


def test_the_process_arm_folds_the_notes_in_and_leaves_enrich_alone(wiki, capsys):
    cap, arm, written = wiki
    put(cap)
    assert arm("--dest", "sources/youtube/yt-job") == 0
    assert json.loads(capsys.readouterr().out)["watch_notes"] is True
    assert "## Watch notes" in written["body"] and "## Watch notes" in (cap / "page.md").read_text()
    assert sorted(p.name for p in (cap / "enrich").iterdir()) == ["watch.json", "watch.md"]


def test_a_process_run_with_no_enrich_reports_no_notes(wiki, capsys):
    _cap, arm, written = wiki
    assert arm("--dest", "sources/youtube/yt-job") == 0
    assert json.loads(capsys.readouterr().out)["watch_notes"] is False and "Watch notes" not in written["body"]


def test_a_fresh_harvest_drops_what_an_enrich_unit_made_of_the_old_bytes(wiki):
    cap, arm, _written = wiki
    put(cap)
    assert arm("--record") == 0
    assert not (cap / "enrich").exists() and (cap / "capture.json").is_file()


def test_a_link_in_the_place_of_the_pair_is_no_notes(notes, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    put(elsewhere)
    cap = tmp_path / "cap"
    cap.mkdir()
    (cap / "enrich").symlink_to(elsewhere / "enrich", target_is_directory=True)
    assert notes.load(cap) is None
    cap2 = tmp_path / "cap2"
    put(cap2)
    (cap2 / "enrich" / "watch.md").unlink()
    (cap2 / "enrich" / "watch.md").symlink_to(elsewhere / "enrich" / "watch.md")
    assert notes.load(cap2) is None


def test_a_fresh_harvest_unlinks_a_symlinked_enrich_and_leaves_its_target(wiki):
    cap, arm, _written = wiki
    target = put(cap.parent / "elsewhere")
    (cap / "enrich").symlink_to(target, target_is_directory=True)
    assert arm("--record") == 0
    assert not (cap / "enrich").exists() and (target / "watch.md").is_file()
