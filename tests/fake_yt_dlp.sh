#!/bin/sh
# `yt-dlp` as the harness's PATH has it, so `skills enable` records this file
# as the unit's bin and a stage's jail runs it, through a link: a video the
# harness holds a fixture for (`<fixtures>/<video id>/`, the path written in
# at install) is answered from it, offline, and every other call is the real
# yt-dlp's.
fixtures=@YT_FIXTURES@
here="$(cd "$(dirname "$0")" && pwd)"
item=""; out=""; dump=""; prev=""
for arg in "$@"; do
    [ "$prev" = "-o" ] && out="$arg"
    [ "$arg" = "--dump-json" ] && dump=1
    prev="$arg"; item="$arg"
done
vid="${item##*v=}"; vid="${vid%%&*}"
fixture="$fixtures/$vid"
if [ -n "$vid" ] && [ "$vid" != "$item" ] && [ -d "$fixture" ]; then
    if [ -n "$dump" ]; then
        cat "$fixture/metadata.json"
    elif [ -n "$out" ]; then
        dir="$(dirname "$out")"
        mkdir -p "$dir"
        for vtt in "$fixture"/*.vtt; do [ -e "$vtt" ] && cp "$vtt" "$dir/"; done
    fi
    exit 0
fi
real="$(PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vxF "$here" | paste -sd: -)" command -v yt-dlp)"
[ -n "$real" ] || { echo "yt-dlp: not installed" >&2; exit 127; }
exec "$real" "$@"
