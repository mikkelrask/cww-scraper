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
from tqdm import tqdm

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


# Removed helper functions that were replaced by internal logic in find_matches


# ----------------------------
# MATCHING
# ----------------------------

def find_matches(
    episodes: list[dict[str, Any]],
    lib: Library,
    artist_cache: dict[str, Any],
) -> list[Item]:
    """Find matching tracks in the beets library."""
    
    if artist_cache is None:
        artist_cache = {}
    
    print("  Building target lookup set from scraped tracks...")
    # target_keys: set of (type, artist_ident, title_norm)
    # type can be 'mbid' or 'name'
    target_keys = set()
    
    for episode in episodes:
        for track in episode.get("tracklist", []):
            artist_raw = track.get("artist", "").strip()
            title_raw = track.get("track", "").strip()
            if not artist_raw or not title_raw:
                continue
                
            title_norm = normalize(title_raw)
            artist_norm = normalize(artist_raw)
            
            if not title_norm or not artist_norm:
                continue
                
            # 1. Always add the raw scraped name (normalized)
            target_keys.add(('name', artist_norm, title_norm))
            
            # 2. Add cache-based names and MBIDs
            # Check for name in cache (direct or normalized)
            cached = artist_cache.get(artist_raw) or artist_cache.get(artist_norm)
            if cached:
                mbid = cached.get("mbid")
                if mbid:
                    target_keys.add(('mbid', mbid, title_norm))
                
                canonical = cached.get("canonical_name")
                if canonical:
                    canonical_norm = normalize(canonical)
                    if canonical_norm:
                        target_keys.add(('name', canonical_norm, title_norm))

    print(f"  Created {len(target_keys)} matching targets.")

    matches: list[Item] = []
    seen_ids: set[int] = set()
    mbid_matches = 0
    name_matches = 0
    
    print("  Iterating through beets library...")
    # Get total count for progress bar
    total_items = len(lib.items())
    
    for item in tqdm(lib.items(), total=total_items, unit="item"):
        # Beets items have attributes like 'artist', 'title', 'mb_artistid'
        title_norm = normalize(item.title)
        if not title_norm:
            continue
        
        matched = False
        
        # Check MBID first (most accurate)
        mbid = item.get("mb_artistid")
        if mbid and ('mbid', mbid, title_norm) in target_keys:
            if item.id not in seen_ids:
                matches.append(item)
                seen_ids.add(item.id)
                mbid_matches += 1
                matched = True
        
        if matched:
            continue
            
        # Check artist name
        artist_norm = normalize(item.artist)
        if artist_norm and ('name', artist_norm, title_norm) in target_keys:
            if item.id not in seen_ids:
                matches.append(item)
                seen_ids.add(item.id)
                name_matches += 1
                matched = True
                
        if matched:
            continue
            
        # Optional: Check album artist for various artists / compilations
        albumartist_norm = normalize(item.albumartist)
        if albumartist_norm and albumartist_norm != artist_norm and ('name', albumartist_norm, title_norm) in target_keys:
            if item.id not in seen_ids:
                matches.append(item)
                seen_ids.add(item.id)
                name_matches += 1

    print(f"  Matches found: {len(matches)} (MBID: {mbid_matches}, Name: {name_matches})")
    return matches


# ----------------------------
# TAGGING
# ----------------------------

def tag_items(items: list[Item], dry_run: bool) -> list[dict[str, str]]:
    """Tag items with CWW genre, return preview of changes."""
    preview: list[dict[str, str]] = []

    print(f"  {'Pre-viewing' if dry_run else 'Tagging'} {len(items)} items...")
    for item in tqdm(items, unit="track", disable=len(items) < 10):
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
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="Minimum similarity score to use from MB cache (0-100)",
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
        
        if args.min_score > 0:
            original_count = len(artist_cache)
            # Filter cache: Keep beets entries or MB entries with sufficient score
            artist_cache = {
                k: v for k, v in artist_cache.items() 
                if v.get("source") == "beets" or v.get("score", 0) >= args.min_score
            }
            removed = original_count - len(artist_cache)
            if removed > 0:
                print(f"  Filtered out {removed} entries with score < {args.min_score}")

    print("Loading beets library...")
    lib = load_library()

    print("Finding matches...")
    matches = find_matches(
        data,
        lib,
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
