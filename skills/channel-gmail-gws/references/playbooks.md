# channel-gmail-gws — the playbooks

A playbook is one small file that tells an attended mode what to do. The
mode reads this unit's policy overlay (the profile) first, then the
playbook; later text wins. Each is `llm-wiki-ops reference
channel-gmail-gws/playbook-<name>`.

| playbook | mode | what it does | writes |
| :--- | :--- | :--- | :--- |
| `email-client-triage` | `triage` (default) | the seven-bucket sort of unread mail, proposing actions | none by default |
| `daily-digest` | `digest` (default) | one screen of the last day, grouped | none |
| `newsletter-digest` | `digest` | newsletters distilled into what is worth knowing, and wiki candidates | none |
| `reply-drafts` | `reply` (default) | threaded drafts for direct questions from known people | drafts |
| `followup-chaser` | `followup` (default) | sent threads unanswered for days → nudge drafts | drafts |
| `inbox-zero` | `clean` (default) | label and archive noise, leaving only what needs a person | label, archive (with `--apply`) |
| `vip-watch` | `triage` | only `$vips` and `$family`; everything else counted | star (with `--apply`) |
| `template` | — | the shape to copy into the overlay as `## Playbook: <name>` | — |

## The shape

```
# <name>
purpose: one line
mode: triage | digest | reply | followup | clean
scope:
  query: <gmail search>     # --query overrides
  max: <n>                  # --max overrides
  needs: headers | bodies
categories:                 # first match wins; `default` last
  - name: …
    match: …                # from:, label:, subject~, has:attachment, thread:unanswered, newer:/older:, $list
    action: report | draft | label:<Name> | archive | read | star
    note: how to say it in the report
writes: [label, archive, read, star]   # what --apply may perform; drafts need no entry
drafting:                   # only where an action is draft
  …
output: how the report is laid out
```

A profile list (`$vips`, `$noise`, …) can stand anywhere a `from:` rule can.
`thread:unanswered` means the newest message in the thread is not the
operator's (the profile's `also-me` counts as theirs).
