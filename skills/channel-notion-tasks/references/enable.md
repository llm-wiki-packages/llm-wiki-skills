# channel-notion-tasks — after enabling

1. Ask a slug and a description, then declare the job:
   `llm-wiki-ops pipeline jobs add notion-tasks slug=notion-tasks
   description="<what this is>" skill=channel-notion-tasks
   options.workspace=<workspace> [every=1d]` — the target is a bare channel
   NAME, never a url, and a wiki holds ONE job per target: a second workspace
   needs its own name (`acme-tasks`), reused as its slug. `add` refuses
   without `options.workspace` (the skill's one required input). The manifest's `watch.dest` puts its daily
   ledgers under `research/channels/<slug>/` — the ledger route, outside the
   searchable corpus and the curation lifecycle (tasks are a stream; the
   wiki's synthesize policy is how their substance reaches `wiki/`). The
   watch's own `_raw/<slug>/` is already machine-local by construction, so
   there is nothing else to seed.
   **A job declared before this skill's 1.7.0 MUST be re-pointed before its
   next pull — this is not optional.** Such a job keeps its staged literal,
   `sources/tasks/<slug>/`, and `dest` is the whole of the route: it is where
   the skill's process step writes the day's ledger, and it is what the host
   reads to decide what a day directory is. A dest outside
   `research/channels/` puts a `type: ledger` page in the corpus, staged and
   in the curation lifecycle, where a ledger does not belong — and sends the
   day directory down the one-page-per-capture route, which is not what a
   channel harvest leaves. The skill cannot detect it: a harvest ticket's
   `dest` is null. Check each job with `llm-wiki-ops pipeline jobs show <slug>` (it
   names `dest` and the target), and re-point any that is not under
   `research/channels/`. `pipeline jobs edit` refuses `dest`, but re-running `add`
   with the same target and slug moves it and keeps every other key:
   `llm-wiki-ops pipeline jobs add <its target> slug=<slug> dest=research/channels/<slug>`.
2. **The credential: the wiki's vault, never a login.** Harvest reaches Notion
   through the `notion` route in its sandbox (the sandbox reference's
   `## Credential` section spells it out), and the route's token is the
   wiki's own. On each machine that pulls, store the Notion bot token for
   the workspace the job names, on stdin and never on a command line:

   ```sh
   llm-wiki-ops credentials set notion
   ```

   No `ntn login`, and no route in a harness profile: the jail holds a
   phantom and the proxy supplies the token to `api.notion.com` alone.
   Without the token a harvest reports `failed`, `auth`, on
   `api.notion.com`.

   ```sh
   llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/notion/notion.harvest.md
   ```
3. **No credential to bind, and why.** `requires.credential` stays `false`:
   `true` asks each machine to `credentials bind` a payload the slice is
   handed, and this skill reads none. Its credential is the sandbox's
   `notion` route, resolved from the wiki's vault on whichever machine runs
   the harvest. Where more than one machine has the skill enabled, pin the
   job to one that holds the token: `llm-wiki-ops pipeline jobs edit
   <slug> harvest.machine=<machine id>`.
