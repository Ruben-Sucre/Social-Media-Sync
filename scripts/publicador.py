"""Small CLI to integrate with n8n or external orchestrators.

- `--get-next`   -> prints the next processed video path (one line)
- `--mark-posted VIDEO_ID` -> mark the given video as posted in the inventory

These primitives make it easy for a workflow system like n8n to query and mark
videos as posted after successful uploads.
"""

from __future__ import annotations

import argparse
from typing import Optional
from pathlib import Path

from filelock import FileLock
from datetime import datetime, timezone

from scripts.common import (
    BASE_DIR,
    INVENTORY_PATH,
    LOCK_PATH,
    update_inventory_by_video_id,
    logger,
)
import polars as pl


def cli_get_next() -> Optional[str]:
    """Return the next processed video path that exists on disk.

    Scans the inventory for items with `status_fb == 'pending'` and
    `path_local` pointing at `processed/`. For each candidate we verify the
    file exists on disk. If a processed file is missing, the entry is marked
    as `failed` and the search continues. Uses `FileLock` to avoid races with
    concurrent writers.
    """
    lock = FileLock(str(LOCK_PATH))
    to_mark_failed: list[str] = []
    try:
        with lock:
            if not INVENTORY_PATH.exists():
                return None
            df = pl.read_parquet(INVENTORY_PATH)
            found_path: Optional[str] = None
            for row in df.to_dicts():
                if row.get("status_fb") != "pending":
                    continue
                path_local = row.get("path_local") or ""
                if "processed" not in path_local:
                    continue
                candidate = BASE_DIR / Path(path_local)
                if candidate.exists():
                    found_path = path_local
                    # don't return yet; allow marking of earlier missing files
                    break
                # mark as failed in the in-memory DF (we're holding the lock)
                logger.error(
                    "Processed file missing for %s: %s", row.get("video_id"), candidate
                )
                to_mark_failed.append(row.get("video_id"))

            if to_mark_failed:
                # update status_fb and updated_at for the missing entries
                exprs = [
                    pl.when(pl.col("video_id").is_in(to_mark_failed))
                    .then(pl.lit("failed"))
                    .otherwise(pl.col("status_fb"))
                    .alias("status_fb"),
                    pl.when(pl.col("video_id").is_in(to_mark_failed))
                    .then(pl.lit(datetime.now(timezone.utc)))
                    .otherwise(pl.col("updated_at"))
                    .alias("updated_at"),
                ]
                df = df.with_columns(exprs)
                df.write_parquet(INVENTORY_PATH)
            if found_path:
                return found_path
    except Exception:
        logger.exception("Failed scanning inventory for next processed video")
        return None

    return None


def cli_mark_posted(video_id: str) -> bool:
    ok = update_inventory_by_video_id(video_id, {"status_fb": "posted"})
    if ok:
        logger.info("Marked %s as posted", video_id)
    else:
        logger.warning("Could not find %s to mark as posted", video_id)
    return ok


def cli_mark_failed(video_id: str) -> bool:
    """Mark a video as failed in the inventory.

    This is used by external orchestrators (n8n) when an upload fails so the
    video doesn't block the queue. Uses FileLock via update_inventory_by_video_id.
    """
    ok = update_inventory_by_video_id(video_id, {"status_fb": "failed"})
    if ok:
        logger.info("Marked %s as failed", video_id)
    else:
        logger.warning("Could not find %s to mark as failed", video_id)
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--get-next", action="store_true", help="Print next processed video path"
    )
    parser.add_argument(
        "--mark-posted", metavar="VIDEO_ID", help="Mark a video as posted"
    )
    parser.add_argument(
        "--mark-failed", metavar="VIDEO_ID", help="Mark a video as failed"
    )

    args = parser.parse_args()

    if args.get_next:
        p = cli_get_next()
        if p:
            print(p)
        else:
            # no videos available
            print("")
    elif args.mark_posted:
        ok = cli_mark_posted(args.mark_posted)
        if not ok:
            raise SystemExit(2)
    elif args.mark_failed:
        ok = cli_mark_failed(args.mark_failed)
        if not ok:
            raise SystemExit(2)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
