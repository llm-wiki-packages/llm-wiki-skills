# daily-digest
purpose: one screen that replaces opening the inbox — what happened in the last day, in the operator's terms
mode: digest
scope:
  query: newer_than:1d in:inbox -category:promotions -category:social
  max: 150
  needs: headers      # bodies for anything from $vips / $family / needs-reply
categories:
  - name: needs-me
    match: from:$vips OR from:$family OR thread:unanswered addressed to me with a question
    action: report
    note: who, what, deadline; read the body before writing the line
  - name: decisions-and-dates
    match: subject~(rsvp|deadline|due|sign|approve|meeting|invite|calendar)
    action: report
    note: the date and the ask only
  - name: money
    match: from:$receipts OR subject~(invoice|payment|statement|refund|charge)
    action: report
    note: one line per item over $50, else a count and sum
  - name: people
    match: from a person, otherwise unplaced
    action: report
    note: one line each, grouped by sender
  - name: services
    match: automated (github, ci, saas, delivery, alerts)
    action: report
    note: counts per service; surface only failures/security
  - name: newsletters
    match: from:$newsletters OR list-unsubscribe present
    action: report
    note: titles only; "→ /channel-gmail-gws digest --playbook newsletter-digest" hint
  - name: default
    action: report
writes: []
output: |
  ## <mailbox> — digest — <date> (<N> messages, <window>)
  **Needs me** — bullets
  **Dates & decisions** — bullets with dates bolded
  **Money** — bullets / count
  **People** — grouped bullets
  **Services** — one line
  **Newsletters** — one line
