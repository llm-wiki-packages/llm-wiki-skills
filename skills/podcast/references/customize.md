# podcast — customizing this skill

The show's hosts, length, tone and shape belong to the wiki, not to this
unit's body. Prefer the wiki's `podcast` overlay. Editing `SKILL.md` makes
the unit `customized`, and `skills install` then refuses to refresh it.
This unit is meant as a starting point: copy it under a new name for a
second show with a different format.

Ask, with an operator at the keyboard:

- What is the show called, and who hosts it? One host, two, or three; a
  name and a personality each. The names must match the speaker names in
  the wiki's `[narrate.voices]`, or the hosts get the default voices.
- How long should an episode run: a five-minute recap, or a twenty-minute
  deep dive?
- What tone: a study buddy, a radio show, a debate, a bedtime story?
- What shape: segments by theme, a question per page, a recap then a quiz?
- What should a weekly episode cover by default: new `sources/` pages, one
  course, one folder?

Then offer to save the answers:

```sh
{{@brain-cli-ops}} policy get podcast     # read FIRST
{{@brain-cli-ops}} policy set podcast     # on the operator's yes, prose on stdin
```
