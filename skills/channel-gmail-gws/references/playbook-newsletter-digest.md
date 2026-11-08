# newsletter-digest
purpose: read the newsletters so I don't have to — what's worth knowing, what's worth keeping in the wiki
mode: digest
scope:
  query: newer_than:7d (category:promotions OR from:$newsletters OR label:Newsletters) -from:$noise
  max: 60
  needs: bodies
categories:
  - name: worth-reading
    match: from:$vips authors, or a body with a concrete claim/number/technique bearing on the priorities the wiki's AGENTS.md names
    action: report
    note: 1–2 lines: the claim, why it matters; cite sender + subject
  - name: wiki-candidate
    match: a worth-reading item with lasting reference value (not news)
    action: report
    note: propose a source URL for the wiki, never add it yourself
  - name: skim
    match: everything else that is editorial
    action: report
    note: title only
  - name: promo
    match: pure sales / discount mail
    action: report
    note: count only
  - name: default
    action: report
writes: []
output: |
  ## <mailbox> — newsletters — <week of date>
  **Worth knowing** — bullets, each with (sender · subject)
  **Wiki candidates** — url list with one-line why
  **Skimmed** — titles, one line each
  promo count line
