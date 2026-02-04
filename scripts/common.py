"""Common project utilities: paths, inventory helpers and logging.

- Uses project root relative to the `scripts` package so paths remain portable.
- Provides lightweight helpers around a Parquet "inventory" using Polars.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Dict

import polars as pl
from filelock import FileLock



# --- Paths ---------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VIDEOS_DIR = BASE_DIR / "videos"
RAW_DIR = VIDEOS_DIR / "raw"
PROCESSED_DIR = VIDEOS_DIR / "processed"
LOGS_DIR = BASE_DIR / "logs"
INVENTORY_PATH = DATA_DIR / "inventario_videos.parquet"
LOCK_PATH = DATA_DIR / "inventario.lock"
LOG_FILE = LOGS_DIR / "pipeline.log"


# --- Inventory schema ---------------------------------------------------
INVENTORY_COLUMNS = [
    ("video_id", pl.Utf8),
    ("source_url", pl.Utf8),
    ("title", pl.Utf8),
    ("duration", pl.Int64),
    ("path_local", pl.Utf8),
    ("status_fb", pl.Utf8),
    ("created_at", pl.Datetime("us", "UTC")),
    ("updated_at", pl.Datetime("us", "UTC")),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)



# --- Logging ------------------------------------------------------------
def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("pipeline")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File (ensure logs dir exists)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


logger = _setup_logger()


# --- Helpers ------------------------------------------------------------
def ensure_dirs() -> None:
    """Create the basic folders if they don't exist."""
    for p in (DATA_DIR, RAW_DIR, PROCESSED_DIR, LOGS_DIR):
        p.mkdir(parents=True, exist_ok=True)


def ensure_inventory() -> None:
    """Create an empty inventory file with the expected schema if missing."""
    ensure_dirs()
    lock = FileLock(str(LOCK_PATH))
    try:
        with lock:
            if INVENTORY_PATH.exists():
                return

            cols = {name: pl.Series(name, [], dtype=dtype) for name, dtype in INVENTORY_COLUMNS}
            df = pl.DataFrame(cols)
            df = df.with_columns(
                df["created_at"].dt.convert_time_zone("UTC"),
                df["updated_at"].dt.convert_time_zone("UTC"),
            )
            df.write_parquet(INVENTORY_PATH)
            logger.info("Created new inventory at %s", INVENTORY_PATH)
    except Exception:
        logger.exception("Failed to create inventory at %s", INVENTORY_PATH)
        raise


def _read_inventory_lazy() -> pl.LazyFrame:
    """Return a lazy frame for inventory (safe to call when file missing)."""
    ensure_inventory()
    return pl.scan_parquet(str(INVENTORY_PATH))


def read_inventory() -> pl.DataFrame:
    """Read the inventory file and return it as a Polars DataFrame."""
    ensure_dirs()
    if not INVENTORY_PATH.exists():
        cols = {name: pl.Series(name, [], dtype=dtype) for name, dtype in INVENTORY_COLUMNS}
        df = pl.DataFrame(cols)
        df.write_parquet(INVENTORY_PATH)
        return df

    df = pl.read_parquet(INVENTORY_PATH)
    return df.with_columns(
        df["created_at"].dt.convert_time_zone("UTC"),
        df["updated_at"].dt.convert_time_zone("UTC"),
    )


def _append_to_inventory(rows: Iterable[Dict]) -> None:
    """Append new rows to inventory while attempting to avoid duplicates.

    Uses a simple in-memory append: load existing DF, concat, dedupe on `video_id`.
    This is fine for small-to-medium inventories. For very large inventories consider
    partitioned parquet or a proper DB.
    """
    ensure_inventory()
    new_df = pl.DataFrame(rows)
    if new_df.is_empty():
        return

    new_df = new_df.with_columns(
        new_df["created_at"].dt.convert_time_zone("UTC"),
        new_df["updated_at"].dt.convert_time_zone("UTC"),
    )
    lock = FileLock(str(LOCK_PATH))
    try:
        with lock:
            existing = pl.read_parquet(INVENTORY_PATH)
            combined = pl.concat([existing, new_df], how="vertical")
            combined = combined.unique(subset=["video_id"], keep="first")
            combined.write_parquet(INVENTORY_PATH)
            logger.info("Appended %d rows to inventory", len(new_df))
    except Exception:
        logger.exception("Failed appending to inventory at %s", INVENTORY_PATH)
        raise


def update_inventory_by_video_id(video_id: str, updates: Dict) -> bool:
    """Update a row identified by `video_id`.

    Returns True if a row was updated. The function applies `updates` to any
    matching row and automatically sets `updated_at` to the current UTC time.
    """
    lock = FileLock(str(LOCK_PATH))
    try:
        with lock:
            df = pl.read_parquet(INVENTORY_PATH)
            mask = df["video_id"] == video_id
            if mask.any() is False:
                return False

            # Build expressions to update columns in a single pass
            exprs = []
            for k, v in updates.items():
                if k in df.columns:
                    exprs.append(
                        pl.when(pl.col("video_id") == video_id)
                        .then(pl.lit(v))
                        .otherwise(pl.col(k))
                        .alias(k)
                    )

            # Update `updated_at` timestamp for that row
            exprs.append(
                pl.when(pl.col("video_id") == video_id)
                .then(pl.lit(datetime.now(timezone.utc)))
                .otherwise(pl.col("updated_at"))
                .alias("updated_at")
            )

            df = df.with_columns(exprs)
            df.write_parquet(INVENTORY_PATH)
            logger.info("Updated inventory for %s: %s", video_id, updates)
            return True
    except Exception:
        logger.exception("Failed updating inventory for %s", video_id)
        raise


def find_next_processed_pending() -> Dict | None:
    """Return the first processed video with status 'pending', or None."""
    lf = _read_inventory_lazy()
    res = (
        lf.filter((pl.col("status_fb") == "pending") & pl.col("path_local").str.contains("processed"))
        .select(["video_id", "path_local"]) 
        .limit(1)
        .collect()
    )
    if res.height == 0:
        return None
    return {"video_id": res[0, "video_id"], "path_local": res[0, "path_local"]}
