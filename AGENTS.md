# Agent Guidelines for cww-scraper

Python web scraping project that extracts episode data from chanceswithwolves.com.

## Project Overview

- **Language**: Python 3
- **Dependencies**: requests, beautifulsoup4, beets, ruff
- **Virtual Environment**: `.venv` (use `source .venv/bin/activate` to activate)
- **Entry Points**: `scraper.py`, `build_artist_cache.py`, `clean_artist_cache.py`, `add_cww_genre.py`

## Commands

### Install Dependencies

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Linting

```bash
uv run ruff check .
```

Auto-fix issues:

```bash
uv run ruff check . --fix
```

### Running the Scraper

```bash
uv run scraper.py
```

### Running the Genre Tagger

```bash
uv run add_cww_genre.py                    # Tag matched tracks
uv run add_cww_genre.py --dry-run           # Preview without tagging
uv run add_cww_genre.py --input episodes.json --dry-run  # Custom input
```

### Running Tests

No tests exist yet. When added, run with:

```bash
uv run pytest
```

Run a single test:

```bash
uv run pytest path/to/test_file.py::test_function_name
```

## Code Style

### General

- Follow PEP 8
- 4 spaces for indentation
- Max line length: 88 characters (ruff default)
- Use type hints for all public functions

### Imports

Order: stdlib → third-party → local. Separate groups with blank lines. Sort alphabetically.

```python
import json
import re
import time

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
```

### Naming

- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private functions: prefix with `_`

### Type Hints

Required for all function signatures:

```python
def get_soup(url: str, retries: int = 3) -> BeautifulSoup | None:
    ...

def extract_episode_links(soup: BeautifulSoup) -> list[str]:
    ...
```

### Error Handling

- Use specific exceptions (e.g., `requests.RequestException`)
- Include context in error messages
- Use `print()` for status output
- Continue on non-critical errors
- Implement retry logic with exponential backoff for network requests

### Functions

- Keep functions focused and single-purpose
- Docstrings for all public functions: describe what, args, returns
- Prefer early returns over nested conditionals

### Constants

- Place at top of file after imports
- Use descriptive names (e.g., `BASE_URL`, `OUTPUT_FILE`)

### Web Scraping

- Always include User-Agent header (from `.env` or default)
- Rate limit requests (4 req/sec max for MusicBrainz)
- Use `difflib.SequenceMatcher` similarity (80-85% threshold) to verify MusicBrainz Lucene scores
- Handle missing data gracefully (check for None before accessing attributes)
- Use BeautifulSoup methods: `find()`, `find_all()`, `get()` with fallbacks

### Artist Matching Strategy

1.  **Normalize**: Standardize artist/title strings (lowercase, remove parens, replace symbols).
2.  **MBID Match**: High confidence matching using MusicBrainz Artist IDs from the cache.
3.  **Name Match**: Fallback matching using normalized artist/title strings.
4.  **Verification**: Always use `calculate_similarity` for MB API results to avoid false positives from relative Lucene scores.

### File Operations

- Use context managers: `with open(...) as f:`
- Specify encoding: `encoding="utf-8"`
- Handle `FileNotFoundError` and `json.JSONDecodeError`

### JSON Output

- Use `indent=2` for pretty-printing
- Set `ensure_ascii=False` for non-ASCII content

## File Structure

```
cww-scraper/
├── scraper.py               # Main scraper (episodes.json)
├── build_artist_cache.py    # MB lookup for canonical names/IDs
├── clean_artist_cache.py    # Verify/prune cache using similarity
├── add_cww_genre.py         # Tag tracks in beets library
├── requirements.txt         # Dependencies
├── episodes.json            # Episode data (generated)
├── artist_cache.json        # Artist mapping (generated)
├── latest_episode_info.json # Last scraped episode URL (generated)
├── cww_tag_preview.json    # Tag preview output (generated)
└── .venv/                  # Virtual environment
```

## Common Tasks

### Add dependency

1. `uv pip install <package>`
2. Add to `requirements.txt`
3. Run `ruff check .`

### Modify scraper

1. Test: `python scraper.py`
2. Check output in `episodes.json`
3. Run `ruff check .` before committing

### Debug

```bash
uv run python -m pdb scraper.py
```
