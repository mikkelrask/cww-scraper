#!/usr/bin/env python3
"""
Scraper for chanceswithwolves.com
Extracts episode data including soundcloud URL, thumbnail, and tracklist.
"""

import json
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote

BASE_URL = "https://www.chanceswithwolves.com"
OUTPUT_FILE = "episodes.json"


def get_soup(url, retries=3):
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


def extract_episode_links(soup):
    """Extract all episode URLs from a page."""
    links = set()
    for a in soup.find_all("a", class_="masonry-link"):
        href = a.get("href")
        if href:
            full_url = urljoin(BASE_URL, href)
            if "/episode-" in full_url or full_url.startswith(BASE_URL):
                links.add(full_url)
    return sorted(links)


def get_episode_range_urls():
    """Get URLs for all episode range pages."""
    return [
        f"{BASE_URL}/episodes-501-now",
        f"{BASE_URL}/401-now",
        f"{BASE_URL}/episodes-301-now",
        f"{BASE_URL}/episodes-201-300",
        f"{BASE_URL}/episodes-101-200",
        f"{BASE_URL}/episodes0-100",
        f"{BASE_URL}/specialmixes",
    ]


def extract_episode_data(url, soup):
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


def scrape_episodes(episode_urls):
    """Scrape all episode pages."""
    episodes = []
    total = len(episode_urls)

    for i, url in enumerate(episode_urls, 1):
        print(f"Scraping {i}/{total}: {url}")
        soup = get_soup(url)
        if soup:
            data = extract_episode_data(url, soup)
            episodes.append(data)
            print(
                f"  -> Thumbnail: {data['thumbnail'][:50] if data['thumbnail'] else 'N/A'}..."
            )
            print(f"  -> Audio: {data['audio_type']}: {data['audio_url']}")
            print(f"  -> Tracks: {len(data['tracklist'])}")
        else:
            print(f"  -> Failed to fetch")
        time.sleep(0.5)  # Rate limiting

    return episodes


def main():
    all_episode_urls = set()

    # First get homepage
    print(f"Fetching homepage: {BASE_URL}")
    soup = get_soup(BASE_URL)
    if soup:
        print("Extracting episode links from homepage...")
        episode_urls = extract_episode_links(soup)
        all_episode_urls.update(episode_urls)
        print(f"Found {len(episode_urls)} episode links from homepage")

    # Also get episode range pages
    print("\nFetching episode range pages...")
    range_urls = get_episode_range_urls()
    for range_url in range_urls:
        print(f"Fetching: {range_url}")
        soup = get_soup(range_url)
        if soup:
            episode_urls = extract_episode_links(soup)
            new_count = len([u for u in episode_urls if u not in all_episode_urls])
            all_episode_urls.update(episode_urls)
            print(f"  -> Found {len(episode_urls)} links ({new_count} new)")

    episode_urls = sorted(all_episode_urls)
    print(f"\nTotal unique episode URLs: {len(episode_urls)}")

    # Also check for pagination/episode range pages
    # The site has pages like /episodes-501-now, /401-now, etc.
    # For now, we'll work with what we have from homepage

    if episode_urls:
        episodes = scrape_episodes(episode_urls)

        # Save to JSON
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(episodes, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {len(episodes)} episodes to {OUTPUT_FILE}")
    else:
        print("No episode links found")


if __name__ == "__main__":
    main()
