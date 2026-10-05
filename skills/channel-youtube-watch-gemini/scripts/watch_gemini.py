#!/usr/bin/env python3
"""channel-youtube-watch-gemini's one step: Google's video model watches the
video and the notes land beside the capture. No model session — the pass
starts this script itself, under the unit's enrich sandbox.

  llm-wiki-ops run ops/skills/channel-youtube-watch-gemini/scripts/watch_gemini.py ticket=<id>
  watch_gemini.py --item <youtube url> --capture-dir <dir> [--question T] [--model M]

The pass starts the first form: the script reads its ticket through `tickets
open`, writes `enrich/watch.md` and `enrich/watch.json` in the ticket's
capture directory, and posts `tickets update` itself. The second is a hand
run with no ticket: the key comes from `GEMINI_API_KEY`, nothing is posted,
and the outcome is printed as JSON.

The YouTube url goes to Google as a url; nothing is downloaded and nothing is
uploaded, so a video that is not a public YouTube one is refused before any
request. The key rides the `x-goog-api-key` header and is scrubbed from every
message this script prints or posts. `--api-base` points a hand run or a test
at another server; the pass never passes one.

The request shape and the failure categories are derived from simple10's
claude-video-watch (MIT, see LICENSE-claude-video-watch).

Stdlib only, and deliberately NO PEP 723 block: a script stage is refused one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

UNIT = "channel-youtube-watch-gemini"
OPS = "llm-wiki-ops"
API = "https://generativelanguage.googleapis.com"
ENV_KEY = "GEMINI_API_KEY"
# Upstream claude-video-watch's default. Unverified against the live API here.
DEFAULT_MODEL = "gemini-3.7-flash"
TIMEOUT_S = 600.0
# What one request may bring back; a longer answer is cut, never refused.
MAX_NOTES_CHARS = 60_000

HERE = Path(__file__).resolve().parent
QUESTION_FILE = HERE.parent / "references" / "question.md"
NOTES_DIR = "enrich"
NOTES_NAME = "watch.md"
META_NAME = "watch.json"

_YOUTUBE = re.compile(
    r"^https?://(?:(?:www\.|m\.|music\.)?youtube\.com/(?:watch\?\S*\bv=|shorts/|live/)|youtu\.be/)\S+$", re.I
)

# category -> (what the operator should do, whether a re-run could fix it).
# A category a re-run cannot fix is a lasting fact about the video.
CATEGORIES = {
    "auth": ("check the Gemini key bound to this job (https://aistudio.google.com/apikey)", True),
    "quota": ("the key is rate-limited or out of quota; wait or check its plan", True),
    "service": ("Gemini had a server error; retry shortly", True),
    "network": ("could not reach generativelanguage.googleapis.com; check egress rules", True),
    "response": ("Gemini returned something this version cannot read", True),
    "request": ("Gemini did not accept the request: check the model id (`enrich.options.model`)", True),
    "rejected": ("Gemini refused this video; it may be private, unsupported or too long", False),
}


class _NoRedirect(HTTPRedirectHandler):
    """A POST that carries the key is never replayed at a `Location`."""

    def redirect_request(self, *args, **kwargs):
        return None


OPENER = build_opener(_NoRedirect)


def clear(path: Path) -> None:
    """`path` gone. A symlink goes as the link: `rmtree` neither follows one nor
    says so, and what it points at is not this step's."""
    if path.is_symlink():
        path.unlink()
    else:
        shutil.rmtree(path, ignore_errors=True)


class Failure(Exception):
    def __init__(self, category: str, detail: str):
        super().__init__(category, detail)
        self.category, self.detail = category, detail

    @property
    def lasting(self) -> bool:
        return not CATEGORIES[self.category][1]

    def reason(self) -> str:
        return f"gemini {self.category}: {CATEGORIES[self.category][0]}. Detail: {self.detail or 'none'}"


def is_youtube(url) -> bool:
    return isinstance(url, str) and bool(_YOUTUBE.match(url))


def scrub(text, key) -> str:
    """One line, short, with the key gone."""
    text = " ".join(str(text or "").split())
    return (text.replace(key, "[redacted]") if key else text)[:400]


def default_question() -> str:
    return QUESTION_FILE.read_text(encoding="utf-8").strip()


def _error_message(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
        if isinstance(data, list) and data:  # auth errors arrive wrapped in a one-element array
            data = data[0]
        return str(data["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return text


def ask(url: str, question: str, *, model: str, key: str, api_base: str = API, timeout: float = TIMEOUT_S) -> dict:
    """One Interactions call: Google watches `url` and answers `question`."""
    payload = {
        "model": model,
        "input": [
            {"type": "video", "uri": url, "processing": "agentic"},
            {"type": "text", "text": question},
        ],
    }
    request = Request(
        f"{api_base.rstrip('/')}/v1beta/interactions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with OPENER.open(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        message = _error_message(exc.read())
        # A malformed key answers 400 "API key not valid", not 401. A 400 that names
        # the model, or a 404, is a config fault every capture would hit, so it
        # is a visible failure and never a quiet lasting fact about one video.
        category = (
            "auth" if exc.code in (401, 403) or "api key" in message.lower()
            else "quota" if exc.code == 429
            else "service" if exc.code >= 500
            else "response" if exc.code < 400
            else "request" if exc.code == 404 or "model" in message.lower()
            else "rejected"
        )
        raise Failure(category, scrub(f"HTTP {exc.code}: {message}", key)) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise Failure("network", scrub(f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}", key)) from None
    try:
        data = json.loads(body)
        parts = [
            part["text"]
            for step in data["steps"]
            if step.get("type") == "model_output"
            for part in step.get("content", [])
            if part.get("type") == "text" and part.get("text")
        ]
        tokens = (data.get("usage") or {}).get("total_tokens")
    except (ValueError, KeyError, TypeError, AttributeError):
        raise Failure("response", scrub(body[:300].decode("utf-8", errors="replace"), key)) from None
    if not parts:
        raise Failure("response", f"no answer text (status {data.get('status')})")
    text = "".join(ch for ch in "\n".join(parts) if ch in "\n\t" or ch.isprintable()).strip()
    return {"text": text[:MAX_NOTES_CHARS], "tokens": tokens if isinstance(tokens, int) else None}


def write_notes(cap_dir: Path, text: str, *, model: str, tokens) -> Path:
    """`enrich/` rebuilt from nothing — the watch.md/watch.json pair the
    channel-youtube process step reads."""
    notes = cap_dir / NOTES_DIR
    clear(notes)
    notes.mkdir(parents=True)
    (notes / NOTES_NAME).write_text(text.rstrip() + "\n", encoding="utf-8")
    meta = {
        "v": 1,
        "engine": "gemini",
        "unit": UNIT,
        "model": model,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tokens": tokens,
        "frames": None,
    }
    (notes / META_NAME).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return notes


# ---------------------------------------------------------------- the front door
# `front_door`, `open_ticket` and `post_update` are the catalog's one copied
# piece of code (a gate holds every copy equal); they are not edited here.


def front_door() -> list:
    """The front door, as an argv prefix.

    A hosted run exports `LLM_WIKI_OPS`, naming the CLI it was itself reached
    by — a command LINE, not a path — and that is the one spelling a jail is
    sure to carry. Otherwise the bare name on PATH. Empty when there is
    neither."""
    named = os.environ.get("LLM_WIKI_OPS")
    if named:
        return shlex.split(named)
    found = shutil.which(OPS)
    return [found] if found else []


def open_ticket(ticket: str, stage: str | None = None) -> dict:
    """This worker's own ticket (A-1), through the front door. Exits naming
    the refusal."""
    me = Path(__file__).stem
    door = front_door()
    if not door:
        sys.exit(f"{me}: `{OPS}` is not on PATH and `LLM_WIKI_OPS` names nothing — the front door is how this unit reaches the plugin")
    argv = [*door, "--json", "pipeline", "tickets", "open", ticket]
    if stage:
        argv.append(f"stage={stage}")
    cp = subprocess.run(argv, capture_output=True, text=True)
    if cp.returncode != 0:
        sys.exit(f"{me}: `tickets open {ticket}` refused — {(cp.stdout + cp.stderr).strip()}")
    try:
        return json.loads(cp.stdout)["ticket"]
    except (ValueError, KeyError) as exc:
        sys.exit(f"{me}: `tickets open {ticket}` did not answer a ticket ({exc}) — {cp.stdout}")


def post_update(
    ticket: str,
    stage: str,
    status: str,
    *,
    reason: str | None = None,
    captured=(),
    missing=(),
    written_from: str | None = None,
    produced: int | None = None,
    note: str | None = None,
) -> int:
    """This worker's progress (A-2), through the front door. `missing` is an
    iterable of `(host, url, why)`; a `,` inside `url` is typed as `%2C`,
    the side note every unit's `missing=` build follows the same way."""
    me = Path(__file__).stem
    door = front_door()
    if not door:
        sys.exit(f"{me}: `{OPS}` is not on PATH and `LLM_WIKI_OPS` names nothing — the front door is how this unit posts progress")
    argv = [*door, "--json", "pipeline", "tickets", "update", ticket, f"stage={stage}", f"status={status}"]
    if reason:
        argv.append(f"reason={reason}")
    for directory in captured:
        argv.append(f"captured={directory}")
    for host, url, why in missing:
        argv.append(f"missing={host},{url.replace(',', '%2C')},{why}")
    if written_from:
        argv.append(f"written_from={written_from}")
    if produced is not None:
        argv.append(f"produced={produced}")
    if note:
        argv.append(f"note={note}")
    cp = subprocess.run(argv, capture_output=True, text=True)
    if cp.returncode != 0:
        print(f"{me}: `tickets update` refused — {(cp.stdout + cp.stderr).strip()}", file=sys.stderr)
    return cp.returncode


def stored_key(name: str) -> str | None:
    """The credential's payload through the front door; None where it is absent."""
    door = front_door()
    if not door:
        sys.exit(f"watch_gemini: `{OPS}` is not on PATH and `LLM_WIKI_OPS` names nothing — the front door is how this unit reads its key")
    cp = subprocess.run([*door, "--json", "credentials", "get", name], capture_output=True, text=True)
    if cp.returncode != 0:
        return None
    try:
        value = json.loads(cp.stdout).get("value")
    except (ValueError, AttributeError):
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def key_for(ticket: dict | None) -> str | None:
    """A route's phantom rides `GEMINI_API_KEY` and the proxy swaps in the real
    value; with no route the binding's payload is read by name. The value never
    touches a command line."""
    named = ticket.get("credential") if ticket else None
    if ticket and not ticket.get("credential_route") and named:
        return stored_key(named)
    return (os.environ.get(ENV_KEY) or "").strip() or None


# ------------------------------------------------------------------- the steps


def watch(item, cap_dir: Path, *, options: dict, key: str | None, api_base: str | None = None) -> tuple[str, str, int | None]:
    """`(status, reason, produced)`. `enrich/` is cleared first: what an earlier
    run left must not outlive this one."""
    clear(cap_dir / NOTES_DIR)
    if not is_youtube(item):
        return "ok", "not_youtube: only a public YouTube url can be sent to Gemini as a url", 0
    if not key:
        return "failed", f"no_key: bind a Gemini key to this job (or set {ENV_KEY} on a hand run)", None
    question = (options.get("question") or "").strip() or default_question()
    model = (options.get("model") or "").strip() or DEFAULT_MODEL
    try:
        got = ask(item, question, model=model, key=key, api_base=api_base or API)
    except Failure as failure:
        return ("ok" if failure.lasting else "failed"), failure.reason(), (0 if failure.lasting else None)
    write_notes(cap_dir, got["text"], model=model, tokens=got["tokens"])
    return "ok", f"{model} watched {item}", 1


def run_ticketed(ticket_id: str, api_base: str | None = None) -> int:
    ticket = open_ticket(ticket_id, "enrich")
    relative = Path(ticket.get("capture_dir") or "")
    if not ticket.get("capture_dir") or relative.is_absolute() or ".." in relative.parts:
        return post_update(ticket_id, "enrich", "failed", reason="the ticket names no wiki-relative capture_dir")
    cap_dir = Path.cwd() / relative
    item = ticket.get("item")
    if not item:
        try:
            item = json.loads((cap_dir / "capture.json").read_text(encoding="utf-8")).get("item")
        except (OSError, ValueError, AttributeError):
            item = None
    options = (ticket.get("enrich") or {}).get("options") or {}
    key = key_for(ticket)
    status, reason, produced = watch(item, cap_dir, options=options, key=key, api_base=api_base)
    return post_update(ticket_id, "enrich", status, reason=scrub(reason, key), produced=produced)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ticket_kv", nargs="?", metavar="ticket=<id>", help="the ticket id, as `run` invokes this script — `ticket=<id>`, not a flag")
    parser.add_argument("--item", help="a hand run: the YouTube url to watch")
    parser.add_argument("--capture-dir", help="a hand run: where `enrich/` is written")
    parser.add_argument("--question", help="a hand run: the question, instead of the default")
    parser.add_argument("--model", help=f"a hand run: the model, instead of {DEFAULT_MODEL}")
    parser.add_argument("--api-base", default=None, help="a hand run or a test: another server for the Interactions call; the pass never passes one")
    args = parser.parse_args(argv)
    if args.ticket_kv:
        if not args.ticket_kv.startswith("ticket=") or args.item or args.capture_dir:
            sys.exit("watch_gemini: pass ticket=<id>, or --item <url> --capture-dir <dir> for a hand run")
        return run_ticketed(args.ticket_kv.removeprefix("ticket="), args.api_base)
    if not (args.item and args.capture_dir):
        sys.exit("watch_gemini: pass ticket=<id> (as `run` invokes this script) or --item <url> --capture-dir <dir> for a hand run")
    cap_dir = Path(args.capture_dir)
    cap_dir.mkdir(parents=True, exist_ok=True)
    key = key_for(None)
    status, reason, produced = watch(
        args.item, cap_dir, options={"question": args.question, "model": args.model}, key=key, api_base=args.api_base
    )
    print(json.dumps({"status": status, "reason": scrub(reason, key), "produced": produced}))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
