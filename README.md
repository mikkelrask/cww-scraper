# CWW Scraper

A Python web scraper that extracts episode data from [Chances With Wolves](https://www.chanceswithwolves.com).

This scraper now checks for new episodes before scraping and only extracts data for episodes not previously recorded. It saves the latest episode URL to `latest_episode_info.json` to enable incremental updates.

## What it extracts

- Episode thumbnails
- Audio URLs (Soundcloud or Archive.org)
- Tracklists (track title and artist)

## Requirements

- Python 3
- `uv` (for virtual environment and dependency management)
- `requests`, `beautifulsoup4`, `ruff`

## Setup

First, create and activate a virtual environment and install dependencies:
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install ruff # ruff is used for linting
```

## Run

Activate the virtual environment and run the scraper:
```bash
source .venv/bin/activate
python scraper.py
```

Output is saved to `episodes.json`. The latest scraped episode URL is stored in `latest_episode_info.json`.

## Lint

Activate the virtual environment and run ruff:
```bash
source .venv/bin/activate
ruff check .
```

To auto-fix issues:
```bash
source .venv/bin/activate
ruff check . --fix
```