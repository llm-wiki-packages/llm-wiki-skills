# followup-chaser
purpose: find what I asked for and never got, and draft the nudge
mode: followup
scope:
  query: in:sent newer_than:14d older_than:2d
  max: 80
  needs: headers      # bodies for the sent message when drafting
categories:
  - name: chase
    match: thread:unanswered (my sent message is the last in its thread) AND the message asks a question or for a deliverable AND (to:$waiting OR to:$vips OR any person)
    action: draft
    note: who, what I asked, days waiting
  - name: chase-soft
    match: thread:unanswered, no explicit ask (fyi I sent)
    action: report
    note: list; no draft
  - name: answered
    match: a reply from them exists after my message
    action: report
    note: count only
  - name: default
    action: report
writes: []
drafting:
  voice: profile.draft voice, lighter
  rules:
    - 2–3 sentences: a friendly bump, restate the one ask, offer an easy out ("if this has moved on, no worries")
    - escalate tone only on the second chase of the same thread (check Drafts/sent for an earlier nudge)
    - never chase $family; never chase within 2 days; never chase over a weekend unless $vips
    - one draft per thread, threaded as a reply to my own sent message
output: |
  ## <mailbox> — follow-ups — <date>
  **Chase (drafted)** — recipient — subject — asked <N> days ago — draft id
  **Unanswered, no ask** — list
  one count line for answered threads
