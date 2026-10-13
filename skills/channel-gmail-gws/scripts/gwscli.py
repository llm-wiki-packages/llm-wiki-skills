#!/usr/bin/env python3
"""The one way this unit calls `gws`: an argv list, one mailbox's login
directory, JSON back. Imported by the unit's scripts; it runs nothing itself.

Read-only helpers (`profile`, `list_ids`, `fetch`) and the message parsing
the harvest and the attended pull share. Nothing here sends, drafts or
modifies: those calls live in `gmail_draft.py` and `gmail_apply.py`, each
with its own refusal of everything else.

Stdlib only, and no PEP 723 block: a block routes a script through
`uv run --script`, which needs a writable uv cache a slice need not grant.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess

GWS = "gws"
# The login a jailed run reads is a file-backed one: a jail cannot reach the
# macOS keychain the default backend keeps the key in. Set here, not in the
# sandbox profile, because an attended `[unsandboxed]` run composes no profile.
KEYRING_BACKEND = "file"
TIMEOUT_S = 120
# gws's own exit codes (`gws --help`, EXIT CODES).
RC_API, RC_AUTH = 1, 2


class GwsError(Exception):
    """A `gws` call that did not answer JSON. `why` is a report word:
    `auth`, `timeout` or `error`."""

    def __init__(self, why: str, said: str):
        super().__init__(said)
        self.why = why
        self.said = said


def env_for(config_dir: str | None) -> dict:
    env = dict(os.environ)
    if config_dir:
        env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = config_dir
    env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", KEYRING_BACKEND)
    return env


def call(argv: list, config_dir: str | None = None, *, binary: str | None = None) -> dict:
    """`gws <argv>`, its stdout parsed. Raises GwsError naming why."""
    try:
        done = subprocess.run([binary or GWS, *argv], capture_output=True, text=True, env=env_for(config_dir), timeout=TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        raise GwsError("timeout", f"`gws {' '.join(argv[:4])}` ran past {TIMEOUT_S}s") from None
    except OSError as exc:
        raise GwsError("error", f"could not start gws: {type(exc).__name__}: {exc}") from None
    said = " ".join((done.stderr or done.stdout or "").split())[:400]
    if done.returncode == RC_AUTH:
        raise GwsError("auth", f"gws has no usable login here (exit 2): {said}")
    if done.returncode != 0:
        raise GwsError("error", f"`gws {' '.join(argv[:4])}` failed (exit {done.returncode}): {said}")
    try:
        found = json.loads(done.stdout or "{}")
    except ValueError:
        raise GwsError("error", f"gws answered no JSON: {done.stdout[:200]!r}") from None
    return found if isinstance(found, dict) else {"value": found}


def params(**kw) -> list:
    return ["--params", json.dumps({"userId": "me", **kw})]


def profile(config_dir: str | None = None) -> str:
    """The address this login is signed into."""
    return str(call(["gmail", "users", "getProfile", *params()], config_dir).get("emailAddress") or "")


def list_ids(query: str, config_dir: str | None = None, *, limit: int = 5000) -> tuple[list, bool]:
    """Every message id the query matches, newest first, as Gmail lists them,
    and whether `limit` cut the listing short. Ids are cheap; the listing is
    paged to its end so a caller can take the OLDEST."""
    ids, token = [], None
    while len(ids) < limit:
        extra = {"maxResults": 500, **({"q": query} if query else {}), **({"pageToken": token} if token else {})}
        page = call(["gmail", "users", "messages", "list", *params(**extra)], config_dir)
        ids.extend(str(m["id"]) for m in page.get("messages") or [] if isinstance(m, dict) and m.get("id"))
        token = page.get("nextPageToken")
        if not token:
            return ids[:limit], False
    return ids[:limit], True


def fetch(mid: str, config_dir: str | None = None) -> dict:
    """One message, `format=full`: headers, labels, snippet, the plain-text
    body, attachment names. Through gws, `metadata` and `minimal` come back
    without `snippet`, which the attended triage classifies on."""
    raw = call(["gmail", "users", "messages", "get", *params(id=mid, format="full")], config_dir)
    return record_of(raw)


def header(payload: dict, name: str) -> str:
    for one in payload.get("headers") or []:
        if isinstance(one, dict) and str(one.get("name", "")).lower() == name.lower():
            return str(one.get("value") or "")
    return ""


def _decoded(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    except (ValueError, TypeError):
        return ""


def _parts(part: dict):
    yield part
    for child in part.get("parts") or []:
        if isinstance(child, dict):
            yield from _parts(child)


_TAG = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.S | re.I)


def body_text(payload: dict) -> str:
    """The first `text/plain` part; else the first `text/html` part with its
    tags dropped. Attachments are never read."""
    found = {"text/plain": None, "text/html": None}
    for part in _parts(payload):
        mime = str(part.get("mimeType") or "").lower()
        data = (part.get("body") or {}).get("data")
        if mime in found and found[mime] is None and data and not part.get("filename"):
            found[mime] = _decoded(data)
    if found["text/plain"] is not None:
        return found["text/plain"]
    if found["text/html"] is not None:
        return html.unescape(_TAG.sub(" ", found["text/html"]))
    return ""


def attachments(payload: dict) -> list:
    return [{"name": str(p["filename"]), "mime": str(p.get("mimeType") or "")} for p in _parts(payload) if p.get("filename")]


def record_of(raw: dict) -> dict:
    """A `messages.get` answer as the flat record every script here reads."""
    payload = raw.get("payload") or {}
    try:
        when = int(raw.get("internalDate"))
    except (TypeError, ValueError):
        when = None
    return {
        "id": str(raw.get("id") or ""),
        "thread": str(raw.get("threadId") or ""),
        "internal_date": when,
        "date": header(payload, "Date"),
        "from": header(payload, "From"),
        "to": header(payload, "To"),
        "cc": header(payload, "Cc"),
        "subject": header(payload, "Subject"),
        "list_unsubscribe": bool(header(payload, "List-Unsubscribe")),
        "labels": [str(x) for x in raw.get("labelIds") or []],
        "snippet": str(raw.get("snippet") or ""),
        "attachments": attachments(payload),
        "body": body_text(payload),
    }
