# channel-github — after enabling

1. **Run setup first**: `/channel-github setup`. It proposes the category
   taxonomy the process step tags with and writes it to the `channel-github`
   overlay. Pages written before a taxonomy exists fall back to GitHub
   topics, and the `retag` mode fixes them later.

2. **The token (recommended).** Keyless harvest runs at 60 API calls an
   hour, enough for a few dozen READMEs a run. The `github` route on the
   harvest stage of the unit's sandbox raises that to 5000 (the sandbox's
   `## Credential` section spells it out). Mint a fine-grained personal
   access token with **no permissions at all** — public repository read is
   implicit. On each machine that harvests, name the wiki's vault, `<key>`
   being this wiki's key in `{{@brain-cli}} machine wikis ls`:

   ```sh
   {{@brain-cli}} machine wikis vault <key> local
   ```

   Store the token, never on a command line, as `{"value": "<token>",
   "host": "api.github.com"}` at the prompt:

   ```sh
   {{@brain-cli-ops}} credentials set github
   ```

   Then, once the skill is enabled, map the route:

   ```sh
   {{@brain-cli-ops}} credentials bind skill channel-github github=github
   ```

   `skills enable --confirm`, which `/{{@brain-plugin}}:enable` runs, maps nothing:
   it lists `github` as unmapped, with that line. The binding is
   `"optional"`, so an unmapped machine still harvests, keyless.

   ```sh
   {{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/github.md
   ```

3. **The harvest jobs.** The target is a bare channel name, and `dest`
   comes from the manifest — `sources/github`, shared by every github
   harvest job; do not override it:

   ```sh
   {{@brain-cli-ops}} jobs add github-stars slug=github-stars skill=channel-github description="My GitHub stars" options.select=stars:<your-login>
   {{@brain-cli-ops}} jobs add github-watch slug=github-watch skill=channel-github description="Orgs and repos I follow" options.select=org:<org>,repo:<owner>/<name>
   ```

   One job per purpose keeps `gh_via` meaningful: stars are what the
   operator chose, a watch is what they follow. `every` defaults to `1d`;
   the first stars run on a large account is capped at `max_captures` and
   catches up over the next runs.

4. **The list routine.** One routines job regenerates the list pages. Name
   its `dest` — `research/github/<slug>`, outside the corpus and curation,
   so a daily regeneration churns nothing; left out, `add` would route it to
   the manifest's `sources/github`:

   ```sh
   {{@brain-cli-ops}} jobs add github-lists routines=channel-github dest=research/github/github-lists every=1d description="GitHub list pages"
   ```

5. **Clipped repos the watches do not cover.** `/channel-github pending`
   lists clips with no GitHub facts and the `repo:` selectors that fill
   them in. Put those on a job of their own:

   ```sh
   {{@brain-cli-ops}} jobs add github-clips slug=github-clips skill=channel-github description="Clipped repos" options.select=<the selectors pending printed>
   ```

6. Enable the skill on every OTHER machine that harvests
   (`/{{@brain-plugin}}:enable channel-github`) — installed is not loaded, and
   enablement never travels with a `git pull`.
