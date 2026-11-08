# study-plan — usage

A session skill with no scripts. Invoked `/study-plan [focus]`.

A routine entry's `args` become the words before `ticket=<id> stage=routine`
(SKILL.md, scope). No word of an arg may be `--` or `--help` or begin
`ticket=` or `stage=`, and no arg may carry a control character or a newline.

## Arguments

| argument | by hand | unattended (under `ticket=`) |
| :--- | :--- | :--- |
| none | plans everything the syllabus has due inside the horizon | same |
| a course or a topic | narrows the plan to it | same |
| an exam the syllabus names | writes or refreshes that exam's study guide too, inside the horizon or not | same |

Nothing is asked mid-run, by hand or not.

## Knobs

- The `study-plan` overlay: horizon, plan size and layout, when an exam
  gets a guide of its own (SKILL.md § 1).
- What is weak is the quiz's: the `quiz` overlay's weak-spot rule, read by
  the same call, else the quiz's stock rule, over the sessions the quiz's
  own lookup finds (SKILL.md § 3).
- What it writes: the guide titled `Study plan`, and one
  `<assessment> study guide` per exam due (SKILL.md § 5, § 6).
