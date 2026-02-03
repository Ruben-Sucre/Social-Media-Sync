"""Small editor that prepares videos for publishing.

For now this is a simple "hook" that moves files from `videos/raw/` to
`videos/processed/` for items with `status_fb == 'pending'` in the inventory.
Movies / transcoding will live here later (TODO: MoviePy logic).
"""
from __future__ import annotations

from pathlib import Path
import shutil
import polars as pl
from moviepy.editor import VideoFileClip, vfx
import random
from datetime import datetime, timezone

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
    """Process pending raw videos, apply transformations, and update inventory.

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

        try:
            # Load video
            clip = VideoFileClip(str(src))

            # Define transformations
            transformations = [
                lambda c: c.fx(vfx.mirror_x),
                lambda c: c.crop(x1=c.w * 0.05, y1=c.h * 0.05, x2=c.w * 0.95, y2=c.h * 0.95).resize(height=c.h),
                lambda c: c.fx(vfx.colorx, random.uniform(0.9, 1.1)),
                lambda c: c.fx(vfx.speedx, random.uniform(1.01, 1.03)),
            ]

            # Apply random transformations
            selected_transforms = random.sample(transformations, k=2)
            for transform in selected_transforms:
                clip = transform(clip)

            # Export processed video
            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
            dst = PROCESSED_DIR / src.name
            clip.write_videofile(
                str(dst), codec="libx264", audio_codec="aac", remove_temp=True
            )

            # Update inventory
            new_rel = str(dst.relative_to(BASE_DIR))
            update_inventory_by_video_id(
                row.get("video_id"),
                {
                    "path_local": new_rel,
                    "status_fb": "ready",
                    "updated_at": datetime.now(timezone.utc),
                },
            )

            processed_count += 1
            logger.info("Processed and transformed %s -> %s", src, dst)

        except Exception as e:
            logger.error("Failed to process video %s: %s", row.get("video_id"), e)
        finally:
            clip.close()

    return processed_count


if __name__ == "__main__":
    n = process_pending()
    print(f"Processed {n} videos")
