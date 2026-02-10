"""Video ingestion utilities and helpers.

This module provides small, testable functions that:
- obtain a list of video URLs (stubs for now)
- download videos into the `videos/raw/` folder using yt-dlp
- add entries to the inventory with `status_fb = 'pending'`

Note: The download step uses yt-dlp programmatically; ensure the package is
installed and Playwright/other browsers are set up when needed.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone
from typing import List, cast, Any, Optional
from scripts.exceptions import DownloadError, InventoryUpdateError
from scripts.utils import random_wait, retry

from fake_useragent import UserAgent
from yt_dlp import YoutubeDL
from yt_dlp.networking.impersonate import ImpersonateTarget
import polars as pl

from scripts.common import (
    BASE_DIR,
    RAW_DIR,
    ensure_dirs,
    _read_inventory_lazy,
    _append_to_inventory,
    logger,
)


# Configuration from environment variables
TIKTOK_TIMEOUT = int(os.getenv("TIKTOK_TIMEOUT", "45000"))  # ms
TIKTOK_SCROLL_ATTEMPTS = int(os.getenv("TIKTOK_SCROLL_ATTEMPTS", "3"))
TIKTOK_SCROLL_WAIT_MIN = int(os.getenv("TIKTOK_SCROLL_WAIT_MIN", "2"))
TIKTOK_SCROLL_WAIT_MAX = int(os.getenv("TIKTOK_SCROLL_WAIT_MAX", "5"))

# User-Agent rotation pool (10+ realistic agents)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
]

DEFAULT_USER_AGENT = USER_AGENTS[0]

# TikTok CSS selectors with fallback strategies
TIKTOK_VIDEO_SELECTORS = [
    'a[href*="/video/"]',  # Primary selector
    'a[data-e2e="search-card-video-link"]',  # Search results
    'div[data-e2e="search-card-desc"] a',  # Description links
]


def obtener_tendencias(source: str | None = None) -> List[str]:
    """Return a list of video URLs to ingest.

    This is a lightweight stub used by tests and early development. Replace
    with real scraping or Playwright-driven logic when integrating full
    discovery pipelines.
    """
    return [source] if source else []


def procesar_hashtag(hashtag: str, max_videos: int = 10) -> List[str]:
    """Return video URLs for a given hashtag using Playwright.
    
    Args:
        hashtag: TikTok hashtag URL (e.g., 'https://www.tiktok.com/tag/programacion')
        max_videos: Maximum number of video URLs to extract
        
    Returns:
        List of video URLs found for the hashtag
        
    Note:
        Requires playwright to be installed:
        pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        logger.warning("Playwright not installed. Install with: pip install playwright")
        return []
    
    video_urls = []
    user_agent = _get_random_user_agent()
    
    logger.info(
        "Starting hashtag scraping",
        extra={
            "hashtag": hashtag,
            "max_videos": max_videos,
            "user_agent": user_agent[:50] + "...",
            "timeout_ms": TIKTOK_TIMEOUT,
        }
    )
    
    try:
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            
            # Create context with realistic user agent
            context = browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
            )
            
            page = context.new_page()
            
            logger.info(f"Navigating to hashtag: {hashtag}")
            
            # Navigate to hashtag page
            try:
                page.goto(hashtag, wait_until='networkidle', timeout=TIKTOK_TIMEOUT)
                random_wait(TIKTOK_SCROLL_WAIT_MIN, TIKTOK_SCROLL_WAIT_MAX)
            except PlaywrightTimeout:
                logger.warning(
                    "Timeout loading hashtag page",
                    extra={"hashtag": hashtag, "timeout_ms": TIKTOK_TIMEOUT}
                )
            
            # Scroll to load more videos
            for i in range(TIKTOK_SCROLL_ATTEMPTS):
                logger.info(
                    f"Scroll attempt {i+1}/{TIKTOK_SCROLL_ATTEMPTS}",
                    extra={"attempt": i+1, "max_attempts": TIKTOK_SCROLL_ATTEMPTS}
                )
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                random_wait(TIKTOK_SCROLL_WAIT_MIN, TIKTOK_SCROLL_WAIT_MAX)
            
            # Extract video URLs with selector fallback
            links = _extract_video_links(page)
            
            logger.info(
                f"Found {len(links)} potential video links",
                extra={"link_count": len(links), "hashtag": hashtag}
            )
            
            seen = set()
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if not href:
                        continue
                    
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = f"https://www.tiktok.com{href}"
                    
                    # Filter valid TikTok video URLs
                    if '/video/' in href and href not in seen:
                        video_urls.append(href)
                        seen.add(href)
                        logger.info(
                            "Extracted video URL",
                            extra={"url": href, "count": len(video_urls)}
                        )
                        
                        if len(video_urls) >= max_videos:
                            break
                            
                except Exception as e:
                    logger.warning(
                        "Error extracting link",
                        extra={"error": str(e), "error_type": type(e).__name__}
                    )
                    continue
            
            browser.close()
            
        logger.info(
            "Successfully extracted video URLs",
            extra={
                "hashtag": hashtag,
                "extracted_count": len(video_urls),
                "requested_count": max_videos,
            }
        )
        return video_urls[:max_videos]
        
    except Exception as exc:
        logger.exception(
            "Failed to process hashtag",
            extra={"hashtag": hashtag, "error": str(exc), "error_type": type(exc).__name__}
        )
        return []


def _get_random_user_agent() -> str:
    """Get a random user agent from the predefined pool.
    
    Falls back to fake_useragent library if pool is unavailable.
    """
    try:
        if USER_AGENTS:
            return random.choice(USER_AGENTS)
        # Fallback to fake_useragent
        return UserAgent().random
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "Falling back to default User-Agent",
            extra={"error": str(exc), "error_type": type(exc).__name__}
        )
        return DEFAULT_USER_AGENT


def _extract_video_links(page) -> list:
    """Extract video links using multiple selector strategies.
    
    Tries multiple CSS selectors with fallback to handle TikTok UI changes.
    
    Args:
        page: Playwright page object
        
    Returns:
        List of link elements found
    """
    for selector in TIKTOK_VIDEO_SELECTORS:
        try:
            links = page.query_selector_all(selector)
            if links:
                logger.info(
                    f"Found links using selector: {selector}",
                    extra={"selector": selector, "count": len(links)}
                )
                return links
        except Exception as e:
            logger.warning(
                f"Selector failed: {selector}",
                extra={"selector": selector, "error": str(e)}
            )
            continue
    
    logger.warning(
        "All selectors failed, no video links found",
        extra={"selectors_tried": TIKTOK_VIDEO_SELECTORS}
    )
    return []


def _already_exists(video_id: str) -> bool:
    lf = _read_inventory_lazy()
    exists = (
        lf.filter(pl.col("video_id") == video_id)
        .select(pl.col("video_id"))
        .limit(1)
        .collect()
    )
    return exists.height > 0


def ingest(source_url: str, retries: int = 3) -> None:
    """Single-shot ingestion: download at most one new video for `source_url`."""
    if not source_url:
        logger.warning("No source_url provided to ingest()")
        return

    ensure_dirs()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    user_agent = _get_random_user_agent()

    listing_opts = {
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
        "user_agent": user_agent,
        # Use impersonation to bypass TikTok 403 blocks
        "impersonate": ImpersonateTarget(client="chrome"),
        # human-like ytdlp sleep hints
        "sleep_interval": 3,
        "max_sleep_interval": 10,
        "sleep_subtitles": 1,
    }

    try:
        random_wait(1, 6)
        with YoutubeDL(cast(Any, listing_opts)) as ydl:
            listing = ydl.extract_info(source_url, download=False)
    except Exception as exc:
        logger.exception("Failed to fetch listing for %s: %s", source_url, exc)
        raise DownloadError(f"Failed to fetch listing for {source_url}") from exc

    entries = cast(list, listing.get("entries")) if listing.get("entries") is not None else []
    if not entries and listing.get("id") is not None:
        entries = [listing]

    target_entry = None
    for entry in entries:
        video_id = cast(str, entry.get("id")) if entry.get("id") is not None else None
        entry_url = entry.get("url") or entry.get("webpage_url")
        if not video_id or not entry_url:
            continue
        if _already_exists(video_id):
            continue
        target_entry = entry
        break

    if not target_entry:
        logger.info("No new videos found")
        return

    # Prefer webpage_url over url (CDN URL) as CDN URLs expire quickly
    target_url = target_entry.get("webpage_url") or target_entry.get("url")
    if not target_url:
        logger.warning("Candidate video missing URL, skipping download")
        return

    download_opts = {
        "outtmpl": str(RAW_DIR / "%(id)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
        "user_agent": user_agent,
        # Use impersonation to bypass TikTok 403 blocks
        "impersonate": ImpersonateTarget(client="chrome"),
        # hints for yt-dlp to act more human-like
        "sleep_interval": 3,
        "max_sleep_interval": 10,
        "sleep_subtitles": 1,
    }
    # ensure we have a video_id for status updates
    video_id = cast(str, target_entry.get("id")) if target_entry.get("id") is not None else None

    def _do_download():
        with YoutubeDL(cast(Any, download_opts)) as ydl:
            return ydl.extract_info(target_url, download=True)

    try:
        random_wait(1, 6)
        # decorate the small helper with retry behavior
        info = retry(retries=retries, base=5.0, factor=3.0, max_wait=90.0, jitter=True)(_do_download)()
    except Exception as exc:
        logger.error("Download failed for %s after retries: %s", target_url, exc)
        from scripts.common import update_inventory_by_video_id
        if video_id:
            try:
                update_inventory_by_video_id(video_id, {"status_fb": "failed"})
            except Exception as update_exc:
                logger.error("Failed to mark video %s as failed in inventory: %s", video_id, update_exc)
        raise DownloadError(f"Failed to download {target_url} after {retries} attempts") from exc

    video_id = cast(str, info.get("id")) if info.get("id") is not None else (
        cast(str, target_entry.get("id")) if target_entry.get("id") is not None else None
    )
    if not video_id:
        logger.warning("Downloaded video missing ID, skipping inventory append")
        return

    matches = list(RAW_DIR.glob(f"{video_id}.*"))
    path_local = str(matches[0].relative_to(BASE_DIR)) if matches else ""

    row = {
        "video_id": video_id,
        "source_url": info.get("webpage_url")
        or target_entry.get("webpage_url")
        or source_url,
        "title": info.get("title", ""),
        "duration": int(info.get("duration") or 0),
        "path_local": path_local,
        "status_fb": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    try:
        _append_to_inventory([row])
    except Exception as exc:
        logger.exception("Failed to update inventory for %s: %s", video_id, exc)
        raise InventoryUpdateError(f"Failed to update inventory for {video_id}") from exc

    logger.info("Downloaded %s", video_id)


def ingest_from_hashtag(hashtag_url: str, max_videos: int = 5) -> int:
    """Ingest multiple videos from a hashtag.
    
    Args:
        hashtag_url: TikTok hashtag URL (e.g., 'https://www.tiktok.com/tag/programacion')
        max_videos: Maximum number of videos to ingest
        
    Returns:
        Number of videos successfully ingested
    """
    logger.info(
        "Starting hashtag ingestion",
        extra={
            "hashtag_url": hashtag_url,
            "max_videos": max_videos,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    
    video_urls = procesar_hashtag(hashtag_url, max_videos=max_videos)
    
    if not video_urls:
        logger.info(
            "No videos found for hashtag",
            extra={"hashtag_url": hashtag_url, "videos_found": 0}
        )
        return 0
    
    logger.info(
        "Found videos, starting ingestion",
        extra={"video_count": len(video_urls), "hashtag_url": hashtag_url}
    )
    
    success_count = 0
    failed_urls = []
    
    for idx, url in enumerate(video_urls, 1):
        try:
            logger.info(
                f"Ingesting video {idx}/{len(video_urls)}",
                extra={"url": url, "progress": f"{idx}/{len(video_urls)}"}
            )
            ingest(url)
            success_count += 1
        except Exception as e:
            failed_urls.append({"url": url, "error": str(e)})
            logger.error(
                "Failed to ingest video",
                extra={
                    "url": url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "progress": f"{idx}/{len(video_urls)}",
                }
            )
            continue
    
    logger.info(
        "Hashtag ingestion completed",
        extra={
            "hashtag_url": hashtag_url,
            "success_count": success_count,
            "total_videos": len(video_urls),
            "success_rate": f"{(success_count/len(video_urls)*100):.1f}%",
            "failed_count": len(failed_urls),
            "failed_urls": failed_urls if failed_urls else None,
        }
    )
    return success_count


