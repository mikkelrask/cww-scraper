#!/usr/bin/env python3
"""
Build artist cache from MusicBrainz API.
Extracts unique artists from episodes.json and looks up canonical names.
Uses beets library for local matching before hitting the API.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from collections import Counter
from typing import Any

import requests
from beets import config
from beets.library import Library
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


def load_beets_library() -> dict[str, dict[str, Any]]:
    """Load artists from beets library for local matching."""
    try:
        config.read()
        library_path = config["library"].as_filename()
    except Exception as e:
        print(f"  Warning: Could not read beets config: {e}", file=sys.stderr)
        return {}

    if not library_path:
        print("  Warning: No library path in beets config", file=sys.stderr)
        return {}

    if not Path(library_path).exists():
        print(f"  Warning: Library file not found: {library_path}", file=sys.stderr)
        return {}

    try:
        lib = Library(library_path)
    except Exception as e:
        print(f"  Warning: Could not open library: {e}", file=sys.stderr)
        return {}

    print(f"  Loading unique artists from {library_path}...")

    artists: dict[str, dict[str, Any]] = {}

    try:
        count = 0
        for item in lib.items():
            artist = item.artist
            if artist:
                normalized = normalize(artist)
                # Only add if not already in dict
                if artist not in artists:
                    artists[artist] = {
                        "source": "beets",
                        "original": artist,
                        "mbid": getattr(item, "mb_artist_id", None),
                    }
                if normalized not in artists:
                    artists[normalized] = {
                        "source": "beets",
                        "original": artist,
                        "mbid": getattr(item, "mb_artist_id", None),
                    }
            count += 1
            if count % 5000 == 0:
                print(f"    {count} items processed...")
    except Exception as e:
        print(f"  Warning: Error loading items: {e}", file=sys.stderr)

    print(f"  Loaded {len(artists)} unique artist names")
    return artists


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


def normalize(text: str) -> str:
    """Basic normalization for matching."""
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = text.replace("&", "and")
    text = text.replace("/", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
                        "source": "musicbrainz",
                    }
                return None  # No match found
            elif resp.status_code == 503:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                return None
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


def resolve_artist(
    scraped_artist: str,
    beets_artists: dict[str, dict],
    cache: dict,
    mb_lookup: bool = True,
) -> dict | None:
    """
    Resolve scraped artist name to canonical form.
    
    Strategy:
    1. Exact match in beets library
    2. Normalized match in beets library
    3. Exact match in cache
    4. Normalized match in cache
    5. MB API with full name
    6. MB API with normalized name
    """
    # 1. Exact match in beets
    if scraped_artist in beets_artists:
        result = beets_artists[scraped_artist].copy()
        result["match_type"] = "beets_exact"
        return result

    # 2. Normalized match in beets
    normalized = normalize(scraped_artist)
    if normalized in beets_artists:
        result = beets_artists[normalized].copy()
        result["match_type"] = "beets_normalized"
        return result

    # 3. Check cache (both full and normalized)
    if scraped_artist in cache:
        result = cache[scraped_artist].copy()
        result["match_type"] = "cache_exact"
        return result
    if normalized in cache:
        result = cache[normalized].copy()
        result["match_type"] = "cache_normalized"
        return result

    if not mb_lookup:
        return None

    # 5. MB API with full name
    result = lookup_artist(scraped_artist)
    if result:
        result["match_type"] = "mb_full"
        return result

    # 6. MB API with normalized name
    result = lookup_artist(normalized)
    if result:
        result["match_type"] = "mb_normalized"
        return result

    return None


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
    parser.add_argument(
        "--no-beets",
        action="store_true",
        help="Skip beets library matching",
    )
    parser.add_argument(
        "--no-mb",
        action="store_true",
        help="Skip MusicBrainz API calls",
    )
    args = parser.parse_args()

    print(f"Loading episodes from {args.input}...")
    episodes = load_episodes(args.input)
    artists = extract_artists(episodes)

    print(f"Found {len(artists)} unique artists")
    print(f"Total tracks: {sum(c for _, c in artists)}")

    # Load beets library for local matching
    beets_artists: dict[str, dict] = {}
    if not args.no_beets:
        print("Loading beets library...")
        beets_artists = load_beets_library()
        print(f"Beets artists: {len(beets_artists)}")

    cache = load_cache(args.cache)
    print(f"Existing cache entries: {len(cache)}")

    # Filter out already-cached artists
    artists_to_lookup = []
    for artist, count in artists:
        normalized = normalize(artist)
        # Check if both full and normalized are cached
        if artist not in cache and normalized not in cache:
            artists_to_lookup.append((artist, normalized, count))

    print(f"Artists to lookup: {len(artists_to_lookup)}")

    if args.limit > 0:
        artists_to_lookup = artists_to_lookup[:args.limit]
        print(f"Limited to: {len(artists_to_lookup)}")

    if args.dry_run:
        print("\nDry run - showing top artists to lookup:")
        for artist, normalized, count in artists_to_lookup[:10]:
            print(f"  {artist} -> {normalized} ({count} tracks)")
        return

    if not artists_to_lookup:
        print("No new artists to look up!")
        return

    # Match statistics
    stats = {
        "beets_exact": 0,
        "beets_normalized": 0,
        "cache_exact": 0,
        "cache_normalized": 0,
        "mb_full": 0,
        "mb_normalized": 0,
        "not_found": 0,
    }

    print(f"\nResolving {len(artists_to_lookup)} artists...")
    for artist, normalized, count in tqdm(artists_to_lookup, unit="artist"):
        result = resolve_artist(artist, beets_artists, cache, mb_lookup=not args.no_mb)

        if result:
            match_type = result.get("match_type", "unknown")
            stats[match_type] = stats.get(match_type, 0) + 1

            # Remove match_type from result before caching (it's just for stats)
            result_for_cache = {k: v for k, v in result.items() if k != "match_type"}

            # Cache both full name and normalized
            cache[artist] = result_for_cache
            cache[normalized] = result_for_cache
        else:
            stats["not_found"] += 1
            # Don't cache failures - might find them later with different approach

        time.sleep(REQUEST_DELAY)

    save_cache(cache, args.cache)

    print(f"\nCache saved to {args.cache}")
    print(f"Total entries: {len(cache)}")
    print("\nMatch statistics:")
    for key, count in stats.items():
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
