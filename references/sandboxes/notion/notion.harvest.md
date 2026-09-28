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

Not a venue route. `ntn` owns its own login — its bot token needs no
refresh — so it is never stored in a wiki's vault, and this reference
carries no machine-owned block, no `network.custom_credentials`, no
`credential_capture`. This wiki writes no route for it at all.

Reaching Notion is the harness profile's job instead: this machine's admin
hand-writes a `notion` route into it — nothing mints this one, so every
field is theirs to type. Its own facts, whatever shape the profile takes:
named `notion`; `upstream` `https://api.notion.com`; `env_var`
`NOTION_API_TOKEN`; `credential_format` `"Bearer {}"`; `credential_key`
`cmd://notion`; a capture whose command begins with `ntn`'s own absolute
path on this machine — never the bare name — then `auth`, `token`; and a
`timeout_secs` of its own. The profile's shape — where a route nests, and
what else a complete profile must carry — is `llm-wiki-ops reference
harness`, not restated here.

A route added to the harness profile that this machine falls back to
reaches every session jail of that harness, in every wiki on this machine.

A profile scoped to this wiki alone is never merged with that fallback —
it replaces it outright — so it must be a complete profile in its own
right, per that same reference; a file holding only the `notion` route
refuses every spawn. Once it is complete, its routes reach every session
jail of that harness in this wiki — not harvest's alone — and none of
another wiki's.

Once the route exists, a spawned harvest session's environment always
holds a phantom `NOTION_API_TOKEN` value; the proxy adds the real token,
as `Authorization: Bearer <token>`, only to requests bound for
`api.notion.com` — everywhere else the phantom stands. The token itself
never enters the jail, and the jail reads no `~/.config/notion`. Until the
admin adds the route, this unit's harvest has no way to reach Notion under
the proxy.

## Customize

- `NOTION_API_VERSION`, if Notion retires `2025-09-03`. Check every harvest
  command under the new version before changing it.

## Never loosen

- Add no `notion.so` or `www.notion.so` host: `api.notion.com` is the only
  source, and fetching a page's web view is improvising another.
- Add no `developers.notion.com`: set the version instead.
- Add no `~/.config/notion` read: the route carries the token, and the
  login stays outside the jail.

## Profile

```jsonc
// notion.harvest: the jail of a Notion harvest stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "notion-harvest",
      "description": "the Notion harvest slice: this venue's API host."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue: Notion's public API, the one host `ntn` calls.
        "api.notion.com"
      ]
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
