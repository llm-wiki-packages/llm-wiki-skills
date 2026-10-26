# circle

The sandbox for the Circle venue's `harvest` stage. A Circle.so community's
harvest: the SPA's pages, its signed HLS media and its asset CDN, rendered
in a persistent-profile Chrome.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `circle.so`: the platform apex.
- `*.circle.so`: every community subdomain, and the media and asset hosts
  under it (`cdn-media.circle.so`, `assets-v2.circle.so`).

The model endpoints are the harness profile's; see `{{@brain-cli-ops}} reference
harness`.

## Filesystem

`machine_reads: playwright-cache`: read on Playwright's browser build
(`$HOME/.cache/ms-playwright` on Linux, `$HOME/Library/Caches/ms-playwright`
on macOS), which the capture scripts launch.

## Credential

`requires.credentials.dir` is `"required"`. A members-only community replays the
per-domain login profile `{{@brain-cli-ops}} credentials login <domain>` minted:
mapped to the job (`credentials bind job <slug> dir=<domain>`), it is
granted to this slice read-write and the ticket hands it over as
`credential_dir`, which `capture_lesson.py` reads off `tickets open`.
Unmapped, this machine claims no harvest of the job. A slot and not a route:
the profile carries the `cf_clearance` Chrome replays, and no proxy can
inject a browser session.

## Customize

- A custom-domain community: its host is the ticket's own and joins the
  slice's egress at dispatch, so it needs no entry here.
- Wistia-embedded lessons: `fast.wistia.com`, `fast.wistia.net` and
  `embed-cloudfront.wistia.com` only if the operator wants those lessons
  fetched without a per-job widen.

## Never loosen

Do not widen `*.circle.so` to `*`, and add no host a lesson did not name in
a report's `missing[]`.
