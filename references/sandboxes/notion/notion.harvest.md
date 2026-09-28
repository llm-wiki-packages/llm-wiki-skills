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

A proxy route, never a payload file. The machine block below adds a
`notion` credential route: the supervisor runs `ntn auth token` outside
the jail, and the proxy adds `Authorization: Bearer <token>` to requests
bound for `api.notion.com`. Inside the jail `NOTION_API_TOKEN` holds a
phantom value, and the token itself never enters the jail. The jail reads
no `~/.config/notion`.

Only a machine may add a route. The block below is this machine's allow
fragment for it, applied when the operator enables the sandbox; a wiki
template never carries it.

## Machine

`{bin:ntn}` is resolved on the machine, as `requires.bins` is. Never
write a machine path here. `credential_capture` runs on the supervisor
side, through nono's own PATH lookup, so its command takes the bare
name (`"ntn"`), never a `{bin:}` placeholder.

```json
{
  "network": {
    "credentials": ["notion"],
    "custom_credentials": {
      "notion": {
        "upstream": "https://api.notion.com",
        "credential_key": "cmd://notion",
        "env_var": "NOTION_API_TOKEN",
        "credential_format": "Bearer {}"
      }
    }
  },
  "credential_capture": {
    "notion": {
      "command": ["ntn", "auth", "token"],
      "timeout_secs": 10,
      "cache_ttl_secs": 900
    }
  }
}
```

## Probe

Confirms the route inside the composed jail: exit 0 names the bot and its
workspace.

```json
["{bin:ntn}", "whoami"]
```

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
