import importlib.util
import json
import os
import shlex
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


# Answers a test queues for one path, each used once and in order, before the path answers as usual; and every path asked.
QUEUED: dict[str, list[int]] = {}
HITS: dict[str, int] = {}


class Learn(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if not SIGNED_IN["on"] or "BbRouter=ok" not in (self.headers.get("Cookie") or ""):
            self.send_response(401)
            self.end_headers()
            return
        HITS[self.path] = HITS.get(self.path, 0) + 1
        if QUEUED.get(self.path):
            self.send_response(QUEUED[self.path].pop(0))
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


# The plugin's launcher and the boot `run` starts a unit script through, from the ops plugin's root (the CI step's
# `LLM_WIKI_OPS_PLUGIN`): bb.py runs here the way `run` runs it.
_PLUGIN = os.environ.get("LLM_WIKI_OPS_PLUGIN")
_RUN_LIB = Path(_PLUGIN, "packages/llm-wiki-ops-v1/src/llm_wiki_ops/lib/run") if _PLUGIN else None
STATE = ".llm-wiki-browser-state.json"
# Stands in for `credentials browser-state put` (stdin over the slot's state file) and `credentials info`.
OPS_STUB = """import json, os, pathlib, sys
argv = [a for a in sys.argv[1:] if a != "--json"]
if argv[:3] == ["credentials", "browser-state", "put"]:
    pathlib.Path(os.environ["LLM_WIKI_SLOT_DIR"], %r).write_text(sys.stdin.read()); print("{}"); sys.exit(0)
if argv[:2] == ["credentials", "info"]:
    print(os.environ["FAKE_INFO"]); sys.exit(0)
sys.exit(9)
""" % STATE


@pytest.fixture
def learn(tmp_path):
    pytest.importorskip("playwright")
    if _RUN_LIB is None or not (_RUN_LIB / "unitlib" / "llm_wiki_browser.py").is_file():
        pytest.skip("set LLM_WIKI_OPS_PLUGIN to an ops plugin root that ships llm_wiki_browser: bb.py launches through it")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Learn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    LEARN_PORT["port"] = server.server_address[1]
    profile = tmp_path / "profile"
    profile.mkdir()
    # A session cookie in the saved state, as `credentials login` leaves it: no expiry.
    (profile / STATE).write_text(json.dumps({"cookies": [
        {"name": "BbRouter", "value": "ok", "domain": "127.0.0.1", "path": "/", "expires": -1, "httpOnly": True, "secure": False, "sameSite": "Lax"},
    ], "origins": [], "seeded": True}))
    stub = tmp_path / "ops_stub.py"
    stub.write_text(OPS_STUB)
    LEARN_PORT.update(ops=shlex.join([sys.executable, str(stub)]), profile=profile)
    SIGNED_IN["on"] = True
    QUEUED.clear()
    HITS.clear()
    yield profile
    server.shutdown()
    QUEUED.clear()


def site():
    return f"http://127.0.0.1:{LEARN_PORT['port']}"


def run(*argv, slot=None, env=None):
    """bb.py through the plugin's boot, on the run's slot (`slot`, else the fixture's profile) unless `env` says otherwise."""
    environ = {**os.environ, "LLM_WIKI_OPS": LEARN_PORT["ops"], "LLM_WIKI_SLOT_DIR": str(slot or LEARN_PORT["profile"]), **(env or {})}
    environ = {k: v for k, v in environ.items() if v is not None}
    boot = [sys.executable, "-B", str(_RUN_LIB / "unit_boot.py"), str(_RUN_LIB / "unitlib")]
    return subprocess.run([*boot, str(SCRIPT), *argv], capture_output=True, text=True, timeout=120, env=environ)


def test_courses_lists_memberships_through_saved_session(learn):
    r = run("courses", "--site", site())
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [{
        "id": "_55_1", "courseId": "BIO101", "name": "Biology", "role": "Student",
        "ultra": None, "term": None, "available": None, "url": None, "member_available": None, "duration": None, "term_duration": None, "organization": None, "created": None, "last_accessed": None}]


def test_harvest_walks_pages_children_attachments_and_body_files(learn, tmp_path):
    out = tmp_path / "out"
    r = run("harvest", "_55_1", "--out", str(out), "--site", site())
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
    r = run("whoami", "--site", site())
    assert r.returncode == bb.EXIT_AUTH, r.stderr
    assert "login" in r.stderr


def test_a_named_credential_is_the_slot_and_its_host_the_site(learn):
    info = json.dumps({"name": "bb", "kind": "dir", "path": str(learn), "host": site()})
    r = run("whoami", "--credential", "bb", env={"LLM_WIKI_SLOT_DIR": None, "FAKE_INFO": info})
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["name"] == "Ada L"


def test_the_session_is_saved_back_to_the_credential(learn):
    r = run("whoami", "--site", site())
    assert r.returncode == 0, r.stderr
    saved = json.loads((learn / STATE).read_text())
    assert "seeded" not in saved and [c["value"] for c in saved["cookies"] if c["name"] == "BbRouter"] == ["ok"]


def test_a_save_that_does_not_land_is_a_credential_store_error(learn, tmp_path):
    failing = tmp_path / "failing_ops.py"
    failing.write_text("import sys; print('nope', file=sys.stderr); sys.exit(1)\n")
    r = run("whoami", "--site", site(), env={"LLM_WIKI_OPS": shlex.join([sys.executable, str(failing)])})
    assert r.returncode == bb.EXIT_STORE and "credential_store_error" in r.stderr, r.stderr


def bare(*argv, **env):
    """bb.py on the bare interpreter: each refusal here comes before any browser."""
    environ = {k: v for k, v in {**os.environ, **env}.items() if v is not None}
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, timeout=60, env=environ)


def test_a_run_handed_no_credential_and_naming_none_is_usage():
    r = bare("whoami", "--site", "https://bb.example.edu", LLM_WIKI_SLOT_DIR=None)
    assert r.returncode == bb.EXIT_USAGE and "--credential" in r.stderr, r.stderr


def test_a_name_beside_the_runs_slot_is_refused(tmp_path):
    r = bare("whoami", "--credential", "bb", "--site", "https://bb.example.edu", LLM_WIKI_SLOT_DIR=str(tmp_path))
    assert r.returncode == bb.EXIT_USAGE and "drop --credential" in r.stderr, r.stderr


def test_no_site_is_usage(tmp_path):
    r = bare("whoami", LLM_WIKI_SLOT_DIR=str(tmp_path))
    assert r.returncode == bb.EXIT_USAGE and "--site" in r.stderr, r.stderr


def test_a_file_the_site_no_longer_has_is_gone_not_failed_and_is_not_asked_again(learn, tmp_path):
    out = tmp_path / "out"
    QUEUED["/bbcswebdav/xid-p_1"] = [404]
    r = run("harvest", "_55_1", "--out", str(out), "--site", site())
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert (summary["errors"], summary["gone"]) == (0, 1), (out / "errors.json").read_text()
    assert json.loads((out / "gone.json").read_text()) == [
        {"item": "_m_1", "kind": "embedded", "src": "/bbcswebdav/xid-p_1", "status": 404, "since": json.loads((out / "gone.json").read_text())[0]["since"]}]
    # The next pull remembers it: the post has no date to say it changed, so the file is not asked for again.
    asked = HITS["/bbcswebdav/xid-p_1"]
    r = run("harvest", "_55_1", "--out", str(out), "--site", site())
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["gone"] == 1 and HITS["/bbcswebdav/xid-p_1"] == asked


def test_a_busy_site_is_asked_again_before_a_download_counts_as_failed(learn, tmp_path):
    out = tmp_path / "out"
    QUEUED["/bbcswebdav/xid-9_1"] = [503]
    r = run("harvest", "_55_1", "--out", str(out), "--site", site())
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert (summary["errors"], summary["gone"]) == (0, 0)
    assert (out / "files/Week 1/Reading/chapter 1.pdf").read_bytes() == b"chapter-bytes"
    assert HITS["/bbcswebdav/xid-9_1"] == 2


def test_a_site_that_stays_busy_is_an_error_a_re_run_retries(learn, tmp_path):
    out = tmp_path / "out"
    QUEUED["/bbcswebdav/xid-9_1"] = [503, 503, 503]
    r = run("harvest", "_55_1", "--out", str(out), "--site", site())
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert (summary["errors"], summary["gone"]) == (1, 0)
    assert json.loads((out / "errors.json").read_text())[0]["status"] == 503
