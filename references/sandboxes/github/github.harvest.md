# github.harvest

The sandbox for the GitHub venue's `harvest` stage: repo metadata and READMEs
through GitHub's REST API. The stage is a script, `scripts/harvest.py`, with
no model session.

## Bins

None: `harvest.py` is stdlib only.

## Hosts

- `api.github.com`: every call — the listings, the repo objects, and the
  READMEs, which `/repos/{owner}/{repo}/readme` serves raw under `Accept:
  application/vnd.github.raw`.

A script stage runs no harness, so no model host joins it.

## Credential

A venue route, `github`, in this sandbox's `## Machine` block below:
`upstream` `https://api.github.com`, `env_var` `GITHUB_TOKEN`,
`credential_format` `"Bearer {}"`. The manifest declares the binding
`"optional"`: a machine that maps nothing still harvests, keyless, at 60
requests an hour, and the report says `keyless`. Mapped, the jail holds a
phantom in `GITHUB_TOKEN`, `harvest.py` sends it on `credential_mode: route`,
and the proxy puts the real token on requests bound for `api.github.com`
alone — 5000 requests an hour.

The token is the wiki's own vault entry: a fine-grained personal access
token with no permissions at all (public repository read is implicit). Once
per machine that harvests: name the vault, `llm-wiki-cli machine wikis
vault <key> local`; store the token with the host it may be spent at,
`llm-wiki-ops credentials set github` with `{"value": "<token>", "host":
"api.github.com"}` at its prompt; enable this sandbox; bind the stage; then
map the route, `llm-wiki-ops credentials bind skill channel-github
github=github`. The route is the stage's, never the harness profile's.

## Customize

- Nothing. A GitHub Enterprise host is a different venue and a different
  sandbox.

## Never loosen

- Add no `github.com` and no `raw.githubusercontent.com`: the API serves
  everything this stage reads, and the web UI is scraping.
- Add no `*.githubusercontent.com` for README images: pages link them.
- Add no route to the harness profile for this venue: a route written there
  reaches this machine's account from every wiki.

## Profile

```jsonc
// github.harvest: the jail of a GitHub harvest stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "github-harvest",
      "description": "the GitHub harvest slice: this venue's API host."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue: GitHub's REST API, listings and READMEs alike.
        "api.github.com"
      ]
    }
  }
}
```

## Machine

The venue route, as a nono fragment `skills install` writes to the
template's `machine.allow`. Nothing in it names a machine path.

```json
{
  "network": {
    "credentials": ["github"],
    "custom_credentials": {
      "github": {
        "upstream": "https://api.github.com",
        "env_var": "GITHUB_TOKEN",
        "credential_format": "Bearer {}"
      }
    }
  }
}
```
