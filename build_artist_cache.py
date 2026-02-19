#!/usr/bin/env python3
"""
Build artist cache from MusicBrainz API.
Extracts unique artists from episodes.json and looks up canonical names.
"""

import json
import os
import sys
import time
from pathlib import Path
from collections import Counter

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

USER_AGENT = os.environ.get(
    "MUSICBRAINZ_USER_AGENT",
    "cww-scraper/1.0 (https://github.com/username/cww-scraper)",
)

CACHE_FILE = "artist_cache.json"
INPUT_FILE = "episodes.json"
REQUEST_DELAY = 0.25  # 4 req/sec to be safe


def load_episodes(path: str) -> list[dict]:
    """Load episodes from JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def extract_artists(episodes: list[dict]) -> list[tuple[str, int]]:
    """Extract unique artists with counts from episodes."""
    artist_counts: Counter = Counter()

    for episode in episodes:
        for track in episode.get("tracklist", []):
            artist = track.get("artist", "").strip()
            if artist:
                artist_counts[artist] += 1

    # Sort by frequency (most common first)
    return artist_counts.most_common()


def load_cache(path: str) -> dict:
    """Load existing artist cache."""
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: str) -> None:
    """Save artist cache to file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def lookup_artist(name: str) -> dict | None:
    """Look up artist on MusicBrainz with retry logic."""
    url = "https://musicbrainz.org/ws/2/artist"
    params = {"query": name, "fmt": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("artists"):
                    artist = data["artists"][0]
                    return {
                        "mbid": artist.get("id"),
                        "canonical_name": artist.get("name"),
                        "sort_name": artist.get("sort-name"),
                    }
                return {}  # Found but no match
            elif resp.status_code == 503:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                return None
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


def normalize_for_lookup(text: str) -> str:
    """Basic normalization before MB lookup."""
    import re
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)  # Remove parenthetical
    text = text.replace("&", "and")
    text = text.replace("/", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build artist cache from MusicBrainz")
    parser.add_argument(
        "--input",
        default=INPUT_FILE,
        help="Input episodes JSON file",
    )
    parser.add_argument(
        "--cache",
        default=CACHE_FILE,
        help="Output cache file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of artists to process (0 = all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show stats without making API calls",
    )
    args = parser.parse_args()

    print(f"Loading episodes from {args.input}...")
    episodes = load_episodes(args.input)
    artists = extract_artists(episodes)

    print(f"Found {len(artists)} unique artists")
    print(f"Total tracks: {sum(c for _, c in artists)}")

    cache = load_cache(args.cache)
    print(f"Existing cache entries: {len(cache)}")

    # Filter out already-cached artists
    artists_to_lookup = []
    for artist, count in artists:
        normalized = normalize_for_lookup(artist)
        if normalized not in cache:
            artists_to_lookup.append((artist, normalized, count))

    print(f"Artists to lookup: {len(artists_to_lookup)}")

    if args.limit > 0:
        artists_to_lookup = artists_to_lookup[:args.limit]
        print(f"Limited to: {len(artists_to_lookup)}")

    if args.dry_run:
        print("\nDry run - showing top artists to lookup:")
        for artist, normalized, count in artists_to_lookup[:10]:
            print(f"  {artist} ({count} tracks)")
        return

    if not artists_to_lookup:
        print("No new artists to look up!")
        return

    print(f"\nLooking up {len(artists_to_lookup)} artists...")
    for artist, normalized, count in tqdm(artists_to_lookup, unit="artist"):
        result = lookup_artist(normalized)
        if result:
            cache[normalized] = result
        time.sleep(REQUEST_DELAY)

    save_cache(cache, args.cache)
    print(f"\nCache saved to {args.cache}")
    print(f"Total entries: {len(cache)}")


if __name__ == "__main__":
    main()
