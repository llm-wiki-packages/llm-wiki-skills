# vip-watch
purpose: when there is no time for the inbox, just the people who matter
mode: triage
scope:
  query: is:unread newer_than:3d
  max: 40
  needs: bodies
categories:
  - name: vip
    match: from:$vips
    action: star
    note: who, what, deadline, one line — read the body
  - name: family
    match: from:$family
    action: star
    note: same
  - name: vip-thread
    match: a thread where a $vip is on To/Cc and the newest message asks something
    action: report
  - name: default
    action: report
    note: COUNT ONLY — nothing else is listed in this playbook
writes: [star]
output: |
  ## <mailbox> — vip watch — <date>
  one bullet per vip/family message, newest first, with "→ /channel-gmail-gws reply" hint where a reply is due
  final line: "<n> other unread, not shown"
