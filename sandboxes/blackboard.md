# blackboard

The sandbox for the Blackboard venue. The unit declares no stage: it runs by
hand, in the operator's session, so `routine` adds nothing to its stock base
and no host is granted here.

## What a session reaches

`bb.py` drives Playwright's browser build against the institution's
Blackboard host and the `*.blackboardcdn.com` CDN every `/bbcswebdav/` file
redirects to. A scheduled stage, if one is ever added, names those hosts
here.

The model endpoints are the harness profile's; see `{{@brain-cli-ops}} reference
harness`.

## Credential

A `kind=dir` credential, `login=browser`: the persistent browser profile the
operator signed in to, plus the session cookies `bb.py` saves beside it.

## Never loosen

Do not widen to `*`. Off-site links (`external.json`) are not fetched by the
unit, so no video host belongs here.
