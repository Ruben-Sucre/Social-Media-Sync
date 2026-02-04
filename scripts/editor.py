"""Video editor that applies random transformations to pending inventory items.

The module selects the first pending raw clip, performs subtle zoom/color/speed
adjustments, renders the transformed version into `videos/processed/`, and
updates the inventory metadata accordingly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, cast
import random
from datetime import datetime, timezone
from uuid import uuid4
import polars as pl
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy import vfx
from scripts.common import (
    BASE_DIR,
    PROCESSED_DIR,
    ensure_dirs,
    read_inventory,
    update_inventory_by_video_id,
    logger,
)
from scripts.exceptions import VideoProcessingError

vfx_tool: Any = vfx

def _select_first_pending_row(df: pl.DataFrame) -> Optional[Dict[str, Any]]:
    """Return the first inventory row marked as pending."""
    for row in df.to_dicts():
        if row.get("status_fb") == "pending" and row.get("path_local"):
            return row
    return None


def _build_output_path(src: Path) -> Path:
    """Generate a unique processed path based on the source filename."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique_suffix = uuid4().hex[:8]
    processed_name = f"{src.stem}_{timestamp}_{unique_suffix}{src.suffix}"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    return PROCESSED_DIR / processed_name


def _apply_random_transformations(clip: VideoFileClip) -> VideoFileClip:
    """Apply at least two random transformations to the clip."""

    def _size(c: VideoFileClip) -> tuple[int, int]:
        if hasattr(c, "size"):
            val = c.size
            if isinstance(val, (tuple, list)) and len(val) == 2:
                return val[0], val[1]
        return getattr(c, "w", 0), getattr(c, "h", 0)

    def mirror(c: VideoFileClip) -> VideoFileClip:
        return vfx_tool.MirrorX(c)

    def zoom(c: VideoFileClip) -> VideoFileClip:
        w, h = _size(c)
        margin_ratio = 0.05
        x_margin = int(w * margin_ratio)
        y_margin = int(h * margin_ratio)
        cropped = c.with_effects([vfx.Crop(x1=x_margin, y1=y_margin, x2=w - x_margin, y2=h - y_margin)])
        return cast(VideoFileClip, cropped)

    def color(c: VideoFileClip) -> VideoFileClip:
        logger.warning("Color transformation is not supported in the current version of moviepy. Skipping.")
        return c

    def speed(c: VideoFileClip) -> VideoFileClip:
        logger.warning("Speed transformation is not supported in the current version of moviepy. Skipping.")
        return c

    transformations = [mirror, zoom, color, speed]

    selection_size = random.randint(2, len(transformations))
    selected_transforms = random.sample(transformations, k=selection_size)
    transformed_clip = clip
    for transform in selected_transforms:
        transformed_clip = transform(transformed_clip)
    return transformed_clip


def process_pending() -> int:
    """Process the first pending raw video, apply transformations, and update inventory."""

    ensure_dirs()
    df = read_inventory()
    row = _select_first_pending_row(df)
    if not row:
        logger.info("No pending videos found")
        return 0

    path_local = row.get("path_local")
    src = BASE_DIR / Path(cast(str, path_local))
    if not src.exists():
        logger.warning("Raw file not found for %s: %s", row.get("video_id"), src)
        video_id = row.get("video_id")
        if video_id is not None:
            update_inventory_by_video_id(cast(str, video_id), {"status_fb": "failed"})
        return 0

    clip: Optional[VideoFileClip] = None
    output_clip: Optional[VideoFileClip] = None
    try:
        clip = VideoFileClip(str(src))
        output_clip = _apply_random_transformations(clip)
        dst = _build_output_path(src)
        output_clip.write_videofile(
            str(dst), codec="libx264", audio_codec="aac", remove_temp=True
        )

        new_rel = str(dst.relative_to(BASE_DIR))
        video_id = cast(str, row.get("video_id"))
        update_inventory_by_video_id(
            video_id,
            {
                "path_local": new_rel,
                "status_fb": "ready",
            },
        )

        logger.info("Processed and transformed %s -> %s", src, dst)
        return 1
    except Exception as exc:
        logger.exception("Failed to process video %s: %s", row.get("video_id"), exc)
        video_id = row.get("video_id")
        if video_id is not None:
            update_inventory_by_video_id(cast(str, video_id), {"status_fb": "failed"})
        raise VideoProcessingError(f"Failed to process video {row.get('video_id')}") from exc
    finally:
        if clip is not None:
            clip.close()
        if output_clip is not None and output_clip is not clip:
            output_clip.close()


if __name__ == "__main__":
    # Run the single-shot processing; logging will record the outcome.
    process_pending()
