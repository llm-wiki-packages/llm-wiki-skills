# quiz-show — customizing this skill

The show's hosts, rounds, length and tone belong to the wiki, not to this
unit's body. Prefer the wiki's `quiz-show` overlay; what counts as weak is
the `quiz` overlay's, which the quiz reads too. Editing `SKILL.md` makes the
unit `customized`, and `skills install` then refuses to refresh it. This
unit is meant as a starting point: copy it under a new name for another
format, such as flashcards read aloud or a two-team trivia night.

Ask, with an operator at the keyboard:

- What is the show called, and who hosts it? The names must match the
  speaker names in the wiki's `[narrate.voices]`, or the hosts get the
  default voices.
- How many questions a show, and should there be a lightning round?
- Should the contestant replay the learner's wrong answers, or always
  answer right?
- What tone: a game show, a calm study session, a sports commentary?

Then offer to save the answers:

```sh
{{@brain-cli-ops}} policy get quiz-show     # read FIRST
{{@brain-cli-ops}} policy set quiz-show     # on the operator's yes, prose on stdin
```
