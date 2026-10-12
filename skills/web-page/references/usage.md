# web-page — usage

A script unit: its one stage runs no model session. The runner starts

```sh
llm-wiki-ops run ops/skills/web-page/scripts/fetch.py ticket=<id>
```

There is no hand-run form; the script runs only through the runner, and
`tickets run <id> spawn=self` is refused for this unit's ticket.

## Argv

`fetch.py` takes one argument, `ticket=<id>`, not a flag. Without it, or with
an empty id, it exits naming the missing argument.

## What it reads off the ticket

Through `tickets open <id> stage=harvest`: `target` (only `http` and `https`
are fetched), `capture_dir`, `slug`, `known[]` and `refresh`. It posts
`tickets update` itself and never closes its ticket.

## Knobs

None: the unit declares no `watch.inputs` and no defaults. A target already in
`known[]` is `ok` with nothing captured, unless the ticket is a refresh. See
SKILL.md "What it does" for the outcomes.
