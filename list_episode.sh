#!/usr/bin/env bash
#
# list_episode.sh - List all artist/track combos for a given CWW episode number.
#
# Usage: ./list_episode.sh <episode_number>
#   e.g.  ./list_episode.sh 591

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_FILE="${SCRIPT_DIR}/episodes.json"

if [[ $# -ne 1 ]]; then
    echo "Usage: $(basename "$0") <episode_number>" >&2
    exit 1
fi

EP_NUM="$1"

if [[ ! -f "$DATA_FILE" ]]; then
    echo "Error: Data file not found: $DATA_FILE" >&2
    exit 1
fi

# Find the episode by episode_number field (from page content), or by URL
# matching "episode-{NUMBER}" not followed by another digit (handles suffixes
# like "episode-586-halloween-spooktacula-12").
result=$(jq -r --arg ep "$EP_NUM" '
    .[] |
    select(
        .episode_number == ($ep | tonumber)
        or (.url | test("episode-\($ep)([^0-9]|$)"))
    ) |
    { url, tracklist }
' "$DATA_FILE")

if [[ -z "$result" || "$result" == "null" ]]; then
    echo "Error: Episode $EP_NUM not found in $(basename "$DATA_FILE")." >&2
    exit 1
fi

# Print a header with the episode URL
ep_url=$(echo "$result" | jq -r '.url')
echo "Episode $EP_NUM — $ep_url"
echo

# Print each track with a numbered list
echo "$result" | jq -r '
    .tracklist | to_entries[] |
    "\(.key + 1 | tostring | if length == 1 then " \(.)" else . end).  \(.value.artist) — \(.value.track)"
'
