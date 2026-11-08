# youtube-watch-gemini

The sandbox for `channel-youtube-watch-gemini`. `enrich` sends one request
per video to Google's Gemini API, as the script `scripts/watch_gemini.py`
with no model session: the video's url and the question go out, the notes
come back. `routine` adds nothing to its stock base.

## Hosts

- `generativelanguage.googleapis.com`: the Gemini API, and the host this
  unit's credential is spent at: the exact `host:` keyword the manifest
  claims.

A script stage runs no harness, so no model host joins it.

## Credential

A venue route, `gemini`, on the enrich stage: `upstream`
`https://generativelanguage.googleapis.com`, `env_var` `GEMINI_API_KEY`,
`inject_header` `x-goog-api-key`, `credential_format` `"{}"`. The manifest
declares the binding `"required"`: with no route mapped, the claim gate
holds the stage back. Mapped, the jail holds a phantom in `GEMINI_API_KEY`,
`watch_gemini.py` sends it on `credential_mode: route`, and the proxy puts
the real key on requests bound for this host alone. The key never enters
the jail.

The key is the wiki's own vault entry. Once per machine that enriches: store
the key with the host it may be spent at, `{{@brain-cli-ops}} credentials
set gemini` with `{"value": "<key>", "host":
"generativelanguage.googleapis.com"}` at its prompt; enable the skill; then
map the route, `{{@brain-cli-ops}} credentials bind skill
channel-youtube-watch-gemini gemini=gemini`.

## Customize

- Nothing in the default needs widening. A different Gemini endpoint is a
  different template.

## Never loosen

- Add no other Google host. The one call is the Interactions endpoint under
  the host above; nothing is uploaded and nothing is fetched from the
  video's own hosts.
