# github.routine

The sandbox for the GitHub venue's `routine` stage: `scripts/lists.py`,
run on a cadence by a routines job, regenerating the list pages from the
repo pages the harvest and process stages wrote. No model session and no
host.

## Bins

None: `lists.py` is stdlib only.

## Hosts

None. A script stage runs no harness, and every fact a list shows is
already on a repo page.

## Filesystem

A slice keeps only an in-wiki entry spelled `$WORKDIR/<path>`, so the tree
the run reads is named; `$WORKDIR` alone grants nothing.

- Read `sources/`: the repo pages under `sources/github/` and any GitHub
  clip still under `sources/clips/` (`references/lists.json`'s `repos` and
  `also`).

Nothing here writes: the routines job's `dest`, `research/github/<slug>`,
is granted read-write by the host, and the list pages land there through
`page create` and `page edit`.

## Credential

None.

## Customize

- A `repos` or `also` entry in `lists.json` outside `sources/` needs its
  read here too, spelled `$WORKDIR/<path>`.

## Never loosen

- No write under `sources/`: a list page is regenerated whole, and a repo
  page is the process stage's and the operator's.
- No host: a fact a list needs that no repo page carries belongs in
  harvest, never in a widened routine.

## Profile

```jsonc
// github.routine: the jail of the GitHub list-page routine.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "github-routine",
      "description": "the GitHub list routine: reads the repo pages, no host."
    },
    // No `network`: a script stage runs no harness, and the routine reaches
    // no host.
    "filesystem": {
      // The repo pages and any GitHub clip still under sources/clips/.
      "read": [
        "$WORKDIR/sources"
      ]
    }
  }
}
```
