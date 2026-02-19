#!/usr/bin/env python3
"""
Scraper for chanceswithwolves.com
Extracts episode data including soundcloud URL, thumbnail, and tracklist.
"""

import argparse
import json
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import urljoin, unquote

BASE_URL = "https://www.chanceswithwolves.com"
OUTPUT_FILE = "episodes.json"
LATEST_EPISODE_INFO_FILE = "latest_episode_info.json"
DEFAULT_REQUEST_DELAY = 0.5

def _get_episode_number_from_url(url: str) -> int | None:
    """Extracts the episode number from a URL like '.../episode-XXX'."""
    match = re.search(r"episode-(\d+)", url)
    if match:
        return int(match.group(1))
    return None

def read_latest_episode_info() -> str | None:
    """Reads the URL of the last scraped episode from the info file."""
    try:
        with open(LATEST_EPISODE_INFO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("latest_episode_url")
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def write_latest_episode_info(latest_episode_url: str):
    """Writes the URL of the latest scraped episode to the info file."""
    with open(LATEST_EPISODE_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump({"latest_episode_url": latest_episode_url}, f, indent=2)


def get_soup(url: str, retries: int = 3) -> BeautifulSoup | None:
    """Fetch URL and return BeautifulSoup object."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2**attempt)
    return None


def extract_episode_links(soup: BeautifulSoup) -> list[str]:
    """Extract all episode URLs from a page and sort by episode number."""
    episode_urls_with_numbers = []
    other_urls = []

    for article in soup.find_all("article", class_="masonry-item"):
        a_tag = article.find("a", class_="masonry-link")
        if a_tag:
            href = a_tag.get("href")
            if href:
                full_url = urljoin(BASE_URL, href)
                episode_number = _get_episode_number_from_url(full_url)
                if episode_number is not None:
                    episode_urls_with_numbers.append((episode_number, full_url))
                # Keep other valid episode-like URLs that might not have a clear number
                # but are part of the main site content, e.g., special mixes,
                # ensuring they don't get sorted by non-existent numbers.
                elif "/episode-" in full_url or full_url.startswith(BASE_URL):
                    other_urls.append(full_url)

    # Sort episodes by number in descending order
    episode_urls_with_numbers.sort(key=lambda x: x[0], reverse=True)

    # Extract just the URLs from the sorted list
    sorted_urls = [url for _, url in episode_urls_with_numbers]

    # Append other URLs (like special mixes) at the end, sorted alphabetically for consistency
    # Convert to set first to avoid duplicates if any, then to list for sorting
    sorted_urls.extend(sorted(list(set(other_urls))))

    return sorted_urls


def get_episode_range_urls(soup: BeautifulSoup) -> list[str]:
    """Dynamically get URLs for all episode range pages from navigation."""
    range_urls = []
    # Find the "RADIO SHOWS" navigation item
    radio_shows_li = None
    for li in soup.find_all("li", class_="folder-collection folder"):
        a_tag = li.find("a", string="RADIO SHOWS")
        if a_tag:
            radio_shows_li = li
            break

    if radio_shows_li:
        # Find all <a> tags within the "folder-child" div under "RADIO SHOWS"
        folder_child_ul = radio_shows_li.find("div", class_="folder-child")
        if folder_child_ul:
            for a_tag in folder_child_ul.find_all("a"):
                href = a_tag.get("href")
                if href:
                    full_url = urljoin(BASE_URL, href)
                    range_urls.append(full_url)
    return range_urls


def extract_episode_data(url: str, soup: BeautifulSoup) -> dict[str, Any]:
    """Extract thumbnail, audio URL, and tracklist from episode page."""
    data = {
        "url": url,
        "thumbnail": None,
        "audio_url": None,
        "audio_type": None,
        "tracklist": [],
    }

    # Extract thumbnail - find figure#thumbnail img
    thumbnail = soup.find("figure", id="thumbnail")
    if thumbnail:
        img = thumbnail.find("img")
        if img:
            data["thumbnail"] = img.get("data-src") or img.get("src")

    # Extract Soundcloud URL from iframe
    soundcloud_iframe = soup.find("iframe", src=re.compile(r"soundcloud\.com/player"))
    if soundcloud_iframe:
        src = unquote(soundcloud_iframe.get("src", ""))
        match = re.search(r"tracks?/([0-9]+)", src)
        if match:
            track_id = match.group(1)
            data["audio_url"] = (
                f"https://soundcloud.com/chanceswithwolves/tracks/{track_id}"
            )
            data["audio_type"] = "soundcloud"

    # Extract Archive.org URL (for older episodes)
    if not data["audio_url"]:
        archive_iframe = soup.find("iframe", src=re.compile(r"archive\.org/embed"))
        if archive_iframe:
            src = archive_iframe.get("src", "")
            match = re.search(r"archive\.org/embed/([^/\?]+)", src)
            if match:
                archive_id = match.group(1)
                data["audio_url"] = f"https://archive.org/details/{archive_id}"
                data["audio_type"] = "archive.org"

    # Extract tracklist - find paragraphs with track info after any player block
    # Tracklist is in <p style="white-space:pre-wrap;"> elements (newer episodes)
    # OR in <p><span style="...">track - artist<br>... (older episodes)
    # Format: "tracktitle - artist"

    # Try finding tracklist after soundcloud block first
    soundcloud_block = soup.find("div", class_=re.compile("soundcloud-block"))

    # If no soundcloud block, try html block
    if not soundcloud_block:
        soundcloud_block = soup.find("div", class_=re.compile("html-block"))

    if soundcloud_block:
        # First check the block itself for tracklist (old format)
        # Format: <p><span>track - artist<br>...
        if not data["tracklist"]:
            all_paras = soundcloud_block.find_all("p")
            for p in all_paras:
                spans = p.find_all("span")
                for span in spans:
                    text_content = span.get_text(separator="\n", strip=True)
                    if text_content:
                        lines = text_content.split("\n")
                        for line in lines:
                            line = line.strip()
                            if line and " - " in line:
                                parts = line.split(" - ", 1)
                                if len(parts) == 2:
                                    track = parts[0].strip()
                                    artist = parts[1].strip()
                                    if track and artist:
                                        data["tracklist"].append(
                                            {"track": track, "artist": artist}
                                        )

        # Then check siblings for tracklist (new format)
        current = soundcloud_block.find_next_sibling()
        while current:
            # Stop at certain block types that indicate end of tracklist
            if current.name == "div" and current.get("class"):
                block_class = " ".join(current.get("class", []))
                if (
                    "sqs-block-markdown" in block_class
                    or "sqs-block-video" in block_class
                ):
                    break

            if current.name == "div":
                # Format 1: <p style="white-space:pre-wrap;">
                paras = current.find_all(
                    "p", style=re.compile(r"white-space:\s*pre-wrap")
                )
                for p in paras:
                    text = p.get_text(strip=True)
                    if text and " - " in text:
                        parts = text.split(" - ", 1)
                        if len(parts) == 2:
                            data["tracklist"].append(
                                {"track": parts[0].strip(), "artist": parts[1].strip()}
                            )

                # Format 2: <p><span>track - artist<br> (older episodes)
                paras = current.find_all("p")
                for p in paras:
                    spans = p.find_all("span")
                    for span in spans:
                        text_content = span.get_text(separator="\n", strip=True)
                        if text_content:
                            lines = text_content.split("\n")
                            for line in lines:
                                line = line.strip()
                                if line and " - " in line:
                                    parts = line.split(" - ", 1)
                                    if len(parts) == 2:
                                        track = parts[0].strip()
                                        artist = parts[1].strip()
                                        if track and artist:
                                            data["tracklist"].append(
                                                {"track": track, "artist": artist}
                                            )
            current = current.find_next_sibling()

    return data


def scrape_episodes(episode_urls: list[str], delay: float = DEFAULT_REQUEST_DELAY) -> list[dict[str, Any]]:
    """Scrape all episode pages."""
    episodes = []

    for url in tqdm(episode_urls, desc="Scraping episodes", unit="ep", ncols=80, leave=True):
        soup = get_soup(url)
        if soup:
            data = extract_episode_data(url, soup)
            episodes.append(data)
        time.sleep(delay)

    return episodes


def collect_all_episode_urls(homepage_soup: BeautifulSoup) -> set[str]:
    """Collect all episode URLs from homepage and range pages."""
    all_episode_urls: set[str] = set()

    homepage_episode_links = extract_episode_links(homepage_soup)
    all_episode_urls.update(homepage_episode_links)

    print("\nFetching episode range pages...")
    range_urls = get_episode_range_urls(homepage_soup)

    for range_url in tqdm(range_urls, desc="Fetching range pages", unit="page", ncols=80, leave=True):
        soup = get_soup(range_url)
        if soup:
            episode_urls = extract_episode_links(soup)
            all_episode_urls.update(episode_urls)
        time.sleep(DEFAULT_REQUEST_DELAY)

    return all_episode_urls


def filter_new_episodes(
    all_urls: set[str],
    previously_stored_url: str | None,
    current_latest_url: str,
) -> list[str]:
    """Filter URLs to find episodes that need scraping."""
    sorted_urls = sorted(
        all_urls,
        key=lambda url: _get_episode_number_from_url(url) or 0,
        reverse=True,
    )

    if not previously_stored_url:
        return sorted_urls

    previous_episode_num = _get_episode_number_from_url(previously_stored_url)
    if previous_episode_num is None:
        return sorted_urls

    new_episodes = []
    for url in sorted_urls:
        episode_num = _get_episode_number_from_url(url)
        if episode_num is not None and episode_num > previous_episode_num:
            new_episodes.append(url)

    print(f"Found {len(new_episodes)} new episodes to scrape.")
    return new_episodes


def load_existing_episodes() -> list[dict[str, Any]]:
    """Load existing episodes from JSON file."""
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"No existing {OUTPUT_FILE} found. Starting fresh.")
        return []


def save_episodes(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> None:
    """Merge and save episodes to JSON."""
    combined = {ep["url"]: ep for ep in existing}
    for episode in new:
        combined[episode["url"]] = episode

    final = list(combined.values())
    final.sort(
        key=lambda ep: _get_episode_number_from_url(ep["url"]) or 0,
        reverse=True,
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(new)} new episodes. Total {len(final)} to {OUTPUT_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape CWW episodes")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of episodes to scrape (0 = no limit)",
    )
    args = parser.parse_args()

    print(f"Fetching homepage: {BASE_URL}")
    homepage_soup = get_soup(BASE_URL)
    if not homepage_soup:
        print("Failed to fetch homepage. Exiting.")
        return

    homepage_episode_links = extract_episode_links(homepage_soup)
    if not homepage_episode_links:
        print("No episode links found on homepage. Exiting.")
        return

    current_latest_url = homepage_episode_links[0]
    print(f"Latest episode on site: {current_latest_url}")

    previously_stored_url = read_latest_episode_info()

    if previously_stored_url == current_latest_url:
        print("No new episodes found. Exiting.")
        return

    print("New episode(s) found! Starting scrape.")
    write_latest_episode_info(current_latest_url)

    all_episode_urls = collect_all_episode_urls(homepage_soup)
    episodes_to_scrape = filter_new_episodes(
        all_episode_urls, previously_stored_url, current_latest_url
    )

    if args.limit > 0:
        episodes_to_scrape = episodes_to_scrape[: args.limit]
        print(f"Limited to {args.limit} episodes")

    if not episodes_to_scrape:
        print("No new episodes to scrape.")
        return

    episodes = scrape_episodes(episodes_to_scrape)
    existing = load_existing_episodes()
    save_episodes(existing, episodes)


if __name__ == "__main__":
    main()
