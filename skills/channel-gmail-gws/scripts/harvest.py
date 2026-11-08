#!/usr/bin/env python3
"""The harvest stage of one gmail-gws mailbox: a script, no model session.

  llm-wiki-ops run ops/skills/channel-gmail-gws/scripts/harvest.py ticket=<id>

The runner starts it exactly so, in the stage's jail. It reads its ticket
through `tickets open`, asserts that the granted gws login (`credential_dir`)
is signed into `options.mailbox`, lists every message newer than the cursor,
reads the OLDEST `options.cap` in full, and hands them to `write_items.py
write`, which files the items, posts `tickets update` and only then moves
the cursor. Read-only against the mailbox: it calls `getProfile`,
`messages list` and `messages get`, nothing else.

The job's options are the mechanical filters, each defaulted here when the
job leaves it out: `lookback_days` (the first pull's window), `cap`,
`exclude_labels` and `exclude_senders` (comma-separated, or a list).

Stdlib only, and no PEP 723 block: a script stage refuses one.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import gwscli
import write_items as W

HOST = "gmail.googleapis.com"
DEFAULTS = {
    "lookback_days": 7,
    "cap": 200,
    "exclude_labels": ["CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "SPAM", "TRASH"],
    "exclude_senders": [],
}
# A slice is killed at 30 minutes; what was read by then is handed over,
# contiguous from the old end, so the cursor stays a clean resume point.
BUDGET_S = 25 * 60
# How many ids the listing pages through before it stops: past it, the run is
# partial and the next one starts where this one's cursor lands.
LIST_LIMIT = 5000


def option(options: dict, key: str):
    """One option, typed as its default is, or the default."""
    value = options.get(key)
    default = DEFAULTS[key]
    if value is None or value == "":
        return default
    if isinstance(default, list):
        items = value if isinstance(value, list) else str(value).split(",")
        return [str(one).strip() for one in items if str(one).strip()]
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def query_for(since_ms: int, senders: list) -> str:
    """Gmail's `after:` takes epoch SECONDS, so the boundary over-fetches by
    under a second; `write_items` drops what is behind the cursor."""
    terms = [f"after:{since_ms // 1000}"]
    terms += [f"-from:{one}" for one in senders if " " not in one]
    return " ".join(terms)


def failed(capture_dir: str, ticket_id: str, reason: str, why: str, url: str) -> int:
    return W.main(["write", capture_dir, "--ticket", ticket_id, "--failed", reason, "--missing", HOST, url, why])


def pull(ids: list, config_dir: str, deadline: float, *, clock=time.monotonic) -> tuple[list, str | None]:
    """Read `ids`, oldest first, until the deadline. Returns the records read
    — always a contiguous run from the old end — and why it stopped early."""
    records = []
    for mid in ids:
        if clock() > deadline:
            return records, f"the slice's time ran out after {len(records)} of {len(ids)} message(s)"
        records.append(gwscli.fetch(mid, config_dir))
    return records, None


def run(ticket_id: str, *, clock=time.monotonic) -> int:
    started = clock()
    ticket = W.open_ticket(ticket_id, "harvest")
    capture_dir = ticket.get("capture_dir")
    if not isinstance(capture_dir, str) or not capture_dir:
        sys.exit(f"harvest: ticket {ticket_id} names no capture_dir")
    options = ticket.get("options") if isinstance(ticket.get("options"), dict) else {}
    mailbox = str(options.get("mailbox") or "").strip()
    url = f"gws:{mailbox or '<no mailbox>'}"
    if not mailbox:
        return failed(capture_dir, ticket_id, "the job names no mailbox — `options.mailbox` is this unit's one required input", "error", url)
    config_dir = ticket.get("credential_dir")
    if not isinstance(config_dir, str) or not config_dir:
        return failed(capture_dir, ticket_id, f"no gws login granted (credential_mode {ticket.get('credential_mode')!r}) — bind this job's dir slot to the mailbox's gws config directory", "auth", url)

    try:
        signed_in = gwscli.profile(config_dir)
        if signed_in.casefold() != mailbox.casefold():
            return failed(capture_dir, ticket_id, f"the granted gws login is {signed_in or 'nobody'}, not {mailbox} — refusing to pull another mailbox", "auth", url)
        job = W.job_from(ticket, argparse.Namespace(ticket=ticket_id))
        start = W.since_of(Path(capture_dir), job, option(options, "lookback_days"))
        ids, truncated = gwscli.list_ids(query_for(start["since"], option(options, "exclude_senders")), config_dir, limit=LIST_LIMIT)
        cap = option(options, "cap")
        oldest = list(reversed(ids))[:cap]
        records, stopped = pull(oldest, config_dir, started + BUDGET_S, clock=clock)
    except gwscli.GwsError as exc:
        return failed(capture_dir, ticket_id, exc.said, exc.why, url)

    reasons = [r for r in (stopped,) if r]
    if len(ids) > cap:
        reasons.append(f"capped at {cap}: {len(ids) - cap} newer message(s) left for the next pull")
    if truncated:
        reasons.append(f"the listing stopped at {LIST_LIMIT} ids")
    source = Path(capture_dir) / W.PULL_NAME
    W._write_json(source, records)
    argv = ["write", capture_dir, "--ticket", ticket_id, "--from", W.PULL_NAME, "--cap", str(cap)]
    for label in option(options, "exclude_labels"):
        argv += ["--exclude-label", label]
    for sender in option(options, "exclude_senders"):
        argv += ["--exclude-sender", sender]
    if reasons:
        argv += ["--partial", "; ".join(reasons)]
    return W.main(argv)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ticket_kv", nargs="?", metavar="ticket=<id>", help="the ticket id, as `run` invokes this script — `ticket=<id>`, not a flag")
    args = parser.parse_args(argv)
    if not args.ticket_kv or not args.ticket_kv.startswith("ticket="):
        sys.exit("harvest: pass ticket=<id>, as `run` invokes this script")
    return run(args.ticket_kv[len("ticket="):])


if __name__ == "__main__":
    sys.exit(main())
