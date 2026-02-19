# CWW Scraper 🐺

A Python web scraper that extracts episode data from [Chances With Wolves](https://www.chanceswithwolves.com) — a radio show featuring obscure finds, deep cuts, and sonic oddities.

This scraper checks for new episodes before scraping and only extracts data for episodes not previously recorded. It saves the latest episode URL to `latest_episode_info.json` to enable incremental updates.

- Episode thumbnails
- Audio URLs (Soundcloud or Archive.org)
- Episode tracklists (track title and artist)
- **Artist Resolution**: Cache-based artist lookup with MusicBrainz integration to find canonical names and MBIDs.
- **Library Matching**: Robust matching of scraped tracks against local beets library using both names and MBIDs.

## Requirements

- Python 3
- `uv` (for virtual environment and dependency management)
- `requests`, `beautifulsoup4`, `beets`, `ruff`

## Setup

Create and activate a virtual environment:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Usage

### Scrape episodes

```bash
uv run scraper.py
```

### Build and Clean Artist Cache

The artist cache maps scraped artist names to canonical MusicBrainz names and IDs. This reduces API calls and improves matching accuracy.

```bash
# Build the cache (hits MusicBrainz API)
uv run build_artist_cache.py

# Clean the cache (re-verify existing entries using similarity scoring)
uv run clean_artist_cache.py
```

### Tag your beets library

Match scraped tracks against your beets music library and tag them with the `CWW` genre:

```bash
# Preview matches (recommended first step)
uv run add_cww_genre.py --dry-run

# Run the actual tagging
uv run add_cww_genre.py

# Specify custom input files
uv run add_cww_genre.py --input episodes.json --cache artist_cache.json
```

Matches are performed using:
1.  **MBID overlap**: If both your library and the show track have a MusicBrainz Artist ID.
2.  **Name overlap**: Fuzzy matching between normalized artist/title pairs.

Preview results are saved to `cww_tag_preview.json`.

## Linting

```bash
uv run ruff check .
```

Auto-fix issues:

```bash
uv run ruff check . --fix
```
