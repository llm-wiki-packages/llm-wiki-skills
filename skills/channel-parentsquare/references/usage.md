# channel-parentsquare — usage

Invoked `/channel-parentsquare ticket=<id>`; the runner adds `stage=<harvest|process>` to the
slice prompt, but the step followed is the `stage` that `tickets open <id>` answers.
No other argument. One invocation serves one account and one day directory.

## Scripts

None. The harvest reads through the `parentsquare` MCP server the sandbox declares, and both
steps write with the front door's verbs.

## Knobs

- `watch.inputs.schools` lands as `options.schools`: comma-separated school ids, blank for every
  school the account lists.
- `watch.inputs.lookback_days` lands as `options.lookback_days` (default 3): the feed history
  each pull reads.
- `process.exclude_rules` feeds the junk rules (SKILL.md, process).
- `requires.credentials.env` is `PS_USERNAME` and `PS_PASSWORD`, both required: the machine's
  binding, never read by the unit (`references/enable.md`).
