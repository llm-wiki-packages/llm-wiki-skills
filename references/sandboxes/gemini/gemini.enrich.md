# gemini.enrich

The sandbox for the `enrich` stage of `channel-youtube-watch-gemini`. One
request per video to Google's Gemini API, sent by a script with no model
session: the video's url and the question go out, the notes come back.

## Bins

None.

## Hosts

- `generativelanguage.googleapis.com`: the Gemini API, and the host this
  unit's credential is spent at: the exact `host:` keyword the manifest
  claims.

A script stage runs no harness, so no model endpoint joins.

## Credential

`requires.credential: true`. The binding's payload file is granted per
spawn, the script reads it by name through the front door and sends it in
the `x-goog-api-key` header, and it may be spent only at the host above.
The reference carries no route, so the key is in the jail for the length of
the run.

## Customize

- A route would keep the key out of the jail: a `network.credentials` entry
  naming one, and a `network.custom_credentials` route with `upstream`
  `https://generativelanguage.googleapis.com`, `env_var` `GEMINI_API_KEY` and
  `inject_header` `x-goog-api-key`. The script already sends the phantom it
  finds in `GEMINI_API_KEY` where the ticket names a route. Unmeasured.

## Never loosen

Add no other Google host. The one call is the Interactions endpoint under
the host above; nothing is uploaded and nothing is fetched from the video's
own hosts.

## Profile

```jsonc
// gemini.enrich: the jail of the Gemini enrich stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "gemini-enrich",
      "description": "the Gemini enrich slice: the one API host."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue.
        "generativelanguage.googleapis.com"
      ]
    }
  }
}
```
