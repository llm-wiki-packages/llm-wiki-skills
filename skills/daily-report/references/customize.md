# daily-report — customizing this skill

The brief's look, sections and tone belong to the wiki, not to this unit's
body. Prefer the wiki's `daily-report` overlay and its
`wiki/reports/_template.html`. Editing `SKILL.md` makes the unit `customized`,
and `skills install` then refuses to refresh it.

Ask, with an operator at the keyboard:

- What should the morning brief lead with — attention items, channel
  summaries, or what the wiki did?
- Which sections does nothing feed? Cut them.
- Which other wikis, if any, may the cross-wiki section read? It is off
  until the overlay names one.
- What tone: neutral, or coaching and bold on recommendations?

Then offer to save the answers:

```sh
llm-wiki-ops policy get daily-report     # read FIRST
llm-wiki-ops policy set daily-report     # on the operator's yes, prose on stdin
```

`references/setup.md` is the full interview; `/daily-report setup` runs it.
