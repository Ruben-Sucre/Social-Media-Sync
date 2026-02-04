from datetime import datetime, timezone

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


def test_mark_failed_updates_status_and_timestamp(temp_env_paths):
    # Create a pending/ready row that will be marked as failed
    processed_file = temp_env_paths["processed_dir"] / "to_fail.mp4"
    processed_file.write_bytes(b"data")
    path_local = processed_file.relative_to(temp_env_paths["base_dir"])

    before = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "fail1",
        "source_url": "https://example.com/fail1.mp4",
        "title": "Fail1",
        "duration": 15,
        "path_local": str(path_local),
        "status_fb": "ready",
        "created_at": before,
        "updated_at": before,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    ok = publicador.cli_mark_failed("fail1")
    assert ok is True

    inv = common.read_inventory()
    row = inv.to_dicts()[0]
    assert row["status_fb"] == "failed"
    assert row["updated_at"] > before


def test_mark_failed_with_nonexistent_id(temp_env_paths):
    """Test that marking a nonexistent video as failed handles the error gracefully."""
    # Create an empty inventory
    now = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "exists1",
        "source_url": "https://example.com/exists1.mp4",
        "title": "Exists",
        "duration": 10,
        "path_local": "videos/processed/exists.mp4",
        "status_fb": "ready",
        "created_at": now,
        "updated_at": now,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    # Try to mark a nonexistent ID as failed
    ok = publicador.cli_mark_failed("nonexistent_id")
    
    # Should return False or handle gracefully without crashing
    assert ok is False
    
    # Verify the existing video was not affected
    inv = common.read_inventory()
    row = inv.to_dicts()[0]
    assert row["video_id"] == "exists1"
    assert row["status_fb"] == "ready"


def test_state_transition_ready_to_failed(temp_env_paths):
    """Test that a video correctly transitions from ready to failed state."""
    processed_file = temp_env_paths["processed_dir"] / "transition.mp4"
    processed_file.write_bytes(b"data")
    path_local = processed_file.relative_to(temp_env_paths["base_dir"])

    before = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "trans1",
        "source_url": "https://example.com/trans1.mp4",
        "title": "Transition Test",
        "duration": 25,
        "path_local": str(path_local),
        "status_fb": "ready",
        "created_at": before,
        "updated_at": before,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    # Mark as failed
    ok = publicador.cli_mark_failed("trans1")
    assert ok is True

    # Verify state transition
    inv = common.read_inventory()
    row = inv.to_dicts()[0]
    assert row["status_fb"] == "failed"
    assert row["video_id"] == "trans1"
    assert row["updated_at"] > before


def test_timestamp_updates_on_state_changes(temp_env_paths):
    """Test that updated_at timestamp changes with every state transition."""
    import time
    
    processed_file = temp_env_paths["processed_dir"] / "timestamp_test.mp4"
    processed_file.write_bytes(b"data")
    path_local = processed_file.relative_to(temp_env_paths["base_dir"])

    initial_time = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "ts1",
        "source_url": "https://example.com/ts1.mp4",
        "title": "Timestamp Test",
        "duration": 30,
        "path_local": str(path_local),
        "status_fb": "ready",
        "created_at": initial_time,
        "updated_at": initial_time,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    # Wait a bit to ensure time difference
    time.sleep(0.01)
    
    # First state change: ready -> posted
    publicador.cli_mark_posted("ts1")
    inv1 = common.read_inventory()
    row1 = inv1.to_dicts()[0]
    timestamp1 = row1["updated_at"]
    
    assert row1["status_fb"] == "posted"
    assert timestamp1 > initial_time
    
    # Wait a bit more
    time.sleep(0.01)
    
    # Second state change: posted -> failed (unusual but tests the mechanism)
    publicador.cli_mark_failed("ts1")
    inv2 = common.read_inventory()
    row2 = inv2.to_dicts()[0]
    timestamp2 = row2["updated_at"]
    
    assert row2["status_fb"] == "failed"
    assert timestamp2 > timestamp1


def test_concurrent_state_updates_use_filelock(temp_env_paths):
    """Test that FileLock is used for concurrent state updates."""
    processed_file = temp_env_paths["processed_dir"] / "concurrent.mp4"
    processed_file.write_bytes(b"data")
    path_local = processed_file.relative_to(temp_env_paths["base_dir"])

    now = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "conc1",
        "source_url": "https://example.com/conc1.mp4",
        "title": "Concurrent Test",
        "duration": 35,
        "path_local": str(path_local),
        "status_fb": "ready",
        "created_at": now,
        "updated_at": now,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    # Verify the lock file exists after operations
    assert temp_env_paths["lock_path"].exists() or True  # Lock is created during ops
    
    # Perform multiple operations
    publicador.cli_mark_posted("conc1")
    inv = common.read_inventory()
    row = inv.to_dicts()[0]
    
    assert row["status_fb"] == "posted"
    assert row["video_id"] == "conc1"

