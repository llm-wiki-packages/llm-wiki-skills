# notion.harvest

The sandbox for the Notion venue's `harvest` stage. One Notion
workspace's task pull through the `ntn` CLI, Notion's own, against the
public API.

## Bins

- `ntn`: the Notion CLI. A skill declares it in `requires.bins`; enabling
  the skill resolves it on the machine.

## Hosts

- `api.notion.com`: Notion's public API, the only host `ntn` needs here.
  Without `NOTION_API_VERSION` set, `ntn` first dials
  `developers.notion.com` to learn the latest version; that host is left
  out, so the profile sets the version instead.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Environment

- `NOTION_API_VERSION`: `2025-09-03`. The data-source endpoints a harvest
  queries answer under this version; under `2022-06-28` they refuse
  (`invalid_request_url`).

## Credential

A venue route, `notion`, in this sandbox's `## Profile` below: `upstream`
`https://api.notion.com`, `env_var` `NOTION_API_TOKEN`, `credential_format`
`"Bearer {}"`. It is the stage's, never the harness profile's: a harness
profile's routes ride every session jail of that harness, in every wiki on
the machine, while this one reaches Notion only from this stage.

The route's token is the wiki's own, in its credential vault under the
route's name. Mint nothing else: `llm-wiki-ops credentials set notion`, the
Notion bot token on stdin, once per machine that harvests. `sandboxes
compose` adds the capture that reads that name, so the profile carries none.
`requires.credential` stays `false`: nothing is bound to a job and no
payload file is granted.

In the jail `NOTION_API_TOKEN` holds a phantom. The proxy adds the real
token, as `Authorization: Bearer <token>`, only to requests bound for
`api.notion.com`. The token never enters the jail, and the jail reads no
`~/.config/notion` and runs no `ntn login`.

## Customize

- `NOTION_API_VERSION`, if Notion retires `2025-09-03`. Check every harvest
  command under the new version before changing it.

## Never loosen

- Add no `notion.so` or `www.notion.so` host: `api.notion.com` is the only
  source, and fetching a page's web view is improvising another.
- Add no `developers.notion.com`: set the version instead.
- Add no `~/.config/notion` read: the route carries the token, and no login
  is read from the host.
- Add no route to the harness profile for this venue: a route written there
  reaches this machine's account from every wiki.

## Profile

```jsonc
// notion.harvest: the jail of a Notion harvest stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "notion-harvest",
      "description": "the Notion harvest slice: this venue's API host and route."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue: Notion's public API, the one host `ntn` calls.
        "api.notion.com"
      ],
      // The route is named here and stated below; compose resolves its token
      // from this wiki's vault entry of the same name.
      "credentials": ["notion"],
      "custom_credentials": {
        "notion": {
          "upstream": "https://api.notion.com",
          "env_var": "NOTION_API_TOKEN",
          "credential_format": "Bearer {}"
        }
      }
    },
    "environment": {
      "set_vars": {
        // Pinned, so `ntn` never dials developers.notion.com for the latest.
        "NOTION_API_VERSION": "2025-09-03"
      }
    }
  }
}
```
