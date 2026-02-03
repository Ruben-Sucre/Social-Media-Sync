"""Video ingestion utilities and helpers.

This module provides small, testable functions that:
- obtain a list of video URLs (stubs for now)
- download videos into the `videos/raw/` folder using yt-dlp
- add entries to the inventory with `status_fb = 'pending'`

Note: The download step uses yt-dlp programmatically; ensure the package is
installed and Playwright/other browsers are set up when needed.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from fake_useragent import UserAgent
from yt_dlp import YoutubeDL
import polars as pl

from scripts.common import (
    BASE_DIR,
    RAW_DIR,
    ensure_dirs,
    _read_inventory_lazy,
    _append_to_inventory,
    logger,
)


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def obtener_tendencias(source: str | None = None) -> List[str]:
    """Stub: return a list of video URLs to ingest.

    Replace this with real scraping / Playwright logic.
    """
    # TODO: implement real trend extraction. For now accept `source` as a single URL
    return [source] if source else []


def procesar_hashtag(hashtag: str) -> List[str]:
    """Stub: return a list of video URLs for a hashtag."""
    # TODO: use Playwright to expand and collect many URLs
    return []


def _resolve_user_agent() -> str:
    try:
        return UserAgent().random
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Falling back to default User-Agent: %s", exc)
        return DEFAULT_USER_AGENT


def _already_exists(video_id: str) -> bool:
    lf = _read_inventory_lazy()
    exists = lf.filter(pl.col("video_id") == video_id).select(pl.col("video_id")).limit(1).collect()
    return exists.height > 0


def ingest(source_url: str) -> None:
    """Single-shot ingestion: download at most one new video for `source_url`."""
    if not source_url:
        logger.warning("No source_url provided to ingest()")
        return

    ensure_dirs()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    user_agent = _resolve_user_agent()

    listing_opts = {
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
        "user_agent": user_agent,
    }

    try:
        with YoutubeDL(listing_opts) as ydl:
            listing = ydl.extract_info(source_url, download=False)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to fetch listing for %s: %s", source_url, exc)
        return

    entries = listing.get("entries") or []
    if not entries and listing.get("id"):
        entries = [listing]

    target_entry = None
    for entry in entries:
        video_id = entry.get("id")
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

    target_url = target_entry.get("url") or target_entry.get("webpage_url")
    if not target_url:
        logger.warning("Candidate video missing URL, skipping download")
        return

    download_opts = {
        "outtmpl": str(RAW_DIR / "%(id)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
        "user_agent": user_agent,
    }

    try:
        with YoutubeDL(download_opts) as ydl:
            info = ydl.extract_info(target_url, download=True)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to download %s: %s", target_url, exc)
        return

    video_id = info.get("id") or target_entry.get("id")
    if not video_id:
        logger.warning("Downloaded video missing ID, skipping inventory append")
        return

    matches = list(RAW_DIR.glob(f"{video_id}.*"))
    path_local = str(matches[0].relative_to(BASE_DIR)) if matches else ""

    row = {
        "video_id": video_id,
        "source_url": info.get("webpage_url") or target_entry.get("webpage_url") or source_url,
        "title": info.get("title", ""),
        "duration": int(info.get("duration") or 0),
        "path_local": path_local,
        "status_fb": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    _append_to_inventory([row])
    logger.info("Downloaded %s", video_id)


if __name__ == "__main__":
    raise SystemExit("Import and call `ingest()` from your orchestrator or tests")
