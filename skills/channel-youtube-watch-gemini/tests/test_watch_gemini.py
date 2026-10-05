"""watch_gemini.py against a local server that speaks the Interactions API's
shape. No network, no key: the script is pointed at it with `--api-base`, or
through the module's own `API` for the ticketed form, which never takes one."""

import importlib.util
import json
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

UNIT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = UNIT_DIR / "scripts" / "watch_gemini.py"
URL = "https://www.youtube.com/watch?v=dQw4fixture"
KEY = "AIza-test-key-0123456789"
ANSWER = "**Overview** A short lesson.\n- [00:10] Progressive overload is defined.\n"


def _load():
    spec = importlib.util.spec_from_file_location("watch_gemini", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def reply(text=ANSWER, tokens=1234):
    return 200, {"status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}], "usage": {"total_tokens": tokens}}


@pytest.fixture
def gemini():
    """A fake Interactions endpoint. `answers` is what it says next, in order
    (the last one repeats); `seen` is every request it got."""
    seen, answers = [], [reply()]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append({"path": self.path, "key": self.headers.get("x-goog-api-key"), "body": body})
            if getattr(server, "redirect", None):
                self.send_response(302)
                self.send_header("Location", server.redirect)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code, doc = answers.pop(0) if len(answers) > 1 else answers[0]
            raw = doc if isinstance(doc, bytes) else json.dumps(doc).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.base = f"http://127.0.0.1:{server.server_port}"
    server.seen, server.answers = seen, answers
    yield server
    server.shutdown()


def watch(mod, gemini, tmp_path, item=URL, options=None, key=KEY):
    return mod.watch(item, tmp_path, options=options or {}, key=key, api_base=gemini.base)


# ------------------------------------------------------------------ the request


def test_the_video_url_and_the_default_question_go_to_google_with_the_key_in_the_header(mod, gemini, tmp_path):
    assert watch(mod, gemini, tmp_path)[0] == "ok"
    (request,) = gemini.seen
    assert request["path"] == "/v1beta/interactions" and request["key"] == KEY
    assert request["body"]["model"] == mod.DEFAULT_MODEL
    video, text = request["body"]["input"]
    assert video == {"type": "video", "uri": URL, "processing": "agentic"}
    assert text == {"type": "text", "text": (UNIT_DIR / "references" / "question.md").read_text(encoding="utf-8").strip()}


def test_the_job_options_replace_the_question_and_the_model(mod, gemini, tmp_path):
    watch(mod, gemini, tmp_path, options={"question": "List every tool named.", "model": "gemini-x"})
    body = gemini.seen[0]["body"]
    assert body["model"] == "gemini-x" and body["input"][1]["text"] == "List every tool named."
    assert json.loads((tmp_path / "enrich" / "watch.json").read_text())["model"] == "gemini-x"


# -------------------------------------------------------------------- the notes


def test_the_notes_land_beside_the_capture_with_their_provenance(mod, gemini, tmp_path):
    status, reason, produced = watch(mod, gemini, tmp_path)
    assert (status, produced) == ("ok", 1) and mod.DEFAULT_MODEL in reason
    assert (tmp_path / "enrich" / "watch.md").read_text(encoding="utf-8") == ANSWER
    meta = json.loads((tmp_path / "enrich" / "watch.json").read_text())
    assert {k: meta[k] for k in ("v", "engine", "unit", "model", "tokens", "frames")} == {
        "v": 1, "engine": "gemini", "unit": mod.UNIT, "model": mod.DEFAULT_MODEL, "tokens": 1234, "frames": None,
    }
    assert meta["generated_at"].endswith("Z")
    assert sorted(p.name for p in (tmp_path / "enrich").iterdir()) == ["watch.json", "watch.md"]


def test_a_rerun_clears_what_an_earlier_run_left(mod, gemini, tmp_path):
    watch(mod, gemini, tmp_path)
    (tmp_path / "enrich" / "stale.txt").write_text("old")
    gemini.answers[:] = [(500, {"error": {"message": "boom"}})]
    assert watch(mod, gemini, tmp_path)[0] == "failed"
    assert not (tmp_path / "enrich").exists(), "a failed run must not leave the success the run before it had"


def test_control_characters_in_the_answer_are_dropped_and_an_endless_one_is_cut(mod, gemini, tmp_path):
    gemini.answers[:] = [reply("a\x00b\x1b[31mred\n" + "x" * (mod.MAX_NOTES_CHARS + 10))]
    watch(mod, gemini, tmp_path)
    text = (tmp_path / "enrich" / "watch.md").read_text(encoding="utf-8")
    assert "\x00" not in text and "\x1b" not in text and len(text) <= mod.MAX_NOTES_CHARS + 1


# --------------------------------------------------------------------- refusals


def test_a_url_that_is_not_a_youtube_one_asks_nothing(mod, gemini, tmp_path):
    for item in ("https://vimeo.com/123", "file:///etc/passwd", "https://evil.example/watch?v=x", None):
        status, reason, produced = watch(mod, gemini, tmp_path, item=item)
        assert (status, produced) == ("ok", 0) and reason.startswith("not_youtube")
    assert gemini.seen == [] and not (tmp_path / "enrich").exists()


def test_no_key_is_a_failure_that_asks_nothing(mod, gemini, tmp_path):
    status, reason, _ = watch(mod, gemini, tmp_path, key=None)
    assert status == "failed" and reason.startswith("no_key") and gemini.seen == []


@pytest.mark.parametrize("code, message, status, category", [
    (401, "bad", "failed", "auth"),
    (400, "API key not valid. Please pass a valid API key.", "failed", "auth"),
    (429, "slow down", "failed", "quota"),
    (503, "overloaded", "failed", "service"),
    (404, "not found", "failed", "request"),
    (400, "models/gemini-x is not found for API version v1beta", "failed", "request"),
    (400, "video is private", "ok", "rejected"),
    (422, "cannot process this video", "ok", "rejected"),
])
def test_each_failure_has_a_category_and_only_a_lasting_one_is_ok(mod, gemini, tmp_path, code, message, status, category):
    gemini.answers[:] = [(code, [{"error": {"message": message + " " + KEY}}])]
    got = watch(mod, gemini, tmp_path)
    assert got[0] == status and got[1].startswith(f"gemini {category}:")
    assert (got[2] == 0) == (status == "ok") and KEY not in got[1], "the key must never reach a reason"
    assert not (tmp_path / "enrich").exists()


@pytest.mark.parametrize("answer", [b"not json", {"steps": []}, {"steps": [{"type": "model_output", "content": []}]}])
def test_an_answer_this_version_cannot_read_is_a_failure(mod, gemini, tmp_path, answer):
    gemini.answers[:] = [(200, answer)]
    status, reason, _ = watch(mod, gemini, tmp_path)
    assert status == "failed" and reason.startswith("gemini response:")


def test_an_unreachable_server_is_a_network_failure(mod, tmp_path):
    status, reason, _ = mod.watch(URL, tmp_path, options={}, key=KEY, api_base="http://127.0.0.1:9")
    assert status == "failed" and reason.startswith("gemini network:")


# --------------------------------------------------------------------- the runs


def test_a_hand_run_prints_its_outcome_and_posts_nothing(mod, gemini, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setenv("LLM_WIKI_OPS", str(tmp_path / "no-front-door"))
    out = tmp_path / "cap"
    assert mod.main(["--item", URL, "--capture-dir", str(out), "--api-base", gemini.base]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "ok", "reason": f"{mod.DEFAULT_MODEL} watched {URL}", "produced": 1}
    assert (out / "enrich" / "watch.md").is_file() and gemini.seen[0]["key"] == KEY


def test_a_hand_run_without_a_key_exits_nonzero(mod, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert mod.main(["--item", URL, "--capture-dir", str(tmp_path / "cap")]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


@pytest.fixture
def door(tmp_path, monkeypatch):
    """A recording `llm-wiki-ops` named by `LLM_WIKI_OPS`, answering `tickets
    open` with `door.ticket` and `credentials get` with a stored key."""
    stub, log = tmp_path / "bin" / "llm-wiki-ops", tmp_path / "calls.jsonl"
    stub.parent.mkdir()
    state = tmp_path / "state.json"
    stub.write_text(
        f"#!{sys.executable}\nimport json, sys\n"
        f"state = json.load(open({str(state)!r}))\n"
        f"open({str(log)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "args = sys.argv[1:]\n"
        "if args[1:4] == ['pipeline', 'tickets', 'open']:\n"
        "    print(json.dumps({'ticket': state['ticket']}))\n"
        "elif args[1:3] == ['credentials', 'get']:\n"
        "    print(json.dumps({'name': args[3], 'value': state['stored']}))\n"
        "else:\n"
        "    print('{}')\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("LLM_WIKI_OPS", str(stub))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    class Door:
        def set(self, ticket, stored=KEY + "\n"):
            state.write_text(json.dumps({"ticket": ticket, "stored": stored}))

        def calls(self):
            return [json.loads(line) for line in log.read_text().splitlines()]

    return Door()


def ticket(**extra):
    return {"capture_dir": "_raw/job/leaf", "item": URL, "credential": "gem", "credential_route": None, "enrich": {"options": {}}, **extra}


def test_a_ticketed_run_reads_the_bound_key_by_name_and_posts_ok(mod, gemini, door, tmp_path, monkeypatch):
    door.set(ticket())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API", gemini.base)
    assert mod.run_ticketed("abc123") == 0
    assert gemini.seen[0]["key"] == KEY
    calls = door.calls()
    assert ["--json", "credentials", "get", "gem"] in calls
    assert calls[-1][:6] == ["--json", "pipeline", "tickets", "update", "abc123", "stage=enrich"] and "status=ok" in calls[-1] and "produced=1" in calls[-1]
    assert not any(KEY in " ".join(c) for c in calls), "the key must never ride a command line"
    assert (tmp_path / "_raw/job/leaf/enrich/watch.md").read_text(encoding="utf-8") == ANSWER


def test_a_route_phantom_rides_the_environment_and_the_payload_is_never_read(mod, gemini, door, tmp_path, monkeypatch):
    door.set(ticket(credential_route="gemini"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API", gemini.base)
    monkeypatch.setenv("GEMINI_API_KEY", "phantom-value")
    mod.run_ticketed("abc123")
    assert gemini.seen[0]["key"] == "phantom-value"
    assert not any(c[1:3] == ["credentials", "get"] for c in door.calls())


def test_a_ticketed_run_takes_the_item_from_capture_json_when_the_ticket_names_none(mod, gemini, door, tmp_path, monkeypatch):
    door.set(ticket(item=None))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API", gemini.base)
    cap = tmp_path / "_raw/job/leaf"
    cap.mkdir(parents=True)
    (cap / "capture.json").write_text(json.dumps({"item": URL}))
    mod.run_ticketed("abc123")
    assert gemini.seen[0]["body"]["input"][0]["uri"] == URL


def test_the_ticket_options_reach_the_request(mod, gemini, door, tmp_path, monkeypatch):
    door.set(ticket(enrich={"options": {"question": "What is shown?", "model": "gemini-y"}}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API", gemini.base)
    mod.run_ticketed("abc123")
    assert gemini.seen[0]["body"]["model"] == "gemini-y" and gemini.seen[0]["body"]["input"][1]["text"] == "What is shown?"


@pytest.mark.parametrize("capture_dir", ["/etc", "../outside", "", None])
def test_a_capture_dir_that_is_not_wiki_relative_is_refused_before_anything_is_written(mod, gemini, door, tmp_path, monkeypatch, capture_dir):
    door.set(ticket(capture_dir=capture_dir))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API", gemini.base)
    mod.run_ticketed("abc123")
    assert "status=failed" in door.calls()[-1] and gemini.seen == []


def test_a_failure_is_posted_failed_with_the_key_scrubbed(mod, gemini, door, tmp_path, monkeypatch):
    door.set(ticket())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "API", gemini.base)
    gemini.answers[:] = [(401, {"error": {"message": f"key {KEY} rejected"}})]
    mod.run_ticketed("abc123")
    update = door.calls()[-1]
    assert "status=failed" in update and not any(KEY in part for part in update)
    assert not any(part.startswith("produced=") for part in update)


def test_a_redirect_is_a_failure_and_the_key_goes_nowhere_else(mod, gemini, tmp_path):
    elsewhere = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            elsewhere.append(self.headers.get("x-goog-api-key"))
            self.send_response(200)
            self.end_headers()

        do_GET = do_POST

        def log_message(self, *args):
            pass

    other = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        gemini.redirect = f"http://127.0.0.1:{other.server_port}/steal"
        status, reason, _ = watch(mod, gemini, tmp_path)
    finally:
        other.shutdown()
    assert (status, reason.startswith("gemini response:")) == ("failed", True) and elsewhere == []


def test_a_symlinked_enrich_directory_is_replaced_and_what_it_pointed_at_is_untouched(mod, gemini, tmp_path):
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "precious.txt").write_text("keep")
    (tmp_path / "enrich").symlink_to(tmp_path / "other", target_is_directory=True)
    assert watch(mod, gemini, tmp_path)[0] == "ok"
    assert not (tmp_path / "enrich").is_symlink() and (tmp_path / "enrich" / "watch.md").is_file()
    assert [p.name for p in (tmp_path / "other").iterdir()] == ["precious.txt"]
