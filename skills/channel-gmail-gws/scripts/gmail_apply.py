#!/usr/bin/env python3
"""Apply an attended mode's label/archive/read/star verdicts — and nothing else.

  gmail_apply.py --from verdicts.json --writes label,archive [--apply]
                 [--create-labels] [--config-dir DIR]

`verdicts.json` is the mode's list, `[{"id": "<msg-id>", "action": "<a>"}]`,
where an action is `report`, `draft`, `archive`, `read`, `star` or
`label:<Name>`. `report` and `draft` are skipped (drafts are
`gmail_draft.py`'s). Every other action must be in `--writes`, the
playbook's `writes:` list, or the whole run refuses before calling anything.
Without `--apply` it prints the batches it would make and writes nothing.

`archive` removes INBOX, `read` removes UNREAD, `star` adds STARRED,
`label:<Name>` adds that user label — resolved by name once; a name the
mailbox lacks is refused unless `--create-labels`. The one write is
`messages batchModify`, 100 ids a call: no trash, no delete, no send.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import gwscli

KINDS = {"archive": ([], ["INBOX"]), "read": ([], ["UNREAD"]), "star": (["STARRED"], [])}
SKIPPED = {"report", "draft"}
CHUNK = 100


def kind_of(action: str) -> str:
    return "label" if action.startswith("label:") else action


def batches(verdicts: list, writes: set) -> tuple[dict, list]:
    """`({(action): [ids]}, refusals)` — the whole plan, judged before any call."""
    plan, refused = {}, []
    for row in verdicts:
        mid, action = str(row.get("id") or ""), str(row.get("action") or "")
        if not mid or action in SKIPPED or not action:
            continue
        kind = kind_of(action)
        if kind not in {*KINDS, "label"} or (kind == "label" and not action[len("label:"):].strip()):
            refused.append(f"{mid}: `{action}` is not an action this script performs")
        elif kind not in writes:
            refused.append(f"{mid}: `{kind}` is not in --writes {sorted(writes)}")
        else:
            plan.setdefault(action, []).append(mid)
    return plan, refused


def label_ids(names: set, create: bool, config_dir: str | None) -> dict:
    found = gwscli.call(["gmail", "users", "labels", "list", *gwscli.params()], config_dir).get("labels") or []
    known = {str(one.get("name")): str(one.get("id")) for one in found if isinstance(one, dict)}
    out = {}
    for name in sorted(names):
        if name in known:
            out[name] = known[name]
        elif create:
            made = gwscli.call(["gmail", "users", "labels", "create", *gwscli.params(), "--json",
                                json.dumps({"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"})], config_dir)
            out[name] = str(made.get("id"))
        else:
            raise SystemExit(f"gmail_apply: the mailbox has no label {name!r} — pass --create-labels if the playbook allows it")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="source", required=True, help="the verdicts, a JSON list of {id, action}")
    ap.add_argument("--writes", default="", help="the playbook's `writes:`, comma-separated: label, archive, read, star")
    ap.add_argument("--apply", action="store_true", help="perform the batches; without it, print them")
    ap.add_argument("--create-labels", action="store_true", help="create a label the mailbox lacks")
    ap.add_argument("--config-dir", help="the gws login directory for this mailbox")
    a = ap.parse_args(argv)
    verdicts = json.loads(Path(a.source).read_text(encoding="utf-8"))
    writes = {w.strip() for w in a.writes.split(",") if w.strip()}
    plan, refused = batches(verdicts if isinstance(verdicts, list) else [], writes)
    if refused:
        print("gmail_apply: refused, nothing applied:\n  " + "\n  ".join(refused), file=sys.stderr)
        return 2
    summary = {action: len(ids) for action, ids in plan.items()}
    if not a.apply:
        print(json.dumps({"applied": False, "would": summary}))
        return 0
    try:
        labels = label_ids({action[len("label:"):].strip() for action in plan if kind_of(action) == "label"}, a.create_labels, a.config_dir)
        for action, ids in plan.items():
            add, remove = KINDS.get(action, ([labels.get(action[len("label:"):].strip())], []))
            for at in range(0, len(ids), CHUNK):
                body = {"ids": ids[at:at + CHUNK], "addLabelIds": add, "removeLabelIds": remove}
                gwscli.call(["gmail", "users", "messages", "batchModify", *gwscli.params(), "--json", json.dumps(body)], a.config_dir)
    except gwscli.GwsError as exc:
        print(f"gmail_apply: {exc.said}", file=sys.stderr)
        return 1
    print(json.dumps({"applied": True, "moved": summary}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
