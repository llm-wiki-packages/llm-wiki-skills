# gmail.harvest

The sandbox for the Gmail venue's `harvest` stage. One mailbox's pull
through the account's Gmail connector. The slice fetches nothing else.

## Bins

None.

## Hosts

- `gmailmcp.googleapis.com`: the Gmail connector's MCP endpoint (`claude mcp
  list`), and the host this unit's credential is spent at.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Credential

`requires.credential: true`. The binding's payload file is granted per
spawn, and it may be spent only at `gmailmcp.googleapis.com`, the exact
`host:` keyword the manifest claims. Whether a jailed `claude -p` loads
account connectors at all is unmeasured (llm-wiki-plugins#2282); a stage
runs only in its jail, so harvest is expected to fail until it does, unless
this machine's operator lists the unit in `[unsandboxed]` for this wiki.

## Customize

- Nothing. Every mailbox reaches the same endpoint.

## Never loosen

Add no Google host besides the connector's: `mail.google.com` is fetched by
no step.

## Profile

```jsonc
// gmail.harvest: the jail of a Gmail harvest stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "gmail-harvest",
      "description": "the Gmail harvest slice: this venue's hosts."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue.
        "gmailmcp.googleapis.com"
      ]
    }
  }
}
```
