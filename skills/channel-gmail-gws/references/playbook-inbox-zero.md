# inbox-zero
purpose: leave the inbox holding only what needs a human; everything else labeled and archived
mode: clean
scope:
  query: in:inbox older_than:1d -is:starred
  max: 300
  needs: headers
categories:
  - name: keep
    match: from:$vips OR from:$family OR subject~(deadline|due|rsvp|sign|approve|school|medical|legal) OR thread:unanswered addressed to me
    action: report
    note: stays in inbox
  - name: receipts
    match: from:$receipts OR subject~(receipt|order|invoice|payment|statement|shipped|delivered)
    action: label:Receipts     # then archive (both listed in writes)
  - name: newsletters
    match: from:$newsletters OR list-unsubscribe present OR label:CATEGORY_PROMOTIONS
    action: label:Newsletters
  - name: noise
    match: from:$noise OR label:CATEGORY_SOCIAL
    action: archive
  - name: services
    match: automated notifications older than 3 days with no failure/security words
    action: archive
  - name: default
    action: report
    note: untouched; suggest a profile list
writes: [label, archive]       # read is deliberately excluded: archived mail stays unread so Gmail search still finds it fresh
rules:
  - every non-`keep` category is archived after labeling; `keep` and `default` are never touched
  - profile hard rules win: nothing from $family or $vips is archived, whatever the category
  - without --apply this is a report of what WOULD move, with counts per label; with --apply, batchModify in chunks of 100 and report the ids moved
  - create a missing label only if the profile's label map names it AND the run passes --apply
output: |
  ## <mailbox> — inbox-zero — <date>
  **Kept in inbox (<n>)** — bullets
  **Moved** — per label: count (+ "proposed" if not applied)
  **Unplaced (<n>)** — senders to add to a profile list
