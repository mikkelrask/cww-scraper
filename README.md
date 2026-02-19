# CWW Scraper 🐺

A Python web scraper that extracts episode data from [Chances With Wolves](https://www.chanceswithwolves.com) — a radio show featuring obscure finds, deep cuts, and sonic oddities.

This scraper checks for new episodes before scraping and only extracts data for episodes not previously recorded. It saves the latest episode URL to `latest_episode_info.json` to enable incremental updates.

## What it extracts

- Episode thumbnails
- Audio URLs (Soundcloud or Archive.org)
- Tracklists (track title and artist)

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
source .venv/bin/activate
python scraper.py
```

Output is saved to `episodes.json`. The latest scraped episode URL is stored in `latest_episode_info.json`.

### Tag your beets library

Match scraped tracks against your beets music library and tag them with the `CWW` genre:

```bash
source .venv/bin/activate
python add_cww_genre.py                    # Tag matched tracks
python add_cww_genre.py --dry-run           # Preview without tagging
python add_cww_genre.py --input episodes.json --dry-run  # Custom input
```

Preview output is saved to `cww_tag_preview.json`.

## Linting

```bash
source .venv/bin/activate
ruff check .
```

Auto-fix issues:

```bash
ruff check . --fix
```
