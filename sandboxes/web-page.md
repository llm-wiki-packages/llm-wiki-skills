# web-page

The sandbox for the web-page unit, whose `harvest` stage is the script
`scripts/fetch.py`: one page fetched with no model session, ever. The
template adds nothing to the stock `harvest` and `routine` bases.

## Hosts

None of its own. The page's host is the ticket's and joins the slice's
egress at dispatch; a script stage runs no harness, so no model host joins
it.

## Credential

None.

## Customize

- Nothing. A site that needs a host the page did not name belongs in a
  per-job widen, never in this template.

## Never loosen

- Add no host: the template stays host-free so that a ticket's host is the
  only one a fetch can reach.
