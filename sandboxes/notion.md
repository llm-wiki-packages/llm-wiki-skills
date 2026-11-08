# notion

The sandbox for the Notion venue's `harvest` stage. One Notion
workspace's task pull through the `ntn` CLI, Notion's own, against the
public API.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `api.notion.com`: Notion's public API, the only host `ntn` needs here.
  Without `NOTION_API_VERSION` set, `ntn` first dials
  `developers.notion.com` to learn the latest version; that host is left
  out, so the template sets the version instead.

The model endpoints are the harness profile's; see `{{@brain-cli-ops}} reference
harness`.

## Environment

- `NOTION_API_VERSION`: `2025-09-03`. The data-source endpoints a harvest
  queries answer under this version; under `2022-06-28` they refuse
  (`invalid_request_url`).

## Credential

A venue route, `notion`, on the harvest stage: `upstream`
`https://api.notion.com`, `env_var` `NOTION_API_TOKEN`, `credential_format`
`"Bearer {}"`. `skills enable` lists the route among the stage's hosts and
routes before the operator's yes; a peer's commit grants nothing by itself.
The route is the stage's, never the harness profile's: a harness profile's
routes ride every session jail of that harness, in every wiki on the
machine, while this one reaches Notion only from this stage.

The route's token is the wiki's own, in its credential vault, and the
route's name is a binding name. Once per machine that harvests, in this
order: name the vault, `{{@brain-cli}} machine wikis vault <key> local`
(`<key>` is this wiki's key in `{{@brain-cli}} machine wikis ls`; the doctor's
`credentials` row names the same line); store the Notion bot token with the
host it may be spent at, `{{@brain-cli-ops}} credentials set notion` with
`{"value": "<token>", "host": "api.notion.com"}` at its prompt; map the
route, `{{@brain-cli-ops}} credentials bind skill channel-notion-tasks
notion=notion`; then enable the skill, whose probe spends that entry inside
the jail and fails on an unmapped route. `skills enable` maps nothing: it
lists `notion` as unmapped, with that line. `sandboxes
compose` adds the `credential_key` and the capture that read the mapped
name, so the template carries neither. The manifest declares the binding
`"required"`, and no `file` or `dir`, so no payload file is granted.

In the jail `NOTION_API_TOKEN` holds a phantom. The proxy adds the real
token, as `Authorization: Bearer <token>`, only to requests bound for
`api.notion.com`. A machine that maps nothing claims no harvest: `jobs
claim` refuses, "harvest requires notion and this machine fills none of
it". The token never enters the jail, and the jail reads no
`~/.config/notion` and runs no `ntn login`.

## Probe

`ntn whoami` runs after the yes, inside the composed jail of the harvest
stage: exit 0 names the bot and its workspace. It spends the wiki's vault
entry `notion`, so store it first.

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
