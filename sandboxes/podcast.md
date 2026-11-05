# podcast

The sandbox for the podcast's `routine` stage: the scheduled run, with
nobody at the keyboard. It reads the pages an episode covers and writes the
episode page under `wiki/podcasts/`. It never makes audio: the `narrate`
engine needs the host's model caches and voices, and renders the page on
the host's own pass.

## Hosts

None of its own. The model endpoints are the harness profile's; see
`{{@brain-cli-ops}} reference harness`.

## Filesystem

A slice keeps only an in-wiki entry spelled `$WORKDIR/<path>`, so each tree
the run reads is named; `$WORKDIR` alone grants nothing.

- Read `.git`: `git changed` lists what changed in `sources/` inside the
  window, which the last unfocused episode's `window_until` opens.
- Read `sources/` and `research/`: the lectures, notes and reading an
  episode covers.
- The `podcast` overlay sits under the ops dir's `policy`, which the stock
  `_base` already reads: the template names no entry for it.
- Write `wiki/`: the episode, created and refreshed through the page verbs.
  A focus that names wiki pages is read through the same grant.

Nothing here writes `.git`: under the ticket, each write is listed in the
ticket's capture directory, which the runner grants itself, `op close`
posts the run's report there, and the host commits at the landing
(`{{@brain-cli-ops}} reference operations`).

## Credential

None.

## Never loosen

- No write under `sources/` or `research/`: an episode reads the
  learner's pages and never edits one.
- No host, no machine read: the engine, its model and the voices stay on
  the host, outside every jail.
- No write under `.llm-wiki/policy`: an overlay is written by an operator.
