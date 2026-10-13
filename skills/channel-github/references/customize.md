# channel-github — customizing this skill

Most of what a wiki customizes is not in this unit's prose. Three surfaces,
each the wiki's:

1. **The overlay** — `llm-wiki-ops policy get channel-github`, written on
   the operator's yes with `policy set channel-github` (`setup` §3):
   - **Categories** — the taxonomy, one bullet each: the tag, when it
     applies, the GitHub topics that map onto it.
   - **README mode** — `full` (default; best recall), `excerpt` (first ~150
     lines), `none` (pages carry only the summary and facts).
   - **Junk rules** — what earns no page beyond the defaults.
   The process step reads it every run; `retag` re-judges pages already
   landed.

2. **Per job** (`options.*`, at `jobs add` or `jobs edit`):
   - `select` — the selectors. Ask which login's stars, which orgs and which
     repos the wiki follows; suggest one job for stars and one for
     everything followed.
   - `max_captures` (150), `jump_abs` (500), `jump_pct` (25),
     `refresh_days` (90) — how eagerly a held repo is re-captured. Lower the
     jump thresholds for a watch of small repos; raise them for a stars
     list of giants.
   - `include_forks` (false), `include_archived` (true), `search_limit`
     (100).

3. **`references/lists.json`** — this unit's file, edited in place:
   - `repos` (`sources/github`) and `also` (`["sources/clips"]`) — where
     the catalog reads repo pages. A tree outside `sources/` needs its read
     in the `github-routine` sandbox too.
   - `weights` — the rank score: `stars` (× log10 of the count), `starred`,
     `clipped`, `watched`, `recent` (pushed within `recent_days`),
     `archived` (a penalty), `jump` (× log10 of the gain).
   - `lists[]` — `name`, `title`, `intro`, `filter`, `sort`, `limit` (0 =
     all), `format` (`compact` | `table`), `enabled`. Filters: `tags_all`,
     `tags_any`, `tags_none`, `via_prefix` (`stars:`, `org:example-org`),
     `starred`, `min_stars`, `include_archived`, `text`. `"kind":
     "whats-new"` takes `window_days` and `min_jump` instead.
   - `by_category` — one list per category with at least `min` repos:
     `enabled`, `min`, `sort`, `format`, `title` (`{category}` filled in).

Layout choices map like this:

| want | set |
| :--- | :--- |
| repo pages only | `lists: []`, `by_category.enabled: false` |
| compact category lists only (repo pages still exist — they are the data) | `by_category.format: compact`, drop `Top` |
| everything | the shipped default |
| a tighter README | the overlay's README mode `excerpt` |

Customized is the point: an edited `lists.json` makes `skills ls` report the
skill `customized`. That is configuration the wiki owns, not drift to
repair — say so in your report so nobody "fixes" it with `skills install
--force`.

## Sandbox

Two stages bind a sandbox:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/github/github.harvest.md
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/github/github.routine.md
```

`/llm-wiki:sandbox channel-github` reviews them into wiki sandboxes, and
`/llm-wiki:enable channel-github` binds the stages. `process` names no
sandbox and runs with no network.
