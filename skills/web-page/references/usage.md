# web-page — usage

A script unit: its one stage runs no model session. The runner starts

```sh
llm-wiki-ops run ops/skills/web-page/scripts/fetch.py ticket=<id>
```

There is no hand-run form (SKILL.md, intro).

## Argv

| script | argv |
| :--- | :--- |
| `fetch.py` | `ticket=<id>`, not a flag; without it, or with an empty id, it exits naming the missing argument |

## Reads off the ticket

`target`, `capture_dir`, `slug`, `known[]` and `refresh`, through
`tickets open <id> stage=harvest`. What it does with them is SKILL.md "What it
does".

## Knobs

None: no `watch.inputs` and no defaults.
