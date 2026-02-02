"""Small editor that prepares videos for publishing.

For now this is a simple "hook" that moves files from `videos/raw/` to
`videos/processed/` for items with `status_fb == 'pending'` in the inventory.
Movies / transcoding will live here later (TODO: MoviePy logic).
"""
from __future__ import annotations

from pathlib import Path
import shutil
import polars as pl

from scripts.common import (
    BASE_DIR,
    RAW_DIR,
    PROCESSED_DIR,
    ensure_dirs,
    read_inventory,
    update_inventory_by_video_id,
    logger,
)


def process_pending() -> int:
    """Move pending raw videos to processed and update inventory.

    Returns the number of videos processed.
    """
    ensure_dirs()
    df = read_inventory()

    processed_count = 0
    for row in df.to_dicts():
        if row.get("status_fb") != "pending":
            continue
        path_local = row.get("path_local")
        if not path_local:
            continue

        src = BASE_DIR / Path(path_local)
        if not src.exists():
            logger.warning("Raw file not found for %s: %s", row.get("video_id"), src)
            continue

        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        dst = PROCESSED_DIR / src.name
        # For now we simply move the file. Future edits (crop, re-encode) go here.
        shutil.move(str(src), str(dst))

        new_rel = str(dst.relative_to(BASE_DIR))
        update_inventory_by_video_id(row.get("video_id"), {"path_local": new_rel})
        processed_count += 1
        logger.info("Moved %s -> %s", src, dst)

        # TODO: Integrate MoviePy processing here (trim, resize, overlay watermark, etc.)

    return processed_count


if __name__ == "__main__":
    n = process_pending()
    print(f"Processed {n} videos")
