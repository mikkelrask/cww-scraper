#!/usr/bin/env python3
"""
Tag tracks in beets library with CWW genre based on scraped episode tracklists.
"""

import json
import re
import sys
import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from beets import config
from beets.library import Library, Item

GENRE_TAG = "CWW"

DEFAULT_INPUT_JSON = "episodes.json"
DEFAULT_CACHE_FILE = "artist_cache.json"
PREVIEW_FILE = "cww_tag_preview.json"


# ----------------------------
# NORMALIZATION
# ----------------------------

def normalize(text: str) -> str:
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = text.replace("&", "and")
    text = text.replace("/", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def load_artist_cache(path: str) -> dict[str, Any]:
    """Load artist cache from JSON file."""
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_canonical_artist(
    artist_raw: str,
    cache: dict[str, Any],
) -> str:
    """
    Get canonical artist name from cache.
    
    Tries: exact match -> normalized match -> returns original.
    """
    if not artist_raw or not cache:
        return artist_raw

    # Try exact match first
    if artist_raw in cache:
        return cache[artist_raw].get("canonical_name") or cache[artist_raw].get("original") or artist_raw

    # Try normalized
    normalized = normalize(artist_raw)
    if normalized in cache:
        return cache[normalized].get("canonical_name") or cache[normalized].get("original") or artist_raw

    return artist_raw


# ----------------------------
# LOAD BEETS LIBRARY
# ----------------------------

def load_library() -> Library:
    """Load and return the beets library."""
    config.read()

    try:
        library_path = config["library"].as_filename()
    except KeyError:
        print("Error: No library configured in beets.", file=sys.stderr)
        print("Run 'beets config' to verify your configuration.", file=sys.stderr)
        sys.exit(1)

    if not library_path:
        print("Error: library path not set in beets config.", file=sys.stderr)
        sys.exit(1)

    library_file = Path(library_path)
    if not library_file.exists():
        print(f"Error: Library file not found: {library_path}", file=sys.stderr)
        print("Run 'beets ls' to verify your library exists.", file=sys.stderr)
        sys.exit(1)

    return Library(library_path)


def build_index(lib: Library) -> dict[str, list[tuple[str, Item]]]:
    """Build an index of artists and titles from the beets library."""
    artist_index: dict[str, list[tuple[str, Item]]] = defaultdict(list)

    for item in lib.items():
        artist = normalize(item.artist)
        title = normalize(item.title)

        if artist and title:
            artist_index[artist].append((title, item))

    return artist_index


def build_mbid_index(lib: Library) -> dict[str, list[tuple[str, Item]]]:
    """Build an index by MusicBrainz artist ID from the beets library."""
    mbid_index: dict[str, list[tuple[str, Item]]] = defaultdict(list)

    for item in lib.items():
        mb_artist_id = getattr(item, "mb_artist_id", None)
        if mb_artist_id:
            title = normalize(item.title)
            if title:
                mbid_index[mb_artist_id].append((title, item))

    return mbid_index


def get_artist_mbid(
    artist_raw: str,
    cache: dict[str, Any],
) -> str | None:
    """Get MusicBrainz artist ID from cache."""
    if not artist_raw or not cache:
        return None

    # Try exact match first
    if artist_raw in cache:
        return cache[artist_raw].get("mbid")

    # Try normalized
    normalized = normalize(artist_raw)
    if normalized in cache:
        return cache[normalized].get("mbid")

    return None


# ----------------------------
# MATCHING
# ----------------------------

def find_matches(
    data: list[dict[str, Any]],
    artist_index: dict[str, list[tuple[str, Item]]],
    mbid_index: dict[str, list[tuple[str, Item]]],
    artist_cache: dict[str, Any] | None = None,
) -> list[Item]:
    """Find matching tracks in the beets library using MBID or name matching."""
    matches: list[Item] = []
    seen_items: set[int] = set()
    mbid_matches = 0
    name_matches = 0

    if artist_cache is None:
        artist_cache = {}

    for episode in data:
        for track in episode.get("tracklist", []):
            artist_raw = track.get("artist", "")
            title_raw = track.get("track", "")
            title = normalize(title_raw)

            matched = False

            # Try MBID matching first (more reliable)
            if artist_cache and mbid_index:
                mbid = get_artist_mbid(artist_raw, artist_cache)
                if mbid and mbid in mbid_index:
                    for lib_title, item in mbid_index[mbid]:
                        if lib_title == title and item.id not in seen_items:
                            matches.append(item)
                            seen_items.add(item.id)
                            mbid_matches += 1
                            matched = True
                            break

            # Fall back to name matching if no MBID match
            if not matched:
                artist = normalize(artist_raw)
                if artist in artist_index:
                    for lib_title, item in artist_index[artist]:
                        if lib_title == title and item.id not in seen_items:
                            matches.append(item)
                            seen_items.add(item.id)
                            name_matches += 1
                            matched = True
                            break

    if artist_cache:
        print(f"  MBID matches: {mbid_matches}")
        print(f"  Name matches: {name_matches}")

    return matches


# ----------------------------
# TAGGING
# ----------------------------

def tag_items(items: list[Item], dry_run: bool) -> list[dict[str, str]]:
    """Tag items with CWW genre, return preview of changes."""
    preview: list[dict[str, str]] = []

    for item in items:
        existing = item.genre or ""

        genres = {g.strip() for g in existing.split(";") if g.strip()}

        if GENRE_TAG not in genres:
            genres.add(GENRE_TAG)

            preview.append({
                "artist": item.artist,
                "title": item.title,
                "path": item.path.decode("utf-8", "ignore"),
            })

            if not dry_run:
                item.genre = "; ".join(sorted(genres))
                item.store()
                item.write()

    return preview


# ----------------------------
# MAIN
# ----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Tag tracks with CWW genre")
    parser.add_argument("--dry-run", action="store_true", help="Preview without tagging")
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_JSON,
        help="Path to episodes JSON file",
    )
    parser.add_argument(
        "--cache",
        default=DEFAULT_CACHE_FILE,
        help="Path to artist cache JSON file",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip using artist cache for matching",
    )

    args = parser.parse_args()

    print("Loading episode JSON...")

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.input}: {e}", file=sys.stderr)
        sys.exit(1)

    # Load artist cache
    artist_cache: dict[str, Any] = {}
    if not args.no_cache:
        print(f"Loading artist cache from {args.cache}...")
        artist_cache = load_artist_cache(args.cache)
        print(f"  Cache entries: {len(artist_cache)}")

    print("Loading beets library...")
    lib = load_library()

    print("Indexing library...")
    artist_index = build_index(lib)
    mbid_index = build_mbid_index(lib)
    print(f"  Artists indexed: {len(artist_index)}")
    print(f"  MBID entries indexed: {len(mbid_index)}")

    print("Finding matches...")
    matches = find_matches(
        data,
        artist_index,
        mbid_index,
        artist_cache if not args.no_cache else None,
    )

    print(f"Tracks to tag: {len(matches)}")

    preview = tag_items(matches, args.dry_run)

    with open(PREVIEW_FILE, "w", encoding="utf-8") as f:
        json.dump(preview, f, indent=2, ensure_ascii=False)

    print(f"Preview written: {PREVIEW_FILE}")

    if args.dry_run:
        print("Dry run complete — no files modified.")
    else:
        print("Tagging complete.")


if __name__ == "__main__":
    main()
