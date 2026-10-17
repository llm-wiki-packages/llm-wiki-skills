# circle.harvest

The sandbox for the Circle venue's `harvest` stage. A Circle.so community's
harvest: the SPA's pages, its signed HLS media and its asset CDN, rendered
in a persistent-profile Chrome.

## Bins

None declared. The capture drives Chrome, which the harvesting machine
supplies.

## Hosts

- `api.anthropic.com`, `api.openai.com`, `chatgpt.com`: the model endpoints.
  A slice needs one to run at all.
- `circle.so`: the platform apex.
- `*.circle.so`: every community subdomain, and the media and asset hosts
  under it (`cdn-media.circle.so`, `assets-v2.circle.so`).

## Filesystem

Read on Playwright's browser build (`$HOME/.cache/ms-playwright` on Linux,
`$HOME/Library/Caches/ms-playwright` on macOS), which the capture
scripts launch.

## Credential

`requires.credentials.dir` is `"required"`. A members-only community replays the
per-domain login profile `llm-wiki-ops credentials login <domain>` minted:
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

## Profile

```jsonc
// circle.harvest: the jail of a Circle harvest stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "circle-harvest",
      "description": "the Circle harvest slice: the model endpoints and this venue's hosts."
    },
    "filesystem": {
      // Playwright's browser build: Linux, then macOS. A path absent on
      // this machine grants nothing.
      "read": [
        "$HOME/.cache/ms-playwright",
        "$HOME/Library/Caches/ms-playwright"
      ]
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The model endpoints: a slice needs one to run at all.
        "api.anthropic.com",
        "api.openai.com",
        "chatgpt.com",
        // The venue.
        "circle.so",
        "*.circle.so"
      ]
    }
  }
}
```
