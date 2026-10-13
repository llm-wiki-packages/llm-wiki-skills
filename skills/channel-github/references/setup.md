# channel-github — setup

The interview that makes GitHub repos land organized. Run with the operator
at the keyboard; every write below is on their yes. Re-run any step later —
each reads what is there first.

## 1. Read what the wiki already cares about

This section answers which tags, areas and repo categories the wiki already uses.

```sh
llm-wiki-ops run ops/skills/channel-github/scripts/catalog.py census
llm-wiki-ops policy get channel-github
```

`census` answers the tags, areas and `wiki/areas/` hubs in use across
`wiki/` and `sources/`, and — once repos have landed — the categories and
GitHub topics on repo pages. Read the wiki's `AGENTS.md` "Purpose and
scope" too: its priorities say which domains deserve fine categories and
which one coarse bucket.

No repo landed yet, and a stars job declared (§8)? Offer to run it first,
so the proposal is grounded in the operator's real stars, not guessed:

```sh
llm-wiki-ops jobs claim <slug>
llm-wiki-ops jobs run job=<slug> wait=600s
```

## 2. Propose the taxonomy

This section answers what a good category set looks like.

8–20 categories, each a kebab-case tag:

- **Named for what a repo is FOR**, in the operator's vocabulary — reuse a
  tag or area the census shows before inventing one (`marketing` already
  tags clips → the category is `marketing`, not `growth-tools`).
- **Granular where the priorities are** (for an AI-focused wiki:
  `agent-skills`, `mcp-servers`, `agent-frameworks`, `coding-agents`,
  `evals`, `rag`), one bucket where they are not.
- **Facets, not a tree**: a repo takes 1–4, so `agent-skills` + `marketing`
  together answer "agent skills for marketing". Prefer a domain facet
  (`marketing`, `health`, `finance`) plus a kind facet (`agent-skills`,
  `cli`, `library`, `app`, `dataset`) over compound names.
- Each gets one line: when it applies, and the GitHub topics that map to it.

Show it as a table — category, when it applies, mapped topics, and (once
repos have landed) how many repo pages would take it. Iterate until the
operator says yes.

## 3. Save it — the overlay the process step reads

This section answers what the `channel-github` overlay holds and how it is written.

`llm-wiki-ops policy set channel-github`, the whole text on stdin, freeform
bullets, never a schema (read it first, and keep what it already says):

```markdown
## Categories (setup, YYYY-MM-DD)

Tag each repo with 1–4 of these, by what it is FOR:

- `agent-skills` — packaged skills, prompts or plugins an agent loads. Topics: claude-skills, agent-skills, cursor-rules.
- `marketing` — anything whose user is a marketer: copy, SEO, ads, social. Topics: seo, marketing, copywriting.

## README mode

full — the body is what search indexes.

## Junk (beyond the unit's defaults)

- (the operator's rules, or none)
```

The process step reads it on every capture, so a change applies to the next
one; §7 fixes what already landed.

## 4. Lists

This section answers which list pages the routine writes and how they rank.

Show `references/lists.json` (the wiki's copy) and the result:

```sh
llm-wiki-ops run ops/skills/channel-github/scripts/catalog.py preview
```

Ask:

- Which standing lists? Stars, Clipped, Top 50 and What's new ship enabled.
  A custom list is a `name`, a `filter` (`tags_all`, `tags_any`,
  `tags_none`, `via_prefix`, `starred`, `min_stars`, `include_archived`,
  `text`), a `sort` (`score`, `stars`, `starred`, `pushed`, `jump`,
  `first_seen`, `name`), a `limit` and a `format` (`compact` bullets or
  `table`).
- One list page per category (`by_category`, on by default, for categories
  with at least `min` repos)?
- Ranking weights: starred > clipped > stars by default. Should a star count
  outweigh the operator's own star?

Edit the file on their answers (`references/customize.md` names every key),
then `preview` again before anything is written.

## 5. Clipping GitHub repos

This section answers how a browser clip becomes the same page a harvest writes.

Both templates write a harvest-shaped page, so a clip IS a repo page and the
next harvest merges into it:

- **Web Clipper** (the browser extension): Settings → Templates → Import,
  and pick this unit's `references/clipper-github-repo.json` (`llm-wiki-ops
  reference channel-github/clipper-github-repo` names its location). Its
  trigger selects it on any `github.com/<owner>/<repo>` page, its note
  location is `sources/github`, and its note name is `<owner>--<repo>` — the
  harvest's own title. Check the first clip: the stars and topics selectors
  read GitHub's current markup, which changes.
- **Obsidian**: copy `references/template-github-repo.md` to
  `templates/GitHub Repo.md`.

A clip carries `status: draft`; the commit sweep adopts it like any clip.
`/channel-github pending` lists clips with no GitHub facts yet.

## 6. Steer curate and dream

This section answers the overlay lines that keep curate and dream from judging repos one by one.

Repo pages are numerous and small: without these, curate judges each by
hand and dream writes a digest per repo. Append to each (`policy get`
first, then `policy set` the whole text):

**curate** —

```markdown
- `sources/github/` repo pages (`type: repo`): accept unless junk by the
  channel-github overlay's rules. A re-capture that changed only `gh_*`
  facts, the facts line or the README is a re-accept, not a re-review.
  A repo page and a clip of the same repo are one page, never duplicates.
```

**dream** —

```markdown
- GitHub repo pages (`type: repo`) are catalog entries, not sources to
  digest: no `wiki/sources/` summary per repo. Make an entity page only for
  a repo that two or more non-github sources discuss. A topic page links
  the `GitHub list — <category>` page instead of listing repos.
- List pages (`type: list`) are never distilled.
```

## 7. Re-tag what already landed

This section answers how pages captured before a taxonomy change are fixed.

The `retag` mode in SKILL.md: `catalog.py scan`, judge, then `page edit
<path> tags=<signals>,<categories>` per page that changes, on the
operator's yes.

## 8. The jobs

This section answers which jobs to declare: the harvest jobs and the one routines job.

`references/enable.md` holds the lines: one harvest job for the operator's
stars, one for what they follow, and one routines job for the lists.

## 9. Offer to save

This section answers what else to keep as the wiki's defaults.

Anything asked here and not yet saved — the operator's GitHub login, the
cadence the lists regenerate at — offer `llm-wiki-ops policy set
channel-github` (read first).
