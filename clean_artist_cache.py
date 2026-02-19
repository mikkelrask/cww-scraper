#!/usr/bin/env python3
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

# Paths
CACHE_FILE = "artist_cache.json"
BACKUP_FILE = "artist_cache.backup.json"
REMOVED_FILE = "removed_entries.json"

def normalize(text: str) -> str:
    """Basic normalization for matching."""
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = text.replace("&", "and")
    text = text.replace("/", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def calculate_similarity(a: str, b: str) -> int:
    """Calculate string similarity ratio as a percentage (0-100)."""
    if not a or not b:
        return 0
    norm_a = normalize(a)
    norm_b = normalize(b)
    ratio = SequenceMatcher(None, norm_a, norm_b).ratio()
    return int(ratio * 100)

def clean_cache(min_score: int = 80):
    if not os.path.exists(CACHE_FILE):
        print(f"Error: {CACHE_FILE} not found.")
        return

    print(f"Loading {CACHE_FILE}...")
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)

    # Backup original
    print(f"Creating backup: {BACKUP_FILE}...")
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    total_entries = len(cache)
    cleaned_cache = {}
    removed_entries = {}
    
    mb_count = 0
    beets_count = 0
    removed_count = 0

    print(f"Cleaning {total_entries} entries (threshold: {min_score}%)...")
    
    for key, data in cache.items():
        source = data.get("source")
        
        if source == "beets":
            # Keep beets matches (usually local and reliable)
            cleaned_cache[key] = data
            beets_count += 1
        elif source == "musicbrainz":
            mb_count += 1
            canonical_name = data.get("canonical_name", "")
            
            # Use our new similarity check
            sim = calculate_similarity(key, canonical_name)
            
            # MusicBrainz aliases are not in the old cache, so we can only check against canonical_name
            # If the old cache had a 'score' of 100, we check if our similarity matches that confidence
            if sim >= min_score:
                # Update the score to reflect real similarity
                data["score"] = sim
                cleaned_cache[key] = data
            else:
                removed_entries[key] = {
                    "original_data": data,
                    "calculated_similarity": sim
                }
                removed_count += 1
        else:
            # Keep unknown sources just in case
            cleaned_cache[key] = data

    print("\nResults:")
    print(f"  Total processed: {total_entries}")
    print(f"  Beets entries kept: {beets_count}")
    print(f"  MusicBrainz entries checked: {mb_count}")
    print(f"  MusicBrainz entries kept: {mb_count - removed_count}")
    print(f"  MusicBrainz entries removed: {removed_count}")

    # Save cleaned cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned_cache, f, indent=2, ensure_ascii=False)
    
    # Save removed entries for manual review
    if removed_entries:
        with open(REMOVED_FILE, "w", encoding="utf-8") as f:
            json.dump(removed_entries, f, indent=2, ensure_ascii=False)
        print(f"  Details of removed entries saved to: {REMOVED_FILE}")

    print(f"\nCleaned cache saved to {CACHE_FILE}")

if __name__ == "__main__":
    clean_cache()
