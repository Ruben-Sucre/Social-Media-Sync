#!/usr/bin/env python3
"""Cleanup script for removing old ready videos.

This script deletes videos with status 'ready' that haven't been posted
within the configured time window (default: 48 hours).

Usage:
    python -m scripts.cleanup [--hours HOURS] [--dry-run]
    
Examples:
    python -m scripts.cleanup              # Delete videos older than 48h
    python -m scripts.cleanup --hours 24   # Delete videos older than 24h
    python -m scripts.cleanup --dry-run    # Show what would be deleted
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import polars as pl

from scripts.common import (
    BASE_DIR,
    INVENTORY_PATH,
    cleanup_old_ready_videos,
    logger,
)


def show_cleanup_preview(hours: int = 48) -> None:
    """Show videos that would be deleted without actually deleting them."""
    if not INVENTORY_PATH.exists():
        print("No inventory found.")
        return
    
    df = pl.read_parquet(INVENTORY_PATH)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    old_ready = df.filter(
        (pl.col("status_fb") == "ready") &
        (pl.col("updated_at") < cutoff_time)
    )
    
    if old_ready.is_empty():
        print(f"✅ No videos to cleanup (all ready videos are less than {hours}h old)")
        return
    
    print(f"🗑️  Videos that would be deleted ({len(old_ready)} total):")
    print(f"   Cutoff: {cutoff_time.isoformat()}")
    print("")
    
    for row in old_ready.to_dicts():
        video_id = row.get("video_id", "unknown")
        updated_at = row.get("updated_at")
        age_hours = (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600
        path = row.get("path_local", "")
        
        file_exists = (BASE_DIR / path).exists() if path else False
        status = "📁" if file_exists else "❌"
        
        print(f"   {status} {video_id} ({age_hours:.1f}h old)")
        print(f"      Path: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup old ready videos that haven't been posted"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Delete videos older than this many hours (default: 48)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    args = parser.parse_args()
    
    print(f"🧹 Video Cleanup (threshold: {args.hours}h)")
    print("")
    
    if args.dry_run:
        show_cleanup_preview(args.hours)
    else:
        deleted = cleanup_old_ready_videos(args.hours)
        print(f"✅ Deleted {deleted} old video(s)")


if __name__ == "__main__":
    main()
