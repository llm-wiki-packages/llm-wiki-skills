# gmail-gws.harvest

The sandbox for the gmail-gws venue's `harvest` stage. One mailbox's pull
through the `gws` CLI (Google's Workspace CLI) against the Gmail API, run by
the unit's `scripts/harvest.py` with no model session.

## Bins

- `gws`: the Google Workspace CLI. The unit declares it in `requires.bins`;
  enabling the unit resolves it on the machine.

## Hosts

- `gmail.googleapis.com`: the Gmail API — `getProfile`, `messages list`,
  `messages get`, the only methods the harvest calls.
- `oauth2.googleapis.com`: where gws trades the login's refresh token for an
  access token, about once an hour of use.
- `www.googleapis.com`: where gws fetches the Gmail discovery document it
  builds every call from. It caches the document under the login directory's
  `cache/`, so a warm login may never dial it (unverified how long the cache
  is trusted).

The model endpoints are the harness profile's; a script stage runs no
harness and gets none.

## Credential

`requires.credentials.dir` is `"required"`: the job's gws login directory, a
`GOOGLE_WORKSPACE_CLI_CONFIG_DIR` holding a READ-ONLY Gmail login, adopted
as a `dir` credential and bound to the job (`credentials bind job <slug>
dir=<name>`). The slice is granted that directory alone, read-write — gws
rewrites its token cache there — and the ticket hands it over as
`credential_dir`, which `harvest.py` points gws at. A slot and not a route:
gws mints its own short-lived access tokens from the refresh token, which no
proxy can inject. Unmapped, this machine claims no harvest of the job.

The login is made with `GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file`, so the
key that decrypts it sits in the directory and not in the macOS keychain a
jail cannot reach; `harvest.py` sets the same backend for every gws call.
That a jailed gws refreshes and reads through this grant is unverified by a
live run.

## Customize

- Nothing. Every mailbox reaches the same three hosts.

## Never loosen

- Add no `mail.google.com`: the web UI is fetched by no step.
- Add no Google host for Drive, Calendar or any other service: this login is
  Gmail's, read-only.
- Never bind a login with a Gmail write scope: any of them can also send, and
  this stage runs unattended.

## Profile

```jsonc
// gmail-gws.harvest: the jail of a gmail-gws harvest stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "gmail-gws-harvest",
      "description": "the gmail-gws harvest slice: the Gmail API through gws."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue: the Gmail API.
        "gmail.googleapis.com",
        // gws's token refresh.
        "oauth2.googleapis.com",
        // gws's discovery document, when its cache is cold.
        "www.googleapis.com"
      ]
    }
  }
}
```
