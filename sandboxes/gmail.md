# gmail

The sandbox for the Gmail venue's `harvest` stage. One mailbox's pull
through the account's Gmail connector. The slice fetches nothing else.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `gmailmcp.googleapis.com`: the Gmail connector's MCP endpoint (`claude mcp
  list`), and the host this unit's credential is spent at.

The model endpoints are the harness profile's; see `{{@brain-cli-ops}} reference
harness`.

## Credential

`requires.credentials.file: "required"`: the slot's value is granted per spawn as the
slice's own copy of a payload file, and it may be spent only at
`gmailmcp.googleapis.com`, the exact `host:` keyword the manifest claims. A
slot and not a route: the value is never read, and a route would put it on
the connector's own requests. Whether a jailed `claude -p` loads
account connectors at all is unmeasured (llm-wiki-plugins#2282); a stage
runs only in its jail, so harvest is expected to fail until it does, unless
this machine's operator lists the unit in `[unsandboxed]` for this wiki.

## Customize

- Nothing. Every mailbox reaches the same endpoint.

## Never loosen

Add no Google host besides the connector's: `mail.google.com` is fetched by
no step.
