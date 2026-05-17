#!/usr/bin/env bash
#
# dl_episode.sh - Download a CWW episode audio.
#
# Usage: ./dl_episode.sh <episode_number>
#   e.g.  ./dl_episode.sh 591

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

result=$(jq -r --arg ep "$EP_NUM" '
    .[] |
    select(
        .episode_number == ($ep | tonumber)
        or (.url | test("episode-\($ep)([^0-9]|$)"))
    ) |
    { episode_number, url, audio_url, audio_type }
' "$DATA_FILE")

if [[ -z "$result" || "$result" == "null" ]]; then
    echo "Error: Episode $EP_NUM not found in $(basename "$DATA_FILE")." >&2
    exit 1
fi

audio_url=$(echo "$result" | jq -r '.audio_url // empty')

if [[ -z "$audio_url" ]]; then
    echo "Error: Episode $EP_NUM has no audio URL." >&2
    exit 1
fi

audio_type=$(echo "$result" | jq -r '.audio_type // "unknown"')
ep_url=$(echo "$result" | jq -r '.url')

echo "Episode $EP_NUM — $ep_url"
echo "Audio: $audio_url ($audio_type)"

case "$audio_type" in
    archive.org)
        id=$(echo "$audio_url" | sed 's|https://archive.org/details/||')
        direct_url="https://archive.org/download/${id}/${id}.mp3"
        echo "Downloading: $direct_url"
        curl -# -L -o "CWW Episode $EP_NUM.mp3" "$direct_url"
        ;;
    soundcloud)
        path=$(echo "$ep_url" | sed 's|https://www.chanceswithwolves.com||')
        sc_url="https://soundcloud.com/chanceswithwolves${path}"
        echo "Downloading from SoundCloud slug: $sc_url"
        yt-dlp -o "CWW Episode $EP_NUM - %(title)s.%(ext)s" "$sc_url"
        ;;
    *)
        echo "Unknown audio type, trying as-is with yt-dlp..."
        yt-dlp -o "CWW Episode $EP_NUM - %(title)s.%(ext)s" "$audio_url"
        ;;
esac
