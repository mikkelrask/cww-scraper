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


# ----------------------------
# MATCHING
# ----------------------------

def find_matches(
    data: list[dict[str, Any]],
    artist_index: dict[str, list[tuple[str, Item]]],
) -> list[Item]:
    """Find matching tracks in the beets library."""
    matches: list[Item] = []
    seen_items: set[int] = set()
    seen_items = set()

    for episode in data:
        for track in episode.get("tracklist", []):
            artist_raw = track.get("artist", "")
            title_raw = track.get("track", "")

            artist = normalize(artist_raw)
            title = normalize(title_raw)

            if artist not in artist_index:
                continue

            for lib_title, item in artist_index[artist]:
                if lib_title == title:
                    if item.id not in seen_items:
                        matches.append(item)
                        seen_items.add(item.id)

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

    print("Loading beets library...")
    lib = load_library()

    print("Indexing library...")
    artist_index = build_index(lib)

    print("Finding matches...")
    matches = find_matches(data, artist_index)

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
