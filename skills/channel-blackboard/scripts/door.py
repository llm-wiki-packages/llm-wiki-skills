#!/usr/bin/env python3
"""The front door, shared by this unit's scripts: the ticket verbs every
worker calls and one JSON-answered verb call for the rest. A sibling module,
so the three scripts that reach the plugin hold one copy between them.

stdlib only: a script stage refuses a PEP 723 block.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

OPS = "llm-wiki-ops"


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
    argv = [*door, "--json", "tickets", "open", ticket]
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
    argv = [*door, "--json", "tickets", "update", ticket, f"stage={stage}", f"status={status}"]
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


def ops_json(*args: str, stdin: str | None = None) -> tuple[int, dict]:
    """One front-door verb answered as JSON: `(exit code, answer)`. A verb
    that printed no JSON answers `{"error": <what it said>}` on a non-zero
    exit, so a caller reads the refusal and never takes prose for a path."""
    door = front_door()
    if not door:
        return 127, {"error": f"`{OPS}` is not on PATH and `LLM_WIKI_OPS` names nothing"}
    cp = subprocess.run([*door, "--json", *args], input=stdin, capture_output=True, text=True)
    try:
        answer = json.loads(cp.stdout)
    except ValueError:
        answer = None
    if not isinstance(answer, dict):
        answer = {"error": (cp.stderr or cp.stdout).strip()[:400]} if cp.returncode else {}
    return cp.returncode, answer
