# quiz-show — usage

A session skill with no scripts. Invoked `/quiz-show [focus]`.

A routine entry's `args` become the words before `ticket=<id> stage=routine`
(SKILL.md, scope). No word of an arg may be `--` or `--help` or begin
`ticket=` or `stage=`, and no arg may carry a control character or a newline.

## Arguments

| argument | by hand | unattended (under `ticket=`) |
| :--- | :--- | :--- |
| none | quizzes the weak spots of the newest quiz sessions | same |
| a course, a topic or an exam | quizzes what it names, its weak spots first | same |

Nothing is asked mid-run, by hand or not.

## Knobs

- The `quiz-show` overlay: the show's name, its hosts, the rounds and the
  length (SKILL.md § 1).
- What is weak is the quiz's: the `quiz` overlay's weak-spot rule, read by
  the same call, else the quiz's stock rule (SKILL.md § 2).
- The wiki's `[narrate.voices]`: which voice speaks each host's name. That
  table is the `narrate` engine's, not this unit's.
- What it writes: one `podcast` page under `wiki/podcasts/`, its script in
  a `narrate` block, asking for its audio with `audio: podcast`
  (SKILL.md § 5).
