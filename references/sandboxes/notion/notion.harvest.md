# notion.harvest

The sandbox for the Notion venue's `harvest` stage. One Notion
workspace's task pull through the `ntn` CLI, Notion's own, against the
public API.

## Bins

- `ntn`: the Notion CLI. A skill declares it in `requires.bins`; enabling
  the skill resolves it on the machine.

## Hosts

- `api.anthropic.com`, `api.openai.com`, `chatgpt.com`: the model endpoints.
  A slice needs one to run at all.
- `api.notion.com`: Notion's public API, the only host `ntn` needs here.
  Without `NOTION_API_VERSION` set, `ntn` first dials
  `developers.notion.com` to learn the latest version; that host is left
  out, so the profile sets the version instead.

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
adds a `notion` route to the harness profile, with `upstream`
`https://api.notion.com`, `env_var` `NOTION_API_TOKEN`, `credential_format`
`"Bearer {}"`, and a capture that runs `ntn auth token` outside the jail.
Once the harness profile carries that route, a spawned harvest session sees
`NOTION_API_TOKEN` hold a phantom value on requests bound for
`api.notion.com`; the token itself never enters the jail, and the jail
reads no `~/.config/notion`. Until the admin adds it, this unit's harvest
has no way to reach Notion under the proxy (llm-wiki-plugins#2645).

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
      "description": "the Notion harvest slice: the model endpoints and this venue's API host."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The model endpoints: a slice needs one to run at all.
        "api.anthropic.com",
        "api.openai.com",
        "chatgpt.com",
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
