# parentsquare

The sandbox for the ParentSquare venue's `harvest` stage: a model session
reading a school feed through `parentsquare-mcp`, a stdio MCP server the
harness starts inside the jail. Read tools only.

`process` and `routine` add nothing to their stock bases.

## Bin

`parentsquare-mcp`, version 0.4.0, the server the unit's `requires.bins`
declares. Install it once with `uv tool install parentsquare-mcp==0.4.0`,
never `uvx`: `uvx` needs a writable uv cache and tool directory, which a
slice does not have. The slice floor grants the bin's toolchain reads
(console script, virtual environment and the Python it runs under), so this
template asks for no machine grant.

## Hosts

- `www.parentsquare.com`: every call the server makes — sign-in, the feed,
  the calendar export and the notices.

Attachment bytes are the one gap. `get_post` fetches an image attachment and
`download_file` any attachment from the URL the page names, and the server's
source says those are S3 or CDN URLs; it pins no host and no run has
measured one. They are refused in this jail and the server reports the
failure. The harvest reads post text, which needs neither.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## MCP

The stage's `mcp` block names the one server the harness starts in the jail.
The cookie, the audit log and the downloads go to the slice's scratch
directory.

## Credential

`requires.credentials.env` declares `PS_USERNAME` and `PS_PASSWORD`, the
only intake the server has in a jail: it falls back to the 1Password or
LastPass CLI otherwise. Each is set to the operator's bound value in the
environment of every process in the jail, so the model can print it;
`skills enable` says how wide the pair is before the yes. The template's
`mcp` block does not mention them: a name the unit declares there refuses at
the slice's start. An account that asks for an emailed MFA code cannot harvest
unattended, and the session reports `auth`.

## Customize

- Attachment hosts, once a real URL names one: add the exact host, never a
  wildcard over a storage provider.

## Never loosen

- Set no `PS_ENABLE_WRITES`: the server's write tools edit the live school
  roster, and this stage only reads.
- Put no credential in the `mcp` block: a secret comes from
  `requires.credentials.env`.
- Point no `PS_*` path at the wiki or the home directory: cookie, audit log
  and downloads live in the slice's `{scratch}`, which is reaped with it.
- Add no other host: `www.parentsquare.com` serves everything the harvest
  reads.
