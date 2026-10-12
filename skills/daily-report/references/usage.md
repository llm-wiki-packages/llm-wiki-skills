# daily-report — usage

A session skill with no scripts. Invoked `/daily-report [date|focus|setup]`.

A scheduled run is `/daily-report <args…> ticket=<id> stage=routine`: the
words before `ticket=` are its date or focus, and nobody is there to answer.

## Arguments

| argument | by hand | unattended (under `ticket=`) |
| :--- | :--- | :--- |
| none | reports today, everything since the last report | same |
| a date | reports as that date | safe |
| a focus (any words) | narrows the report to it | safe |
| `setup` alone | runs the interview (SKILL.md § 8) | never the interview: the run reports and notes that setup needs an operator |
| `setup` then words | the whole is a focus | a leading `setup` is still not the interview |

Nothing else is asked mid-run; § 8 is the sole exception, and it needs a
person at the keyboard.

## Knobs

- The `daily-report` overlay (section plan, tone, cross-wiki list, tighter
  promotions) and the `daily-report-setup` marker, both read by
  `llm-wiki-ops policy get daily-report daily-report-setup` (SKILL.md § 1).
- The report window opens at the newest `ok` `daily-report` run (SKILL.md § 2).
- `references/setup.md` is the interview and the brief's template rules,
  printed by `llm-wiki-ops reference daily-report/setup`.
