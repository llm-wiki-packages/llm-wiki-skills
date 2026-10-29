# study-plan

The sandbox for the study plan's `routine` stage: the scheduled evening
run, with nobody at the keyboard. It reads the syllabus and the quiz logs,
and writes the plan and any exam's study guide under `wiki/`.

## Hosts

None of its own. The model endpoints are the harness profile's; see
`{{@brain-cli-ops}} reference harness`.

## Filesystem

A slice keeps only an in-wiki entry spelled `$WORKDIR/<path>`, so each tree
the run reads is named; `$WORKDIR` alone grants nothing.

- Read `sources/`: the syllabus is a `playbook` page, by convention under
  `sources/playbooks/`, and the learner may move it anywhere in the tree.
- Read `research/`: the quiz logs under `research/logs/`, one page per
  session.
- The `study-plan` and `quiz` overlays sit under the ops dir's `policy`,
  which the stock `_base` already reads: the template names no entry for
  them.
- Write `wiki/`: the plan and the exam guides, created and refreshed through
  the page verbs. The concepts and questions the guides embed are read
  through the same grant.

Nothing here reads or writes `.git`: under the ticket, each write is listed
in the ticket's capture directory, which the runner grants itself, `op
close` posts the run's report there, and the host commits at the landing
(`{{@brain-cli-ops}} reference operations`).

## Credential

None.

## Never loosen

- No write under `sources/`: the syllabus is the learner's, and a run
  nobody is watching never edits it.
- No write under `research/`: the quiz logs are the quiz's record; a plan
  reads them and never rewrites one.
- No write under `.llm-wiki/policy`: an overlay is written by an operator.
