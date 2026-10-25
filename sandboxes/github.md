# github

The sandbox for the GitHub venue. `harvest` reads repo metadata and READMEs
through GitHub's REST API, as the script `scripts/harvest.py` with no model
session. `routine` runs `scripts/lists.py` on a cadence, regenerating the
list pages from the repo pages the harvest and process stages wrote, with no
host. `process` adds nothing to its stock base.

## Hosts

- `api.github.com`: every harvest call — the listings, the repo objects, and
  the READMEs, which `/repos/{owner}/{repo}/readme` serves raw under `Accept:
  application/vnd.github.raw`.

A script stage runs no harness, so no model host joins it. The routine
reaches no host: every fact a list shows is already on a repo page.

## Credential

A venue route, `github`, on the harvest stage: `upstream`
`https://api.github.com`, `env_var` `GITHUB_TOKEN`, `credential_format`
`"Bearer {}"`. The manifest declares the binding `"optional"`: a machine that
maps nothing still harvests, keyless, at 60 requests an hour, and the report
says `keyless`. Mapped, the jail holds a phantom in `GITHUB_TOKEN`,
`harvest.py` sends it on `credential_mode: route`, and the proxy puts the
real token on requests bound for `api.github.com` alone — 5000 requests an
hour.

The token is the wiki's own vault entry: a fine-grained personal access
token with no permissions at all (public repository read is implicit). Once
per machine that harvests: name the vault, `llm-wiki-cli machine wikis
vault <key> local`; store the token with the host it may be spent at,
`llm-wiki-ops credentials set github` with `{"value": "<token>", "host":
"api.github.com"}` at its prompt; enable the skill; then map the route,
`llm-wiki-ops credentials bind skill channel-github github=github`. The
route is the stage's, never the harness profile's.

The routine has no credential.

## Filesystem

The routine reads `sources/`: the repo pages under `sources/github/` and any
GitHub clip still under `sources/clips/` (`references/lists.json`'s `repos`
and `also`). A slice keeps only an in-wiki entry spelled `$WORKDIR/<path>`,
so the tree the run reads is named; `$WORKDIR` alone grants nothing.

Nothing here writes: the routines job's `dest`, `research/github/<slug>`, is
granted read-write by the host, and the list pages land there through `page
create` and `page edit`.

## Customize

- A `repos` or `also` entry in `lists.json` outside `sources/` needs its
  read on the `routine` stage too, spelled `$WORKDIR/<path>`.
- A GitHub Enterprise host is a different venue and a different template.

## Never loosen

- Add no `github.com` and no `raw.githubusercontent.com`: the API serves
  everything the harvest reads, and the web UI is scraping.
- Add no `*.githubusercontent.com` for README images: pages link them.
- Add no route to the harness profile for this venue: a route written there
  reaches this machine's account from every wiki.
- No write under `sources/` on the routine: a list page is regenerated whole,
  and a repo page is the process stage's and the operator's.
- No host on the routine: a fact a list needs that no repo page carries
  belongs in harvest, never in a widened routine.
