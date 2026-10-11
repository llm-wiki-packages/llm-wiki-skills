# daily-report.routine

The sandbox for the daily report's `routine` stage: the scheduled morning
run, with nobody at the keyboard. It reads the wiki and writes the day's
report and its promotions under `wiki/`.

## Bins

None.

## Hosts

None of its own. The model endpoints are the harness profile's; see
`llm-wiki-ops reference harness`.

## Filesystem

- Read: the whole wiki. The run reads the channel ledgers under
  `research/channels/`, the ops digest under `research/reports/`, the
  profile, the previous report and the template.
- Write: `wiki/`. The report's markdown and HTML under `wiki/reports/`,
  the promotions on existing `wiki/` pages and the entity stubs, and the
  `wiki/log.md` and `wiki/index.md` entries.

`op open`, `op close`, `git commit` and the routine report ask nothing of
this file, and it could grant them nothing: the commit route (`.git`, and
the wiki's git lock under `.llm-wiki.local/`) is the runner's to grant and
the floor refuses a sandbox naming it, and the runner grants the ticket's
capture directory itself.

## Credential

None.

## Customize

- A cross-wiki what's-new the overlay names is a read of another wiki,
  which this sandbox does not grant: the run notes the denied read and
  skips that wiki. Grant the peer's path read-only in the enabled copy and
  an allow file, never here.

## Never loosen

- No `.llm-wiki/policy`: an overlay is written by an operator answering
  `/daily-report setup`, never by a run nobody is watching.
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
      "description": "the scheduled daily report: reads the wiki, writes `wiki/`."
    },
    // No `network`: the harness profile supplies the model hosts, and the
    // run reaches no other.
    "filesystem": {
      "read": [
        "$WORKDIR"
      ],
      // `wiki/` alone: the report, its promotions, and the log and index
      // entries. An overlay is the operator's, so `.llm-wiki/policy` stays
      // out.
      "allow": [
        "$WORKDIR/wiki"
      ]
    }
  }
}
```
