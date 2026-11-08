# daily-report — usage

A session skill with no scripts. Invoked `/daily-report [date|focus|setup]`.

A routine entry's `args` become the words before `ticket=<id> stage=routine`
(SKILL.md, scope). No word of an arg may be `--` or `--help` or begin
`ticket=` or `stage=`, and no arg may carry a control character or a newline.

## Arguments

| argument | by hand | unattended (under `ticket=`) |
| :--- | :--- | :--- |
| none | reports today, everything since the last report | same |
| a date | reports as that date | safe |
| a focus (words, subject to the limits above) | narrows the report to it | safe |
| `setup` alone | runs the interview (SKILL.md § 8) | never the interview: the run reports and notes that setup needs an operator |
| `setup` then words | the whole is a focus | a leading `setup` is still not the interview |

Nothing else is asked mid-run; § 8 is the sole exception, and it needs a
person at the keyboard.

## Knobs

- The `daily-report` overlay (section plan, tone, cross-wiki list, tighter
  promotions) and the `daily-report-setup` marker, both read by
  `{{@brain-cli-ops}} policy get daily-report daily-report-setup` (SKILL.md § 1).
- The window opens at the newest `ok` run; with none, at the newest run of any
  outcome; with none, three days back (SKILL.md § 2).
- `wiki/reports/_template.html` is the brief's design language; seeded only
  with an operator present (SKILL.md § 7).
- `references/setup.md` is the interview and the brief's template rules,
  printed by `{{@brain-cli-ops}} reference daily-report/setup`.
