"""Video ingestion utilities and helpers.

This module provides small, testable functions that:
- obtain a list of video URLs (stubs for now)
- download videos into the `videos/raw/` folder using yt-dlp
- add entries to the inventory with `status_fb = 'pending'`

Note: The download step uses yt-dlp programmatically; ensure the package is
installed and Playwright/other browsers are set up when needed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Dict

from yt_dlp import YoutubeDL
import polars as pl

from scripts.common import (
    RAW_DIR,
    INVENTORY_PATH,
    ensure_dirs,
    _read_inventory_lazy,
    _append_to_inventory,
    logger,
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


def _already_exists(video_id: str) -> bool:
    lf = _read_inventory_lazy()
    exists = lf.filter(pl.col("video_id") == video_id).select(pl.col("video_id")).limit(1).collect()
    return exists.height > 0


def ingest(urls: Iterable[str]) -> None:
    """Download given video URLs into `videos/raw/` and record them in inventory.

    This uses yt-dlp programmatically and writes metadata to the Parquet inventory.
    Download locations are kept under `videos/raw/` and `path_local` stores a
    project-relative path (POSIX string) to the file.
    """
    ensure_dirs()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": str(RAW_DIR / "%(id)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Failed to download %s: %s", url, exc)
                continue

            video_id = info.get("id")
            if not video_id:
                logger.warning("No id found for %s, skipping", url)
                continue

            if _already_exists(video_id):
                logger.info("Skipping already ingested video %s", video_id)
                continue

            # find downloaded filename (match id.*)
            matches = list(RAW_DIR.glob(f"{video_id}.*"))
            path_local = str(matches[0].relative_to(Path(__file__).resolve().parent.parent)) if matches else ""

            from datetime import datetime

            row = {
                "video_id": video_id,
                "source_url": url,
                "title": info.get("title", ""),
                "duration": int(info.get("duration") or 0),
                "path_local": path_local,
                "status_fb": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            _append_to_inventory([row])
            logger.info("Ingested %s -> %s", url, video_id)


if __name__ == "__main__":
    raise SystemExit("Import and call `ingest()` from your orchestrator or tests")
