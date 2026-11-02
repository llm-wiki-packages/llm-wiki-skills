# blackboard

The sandbox for the Blackboard venue's `harvest` stage: `bb.py` driving
Playwright's browser build against the institution's Blackboard host, on the
signed-in profile.

`process` and `routine` add nothing to their stock bases: `process.py`
reads the capture and writes pages, with no network.

## Hosts

- The institution's own host (`learn.example.edu`) is the job's target,
  minted into the slice's egress per ticket; it needs no entry here.
- `blackboard.com`, `*.blackboard.com`: Blackboard-hosted sites.
- `*.blackboardcdn.com`: the CDN every `/bbcswebdav/` file redirects to,
  under a signed URL.

The model endpoints are the harness profile's; see `{{@brain-cli-ops}} reference
harness`.

## Filesystem

`machine_reads: playwright-cache`: read on Playwright's browser build
(`$HOME/.cache/ms-playwright` on Linux, `$HOME/Library/Caches/ms-playwright`
on macOS), which `bb.py` launches.

## Credential

`requires.credentials.dir` is `"required"`: the persistent browser profile the
operator signed in to, plus the session cookies `bb.py` saves beside it.
Mapped to the job (`credentials bind job <slug> dir=<credential>`), it is
granted to this slice read-write and the ticket hands it over as
`credential_dir`. Unmapped, this machine claims no harvest of the job.

## Never loosen

Do not widen to `*`. Off-site links (`external.json`) are not fetched by the
unit, so no video host belongs here: a course's YouTube videos are a
`channel-youtube` job's.
