# CWW Scraper

A Python web scraper that extracts episode data from [Chances With Wolves](https://www.chanceswithwolves.com).

## What it extracts

- Episode thumbnails
- Audio URLs (Soundcloud or Archive.org)
- Tracklists (track title and artist)

## Requirements

- Python 3
- `requests` and `beautifulsoup4`

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python scraper.py
```

Output is saved to `episodes.json`.

## Lint

```bash
ruff check .
```
