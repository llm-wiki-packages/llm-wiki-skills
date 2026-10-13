# channel-gmail-gws — the profile interview (`setup`)

The profile is this unit's policy overlay: the operator's own rules, which
the process step junks and categorizes by and every attended mode classifies
and drafts by. Run with the operator at the keyboard; nothing is written
without their yes. With nobody to answer, `setup` writes nothing and says so.

## 1. Read what is there

```sh
llm-wiki-ops policy get channel-gmail-gws
```

Read the wiki's `AGENTS.md` and `wiki/profile/` too: people the wiki
already knows are VIP candidates. If a pipeline job has run, the recent
ledgers under `research/channels/<slug>/` show who writes most.

## 2. Ask, one section at a time

Propose entries from what you read; the operator edits. An empty section
means "no opinion".

## 3. Save — the whole text, on the operator's yes

`llm-wiki-ops policy set channel-gmail-gws`, the full overlay on stdin (the
old text plus the changes; a set replaces). The shape, freeform markdown and
never a schema:

```markdown
## Identity

- mailboxes: me@acme.example (job acme-mail)
- also-me: me@personal.example — counts as "me" for unanswered threads

## $vips — always surfaced first, always worth a reply

- partner@example.com, @bigclient.example

## $family — personal, never archived

## $waiting — people I am waiting on right now

## $noise — safe to archive unread

## $receipts — keep, label Receipts, never reply

## $newsletters — read in a digest, not the inbox

## Label map

- receipts → Receipts; newsletters → Newsletters; waiting → Waiting; action → Action

## Draft voice

- warm, direct, 2–5 sentences; answer the question first
- sign-off: "— <name>"
- never commit to dates, money, legal or medical positions: "let me confirm"

## Hours

- 08:00–18:00 local; outside them nothing is urgent unless a $vips subject says so

## Hard rules (win over any playbook)

- Never archive mail from $family or $vips.
- School, medical, legal → needs-reply or action, never noise.
```

A wiki playbook goes in the same overlay as `## Playbook: <name>`, in the
shape of `llm-wiki-ops reference channel-gmail-gws/playbook-template`.

## 4. After a run, suggest

A sender seen three times or more in no list is a suggestion for `$noise`,
`$newsletters` or `$receipts` — offered, saved only on a yes.
