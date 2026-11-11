# blackboard

The sandbox for the Blackboard venue's `harvest` stage: `bb.py` driving
Playwright's browser build against the institution's Blackboard host, on the
signed-in credential.

`bb.py` is listed under `harvest`, with `credential: true`, so a
`{{@brain-cli-ops}} run` of it (by hand, or as the keepalive check below) runs in
the harvest jail on the credential's slot. Without it, `run` maps `bb.py` to
`routine`, which is handed no credential.

`process` and `routine` add nothing to their stock bases: `process.py`
reads the capture and writes pages, with no network.

## Hosts

- The institution's own host (`learn.example.edu`) is the job's target,
  minted into the slice's egress per ticket; it needs no entry here.
- `blackboard.com`, `*.blackboard.com`: Blackboard-hosted sites.
- `*.blackboardcdn.com`: the CDN every `/bbcswebdav/` file redirects to,
  under a signed URL.
- **The institution's identity provider, per wiki.** Where `options.sso` (or a
  sign-in page with one SAML link) renews an expired session, the browser
  leaves the Blackboard host for the identity provider's sign-in host and
  comes back. Add that host to this wiki's `harvest` stage
  `network.allow_domain`. For Microsoft Entra ID it is
  `login.microsoftonline.com`. Add no other host the identity provider loads
  unless a denial on a renewing harvest names it. The template ships none:
  which identity provider an institution uses is the wiki's fact.

The model endpoints are the harness profile's; see `{{@brain-cli-ops}} reference
harness`.

## Filesystem

`machine_reads: playwright-cache`: read on Playwright's browser build
(`$HOME/.cache/ms-playwright` on Linux, `$HOME/Library/Caches/ms-playwright`
on macOS), which `bb.py` launches.

## Credential

`requires.credentials.dir` is `"required"`: the credential the operator
signed in to with `credentials login`, whose saved browser state `bb.py`'s
launcher seeds Chromium from and saves back to.
Mapped to the job (`credentials bind job <slug> dir=<credential>`), it is
granted to this slice read-write and the ticket hands it over as
`credential_dir`. Unmapped, this machine claims no harvest of the job.

## Never loosen

Do not widen to `*`. Off-site links (`external.json`) are not fetched by the
unit, so no video host belongs here: a course's YouTube videos are a
`channel-youtube` job's.
