# daily-report.routine

The sandbox for the daily report's `routine` stage: the scheduled morning
run, with nobody at the keyboard. It reads what the report is made from and
writes the day's report and its promotions under `wiki/`.

## Bins

None.

## Hosts

None of its own. The model endpoints are the harness profile's; see
`llm-wiki-ops reference harness`.

## Filesystem

A slice keeps only an in-wiki entry spelled `$WORKDIR/<path>`, so each tree
the run reads is named; `$WORKDIR` alone grants nothing.

- Read `.git`: `op latest`, `op since` and `git changed`, which fix the
  window and say what the wiki did. It also exposes every committed file's
  content and `.git/config`'s remote urls, so this list is not a read
  boundary; the grant stays because those three need it.
- Read `.llm-wiki/policy`: the `daily-report` overlay and the
  `daily-report-setup` marker. Unreadable, `policy get` answers no overlay
  and the run reports on stock alone.
- Read `research/`: the channel ledgers under `research/channels/` and the
  ops digest under `research/reports/`.
- Read `sources/`: `page lint` sweeps it beside `wiki/`, and skips a tree it
  cannot read without saying so, so the report's `lint:` would undercount.
- Write `wiki/`: the report's markdown and HTML under `wiki/reports/`, the
  promotions on existing `wiki/` pages and the entity stubs, and the
  `wiki/log.md` and `wiki/index.md` entries. The profile, the previous
  report and the template are read through the same grant.

Nothing here writes `.git`: under the ticket, each write is listed in the
ticket's capture directory, which the runner grants itself — a verb's by the
verb, a Write or Edit by the wiki's `op record` hook — `op close` posts the
run's report there, and the host commits at the landing
(`llm-wiki-ops reference operations`).

## Credential

None.

## Customize

- A cross-wiki what's-new is an attended run's: the run finds a peer's path
  through the machine config, which no sandbox grant reaches, so a
  scheduled run notes each wiki the overlay names and skips it.

## Never loosen

- No write under `.llm-wiki/policy`: an overlay is written by an operator
  answering `/daily-report setup`, never by a run nobody is watching.
- No machine registry: every writer of it runs on the host.
- No write under `sources/` or `research/`: the run promotes into `wiki/`
  and nowhere else.

## Profile

```jsonc
// daily-report.routine: the jail of the scheduled daily report.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "daily-report-routine",
      "description": "the scheduled daily report: reads its inputs, writes `wiki/`."
    },
    // No `network`: the harness profile supplies the model hosts, and the
    // run reaches no other.
    "filesystem": {
      // Each tree by name: a slice drops a bare `$WORKDIR`. `.git` fixes the
      // window, `.llm-wiki/policy` is the overlay, `research/` the ledgers
      // and the digest, `sources/` what `page lint` sweeps beside `wiki/`.
      "read": [
        "$WORKDIR/.git",
        "$WORKDIR/.llm-wiki/policy",
        "$WORKDIR/research",
        "$WORKDIR/sources"
      ],
      // `wiki/` alone: the report, its promotions, and the log and index
      // entries. An overlay is the operator's to write.
      "allow": [
        "$WORKDIR/wiki"
      ]
    }
  }
}
```
