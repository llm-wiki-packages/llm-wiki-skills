# podcast — usage

A session skill with no scripts. Invoked `/podcast [focus]`.

A routine entry's `args` become the words before `ticket=<id> stage=routine`
(SKILL.md, scope). No word of an arg may be `--` or `--help` or begin
`ticket=` or `stage=`, and no arg may carry a control character or a newline.

## Arguments

| argument | by hand | unattended (under `ticket=`) |
| :--- | :--- | :--- |
| none | covers the `sources/` pages new or changed since the last episode | same |
| pages, a folder, a course or a topic | covers what it names | same |
| a span of time ("this week") | covers the `sources/` pages changed inside it | same |

Nothing is asked mid-run, by hand or not.

## Knobs

- The `podcast` overlay: the show's name, its hosts, length, tone and shape,
  and how many pages one episode takes (SKILL.md § 1).
- The wiki's `[narrate.voices]`: which voice speaks each host's name. That
  table is the `narrate` engine's, not this unit's.
- What it writes: one `podcast` page under `wiki/podcasts/`, its script in
  a `narrate` block, asking for its audio with `audio: podcast`
  (SKILL.md § 5).
