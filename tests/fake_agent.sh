#!/bin/sh
# The harness profile's command: a session that is not a model. The runner
# starts it inside the stage's jail as `fake_agent.sh "<prompt>"`, the way it
# starts a real harness; it runs the plan a test wrote for the prompt's
# ticket, `plan.<ticket>.sh` beside this file, which is the one directory the
# machine layer grants every jail a read of. What the plan types is what a
# model following the unit's SKILL.md would type.
prompt="${1:-}"
case "$prompt" in
    *ticket=*) ticket="${prompt#*ticket=}"; ticket="${ticket%% *}" ;;
    *) echo "fake-agent: no ticket= in the prompt: $prompt" >&2; exit 3 ;;
esac
plan="$(dirname "$0")/plan.$ticket.sh"
[ -r "$plan" ] || { echo "fake-agent: no plan for ticket $ticket at $plan" >&2; exit 3; }
exec /bin/sh "$plan"
