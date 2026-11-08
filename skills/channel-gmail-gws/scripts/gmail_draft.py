#!/usr/bin/env python3
"""Create a Gmail DRAFT through gws — never send.

  gmail_draft.py --reply-to MSG_ID [--all] [--body-file F] [--config-dir DIR] [--dry-run]
  gmail_draft.py --to ADDR --subject TEXT [--cc ADDR] [--body-file F] [--config-dir DIR] [--dry-run]

The body is `--body-file`, else stdin. A reply draft is threaded: it reads
the original (`messages get`, metadata), sets In-Reply-To and References,
`Re:`s the subject, addresses Reply-To or From (`--all` adds the original
To and Cc minus this login), and files the draft on the original's thread.
`--dry-run` prints the message and calls nothing that writes.

There is no send path here, by design: the one call that writes is
`gmail.users.drafts.create`, and the draft waits in Gmail for the operator.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from pathlib import Path

import gwscli


def original(mid: str, config_dir: str | None) -> dict:
    meta = ["From", "To", "Cc", "Subject", "Reply-To", "Message-ID", "References"]
    raw = gwscli.call(["gmail", "users", "messages", "get", *gwscli.params(id=mid, format="metadata", metadataHeaders=meta)], config_dir)
    payload = raw.get("payload") or {}
    return {"thread": raw.get("threadId"), **{name: gwscli.header(payload, name) for name in meta}}


def others(values: list, skip: set) -> list:
    return [f"{n} <{e}>" if n else e for n, e in getaddresses(values) if e and e.lower() not in skip]


def compose(a, body: str) -> tuple[EmailMessage, str | None]:
    msg = EmailMessage()
    thread = None
    if a.reply_to:
        orig = original(a.reply_to, a.config_dir)
        thread = orig["thread"]
        to = orig["Reply-To"] or orig["From"]
        subject = orig["Subject"]
        msg["To"] = a.to or to
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if a.all:
            skip = {gwscli.profile(a.config_dir).lower(), parseaddr(to)[1].lower()}
            cc = others([orig["To"], orig["Cc"]], skip)
            if cc:
                msg["Cc"] = ", ".join(cc)
        if orig["Message-ID"]:
            msg["In-Reply-To"] = orig["Message-ID"]
            msg["References"] = " ".join(x for x in (orig["References"], orig["Message-ID"]) if x)
    else:
        msg["To"] = a.to
        msg["Subject"] = a.subject
    if a.cc:
        msg["Cc"] = a.cc
    msg.set_content(body)
    return msg, thread


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reply-to", metavar="MSG_ID", help="draft a threaded reply to this message")
    ap.add_argument("--all", action="store_true", help="with --reply-to: reply to everyone on the original")
    ap.add_argument("--to")
    ap.add_argument("--cc")
    ap.add_argument("--subject")
    ap.add_argument("--body-file", help="the plain-text body (default: stdin)")
    ap.add_argument("--config-dir", help="the gws login directory for this mailbox")
    ap.add_argument("--dry-run", action="store_true", help="print the draft; create nothing")
    a = ap.parse_args(argv)
    if not a.reply_to and not (a.to and a.subject):
        print("gmail_draft: a new draft needs --to and --subject; a reply needs --reply-to", file=sys.stderr)
        return 2
    body = Path(a.body_file).read_text(encoding="utf-8") if a.body_file else sys.stdin.read()
    if not body.strip():
        print("gmail_draft: empty body", file=sys.stderr)
        return 2
    try:
        msg, thread = compose(a, body)
        if a.dry_run:
            print(msg.as_string())
            print(json.dumps({"dry_run": True, "threadId": thread}))
            return 0
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")
        request = {"message": {"raw": raw, **({"threadId": thread} if thread else {})}}
        out = gwscli.call(["gmail", "users", "drafts", "create", *gwscli.params(), "--json", json.dumps(request)], a.config_dir)
    except gwscli.GwsError as exc:
        print(f"gmail_draft: {exc.said}", file=sys.stderr)
        return 1
    made = out.get("message") or {}
    print(json.dumps({"draft_id": out.get("id"), "message_id": made.get("id"), "threadId": made.get("threadId"),
                      "to": msg["To"], "subject": msg["Subject"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
