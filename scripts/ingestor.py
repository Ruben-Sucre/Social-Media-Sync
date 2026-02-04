"""Video ingestion utilities and helpers.

This module provides small, testable functions that:
- obtain a list of video URLs (stubs for now)
- download videos into the `videos/raw/` folder using yt-dlp
- add entries to the inventory with `status_fb = 'pending'`

Note: The download step uses yt-dlp programmatically; ensure the package is
installed and Playwright/other browsers are set up when needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, cast, Any
from scripts.exceptions import DownloadError, InventoryUpdateError
from scripts.utils import random_wait, retry

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
    """Return a list of video URLs to ingest.

    This is a lightweight stub used by tests and early development. Replace
    with real scraping or Playwright-driven logic when integrating full
    discovery pipelines.
    """
    return [source] if source else []


def procesar_hashtag(hashtag: str) -> List[str]:
    """Return video URLs for a given hashtag.

    Currently a stub that returns an empty list. Replace with Playwright or
    other discovery mechanisms to expand hashtags into candidate videos.
    """
    return []


def _resolve_user_agent() -> str:
    try:
        return UserAgent().random
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Falling back to default User-Agent: %s", exc)
        return DEFAULT_USER_AGENT


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

    user_agent = _resolve_user_agent()

    listing_opts = {
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
        "user_agent": user_agent,
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

    target_url = target_entry.get("url") or target_entry.get("webpage_url")
    if not target_url:
        logger.warning("Candidate video missing URL, skipping download")
        return

    download_opts = {
        "outtmpl": str(RAW_DIR / "%(id)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
        "user_agent": user_agent,
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
        _update_inventory_status(video_id, "failed")
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


def _update_inventory_status(video_id: str, status: str) -> None:
    """Update the status of a video in the inventory."""
    try:
        lf = _read_inventory_lazy()
        lf = lf.with_columns(pl.when(pl.col("video_id") == video_id).then(status).otherwise(pl.col("status_fb")))
        lf.write_parquet(BASE_DIR / "data/inventario_videos.parquet")
    except Exception as exc:
        logger.exception("Failed to update status for %s: %s", video_id, exc)
        raise InventoryUpdateError(f"Failed to update status for {video_id}") from exc
