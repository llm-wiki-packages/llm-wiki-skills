# Daily-report setup — the interview, the template, and who owns what

The audience is any agent asked to produce a daily report, or to change how
one looks or reads. Read it before touching the template or authoring a
report. The interview at the bottom is the script for the skill's `setup`
mode; everything above it applies to every run.

## The philosophy — this overrides habit

**Each day's report is standalone HTML, authored fresh from that day's
story.** You are writing the morning brief an expert executive assistant
would prepare, not filling a form. Gather the inputs, reason hard about what
today actually is, then design the page that tells it.

- Decide what sections TODAY needs, in what order, at what depth. A day
  dominated by one negotiation deserves one deep briefing and a paragraph,
  not every section at token depth. A quiet day deserves a short, honest
  page.
- Never analyze the data to fit the template. The template contributes look
  and vocabulary, not structure. If you are hunting for content to fill a
  section, delete the section.
- Depth beats coverage. Every actionable item answers why it matters, what
  to do next, and — when a reply is the next step — a draft the operator can
  copy. Every claim carries its receipt: a source line naming where it came
  from.

## What the template is

`wiki/reports/_template.html` is a working sample page: design tokens, type
scale, and component patterns — masthead, drop-cap narrative summary, focus
list, delta strip, action cards with tabs and a briefing panel, insight rows,
calendar and wins, reach-out rail, watching list. Borrow its tokens and
patterns so consecutive reports feel like issues of one publication.

It is seeded once, with an operator at the keyboard — normally the interview
below — from `dashboard-template.html` beside this file. With nobody to answer
and no template, nothing is seeded: the run renders from the reference copy
read-only and notes the gap.

It is NOT a contract: no required sections, no data schema, no validation. A
wiki wanting a rigid structure writes its own; the plugin never does.

Three rules DO hold for every report, and they are what keep reports viewable
forever, offline, anywhere:

- **Self-contained** — inline CSS and JS only; no external fonts,
  stylesheets, scripts or images. `data:` URIs are fine.
- **Content from external signals renders as text, never as markup.**
- **The markdown sibling is the durable record**; the HTML is the view.

## Who owns what

When the operator asks for a change, route it to the file that owns the
concern, then log the edit with the `schema` prefix.

| Operator says | Edit |
| :--- | :--- |
| "make it burgundy / different fonts / bigger cards" | `wiki/reports/_template.html` tokens — alternate accent ramps are documented in its header |
| "drop the calendar", "add a section for X" | the wiki's `daily-report` overlay, which carries the section plan |
| "recommendations should be bolder / more coaching" | the wiki's `daily-report` overlay, emphasis and tone |
| "redesign the whole thing" | `wiki/reports/_template.html` — run the interview below, keeping the three rules |
| "why did today's report say X" | neither — that is the day's markdown and HTML; answer from them |

Between operator-requested redesigns, keep the look stable: same tokens, same
component vocabulary, issue after issue.

## The setup interview

The one interactive mode. Run it when the wiki has no
`wiki/reports/_template.html`, or whenever the operator asks for a redesign.
With the operator present:

1. **Open the run under `grill`, never `daily-report`** — a `daily-report`
   close here would advance the window cursor past days no report covered —
   then **inventory what is actually connected**. The menu of possible
   sections is this, never the sample:

   ```sh
   llm-wiki-ops op open grill
   llm-wiki-ops pipeline jobs ls
   llm-wiki-ops page ls filter=under:wiki/profile
   llm-wiki-ops search status
   ```

2. **Ask what they care about seeing each morning**, in their words, few
   questions. Map each answer to a source above; anything with nothing
   feeding it is cut, or marked aspirational in the overlay.

3. **Personalize the template copy** — their name, the brief's masthead name,
   palette and fonts if they care — and write it to
   `wiki/reports/_template.html`.

4. **Fold the section plan and tone into the overlay**, on the operator's
   explicit yes and never otherwise:

   ```sh
   llm-wiki-ops policy get daily-report
   llm-wiki-ops policy set daily-report     # the prose arrives on stdin
   ```

   One call carrying the complete folded text: which signals feed which
   sections, and what "needs attention" means for this operator. Show the
   folded result before saving.

5. **Retire the setup marker when §1's read returned it.** The skill's
   first read answers both names at once; a redesign on a wiki that already
   ran setup got no `daily-report-setup` row and skips this step, because
   retiring a name the wiki no longer carries is a refusal that would land
   between the overlay saved above and the commit below, leaving the
   operator's answers uncommitted. When the row came back, spend it here,
   after the overlay is saved and not before — this is the only place it is
   spent, and spending it is what stops every later run offering setup
   again:

   ```sh
   llm-wiki-ops policy retire daily-report-setup
   ```

6. **Close the run** and log the pass to `wiki/log.md` with the `schema`
   prefix:

   ```sh
   llm-wiki-ops git commit message="daily-report: template and overlay"
   llm-wiki-ops op close grill outcome=ok summary="daily-report setup: brief (re)designed"
   ```

A scheduled run never asks questions. It authors the best page it can from
what is there and puts the open questions IN the page.
