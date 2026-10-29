# study-plan — customizing this skill

How far ahead a plan looks, how big it is and how it is laid out belong to
the wiki, not to this unit's body. Prefer the wiki's `study-plan` overlay;
what counts as weak is the `quiz` overlay's, which the quiz reads too.
Editing `SKILL.md` makes the unit `customized`, and `skills install` then
refuses to refresh it.

Ask, with an operator at the keyboard:

- How far ahead should the plan look: the next few days, a week, the run up
  to the next exam?
- How many concepts should one plan hold?
- Should the plan be laid out by day, or by priority?
- How close must an exam be before it gets a study guide of its own?

Then offer to save the answers:

```sh
{{@brain-cli-ops}} policy get study-plan     # read FIRST
{{@brain-cli-ops}} policy set study-plan     # on the operator's yes, prose on stdin
```
