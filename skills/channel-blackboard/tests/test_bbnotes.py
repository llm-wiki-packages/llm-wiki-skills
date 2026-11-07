"""bbnotes on a small harvest, and the two stage scripts run as the runner runs them, with a stand-in front door and browser."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CID = "_42_1"
TARGET = f"https://learn.example.edu/ultra/courses/{CID}/outline"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bb():
    return _load("bbnotes")


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _office(path: Path, member: str, xml: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(member, xml)


def make_harvest(root: Path) -> Path:
    h = root / "harvest"
    _dump(h / "course.json", {"id": CID, "courseId": "PSY2301-21.01", "name": "PSY 2301-21.01.01-2B27-S3, Abnormal Psychology",
                              "availability": {"duration": {"start": "2026-09-30T05:00:00.000Z"}}})
    contents = [
        {"id": "_1_1", "parent": None, "path": "Unit I", "title": "Unit I", "handler": "resource/x-bb-lesson", "modified": "2026-09-17T00:00:00Z"},
        {"id": "_2_1", "parent": "_1_1", "path": "Unit I/Study Guide", "title": "Study Guide", "handler": "resource/x-bb-document",
         "created": "2023-02-19T00:00:00Z", "modified": "2026-09-17T22:31:11Z", "has_body": True},
        {"id": "_3_1", "parent": "_1_1", "path": "Unit I/Scholarly Activity", "title": "Scholarly Activity", "handler": "resource/x-bb-asmt-test-link",
         "modified": "2026-09-17T00:00:00Z", "raw": {"contentHandler": {"gradeColumnId": "_c1_1", "instructions": "<p>Write a <strong>3-page</strong> paper.</p>"}}},
        {"id": "_4_1", "parent": "_1_1", "path": "Unit I/My Library", "title": "My Library", "handler": "resource/x-bb-externallink",
         "url": "https://library.example.edu/", "raw": {"description": "My Library"}},
        {"id": "_5_1", "parent": "_1_1", "path": "Unit I/Welcome/ultraDocumentBody", "title": "ultraDocumentBody", "handler": "resource/x-bb-document",
         "modified": "2026-09-28T00:00:00Z"},
        {"id": "_6_1", "parent": "_1_1", "path": "Unit I/Slides", "title": "Slides", "handler": "resource/x-bb-file", "modified": "2026-09-08T00:00:00Z"},
    ]
    _dump(h / "contents.json", contents)
    (h / "bodies").mkdir()
    (h / "bodies" / "_2_1.html").write_text("<h2>Reading</h2><p>Read chapter 2 by <b>Friday</b>.</p><script>x()</script><p># not a heading [[nor a link]]</p>")
    wrapper = h / "files/Unit I/Welcome/ultraDocumentBody/UNSAFE_HTML_abc.html"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text('<iframe src="/bbcswebdav/x"></iframe>')
    video = wrapper.parent / "Welcome.mp4"
    video.write_bytes(b"\0" * 64)
    (wrapper.parent / "Welcome.transcript.webvtt").write_text(
        "WEBVTT\n\nNOTE llm-wiki transcript\nengine=x\n\n00:00:00.000 --> 00:00:02.000\nWelcome to the course.\n\n"
        "00:00:02.000 --> 00:00:04.000\nWelcome to the course.\n\n00:00:04.000 --> 00:00:06.000\nOffice hours are Thursdays.\n")
    slides = h / "files/Unit I/Slides/Deck.pptx"
    _office(slides, "ppt/slides/slide1.xml",
            '<p:sld xmlns:p="p" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:t>Learning styles</a:t></a:r></a:p></p:sld>')
    doc = h / "files/Unit I/Study Guide/Guide.docx"
    _office(doc, "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Quiz on Unit I is open book.</w:t></w:r></w:p></w:body></w:document>')
    _dump(h / "files.json", [
        {"item": "_5_1", "kind": "embedded", "path": str(wrapper.relative_to(h))},
        {"item": "_5_1", "kind": "nested", "path": str(video.relative_to(h))},
        {"item": "_6_1", "kind": "attachment", "path": str(slides.relative_to(h))},
        {"item": "_2_1", "kind": "nested", "path": str(doc.relative_to(h))},
    ])
    _dump(h / "gradebook-columns.json", [{"id": "_c1_1", "name": "Scholarly Activity", "contentId": "_3_1", "score": {"possible": 100.0},
                                          "grading": {"due": "2026-10-21T04:59:00.000Z"}},
                                         {"id": "_c2_1", "name": "Unit I Discussion Board", "score": {"possible": 100.0},
                                          "grading": {"due": "2026-10-07T04:59:00.000Z"}}])
    _dump(h / "my-grades.json", [{"columnId": "_c1_1", "status": "Graded", "displayGrade": {"score": 98.0}, "feedback": "<p>Upload it directly.</p>"}])
    _dump(h / "announcements.json", [{"id": "_a1_1", "title": "Week 5", "created": "2026-10-24T01:00:00Z", "modified": "2026-10-24T01:00:00Z",
                                      "body": "<p>The library session is <strong>Wednesday</strong>.</p>"}])
    _dump(h / "calendar.json", [{"title": "Unit V Discussion Board", "start": "2026-11-04T05:59:00.000Z", "type": "GradebookColumn"}])
    _dump(h / "discussions.json", [{"id": "_d1_1", "title": "Unit I Discussion Board", "gradebookColumnId": "_c2_1",
                                    "topic": {"id": "_t1_1", "body": "<p>Introduce yourself.</p>"}}])
    _dump(h / "discussions/_d1_1.json", [
        {"id": "_p1_1", "parentId": "_t1_1", "givenName": "Ana", "familyName": "Ruiz", "postDate": "2026-09-30T21:00:00Z", "body": "<p>Hi, I am Ana.</p>"},
        {"id": "_p2_1", "parentId": "_p1_1", "givenName": "Ben", "familyName": "Ode", "postDate": "2026-10-01T10:00:00Z", "body": "<p>Welcome Ana!</p>"},
        {"id": "_p3_1", "parentId": "_t1_1", "givenName": "Cy", "familyName": "Lo", "status": "Draft", "postDate": "2026-10-02T10:00:00Z", "body": "<p>draft</p>"},
    ])
    _dump(h / "external.json", [{"item": "_4_1", "url": "https://youtube.com/embed/xyz", "video": True}])
    return h


@pytest.fixture
def pages(tmp_path, bb):
    bb.set_zone("America/Chicago")
    dirs = bb.split(make_harvest(tmp_path), tmp_path / "items", fetched_at="2026-11-01T00:00:00Z")
    out = {}
    for d in dirs:
        for page in bb.render(d):
            out[page["title"]] = page
    yield out
    bb.set_zone(None)
    bb.ZONE[0] = bb.timezone.utc


def test_split_makes_one_page_per_item_file_video_announcement_board_and_the_course(pages):
    assert sorted(pages) == [
        "PSY 2301 Abnormal Psychology — course overview",
        "PSY 2301 announcement — Week 5",
        "PSY 2301 discussion — Unit I Discussion Board",
        "PSY 2301 — Scholarly Activity",
        "PSY 2301 — Slides",
        "PSY 2301 — Study Guide",
        "PSY 2301 — Study Guide — Guide.docx",
        "PSY 2301 — Welcome — Welcome (video)",
    ]


def test_a_bare_link_and_an_empty_lesson_are_outline_lines_not_pages(pages):
    overview = pages["PSY 2301 Abnormal Psychology — course overview"]["body"]
    assert "- My Library (link) — https://library.example.edu/" in overview
    assert "- Unit I (lesson)" in overview


def test_a_due_date_reads_in_the_job_zone(pages):
    page = pages["PSY 2301 — Scholarly Activity"]["body"]
    assert "- Due: Tue 2026-10-20 11:59 PM CDT" in page
    assert "- My grade: 98 of 100" in page and "Instructor feedback: Upload it directly." in page
    assert "Write a **3-page** paper." in page


def test_venue_markup_is_made_plain_and_scripts_drop(pages):
    body = pages["PSY 2301 — Study Guide"]["body"]
    assert "## Reading" in body and "Read chapter 2 by **Friday**." in body
    assert "x()" not in body
    assert "\\# not a heading [\\[nor a link]\\]" in body
    assert "- [[PSY 2301 — Study Guide — Guide.docx]]" in body


def test_office_files_and_transcripts_become_text(pages):
    assert "### Slide 1\n\nLearning styles" in pages["PSY 2301 — Slides"]["body"]
    assert "Quiz on Unit I is open book." in pages["PSY 2301 — Study Guide — Guide.docx"]["body"]
    video = pages["PSY 2301 — Welcome — Welcome (video)"]
    assert video["type"] == "video" and video.get("problem") is None
    # The repeated caption line is said once; the NOTE block never reaches the page.
    assert "## Transcript\n\nWelcome to the course. Office hours are Thursdays." in video["body"]
    assert "engine=x" not in video["body"]


def test_a_board_threads_replies_and_drops_drafts(pages):
    page = pages["PSY 2301 discussion — Unit I Discussion Board"]
    body = page["body"]
    assert page["published"] == "2026-10-01"
    assert body.index("### Post from Ana Ruiz") < body.index("#### Reply from Ben Ode")
    assert "draft" not in body and "- Posts: 2" in body


def test_a_long_board_continues_in_parts(tmp_path, bb, monkeypatch):
    h = make_harvest(tmp_path)
    posts = [{"id": f"_q{i}_1", "parentId": "_t1_1", "givenName": "P", "familyName": str(i), "postDate": f"2026-10-{1 + i % 28:02d}T00:00:00Z",
              "body": "<p>" + "word " * 400 + "</p>"} for i in range(80)]
    _dump(h / "discussions/_d1_1.json", posts)
    monkeypatch.setattr(bb, "PART_BYTES", 20_000)
    board = next(d for d in bb.split(h, tmp_path / "items") if d.name.startswith("discussion-"))
    parts = bb.render(board)
    assert len(parts) > 3
    assert parts[1]["title"].endswith("(part 2)") and f"[[{parts[1]['title']}]]" in parts[0]["body"]
    assert sum(p["body"].count("### Post from") for p in parts) == 80


def test_a_video_with_no_words_says_so(tmp_path, bb):
    h = make_harvest(tmp_path)
    next(h.rglob("*.transcript.webvtt")).unlink()
    video = next(d for d in bb.split(h, tmp_path / "items") if d.name.startswith("video-"))
    page = bb.render(video)[0]
    assert page["problem"] and "## Transcript" not in page["body"]


def test_split_keeps_identity_and_fingerprint_across_pulls(tmp_path, bb):
    h = make_harvest(tmp_path)
    first = {d.name: json.loads((d / "capture.json").read_text()) for d in bb.split(h, tmp_path / "items")}
    (h / "bodies" / "_2_1.html").write_text("<p>Read chapter 3.</p>")
    second = {d.name: json.loads((d / "capture.json").read_text()) for d in bb.split(h, tmp_path / "items")}
    assert first.keys() == second.keys()
    moved = {k for k in first if first[k]["fingerprint"] != second[k]["fingerprint"]}
    assert moved == {"item-2_1"}
    assert all(c["item"].startswith(f"blackboard:{CID}/") for c in second.values())


def test_notes_writes_frontmattered_notes(tmp_path, bb):
    h = make_harvest(tmp_path)
    assert bb.main(["notes", str(h), "--out", str(tmp_path / "notes"), "--tz", "America/Chicago"]) == 0
    note = (tmp_path / "notes" / "PSY 2301 announcement — Week 5.md").read_text()
    assert note.startswith('---\ntype: "note"\npublished: "2026-10-23"\ncourse: "PSY 2301"\n'
                           'abstract: "Announcement in PSY 2301 Abnormal Psychology, posted 2026-10-23: Week 5. The library session is Wednesday."\n'
                           'kind: "announcement"\nbb_id: "_a1_1"\n---\n# Week 5\n')


def test_notes_refuses_a_directory_that_is_no_harvest(tmp_path, bb, capsys):
    assert bb.main(["notes", str(tmp_path), "--out", str(tmp_path / "n")]) == 2
    assert "no course.json" in capsys.readouterr().err


# ------------------------------------------------------------------ the stage scripts


def front_door(tmp_path, ticket):
    stub = tmp_path / "ops_stub.py"
    stub.write_text(
        "import json, os, pathlib, sys\n"
        "argv = sys.argv[1:]\n"
        "verb = [a for a in argv if not a.startswith('--')]\n"
        f"TICKET = json.loads({json.dumps(json.dumps(ticket))})\n"
        "log = pathlib.Path(os.environ['FAKE_CALLS'])\n"
        "log.open('a').write(json.dumps({'argv': argv, 'stdin': sys.stdin.read() if '--stdin' in argv else None}) + '\\n')\n"
        "if verb[:2] == ['tickets', 'open']:\n"
        "    print(json.dumps({'ticket': TICKET})); sys.exit(0)\n"
        "if verb[:2] == ['tickets', 'update']:\n"
        "    sys.exit(0)\n"
        "if verb[:2] == ['page', 'create']:\n"
        "    kv = dict(a.split('=', 1) for a in verb[2:] if '=' in a)\n"
        "    print(json.dumps({'path': kv['dest'] + '/' + kv['title'] + '.md'})); sys.exit(0)\n"
        "if verb[:2] == ['page', 'edit']:\n"
        "    print(json.dumps({'path': verb[2]})); sys.exit(0)\n"
        "if verb[:2] == ['page', 'ls']:\n"
        "    under = next(a.split(':', 1)[1] for a in verb if a.startswith('filter=under:'))\n"
        "    roots = [p.as_posix() for p in sorted(pathlib.Path(under).rglob('*.md')) if p.read_text().split('\\n---', 1)[0].count('\\n  root: ') and 'true' in p.read_text().split('\\n  root: ', 1)[1].split('\\n', 1)[0]]\n"
        "    print(json.dumps({'pages': [{'path': r} for r in roots], 'count': len(roots)})); sys.exit(0)\n"
        "sys.exit(9)\n"
    )
    return shlex.join([sys.executable, str(stub)])


def fake_browser(tmp_path, exit_code=0):
    """Stands in for the unit env's python: given `bb.py harvest <id> --out DIR …`, writes the fixture harvest into DIR."""
    src = tmp_path / "fixture"
    if not src.exists():
        make_harvest(src)
    fake = tmp_path / f"env_python_{exit_code}"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, shutil, sys\n"
        "argv = sys.argv[1:]\n"
        "open(os.environ['FAKE_BB'], 'a').write(json.dumps(argv) + '\\n')\n"
        f"if {exit_code}:\n"
        "    print('auth: session expired', file=sys.stderr); sys.exit(" + str(exit_code) + ")\n"
        "out = argv[argv.index('--out') + 1]\n"
        f"shutil.copytree({str(src / 'harvest')!r}, out, dirs_exist_ok=True)\n"
    )
    fake.chmod(0o755)
    return str(fake)


# Runs a script with `sys.executable` set to argv[1]: harvest.py launches bb.py on its own interpreter.
ON_PYTHON = "import runpy, sys; sys.executable = sys.argv.pop(1); sys.argv.pop(0); runpy.run_path(sys.argv[0], run_name='__main__')"


def run_stage(tmp_path, script, ticket, bb_exit=0):
    env = {**os.environ, "LLM_WIKI_OPS": front_door(tmp_path, ticket), "FAKE_CALLS": str(tmp_path / "calls.log"), "FAKE_BB": str(tmp_path / "bb.log")}
    on = ["-c", ON_PYTHON, fake_browser(tmp_path, bb_exit)] if script == "harvest.py" else []
    cp = subprocess.run([sys.executable, *on, str(SCRIPTS / script), f"ticket={ticket['ticket']}"], cwd=tmp_path, env=env, capture_output=True, text=True)
    calls = [json.loads(line) for line in (tmp_path / "calls.log").read_text().splitlines()] if (tmp_path / "calls.log").exists() else []
    updates = [c["argv"] for c in calls if c["argv"][1:3] == ["tickets", "update"]]
    return cp, calls, updates


def harvest_ticket(tmp_path, **over):
    t = {"ticket": "t1", "stage": "harvest", "slug": "psy", "target": TARGET, "item": TARGET, "capture_dir": "_raw/psy/course",
         "credential_dir": str(tmp_path / "profile"), "known": [], "options": {}}
    t.update(over)
    return t


def test_a_harvest_posts_every_capture_and_runs_bb_on_the_granted_profile(tmp_path):
    cp, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path))
    assert cp.returncode == 0, cp.stderr
    (bb_call,) = [json.loads(line) for line in (tmp_path / "bb.log").read_text().splitlines()]
    assert bb_call[1:3] == ["harvest", CID] and bb_call[bb_call.index("--site") + 1] == "https://learn.example.edu"
    assert bb_call[bb_call.index("--profile") + 1] == str(tmp_path / "profile")
    (update,) = updates
    assert "status=ok" in update
    captured = [a.split("=", 1)[1] for a in update if a.startswith("captured=")]
    assert len(captured) == 8 and all(c.startswith("_raw/psy/course/items/") for c in captured)
    assert json.loads((tmp_path / captured[0] / "capture.json").read_text())["slug"] == "psy"


def test_a_second_pull_posts_only_what_changed(tmp_path):
    run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path))
    items = tmp_path / "_raw/psy/course/items"
    known = [{"resource": json.loads((d / "capture.json").read_text())["item"], "path": "x"} for d in items.iterdir() if d.is_dir()]
    (tmp_path / "fixture/harvest/bodies/_2_1.html").write_text("<p>Read chapter 3.</p>")
    (tmp_path / "calls.log").unlink()
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, known=known))
    captured = [a for a in updates[0] if a.startswith("captured=")]
    assert captured == ["captured=_raw/psy/course/items/item-2_1"]


def test_an_expired_session_is_a_failed_harvest_naming_auth(tmp_path):
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path), bb_exit=2)
    assert "status=failed" in updates[0] and f"missing=learn.example.edu,{TARGET},auth" in updates[0]


def test_a_target_naming_no_course_is_failed_and_runs_nothing(tmp_path):
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, target="https://learn.example.edu/ultra/stream", item=None))
    assert "status=failed" in updates[0] and not (tmp_path / "bb.log").exists()


def _captures(tmp_path):
    run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path))
    (tmp_path / "calls.log").unlink()
    return tmp_path / "_raw/psy/course/items"


def test_process_writes_the_page_with_its_resource_and_date(tmp_path):
    items = _captures(tmp_path)
    t = {"ticket": "t2", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [], "held": [], "options": {"timezone": "America/Chicago"}}
    cp, calls, updates = run_stage(tmp_path, "process.py", t)
    assert cp.returncode == 0, cp.stderr
    (create,) = [c for c in calls if c["argv"][1:3] == ["page", "create"]]
    assert "title=PSY 2301 — Scholarly Activity" in create["argv"] and "published=2026-09-17" in create["argv"]
    assert "resource=blackboard:_42_1/item-3_1" in create["argv"] and "type=document" in create["argv"]
    assert "Tue 2026-10-20 11:59 PM CDT" in create["stdin"]
    assert "status=ok" in updates[0]
    assert json.loads((items / "item-3_1" / "written.json").read_text()) == ["sources/courses/psy/PSY 2301 — Scholarly Activity.md"]


def test_process_leaves_a_page_a_person_moved_alone(tmp_path):
    _captures(tmp_path)
    moved = tmp_path / "sources/notes/mine.md"
    moved.parent.mkdir(parents=True)
    moved.write_text("x")
    t = {"ticket": "t3", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [{"resource": "blackboard:_42_1/item-3_1", "path": "sources/notes/mine.md", "reason": "moved"}], "held": [], "options": {}}
    _, calls, updates = run_stage(tmp_path, "process.py", t)
    assert not [c for c in calls if c["argv"][1] == "page"]
    assert "status=ok" in updates[0] and any("moved by a person" in a for a in updates[0])


def test_process_writes_nothing_for_a_held_page(tmp_path):
    _captures(tmp_path)
    t = {"ticket": "t4", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [], "held": [{"resource": "blackboard:_42_1/item-3_1"}], "options": {}}
    _, calls, updates = run_stage(tmp_path, "process.py", t)
    assert not [c for c in calls if c["argv"][1] == "page"] and "status=ok" in updates[0]


def test_a_held_page_names_its_status_in_the_reason(tmp_path):
    _captures(tmp_path)
    for status, words in [("unstamped", "doctor --fix"), ("conflict", "page resolve"), ("settling", "a later pull writes it"),
                          ("edited", "edited this page"), ("someday", "(someday)"), (None, "a person holds this page")]:
        t = {"ticket": "t4", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
             "known": [], "held": [{"resource": "blackboard:_42_1/item-3_1", "status": status}], "options": {}}
        _, calls, updates = run_stage(tmp_path, "process.py", t)
        (tmp_path / "calls.log").unlink()
        assert not [c for c in calls if c["argv"][1] == "page"] and "status=ok" in updates[0]
        assert any(a.startswith("reason=") and words in a for a in updates[0]), (status, updates[0])


def test_process_of_a_video_with_no_words_is_partial(tmp_path):
    items = _captures(tmp_path)
    video = next(d for d in items.iterdir() if d.name.startswith("video-"))
    next(video.glob("*.transcript.webvtt")).unlink()
    t = {"ticket": "t5", "stage": "process", "slug": "psy", "capture_dir": video.relative_to(tmp_path).as_posix(), "dest": "sources/courses/psy",
         "known": [], "held": [], "options": {}}
    _, _, updates = run_stage(tmp_path, "process.py", t)
    assert "status=partial" in updates[0] and any("no transcript" in a for a in updates[0])


# ------------------------------------------------------------------ titles, identity, options


def _content(h: Path, *rows) -> None:
    contents = json.loads((h / "contents.json").read_text())
    for at, row in rows:
        contents.insert(at, row)
    _dump(h / "contents.json", contents)
    for at, row in rows:
        (h / "bodies" / f"{row['id']}.html").write_text(f"<p>{row['id']} text</p>")


def _readings(n: str, week: str) -> dict:
    return {"id": f"_r{n}_1", "parent": None, "path": f"{week}/Readings", "title": "Readings", "handler": "resource/x-bb-document"}


def _titles(bb, h, out):
    return {d.name: json.loads((d / "capture.json").read_text())["title"] for d in bb.split(h, out)}


def test_an_item_inserted_before_two_same_titled_items_changes_no_existing_title(tmp_path, bb):
    h = make_harvest(tmp_path)
    _content(h, (0, _readings("1", "Week 2")), (1, _readings("2", "Week 3")))
    first = _titles(bb, h, tmp_path / "items")
    assert first["item-r1_1"] == "PSY 2301 — Readings (Week 2)" and first["item-r2_1"] == "PSY 2301 — Readings (Week 3)"
    _content(h, (0, _readings("0", "Week 1")))
    second = _titles(bb, h, tmp_path / "items")
    assert {k: second[k] for k in first} == first
    assert second["item-r0_1"] == "PSY 2301 — Readings (Week 1)"


def test_same_titles_in_one_folder_fall_back_to_the_id(tmp_path, bb):
    h = make_harvest(tmp_path)
    _content(h, (0, _readings("1", "Week 2")), (1, _readings("2", "Week 2")))
    titles = _titles(bb, h, tmp_path / "items")
    assert titles["item-r1_1"] == "PSY 2301 — Readings (r1_1)" and titles["item-r2_1"] == "PSY 2301 — Readings (r2_1)"


def test_a_course_json_with_no_id_takes_the_targets_or_is_refused(tmp_path, bb):
    h = make_harvest(tmp_path)
    _dump(h / "course.json", None)
    caps = [json.loads((d / "capture.json").read_text()) for d in bb.split(h, tmp_path / "items", course_id="_9_1")]
    assert caps and all(c["item"].startswith("blackboard:_9_1/") for c in caps)
    with pytest.raises(ValueError):
        bb.split(h, tmp_path / "other")


def test_a_title_holds_no_link_marker_and_venue_text_stays_on_its_line(tmp_path, bb):
    assert bb.page_title("Week #2 ^ [draft]") == "Week ＃2 ˆ (draft)"
    h = make_harvest(tmp_path)
    contents = json.loads((h / "contents.json").read_text())
    contents[2]["title"] = "Scholarly\n---\n# Activity"
    _dump(h / "contents.json", contents)
    cols = json.loads((h / "gradebook-columns.json").read_text())
    cols[0]["name"] = "Paper | one\n## two"
    _dump(h / "gradebook-columns.json", cols)
    for d in bb.split(h, tmp_path / "items"):
        for page in bb.render(d):
            lines = page["body"].splitlines()
            assert lines[-1] == "---"
            lines = lines[:-1]
            assert "---" not in lines and not [ln for ln in lines if ln.startswith("## two") or ln == "# Activity"], page["title"]
    overview = next(p for d in (tmp_path / "items").iterdir() if d.name == "course" for p in bb.render(d))["body"]
    assert "| Paper ¦ one ## two |" in overview


def test_a_meeting_link_loses_its_passcode(bb):
    assert bb.shown_url("https://x.zoom.us/j/123?pwd=SECRET") == "https://x.zoom.us/j/123"
    assert bb.shown_url("https://example.edu/a?b=c") == "https://example.edu/a?b=c"


def test_discussions_skip_fetches_no_board_and_makes_no_page(tmp_path):
    cp, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, options={"discussions": "skip"}))
    assert cp.returncode == 0, cp.stderr
    (bb_call,) = [json.loads(line) for line in (tmp_path / "bb.log").read_text().splitlines()]
    assert "--no-discussions" in bb_call
    assert not [a for a in updates[0] if a.startswith("captured=") and "discussion-" in a]


def test_an_unknown_option_word_or_zone_fails_the_harvest(tmp_path):
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, options={"discussions": "maybe"}))
    assert "status=failed" in updates[0] and any("options.discussions" in a for a in updates[0])
    (tmp_path / "calls.log").unlink()
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, options={"timezone": "Mars/Olympus"}))
    assert "status=failed" in updates[0] and any("Mars/Olympus" in a for a in updates[0])


def test_a_harvest_whose_course_json_names_no_id_fails(tmp_path):
    make_harvest(tmp_path / "fixture")
    _dump(tmp_path / "fixture/harvest/course.json", {"name": "x"})
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path))
    assert "status=failed" in updates[0] and f"missing=learn.example.edu,{TARGET},error" in updates[0]


def test_an_item_known_cannot_list_is_held_back_on_its_written_page(tmp_path):
    items = _captures(tmp_path)
    deck = next(d for d in items.iterdir() if d.name.startswith("file-") and any(d.glob("*.pptx")))
    (deck / "written.json").write_text(json.dumps(["sources/courses/psy/PSY 2301 — Slides.md"]))
    (items / "item-2_1" / "written.json").write_text("[]")
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path))
    captured = {a.rsplit("/", 1)[-1] for a in updates[0] if a.startswith("captured=")}
    assert deck.name not in captured and "item-2_1" in captured and len(captured) == 7


def test_process_never_writes_over_another_items_page(tmp_path):
    _captures(tmp_path)
    page = tmp_path / "sources/courses/psy/PSY 2301 — Scholarly Activity.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\nresource: blackboard:_42_1/item-9_1\n---\n# other\n")
    t = {"ticket": "t7", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [], "held": [], "options": {}}
    _, calls, updates = run_stage(tmp_path, "process.py", t)
    assert not [c for c in calls if c["argv"][1] == "page"]
    assert "status=partial" in updates[0] and any("item-9_1" in a and "not written over" in a for a in updates[0])


def test_process_edits_the_page_known_names_for_the_resource(tmp_path):
    _captures(tmp_path)
    t = {"ticket": "t8", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [{"resource": "blackboard:_42_1/item-9_1", "path": "sources/courses/psy/PSY 2301 — Scholarly Activity.md"},
                   {"resource": "blackboard:_42_1/item-3_1", "path": "sources/courses/psy/Renamed.md"}], "held": [], "options": {}}
    _, calls, _ = run_stage(tmp_path, "process.py", t)
    assert [c["argv"][1:4] for c in calls if c["argv"][1] == "page"] == [["page", "edit", "sources/courses/psy/Renamed.md"]]


def test_process_fails_naming_a_zone_it_does_not_know(tmp_path):
    _captures(tmp_path)
    t = {"ticket": "t9", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [], "held": [], "options": {"timezone": "Mars/Olympus"}}
    _, _, updates = run_stage(tmp_path, "process.py", t)
    assert "status=failed" in updates[0] and any("Mars/Olympus" in a for a in updates[0])


def test_every_page_carries_a_one_line_abstract_from_its_facts(pages):
    for title, page in pages.items():
        assert page["abstract"] and len(page["abstract"]) <= 600 and "\n" not in page["abstract"], title
    item = pages["PSY 2301 — Scholarly Activity"]["abstract"]
    assert "Assignment in PSY 2301 Abnormal Psychology" in item and "Due Tue 2026-10-20 11:59 PM CDT. 100 points." in item
    assert "Write a 3-page paper." in item and "**" not in item
    assert pages["PSY 2301 — Welcome — Welcome (video)"]["abstract"].startswith("Video in PSY 2301 Abnormal Psychology: Welcome — Welcome, 6 s.")
    assert pages["PSY 2301 — Study Guide"]["abstract"].endswith("Reading: Read chapter 2 by Friday.")
    assert "Due dates run 2026-10-06 to 2026-10-20" in pages["PSY 2301 Abnormal Psychology — course overview"]["abstract"]


def test_an_abstract_is_cut_to_the_bound(bb):
    said = bb.abstract("x" * 700, "\nmore\n")
    assert len(said) == 600 and said.endswith("…")


def _course_ticket(tmp_path, **options):
    return {"ticket": "t6", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/course", "dest": "sources/courses/psy",
            "known": [], "held": [], "options": {"timezone": "America/Chicago", **options}}


def test_process_carries_the_abstract_on_every_page_it_writes(tmp_path):
    _captures(tmp_path)
    _, calls, _ = run_stage(tmp_path, "process.py", _course_ticket(tmp_path))
    creates = [c["argv"] for c in calls if c["argv"][1:3] == ["page", "create"]]
    assert creates and all(any(a.startswith("abstract=") for a in argv) for argv in creates)


def test_the_course_overview_makes_the_course_root_once(tmp_path):
    _captures(tmp_path)
    _, calls, updates = run_stage(tmp_path, "process.py", _course_ticket(tmp_path))
    (root,) = [c for c in calls if c["argv"][1:3] == ["page", "create"] and "title=README" in c["argv"]]
    assert {"dest=sources/courses/psy", "ops.root=true", "current=true", "term=from 2026-09-30"} <= set(root["argv"])
    abstract = next(a for a in root["argv"] if a.startswith("abstract="))
    assert len(abstract) - len("abstract=") <= 600 and "\n" not in abstract
    (edit,) = [c["argv"] for c in calls if c["argv"][1:3] == ["page", "edit"]]
    assert edit[3:] == ["sources/courses/psy/README.md", "title=PSY 2301 Abnormal Psychology"]
    assert "status=ok" in updates[0]
    assert (tmp_path / "_raw/psy/course/items/course/root-made.json").is_file()
    (tmp_path / "calls.log").unlink()
    _, calls, _ = run_stage(tmp_path, "process.py", _course_ticket(tmp_path))
    assert not [c for c in calls if "title=README" in c["argv"] or c["argv"][1:3] == ["page", "ls"]]


def test_a_root_that_exists_is_left_and_the_question_is_settled(tmp_path):
    _captures(tmp_path)
    readme = tmp_path / "sources/courses/psy/README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text("---\nops:\n  root: true\ncurrent: false\n---\n# Mine\n")
    _, calls, updates = run_stage(tmp_path, "process.py", _course_ticket(tmp_path))
    assert not [c for c in calls if "title=README" in c["argv"]] and "status=ok" in updates[0]
    assert json.loads((tmp_path / "_raw/psy/course/items/course/root-made.json").read_text())["made"] is False


def test_an_unknown_current_word_makes_no_root_and_says_why(tmp_path):
    _captures(tmp_path)
    _, calls, updates = run_stage(tmp_path, "process.py", _course_ticket(tmp_path, current="maybe"))
    assert not [c for c in calls if "title=README" in c["argv"]]
    assert "status=partial" in updates[0] and any("options.current='maybe'" in a for a in updates[0])
    assert not (tmp_path / "_raw/psy/course/items/course/root-made.json").exists()


def test_an_abstract_keeps_the_link_guard_and_drops_controls(bb):
    said = bb.abstract("Week\x07 [[Secret]]", bb.opening("[\\[nor a link]\\]"))
    assert "[[" not in said and "\x07" not in said and "[\\[Secret]\\]" in said


def test_a_root_a_person_made_under_another_name_stands(tmp_path):
    _captures(tmp_path)
    mine = tmp_path / "sources/courses/psy/Psych.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("---\ntitle: Psych\nops:\n  root: 'true'\n---\n# Psych\n")
    _, calls, _ = run_stage(tmp_path, "process.py", _course_ticket(tmp_path))
    assert not [c for c in calls if "title=README" in c["argv"]]


def test_a_past_course_root_says_current_false(tmp_path):
    _captures(tmp_path)
    _, calls, _ = run_stage(tmp_path, "process.py", _course_ticket(tmp_path, current=False))
    (root,) = [c["argv"] for c in calls if "title=README" in c["argv"]]
    assert "current=false" in root


# ------------------------------------------------------------------ layout, fields, index, releases (#105)


def _caps(dirs) -> dict:
    return {d.name: json.loads((d / "capture.json").read_text()) for d in dirs}


def _split(bb, h, out, when="2026-11-01T00:00:00Z", **options):
    return _caps(bb.split(h, out, fetched_at=when, options={"layout": "modules", **options}))


def test_modules_layout_files_each_page_under_its_module_in_outline_order(tmp_path, bb):
    caps = _split(bb, make_harvest(tmp_path), tmp_path / "items")
    assert caps["item-2_1"]["place"] == "01 Unit I/01 Study Guide"
    assert caps["item-3_1"]["place"] == "01 Unit I/02 Scholarly Activity"
    # A file sorts right after the item that carries it, and names it.
    doc = next(c for c in caps.values() if c["title"].endswith("Guide.docx"))
    assert doc["place"] == "01 Unit I/01 Study Guide — Guide.docx" and doc["part_of"] == "item-2_1"
    assert caps["course"]["place"] == "00 Course overview"
    assert caps["announcement-a1_1"]["place"] == "announcements/2026-10-24 Week 5"  # the post's day, in UTC here
    assert caps["discussion-d1_1"]["place"] == "discussions/Unit I Discussion Board"


def test_flat_and_legacy_layouts(tmp_path, bb):
    flat = _split(bb, make_harvest(tmp_path), tmp_path / "flat", layout="flat", announcements_dir="alongside")
    assert flat["item-3_1"]["place"] == "01.02 Unit I — Scholarly Activity"
    assert flat["announcement-a1_1"]["place"] == "2026-10-24 Week 5"
    legacy = _caps(bb.split(make_harvest(tmp_path / "l"), tmp_path / "legacy"))
    assert legacy["item-3_1"]["place"] is None and legacy["item-3_1"]["fields"]["module"] == "Unit I"


def test_a_place_is_decided_once_so_an_inserted_item_renumbers_no_page(tmp_path, bb):
    h = make_harvest(tmp_path)
    first = _split(bb, h, tmp_path / "items")
    contents = json.loads((h / "contents.json").read_text())
    contents.insert(1, {"id": "_9_1", "parent": "_1_1", "path": "Unit I/Intro", "title": "Intro", "handler": "resource/x-bb-document"})
    _dump(h / "contents.json", contents)
    (h / "bodies" / "_9_1.html").write_text("<p>Hello.</p>")
    second = _split(bb, h, tmp_path / "items", when="2026-11-02T00:00:00Z")
    assert second["item-3_1"]["place"] == first["item-3_1"]["place"] == "01 Unit I/02 Scholarly Activity"
    # The field says where it sits now; the filename keeps where it first sat.
    assert first["item-3_1"]["fields"]["position"] == "02" and second["item-3_1"]["fields"]["position"] == "03"
    assert second["item-9_1"]["place"] == "01 Unit I/01 Intro"


def test_page_fields_say_what_and_where_and_keep_grades_out(tmp_path, bb):
    bb.set_zone("America/Chicago")
    try:
        caps = _split(bb, make_harvest(tmp_path), tmp_path / "items")
    finally:
        bb.ZONE[0] = bb.timezone.utc
    f = caps["item-3_1"]["fields"]
    assert f == {"kind": "assignment", "bb_id": "_3_1", "outline_path": "Unit I / Scholarly Activity", "position": "02",
                 "due": "2026-10-20T23:59-05:00", "points": "100"}
    assert caps["item-2_1"]["fields"]["kind"] == "study-guide"
    assert caps["discussion-d1_1"]["fields"]["due"] == "2026-10-06T23:59-05:00"
    assert not [k for c in caps.values() for k in c["fields"] if k in ("score", "grade", "feedback", "status")]


def test_a_folder_holding_one_document_is_that_documents_place(bb):
    o = bb._Outline([
        {"id": "m", "parent": None, "title": "Welcome!", "handler": "resource/x-bb-lesson", "raw": {"position": 0}},
        {"id": "f1", "parent": "m", "title": "Part 1. Greeting", "handler": "resource/x-bb-folder", "raw": {"position": 0}},
        {"id": "d1", "parent": "f1", "title": "ultraDocumentBody", "path": "Welcome!/Part 1. Greeting/ultraDocumentBody",
         "handler": "resource/x-bb-document", "raw": {"position": 0}},
        {"id": "f2", "parent": "m", "title": "Part 2. More", "handler": "resource/x-bb-folder", "raw": {"position": 1}},
        {"id": "d2", "parent": "f2", "title": "A", "handler": "resource/x-bb-document", "raw": {"position": 0}},
        {"id": "d3", "parent": "f2", "title": "B", "handler": "resource/x-bb-document", "raw": {"position": 1}},
    ])
    assert o.anchor("d1") == "f1" and o.prefix("d1") == "01" and o.module("d1") == "m"
    assert o.anchor("d3") == "d3" and o.prefix("d3") == "02.02" and o.path("d3") == "Welcome! / Part 2. More / B"


def test_module_order_reads_roman_numerals_and_numbered_titles(bb):
    assert [bb.module_order(t) for t in ("Unit IV", "Unit IX", "Module 3- Memory", "Part 2. Tour", "Week 12", "Start Here")] == [4, 9, 3, 2, 12, None]


def test_the_overview_is_the_course_index_with_links_due_dates_and_added(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    contents = json.loads((h / "contents.json").read_text())
    contents.append({"id": "_9_1", "parent": "_1_1", "path": "Unit I/Intro", "title": "Intro", "handler": "resource/x-bb-document"})
    _dump(h / "contents.json", contents)
    (h / "bodies" / "_9_1.html").write_text("<p>Hello.</p>")
    _split(bb, h, tmp_path / "items", when="2026-11-03T00:00:00Z")
    body = bb.render(tmp_path / "items" / "course", {"item-3_1": "sources/courses/psy/01 Unit I/02 Scholarly Activity"})[0]["body"]
    assert "- [[sources/courses/psy/01 Unit I/02 Scholarly Activity|Scholarly Activity]] (assignment, due Wed 2026-10-21 04:59 UTC, 100 points)" in body
    assert "  - [[01 Unit I/01 Study Guide — Guide.docx|PSY 2301 — Study Guide — Guide.docx]]" in body
    # The first pull's pages are no news; what a later pull first saw is.
    added = body.split("## Added this week\n\n", 1)[1].split("\n\n", 1)[0]
    assert added == "- 2026-11-03: [[01 Unit I/06 Intro|PSY 2301 — Intro]]"
    assert body.index("## Added this week") < body.index("## Outline") < body.index("## Gradebook")


def test_an_item_gone_two_whole_pulls_is_stamped_removed_and_its_return_clears_it(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    contents = json.loads((h / "contents.json").read_text())
    _dump(h / "contents.json", [c for c in contents if c["id"] != "_3_1"])
    once = bb.split(h, tmp_path / "items", options={"layout": "modules"})
    assert "item-3_1" not in {d.name for d in once}
    # A listing that failed judges nothing.
    _dump(h / "errors.json", [{"what": "contents _1_1", "status": 0}])
    assert "item-3_1" not in {d.name for d in bb.split(h, tmp_path / "items", options={"layout": "modules"})}
    _dump(h / "errors.json", [])
    twice = _caps(bb.split(h, tmp_path / "items", fetched_at="2026-11-04T00:00:00Z", options={"layout": "modules"}))
    assert twice["item-3_1"]["removed"] == "2026-11-04"
    course = json.loads((tmp_path / "items/course/record.json").read_text())
    assert "- PSY 2301 — Scholarly Activity: not listed since 2026-11-04" in bb.render(tmp_path / "items/course")[0]["body"]
    _dump(h / "contents.json", contents)
    back = _split(bb, h, tmp_path / "items", when="2026-11-05T00:00:00Z")
    assert "removed" not in back["item-3_1"] and "removed" not in back["item-3_1"]["fields"]
    assert course["removed"] == [{"day": "2026-11-04", "title": "PSY 2301 — Scholarly Activity"}]
    assert not json.loads((tmp_path / "items/course/record.json").read_text())["removed"]


def test_a_layout_word_that_is_not_one_is_refused(bb):
    for bad in ({"layout": "tree"}, {"backfill": "some"}, {"depth": "0"}, {"announcements_dir": "a/b"}):
        with pytest.raises(ValueError):
            bb.layout_of(bad)
    assert bb.layout_of({})["layout"] == "legacy" and bb.layout_of({"layout": "Modules"})["layout"] == "modules"


def test_backfill_none_holds_back_a_module_a_week_past_its_last_due_date(tmp_path):
    opts = {"layout": "modules", "timezone": "America/Chicago"}
    run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, options=opts))
    items = tmp_path / "_raw/psy/course/items"
    known = [{"resource": json.loads((d / "capture.json").read_text())["item"], "path": "x"} for d in items.iterdir() if d.is_dir()]
    (tmp_path / "fixture/harvest/bodies/_2_1.html").write_text("<p>Read chapter 3.</p>")
    (tmp_path / "calls.log").unlink()
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, known=known, options={**opts, "backfill": "none"}))
    assert not [a for a in updates[0] if a.startswith("captured=")]
    assert any("backfill=none" in a for a in updates[0])
    # The edit held back is posted once the module is no longer frozen.
    (tmp_path / "calls.log").unlink()
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, known=known, options=opts))
    assert [a for a in updates[0] if a.startswith("captured=")] == ["captured=_raw/psy/course/items/item-2_1"]
    (tmp_path / "calls.log").unlink()
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, known=known, options={**opts, "backfill": "all"}))
    assert len([a for a in updates[0] if a.startswith("captured=")]) == 8


def test_a_harvest_with_a_layout_word_that_is_not_one_fails(tmp_path):
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, options={"layout": "tree"}))
    assert "status=failed" in updates[0] and any("options.layout" in a for a in updates[0])


def _modules_ticket(tmp_path, capture, **over):
    t = {"ticket": "m1", "stage": "process", "slug": "psy", "capture_dir": f"_raw/psy/course/items/{capture}", "dest": "sources/courses/psy",
         "known": [], "held": [], "options": {"timezone": "America/Chicago", "layout": "modules"}, "root": {}}
    t.update(over)
    return t


def _modules_captures(tmp_path):
    run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, options={"layout": "modules", "timezone": "America/Chicago"}))
    (tmp_path / "calls.log").unlink()
    return tmp_path / "_raw/psy/course/items"


def test_process_creates_a_new_page_at_its_place_and_titles_it(tmp_path):
    _modules_captures(tmp_path)
    _, calls, updates = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "item-3_1"))
    create, edit = [c["argv"] for c in calls if c["argv"][1] == "page"]
    assert create[1:3] == ["page", "create"] and "title=02 Scholarly Activity" in create and "dest=sources/courses/psy/01 Unit I" in create
    assert {"kind=assignment", "position=02", "points=100", "due=2026-10-20T23:59-05:00", "bb_id=_3_1"} <= set(create)
    assert edit[1:] == ["page", "edit", "sources/courses/psy/01 Unit I/02 Scholarly Activity.md", "title=PSY 2301 — Scholarly Activity"]
    assert "status=ok" in updates[0]


def test_a_file_page_links_the_item_that_carries_it(tmp_path):
    items = _modules_captures(tmp_path)
    doc = next(d.name for d in items.iterdir() if d.is_dir() and any(d.glob("*.docx")))
    known = [{"resource": "blackboard:_42_1/item-2_1", "path": "sources/courses/psy/01 Unit I/01 Study Guide.md"}]
    _, calls, _ = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, doc, known=known))
    create = next(c["argv"] for c in calls if c["argv"][1:3] == ["page", "create"])
    assert "part_of=[[sources/courses/psy/01 Unit I/01 Study Guide|PSY 2301 — Study Guide]]" in create


def test_a_module_page_goes_to_the_folder_whose_root_names_the_module(tmp_path):
    _modules_captures(tmp_path)
    root = tmp_path / "sources/courses/psy/Unit One (mine)/README.md"
    root.parent.mkdir(parents=True)
    root.write_text("---\nops:\n  root: true\nmodule_id: _1_1\n---\n# Unit I\n")
    _, calls, _ = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "item-3_1"))
    create = next(c["argv"] for c in calls if c["argv"][1:3] == ["page", "create"])
    assert "dest=sources/courses/psy/Unit One (mine)" in create


def _created_in(tmp_path, known, readme=None):
    _modules_captures(tmp_path)
    if readme:
        root = tmp_path / "sources/courses/psy" / readme / "README.md"
        root.parent.mkdir(parents=True)
        root.write_text("---\nops:\n  root: true\nmodule_id: _1_1\n---\n# Unit I\n")
    rows = [{"resource": "blackboard:_42_1/item-2_1", "path": path, "reason": why} for path, why in known]
    _, calls, _ = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "item-3_1", known=rows))
    create = next(c["argv"] for c in calls if c["argv"][1:3] == ["page", "create"])
    return next(a for a in create if a.startswith("dest="))


def test_a_new_item_joins_its_modules_pages_where_a_person_moved_them(tmp_path):
    assert _created_in(tmp_path, [("sources/courses/psy/Week one/01 Study Guide.md", None)]) == "dest=sources/courses/psy/Week one"


def test_a_new_item_of_a_flattened_module_goes_to_dest_itself(tmp_path):
    assert _created_in(tmp_path, [("sources/courses/psy/01 Study Guide.md", None)]) == "dest=sources/courses/psy"


def test_a_page_moved_out_of_dest_casts_no_vote_for_its_modules_folder(tmp_path):
    assert _created_in(tmp_path, [("notes/01 Study Guide.md", "moved")]) == "dest=sources/courses/psy/01 Unit I"


def test_a_module_root_outranks_where_the_modules_pages_sit(tmp_path):
    got = _created_in(tmp_path, [("sources/courses/psy/Week one/01 Study Guide.md", None)], readme="Unit One (mine)")
    assert got == "dest=sources/courses/psy/Unit One (mine)"


def test_the_course_capture_makes_each_module_root_once_and_links_by_path(tmp_path):
    _modules_captures(tmp_path)
    (tmp_path / "sources/courses/PSY").mkdir(parents=True)
    _, calls, updates = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "course"))
    roots = [c for c in calls if c["argv"][1:3] == ["page", "create"] and "title=README" in c["argv"]]
    course, module = (c["argv"] for c in roots)
    assert {"group=PSY 2301", "group_type=course", "channel=blackboard", "course=PSY 2301", "course_id=PSY2301-21.01",
            "section=21.01", "term_start=2026-09-30"} <= set(course)
    assert "[[sources/courses/psy/00 Course overview|" in roots[0]["stdin"]
    assert {"dest=sources/courses/psy/01 Unit I", "ops.root=true", "module=Unit I", "module_order=1", "module_kind=lesson", "module_id=_1_1"} <= set(module)
    assert any(a.startswith("released=20") for a in module)
    overview = next(c for c in calls if c["argv"][1:3] == ["page", "create"] and "title=00 Course overview" in c["argv"])
    assert "[[sources/courses/psy/01 Unit I/02 Scholarly Activity|Scholarly Activity]]" in overview["stdin"]
    assert any("sources/courses/PSY differs from sources/courses/psy only by case" in a for a in updates[0])
    made = json.loads((tmp_path / "_raw/psy/course/items/course/modules-made.json").read_text())
    assert made == {"_1_1": "01 Unit I"}
    (tmp_path / "calls.log").unlink()
    _, calls, _ = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "course"))
    assert not [c for c in calls if "title=README" in c["argv"]]


def test_the_jobs_root_keys_go_on_the_course_root_over_the_units(tmp_path):
    _modules_captures(tmp_path)
    _, calls, _ = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "course", root={"group": "Psych", "extract": "light"}))
    course = next(c["argv"] for c in calls if "title=README" in c["argv"] and "dest=sources/courses/psy" in c["argv"])
    assert "group=Psych" in course and "group=PSY 2301" not in course and "ops.extract=light" in course


def test_a_removed_capture_dates_its_page_and_writes_nothing_else(tmp_path):
    items = _modules_captures(tmp_path)
    cap = json.loads((items / "item-3_1/capture.json").read_text())
    cap["removed"] = "2026-11-04"
    (items / "item-3_1/capture.json").write_text(json.dumps(cap))
    known = [{"resource": cap["item"], "path": "sources/courses/psy/01 Unit I/02 Scholarly Activity.md"}]
    _, calls, updates = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "item-3_1", known=known))
    assert [c["argv"][1:] for c in calls if c["argv"][1] == "page"] == [["page", "edit", known[0]["path"], "removed=2026-11-04"]]
    assert "status=ok" in updates[0]


def test_a_board_no_longer_fetched_is_not_removed_from_the_course(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    for when in ("2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"):
        dirs = bb.split(h, tmp_path / "items", fetched_at=when, discussions=False, options={"layout": "modules"})
    assert not [d for d in dirs if json.loads((d / "capture.json").read_text()).get("removed")]


def test_a_kind_whose_listing_failed_is_not_judged_gone(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    _dump(h / "discussions.json", [])
    _dump(h / "errors.json", [{"what": "discussions", "status": 0}])
    for when in ("2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"):
        dirs = bb.split(h, tmp_path / "items", fetched_at=when, options={"layout": "modules"})
    assert not [d for d in dirs if json.loads((d / "capture.json").read_text()).get("removed")]


def test_an_item_with_nothing_left_to_render_is_not_gone(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    (h / "bodies" / "_2_1.html").write_text("")
    for when in ("2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"):
        dirs = bb.split(h, tmp_path / "items", fetched_at=when, options={"layout": "modules"})
    assert not [d for d in dirs if json.loads((d / "capture.json").read_text()).get("removed")]


def test_module_folders_and_long_flat_names_stay_link_safe_and_distinct(tmp_path, bb):
    h = make_harvest(tmp_path)
    contents = json.loads((h / "contents.json").read_text())
    contents[0]["title"] = "Week #3 [Required]"
    contents[1]["title"] = "A very long study guide title " * 4
    _dump(h / "contents.json", contents)
    # The long item carries two files: cut to the name bound, both would be one name.
    files = json.loads((h / "files.json").read_text())
    second = h / "files/Unit I/Study Guide/Other.docx"
    _office(second, "word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>')
    files.append({"item": "_2_1", "kind": "nested", "path": str(second.relative_to(h))})
    _dump(h / "files.json", files)
    caps = _split(bb, h, tmp_path / "items")
    assert caps["item-3_1"]["place"].startswith("01 Week ＃3 (Required)/")
    flat = _split(bb, h, tmp_path / "flat", layout="flat")
    places = [c["place"] for c in flat.values()]
    assert len(places) == len({p.casefold() for p in places})
    assert all(len(p.rsplit("/", 1)[-1].encode()) <= bb.TITLE_MAX_BYTES + 3 for p in places)


def test_an_item_moved_into_a_new_module_gets_that_modules_folder(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    contents = json.loads((h / "contents.json").read_text())
    contents.append({"id": "_7_1", "parent": None, "path": "Unit II", "title": "Unit II", "handler": "resource/x-bb-lesson"})
    for c in contents:
        if c["id"] == "_3_1":
            c["parent"], c["path"] = "_7_1", "Unit II/Scholarly Activity"
    _dump(h / "contents.json", contents)
    _split(bb, h, tmp_path / "items", when="2026-11-02T00:00:00Z")
    record = json.loads((tmp_path / "items/course/record.json").read_text())
    assert {m["title"]: m["folder"] for m in record["modules"]} == {"Unit I": "01 Unit I", "Unit II": "02 Unit II"}


def test_two_captures_planned_to_one_name_are_told_apart_by_key(tmp_path, bb, monkeypatch):
    monkeypatch.setattr(bb._Split, "planned", lambda self, p, title, mid: "01 Unit I/" + "x" * 130 if p["kind"] == "file" else p["key"])
    h = make_harvest(tmp_path)
    files = json.loads((h / "files.json").read_text())
    second = h / "files/Unit I/Study Guide/Other.docx"
    _office(second, "word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>')
    files.append({"item": "_2_1", "kind": "nested", "path": str(second.relative_to(h))})
    _dump(h / "files.json", files)
    places = sorted(c["place"] for c in _split(bb, h, tmp_path / "items").values() if c["kind"] == "file")
    assert len(places) == len(set(places)) == 3 and sum(p.endswith(")") for p in places) == 2


# ---------------------------------------------------------------- review fold (#106)


def _drop_and_remake(h: Path, old: str, new: str) -> None:
    """The instructor deletes item `old` and makes `new` with the same title at the same position."""
    contents = json.loads((h / "contents.json").read_text())
    for c in contents:
        if c["id"] == old:
            c["id"] = new
    _dump(h / "contents.json", contents)


def test_an_item_remade_at_a_dropped_items_place_gets_a_place_of_its_own(tmp_path, bb):
    h = make_harvest(tmp_path)
    first = _split(bb, h, tmp_path / "items")
    _drop_and_remake(h, "_3_1", "_33_1")
    again = _split(bb, h, tmp_path / "items", when="2026-11-02T00:00:00Z")
    old = first["item-3_1"]["place"]
    assert again["item-33_1"]["place"] != old and again["item-33_1"]["place"].startswith("01 Unit I/02 Scholarly Activity")


def test_a_removed_stamp_is_posted_again_until_process_dates_it(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    contents = json.loads((h / "contents.json").read_text())
    _dump(h / "contents.json", [c for c in contents if c["id"] != "_3_1"])
    bb.split(h, tmp_path / "items", fetched_at="2026-11-02T00:00:00Z", options={"layout": "modules"})
    stamped = bb.split(h, tmp_path / "items", fetched_at="2026-11-03T00:00:00Z", options={"layout": "modules"})
    assert "item-3_1" in {d.name for d in stamped}
    # The edit failed (no `dated.json`): the next pull posts it again.
    retried = bb.split(h, tmp_path / "items", fetched_at="2026-11-04T00:00:00Z", options={"layout": "modules"})
    assert "item-3_1" in {d.name for d in retried}
    # A page that never takes the write (archived) is posted a bounded number of times, then left.
    tries = [bb.split(h, tmp_path / "items", fetched_at=f"2026-11-1{n}T00:00:00Z", options={"layout": "modules"}) for n in range(5)]
    assert sum("item-3_1" in {d.name for d in t} for t in tries) == bb.REMOVED_TRIES - 1
    (tmp_path / "items/item-3_1" / bb.DATED).write_text('"2026-11-03"\n')
    done = bb.split(h, tmp_path / "items", fetched_at="2026-11-05T00:00:00Z", options={"layout": "modules"})
    assert "item-3_1" not in {d.name for d in done}
    # Listed again, then dropped again: dated afresh.
    _dump(h / "contents.json", contents)
    bb.split(h, tmp_path / "items", fetched_at="2026-11-06T00:00:00Z", options={"layout": "modules"})
    assert not (tmp_path / "items/item-3_1" / bb.DATED).exists()


def test_a_listing_that_answers_empty_removes_nothing(tmp_path, bb):
    h = make_harvest(tmp_path)
    _split(bb, h, tmp_path / "items")
    _dump(h / "contents.json", [])
    _dump(h / "discussions.json", [])
    for when in ("2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z", "2026-11-04T00:00:00Z"):
        dirs = bb.split(h, tmp_path / "items", fetched_at=when, options={"layout": "modules"})
    assert not [d for d in dirs if json.loads((d / "capture.json").read_text()).get("removed")]


def test_two_modules_of_one_title_get_two_folders(tmp_path, bb):
    h = make_harvest(tmp_path)
    contents = json.loads((h / "contents.json").read_text())
    contents += [{"id": "_8_1", "parent": None, "path": "Unit I", "title": "Unit I", "handler": "resource/x-bb-lesson"},
                 {"id": "_9_1", "parent": "_8_1", "path": "Unit I/Recap", "title": "Recap", "handler": "resource/x-bb-document", "has_body": True}]
    _dump(h / "contents.json", contents)
    (h / "bodies" / "_9_1.html").write_text("<p>Recap.</p>")
    caps = _split(bb, h, tmp_path / "items", prefix="none")
    folders = {c["place"].rsplit("/", 1)[0] for k, c in caps.items() if k in ("item-2_1", "item-9_1")}
    assert len(folders) == 2


def test_a_due_date_the_instructor_took_away_is_cleared_on_the_page(tmp_path, bb):
    caps = _split(bb, make_harvest(tmp_path / "s"), tmp_path / "s" / "items")
    assert caps["item-2_1"]["fields"]["due"] is None and caps["item-2_1"]["fields"]["points"] is None
    _modules_captures(tmp_path)
    known = [{"resource": "blackboard:_42_1/item-2_1", "path": "sources/courses/psy/01 Unit I/01 Study Guide.md"}]
    _, calls, _ = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "item-2_1", known=known))
    edit = next(c["argv"] for c in calls if c["argv"][1:3] == ["page", "edit"])
    assert {"due=", "points=", "removed=", "title=PSY 2301 — Study Guide"} <= set(edit)


def test_a_removed_discussion_dates_every_part_and_is_dated_only_when_all_took(tmp_path):
    items = _modules_captures(tmp_path)
    cap = json.loads((items / "discussion-d1_1/capture.json").read_text())
    cap["removed"] = "2026-11-04"
    (items / "discussion-d1_1/capture.json").write_text(json.dumps(cap))
    known = [{"resource": cap["item"], "path": "sources/courses/psy/discussions/Board.md"},
             {"resource": cap["item"] + "#part-2", "path": "sources/courses/psy/discussions/Board (part 2).md"}]
    _, calls, updates = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "discussion-d1_1", known=known))
    assert sorted(c["argv"][3] for c in calls if c["argv"][1:3] == ["page", "edit"]) == sorted(k["path"] for k in known)
    assert "status=ok" in updates[0] and (items / "discussion-d1_1/dated.json").is_file()


def test_a_long_boards_continued_in_link_names_where_part_two_is(tmp_path, bb):
    h = make_harvest(tmp_path)
    big = "<p>" + "word " * (bb.PART_BYTES // 4) + "</p>"
    _dump(h / "discussions/_d1_1.json", [
        {"id": f"_p{n}_1", "parentId": "_t1_1", "givenName": "Ana", "familyName": "Ruiz", "postDate": "2026-09-30T21:00:00Z", "body": big}
        for n in range(1, 4)])
    legacy = tmp_path / "legacy"
    bb.split(h, legacy)
    d = legacy / "discussion-d1_1"
    title = json.loads((d / "capture.json").read_text())["title"]
    # Written: the link names where part 2 is now.
    pages = bb.render(d, {"discussion-d1_1": "sources/c/Board", "discussion-d1_1#part-2": "notes/mine/Board 2"})
    assert len(pages) >= 2 and "Continued in [[notes/mine/Board 2|" in pages[0]["body"]
    # Not written yet, legacy: its title, cut by the same rule as the page's own name, in `dest`.
    pages = bb.render(d, {"discussion-d1_1": "sources/c/Board", "discussion-d1_1#dir": "sources/c"})
    assert f"Continued in [[sources/c/{bb.page_title(title + ' (part 2)')}|" in pages[0]["body"]
    # Not written yet, placed: beside its first part's planned place, wherever part 1 went.
    placed = tmp_path / "placed"
    bb.split(h, placed, options={"layout": "modules"})
    pages = bb.render(placed / "discussion-d1_1", {"discussion-d1_1": "notes/moved/Board", "discussion-d1_1#base": "sources/c/discussions/Board"})
    assert "Continued in [[sources/c/discussions/Board (part 2)|" in pages[0]["body"]


def test_every_page_ends_on_the_same_closing_line(pages):
    assert pages and all(p["body"].endswith("\n\n---\n") and not p["body"].endswith("---\n\n---\n") for p in pages.values())


def test_closing_is_added_once(bb):
    assert bb.closed("# T\n\ntext\n") == "# T\n\ntext\n\n---\n"
    assert bb.closed(bb.closed("# T\n\ntext\n")) == "# T\n\ntext\n\n---\n"
    assert bb.closed("") == "---\n"


def test_a_held_later_part_is_left_alone_and_the_rest_written(tmp_path):
    items = _modules_captures(tmp_path)
    board = items / "discussion-d1_1"
    cap = json.loads((board / "capture.json").read_text())
    record = json.loads((board / cap["body"]).read_text())
    record["posts"] = [{**record["posts"][0], "id": f"_p{i}_1", "text": "word " * 2000} for i in range(40)]
    (board / cap["body"]).write_text(json.dumps(record))
    held = [{"resource": cap["item"] + "#part-2", "path": "sources/courses/psy/discussions/Board (part 2).md", "status": "settling"}]
    _, calls, updates = run_stage(tmp_path, "process.py", _modules_ticket(tmp_path, "discussion-d1_1", held=held))
    written = [c for c in calls if c["argv"][1:3] in (["page", "create"], ["page", "edit"])]
    assert written and not [c for c in written if "part 2)" in " ".join(c["argv"])]
    assert any("(part 2).md: a person touched this page" in a for a in updates[0]), updates[0]
