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
    assert note.startswith('---\ntype: "note"\npublished: "2026-10-24"\ncourse: "PSY 2301"\n---\n# Week 5\n')


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
        "sys.exit(9)\n"
    )
    return shlex.join([sys.executable, str(stub)])


def fake_browser(tmp_path, exit_code=0):
    """Stands in for `browser_python`: given `bb.py harvest <id> --out DIR …`, writes the fixture harvest into DIR."""
    src = tmp_path / "fixture"
    if not src.exists():
        make_harvest(src)
    fake = tmp_path / f"browser_python_{exit_code}"
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


def run_stage(tmp_path, script, ticket):
    env = {**os.environ, "LLM_WIKI_OPS": front_door(tmp_path, ticket), "FAKE_CALLS": str(tmp_path / "calls.log"), "FAKE_BB": str(tmp_path / "bb.log")}
    cp = subprocess.run([sys.executable, str(SCRIPTS / script), f"ticket={ticket['ticket']}"], cwd=tmp_path, env=env, capture_output=True, text=True)
    calls = [json.loads(line) for line in (tmp_path / "calls.log").read_text().splitlines()] if (tmp_path / "calls.log").exists() else []
    updates = [c["argv"] for c in calls if c["argv"][1:3] == ["tickets", "update"]]
    return cp, calls, updates


def harvest_ticket(tmp_path, **over):
    t = {"ticket": "t1", "stage": "harvest", "slug": "psy", "target": TARGET, "item": TARGET, "capture_dir": "_raw/psy/course",
         "credential_dir": str(tmp_path / "profile"), "browser_python": fake_browser(tmp_path), "known": [], "options": {}}
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
    known = [{"resource": json.loads((d / "capture.json").read_text())["item"], "path": "x"} for d in items.iterdir()]
    (tmp_path / "fixture/harvest/bodies/_2_1.html").write_text("<p>Read chapter 3.</p>")
    (tmp_path / "calls.log").unlink()
    _, _, updates = run_stage(tmp_path, "harvest.py", harvest_ticket(tmp_path, known=known))
    captured = [a for a in updates[0] if a.startswith("captured=")]
    assert captured == ["captured=_raw/psy/course/items/item-2_1"]


def test_an_expired_session_is_a_failed_harvest_naming_auth(tmp_path):
    t = harvest_ticket(tmp_path, browser_python=fake_browser(tmp_path, exit_code=2))
    _, _, updates = run_stage(tmp_path, "harvest.py", t)
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


def test_process_edits_a_page_a_person_moved_where_it_lives(tmp_path):
    _captures(tmp_path)
    moved = tmp_path / "sources/notes/mine.md"
    moved.parent.mkdir(parents=True)
    moved.write_text("x")
    t = {"ticket": "t3", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [{"resource": "blackboard:_42_1/item-3_1", "path": "sources/notes/mine.md", "reason": "moved"}], "held": [], "options": {}}
    _, calls, _ = run_stage(tmp_path, "process.py", t)
    assert [c["argv"][1:4] for c in calls if c["argv"][1] == "page"] == [["page", "edit", "sources/notes/mine.md"]]


def test_process_writes_nothing_for_a_held_page(tmp_path):
    _captures(tmp_path)
    t = {"ticket": "t4", "stage": "process", "slug": "psy", "capture_dir": "_raw/psy/course/items/item-3_1", "dest": "sources/courses/psy",
         "known": [], "held": [{"resource": "blackboard:_42_1/item-3_1"}], "options": {}}
    _, calls, updates = run_stage(tmp_path, "process.py", t)
    assert not [c for c in calls if c["argv"][1] == "page"] and "status=ok" in updates[0]


def test_process_of_a_video_with_no_words_is_partial(tmp_path):
    items = _captures(tmp_path)
    video = next(d for d in items.iterdir() if d.name.startswith("video-"))
    next(video.glob("*.transcript.webvtt")).unlink()
    t = {"ticket": "t5", "stage": "process", "slug": "psy", "capture_dir": video.relative_to(tmp_path).as_posix(), "dest": "sources/courses/psy",
         "known": [], "held": [], "options": {}}
    _, _, updates = run_stage(tmp_path, "process.py", t)
    assert "status=partial" in updates[0] and any("no transcript" in a for a in updates[0])
