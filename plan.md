# Artist/Track Matching Plan

## Problem

The scraped tracklist contains many variations of the same artist:
- "booker t. & the mg's" / "booker t & the mg's" / "booker t. & the mgs"
- "earth, wind & fire" / "earth wind & fire" / "earth wind and fire"

This prevents matching against the beets library and misses many potential tags.

## Goal

Increase match rate between scraped tracks and beets library using MusicBrainz for artist canonicalization.

## Approach

### 1. Artist Normalization (Existing)

The current `normalize()` function in `add_cww_genre.py` does basic cleanup:
- Lowercase
- Remove parenthetical text
- Replace `&` with "and"
- Remove slashes, punctuation
- Collapse whitespace

This catches some cases but not variations like "earth, wind & fire" → "earth wind and fire".

### 2. Fuzzy Matching (Option A)

Use a fuzzy matching library like `rapidfuzz` or `thefuzz` to match normalized artist names against beets library artists.

**Pros:** Fast, no external API calls
**Cons:** Still guessing, not authoritative

### 3. MusicBrainz API (Option B)

Use MusicBrainz API to:
1. Look up artist by name → get canonical name + MBID
2. Store mapping: `"earth wind and fire" → "Earth, Wind & Fire"`
3. Cache results to avoid repeated API calls

**Pros:** Authoritative, handles variations correctly
**Cons:** Rate limited (1 req/sec without auth), requires caching strategy

## Implementation Plan

### Step 1: Build Artist Cache

```python
# artists.json - cached MusicBrainz lookups
{
  "earth wind and fire": {
    "mbid": "f9a2c6f0-7a34-4a1e-9b2b-6b3c4d5e6f7a8",
    "canonical_name": "Earth, Wind & Fire"
  }
}
```

- Fetch unique normalized artists from `episodes.json`
- Batch lookup (but respect rate limits)
- Save to cache file
- Skip already-cached artists on subsequent runs

### Step 2: Use Cache in Matching

Modify `add_cww_genre.py` to:
1. Load artist cache
2. Before matching, normalize artist name
3. Look up in cache → get canonical name
4. Match against beets library using canonical name

### Step 3: Script Structure

```
# New file: add_cww_genre.py already exists, extend it or create new

# Option A: Extend existing script
add_cww_genre.py --build-cache    # Fetch all artists from MB
add_cww_genre.py --use-cache      # Use cached lookups when tagging

# Option B: Separate script
build_artist_cache.py   # One-time: fetch and cache all artists
```

## Rate Limiting Strategy

- MusicBrainz allows 1 request/second without auth
- With auth (email): 5 requests/second
- Cache aggressively — once looked up, never need to fetch again

## File Outputs

- `artist_cache.json` — Maps normalized → canonical names with MBIDs
- Could also store: `"booker t and the mgs" → {mbid, "Booker T. & the M.G.'s"}`

## Future Enhancements

- Track-level matching: If artist matches but title doesn't, use MB to find similar tracks
- Confidence scores: Some matches might be ambiguous
- Manual review: Export uncertain matches for human review

## API Reference

```python
import requests

def lookup_artist(name: str) -> dict | None:
    url = "https://musicbrainz.org/ws/2/artist"
    params = {
        "query": name,
        "fmt": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "cww-scraper/1.0 (your@email)"
    }
    resp = requests.get(url, params=params, headers=headers)
    data = resp.json()
    if data.get("artists"):
        return data["artists"][0]
    return None
```

## Estimated Work

1. **Build cache script:** ~50 lines
2. **Integrate with tagger:** ~20 lines
3. **Testing:** Manual verification of edge cases

The cache building will take time (one API call per unique artist), but it's a one-time cost that enables fast matching forever.
