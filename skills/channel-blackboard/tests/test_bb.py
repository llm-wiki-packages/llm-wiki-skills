import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bb.py"
spec = importlib.util.spec_from_file_location("bb", SCRIPT)
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)


def test_safe_name_strips_separators_and_entities():
    assert bb.safe_name("Week 1: Intro/Overview &amp; <notes>") == "Week 1- Intro-Overview & -notes"
    assert bb.safe_name("   ") == "untitled"


def test_unique_keeps_duplicate_titles_apart():
    taken = set()
    assert [bb.unique(n, taken) for n in ["Week 1", "week 1", "notes.pdf", "notes.pdf"]] == ["Week 1", "week 1 (2)", "notes.pdf", "notes (2).pdf"]


def test_body_file_links_keeps_same_host_collection_links_only():
    body = (
        '<a href="/bbcswebdav/xid-123_1">a</a> <img src="https://bb.example.edu/bbcswebdav/pid-9/x.png">'
        '<a href="https://evil.example.com/bbcswebdav/xid-1">x</a> <a href="/bbcswebdav/xid-123_1">dup</a>'
        '<a href="https://bb.example.edu/ultra/courses">nav</a>'
    )
    assert bb.body_file_links(body, "https://bb.example.edu") == [
        "https://bb.example.edu/bbcswebdav/xid-123_1",
        "https://bb.example.edu/bbcswebdav/pid-9/x.png",
    ]


def test_filename_from_prefers_rfc5987_disposition():
    assert bb.filename_from("attachment; filename*=UTF-8''Syllabus%20Fall.pdf", "https://h/x") == "Syllabus Fall.pdf"
    assert bb.filename_from('attachment; filename="a.docx"', "https://h/x") == "a.docx"
    assert bb.filename_from(None, "https://h/bbcswebdav/xid-1/notes%201.pdf") == "notes 1.pdf"


def test_is_syllabus_by_handler_or_title():
    assert bb.is_syllabus({"contentHandler": {"id": "resource/x-bb-syllabus"}, "title": "x"})
    assert bb.is_syllabus({"title": "Course Syllabus"})
    assert not bb.is_syllabus({"title": "Week 1"})


# --- a fake Learn on localhost, driven through the real browser context ------

API = "/learn/api/public"
SIGNED_IN = {"on": True}
LEARN_PORT = {"port": None}
ROUTES = {
    f"{API}/v1/users/me": {"id": "_7_1", "userName": "student", "name": {"given": "Ada", "family": "L"}},
    f"{API}/v1/users/_7_1/courses?expand=course&limit=100": {
        "results": [{"courseId": "_55_1", "courseRoleId": "Student", "course": {"courseId": "BIO101", "name": "Biology"}}],
    },
    f"{API}/v3/courses/_55_1": {"id": "_55_1", "courseId": "BIO101", "name": "Biology"},
    f"{API}/v1/courses/_55_1/contents?limit=100": {
        "results": [{"id": "_1_1", "title": "Syllabus", "position": 0, "contentHandler": {"id": "resource/x-bb-file"}}],
        "paging": {"nextPage": f"{API}/v1/courses/_55_1/contents?limit=100&offset=1"},
    },
    f"{API}/v1/courses/_55_1/contents?limit=100&offset=1": {
        "results": [{"id": "_2_1", "title": "Week 1", "position": 1, "hasChildren": True, "contentHandler": {"id": "resource/x-bb-folder"}}],
    },
    f"{API}/v1/courses/_55_1/contents/_2_1/children?limit=100": {
        "results": [{
            "id": "_3_1", "title": "Reading", "position": 0, "contentHandler": {"id": "resource/x-bb-document"},
            "body": '<p>Read this</p><a href="/bbcswebdav/xid-9_1">chapter</a><a href="/bbcswebdav/xid-w_1?sig=1">wrap</a>',
        }, {
            "id": "_4_1", "title": "Schedule", "position": 1,
            "contentHandler": {"id": "resource/x-bb-externallink", "url": "/bbcswebdav/xid-s_1"},
        }],
    },
    f"{API}/v1/courses/_55_1/contents/_1_1/attachments?limit=100": {"results": [{"id": "_a_1", "fileName": "syllabus.pdf", "mimeType": "application/pdf"}]},
    f"{API}/v1/courses/_55_1/contents/_3_1/attachments?limit=100": {"results": []},
    f"{API}/v1/courses/_55_1/announcements?limit=100": {"results": [{"id": "_n_1", "title": "Welcome"}]},
    f"{API}/v2/courses/_55_1/gradebook/columns?limit=100": {"results": [{"id": "_g_1", "name": "Essay", "grading": {"due": "2026-11-01"}}]},
    f"{API}/v1/calendars/items?courseId=_55_1&limit=100": {"results": [{"id": "_c_1", "title": "Essay"}]},
    f"{API}/v1/courses/_55_1/discussions?limit=100": {"results": [{"id": "_d_1", "title": "Unit 1 Board", "topic": "<p>Introduce yourself</p>"}]},
    f"{API}/v1/courses/_55_1/discussions/_d_1/messages?limit=100": {"results": [
        {"id": "_m_1", "body": '<p>Hi</p><a href="https://www.youtube.com/watch?v=abc">vid</a><img src="/bbcswebdav/xid-p_1">'},
    ]},
    f"{API}/v2/courses/_55_1/gradebook/users/_7_1?limit=100": {"results": [{"columnId": "_g_1", "displayGrade": {"score": 90}}]},
    f"{API}/v2/courses/_55_1/gradebook/columns/_g_1/attempts?limit=100": {"results": [{"id": "_t_1", "studentSubmission": "<p>my essay</p>"}]},
    "/learn/api/v1/courses/_55_1/gradebook/attempts/_t_1": {"studentSubmissionFiles": [
        {"name": "essay.pdf", "file": {"fileName": "essay.pdf", "permanentUrl": "/bbcswebdav/xid-e_1"}},
    ]},
}
FILES = {
    f"{API}/v1/courses/_55_1/contents/_1_1/attachments/_a_1/download": (b"%PDF-syllabus", None),
    "/bbcswebdav/xid-9_1": (b"chapter-bytes", 'attachment; filename="chapter 1.pdf"'),
    "/bbcswebdav/xid-w_1?sig=1": (b'<iframe src="/bbcswebdav/xid-real_1?sig=2"></iframe>', 'inline; filename="UNSAFE_HTML_1.html"'),
    "/bbcswebdav/xid-real_1?sig=2": (b"<h1>Study guide</h1>", 'inline; filename="guide.html"'),
    "/bbcswebdav/xid-s_1": (b"%PDF-schedule", 'attachment; filename="schedule.pdf"'),
    "/bbcswebdav/xid-p_1": (b"png", 'inline; filename="pic.png"'),
    "/bbcswebdav/xid-e_1": (b"%PDF-essay", None),
}


class Learn(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if not SIGNED_IN["on"] or "BbRouter=ok" not in (self.headers.get("Cookie") or ""):
            self.send_response(401)
            self.end_headers()
            return
        if self.path in FILES:
            data, disp = FILES[self.path]
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            if disp:
                self.send_header("Content-Disposition", disp)
            self.end_headers()
            self.wfile.write(data)
            return
        body = ROUTES.get(self.path)
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body or {"status": 404}).encode())


@pytest.fixture
def learn(tmp_path):
    pytest.importorskip("playwright")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Learn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    LEARN_PORT["port"] = server.server_address[1]
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / bb.SITE).write_text(json.dumps({"base_url": base}))
    # A session cookie in the saved state, as login leaves it: no expiry.
    (profile / bb.STATE).write_text(json.dumps({"cookies": [
        {"name": "BbRouter", "value": "ok", "domain": "127.0.0.1", "path": "/", "expires": -1, "httpOnly": True, "secure": False, "sameSite": "Lax"},
    ]}))
    SIGNED_IN["on"] = True
    yield profile
    server.shutdown()


def run(*argv):
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, timeout=120)


def test_courses_lists_memberships_through_saved_session(learn):
    r = run("courses", "--profile", str(learn))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [{
        "id": "_55_1", "courseId": "BIO101", "name": "Biology", "role": "Student",
        "ultra": None, "term": None, "available": None, "url": None,
    }]


def test_harvest_walks_pages_children_attachments_and_body_files(learn, tmp_path):
    out = tmp_path / "out"
    r = run("harvest", "_55_1", "--out", str(out), "--profile", str(learn))
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert summary["errors"] == 0, (out / "errors.json").read_text()
    assert summary["items"] == 4 and summary["files"] == 7, (out / "files.json").read_text()
    assert summary["syllabus"] == ["Syllabus"]
    assert (summary["discussions"], summary["posts"], summary["attempts"]) == (1, 1, 1)
    assert summary["external_videos"] == ["https://www.youtube.com/watch?v=abc"]
    assert (out / "files/_submissions/Essay/essay.pdf").read_bytes() == b"%PDF-essay"
    assert (out / "files/_discussions/Unit 1 Board/pic.png").read_bytes() == b"png"
    assert json.loads((out / "my-grades.json").read_text())[0]["displayGrade"]["score"] == 90
    assert (out / "files/Syllabus/syllabus.pdf").read_bytes() == b"%PDF-syllabus"
    assert (out / "files/Week 1/Reading/chapter 1.pdf").read_bytes() == b"chapter-bytes"
    assert "Read this" in (out / "bodies/_3_1.html").read_text()
    assert (out / "files/Week 1/Reading/guide.html").read_text() == "<h1>Study guide</h1>"
    assert (out / "files/Week 1/Schedule/schedule.pdf").read_bytes() == b"%PDF-schedule"
    assert all("sig=" not in f["src"] for f in json.loads((out / "files.json").read_text()) if "src" in f)
    assert [c["path"] for c in json.loads((out / "contents.json").read_text())] == ["Syllabus", "Week 1", "Week 1/Reading", "Week 1/Schedule"]


def test_expired_session_exits_auth(learn):
    SIGNED_IN["on"] = False
    r = run("whoami", "--profile", str(learn))
    assert r.returncode == bb.EXIT_AUTH, r.stderr
    assert "login" in r.stderr


def test_credential_names_the_profile_and_its_host_through_the_front_door(learn, tmp_path):
    (learn / bb.SITE).unlink()
    seen = tmp_path / "argv.json"
    stub = tmp_path / "ops-stub"
    stub.write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        f"json.dump(sys.argv[1:], open({str(seen)!r}, 'w'))\n"
        f"print(json.dumps({{'name': 'bb', 'kind': 'dir', 'path': {str(learn)!r}, 'host': 'HOST'}}))\n"
    )
    stub.chmod(0o755)
    base = json.loads((learn / bb.STATE).read_text())["cookies"][0]["domain"]
    port = LEARN_PORT["port"]
    stub.write_text(stub.read_text().replace("HOST", f"http://{base}:{port}"))
    r = subprocess.run([sys.executable, str(SCRIPT), "whoami", "--credential", "bb"], capture_output=True, text=True,
                       timeout=120, env={**os.environ, "LLM_WIKI_OPS": str(stub)})
    assert json.loads(seen.read_text()) == ["--json", "credentials", "info", "bb"]
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["name"] == "Ada L"
