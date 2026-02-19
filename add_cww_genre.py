#!/usr/bin/env python3

import json
import re
import argparse
from collections import defaultdict

from beets import config
from beets.library import Library


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

def load_library():
    config.read()
    library_path = config["library"].as_filename()
    return Library(library_path)


def build_index(lib):
    artist_index = defaultdict(list)

    for item in lib.items():
        artist = normalize(item.artist)
        title = normalize(item.title)

        if artist and title:
            artist_index[artist].append((title, item))

    return artist_index


# ----------------------------
# MATCHING
# ----------------------------

def find_matches(data, artist_index):
    matches = []
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

def tag_items(items, dry_run):
    preview = []

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input", default=DEFAULT_INPUT_JSON)

    args = parser.parse_args()

    print("Loading episode JSON...")

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

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
