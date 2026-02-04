from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest

import scripts.common as common
import scripts.publicador as publicador


@pytest.fixture
def temp_env_paths(tmp_path, monkeypatch):
    base_dir = tmp_path / "project"
    data_dir = base_dir / "data"
    videos_dir = base_dir / "videos"
    raw_dir = videos_dir / "raw"
    processed_dir = videos_dir / "processed"
    logs_dir = base_dir / "logs"

    for path in (data_dir, raw_dir, processed_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    inventory_path = data_dir / "inventario_videos.parquet"
    lock_path = data_dir / "inventario.lock"
    log_file = logs_dir / "pipeline.log"

    patched_paths = {
        "BASE_DIR": base_dir,
        "DATA_DIR": data_dir,
        "VIDEOS_DIR": videos_dir,
        "RAW_DIR": raw_dir,
        "PROCESSED_DIR": processed_dir,
        "LOGS_DIR": logs_dir,
        "INVENTORY_PATH": inventory_path,
        "LOCK_PATH": lock_path,
        "LOG_FILE": log_file,
    }

    for module in (common, publicador):
        for name, value in patched_paths.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)

    return {
        "base_dir": base_dir,
        "raw_dir": raw_dir,
        "processed_dir": processed_dir,
        "inventory_path": inventory_path,
        "lock_path": lock_path,
    }


def test_get_next_returns_existing(temp_env_paths):
    # Create a processed file and inventory row
    processed_file = temp_env_paths["processed_dir"] / "ready.mp4"
    processed_file.write_bytes(b"data")
    path_local = processed_file.relative_to(temp_env_paths["base_dir"])

    now = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "p1",
        "source_url": "https://example.com/1.mp4",
        "title": "P1",
        "duration": 10,
        "path_local": str(path_local),
        "status_fb": "pending",
        "created_at": now,
        "updated_at": now,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    p = publicador.cli_get_next()
    assert p == str(path_local)


def test_get_next_skips_missing_and_marks_failed(temp_env_paths):
    # First row points to missing file, second row exists
    missing = temp_env_paths["processed_dir"] / "missing.mp4"
    exists = temp_env_paths["processed_dir"] / "exists.mp4"
    exists.write_bytes(b"ok")

    now = datetime.now(timezone.utc)
    rows = [
        {
            "video_id": "m1",
            "source_url": "https://example.com/m1.mp4",
            "title": "M1",
            "duration": 11,
            "path_local": str(missing.relative_to(temp_env_paths["base_dir"])),
            "status_fb": "pending",
            "created_at": now,
            "updated_at": now,
        },
        {
            "video_id": "e1",
            "source_url": "https://example.com/e1.mp4",
            "title": "E1",
            "duration": 12,
            "path_local": str(exists.relative_to(temp_env_paths["base_dir"])),
            "status_fb": "pending",
            "created_at": now,
            "updated_at": now,
        },
    ]
    pl.DataFrame(rows).write_parquet(temp_env_paths["inventory_path"])

    p = publicador.cli_get_next()
    assert p == str(exists.relative_to(temp_env_paths["base_dir"]))

    inv = common.read_inventory()
    rows = inv.to_dicts()
    # first should be marked failed
    assert rows[0]["status_fb"] == "failed"


def test_mark_posted_updates_status_and_timestamp(temp_env_paths):
    # Create ready row
    processed_file = temp_env_paths["processed_dir"] / "to_post.mp4"
    processed_file.write_bytes(b"ok")
    path_local = processed_file.relative_to(temp_env_paths["base_dir"])

    before = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "post1",
        "source_url": "https://example.com/post1.mp4",
        "title": "Post1",
        "duration": 20,
        "path_local": str(path_local),
        "status_fb": "ready",
        "created_at": before,
        "updated_at": before,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    ok = publicador.cli_mark_posted("post1")
    assert ok is True

    inv = common.read_inventory()
    row = inv.to_dicts()[0]
    assert row["status_fb"] == "posted"
    assert row["updated_at"] > before
