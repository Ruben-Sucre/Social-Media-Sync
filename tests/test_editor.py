from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

import scripts.common as common
import scripts.editor as editor


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

    for module in (common, editor):
        for name, value in patched_paths.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)

    return {
        "base_dir": base_dir,
        "raw_dir": raw_dir,
        "processed_dir": processed_dir,
        "inventory_path": inventory_path,
    }


def test_process_pending_transforms_single_clip(temp_env_paths, monkeypatch):
    raw_file = temp_env_paths["raw_dir"] / "input.mp4"
    raw_file.write_bytes(b"raw")
    path_local = raw_file.relative_to(temp_env_paths["base_dir"])

    now = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "vid123",
        "source_url": "https://example.com/video.mp4",
        "title": "Sample",
        "duration": 42,
        "path_local": str(path_local),
        "status_fb": "pending",
        "created_at": now,
        "updated_at": now,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    clip_mock = MagicMock(name="clip")
    clip_mock.w = 1920
    clip_mock.h = 1080
    clip_mock.size = (1920, 1080)
    clip_mock.write_videofile = MagicMock()
    clip_mock.close = MagicMock()

    # Mock vfx_tool functions to return the clip unchanged
    vfx_mock = MagicMock()
    vfx_mock.mirror_x = MagicMock(return_value=clip_mock)
    vfx_mock.crop = MagicMock(return_value=clip_mock)
    vfx_mock.resize = MagicMock(return_value=clip_mock)
    vfx_mock.multiply_color = MagicMock(return_value=clip_mock)
    vfx_mock.multiply_speed = MagicMock(return_value=clip_mock)

    video_file_clip = MagicMock(return_value=clip_mock)
    monkeypatch.setattr(editor, "VideoFileClip", video_file_clip)
    monkeypatch.setattr(editor, "vfx_tool", vfx_mock)

    processed = editor.process_pending()

    assert processed == 1
    video_file_clip.assert_called_once_with(str(raw_file))
    clip_mock.write_videofile.assert_called_once()

    write_args, write_kwargs = clip_mock.write_videofile.call_args
    output_path = Path(write_args[0])
    assert temp_env_paths["processed_dir"] in output_path.parents
    assert write_kwargs["codec"] == "libx264"
    assert write_kwargs["audio_codec"] == "aac"
    assert write_kwargs["remove_temp"] is True
    clip_mock.close.assert_called_once()

    updated_rows = common.read_inventory().to_dicts()
    assert updated_rows[0]["status_fb"] == "ready"
    assert updated_rows[0]["path_local"].startswith("videos/processed/")


def test_process_pending_no_pending_returns_zero(temp_env_paths, monkeypatch):
    processed_file = temp_env_paths["processed_dir"] / "ready.mp4"
    processed_file.write_bytes(b"processed")
    path_local = processed_file.relative_to(temp_env_paths["base_dir"])
    now = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "vid999",
        "source_url": "https://example.com/already.mp4",
        "title": "Ready",
        "duration": 84,
        "path_local": str(path_local),
        "status_fb": "ready",
        "created_at": now,
        "updated_at": now,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    video_file_clip = MagicMock()
    monkeypatch.setattr(editor, "VideoFileClip", video_file_clip)

    processed = editor.process_pending()

    assert processed == 0
    video_file_clip.assert_not_called()


def test_process_pending_closes_on_error(temp_env_paths, monkeypatch):
    raw_file = temp_env_paths["raw_dir"] / "error.mp4"
    raw_file.write_bytes(b"raw")
    path_local = raw_file.relative_to(temp_env_paths["base_dir"])

    now = datetime.now(timezone.utc)
    inventory_row = {
        "video_id": "vid-err",
        "source_url": "https://example.com/error.mp4",
        "title": "Err",
        "duration": 99,
        "path_local": str(path_local),
        "status_fb": "pending",
        "created_at": now,
        "updated_at": now,
    }
    pl.DataFrame([inventory_row]).write_parquet(temp_env_paths["inventory_path"])

    clip_mock = MagicMock(name="clip-error")
    clip_mock.w = 640
    clip_mock.h = 360
    clip_mock.size = (640, 360)
    clip_mock.fx.return_value = clip_mock
    clip_mock.crop.return_value = clip_mock
    clip_mock.resize.return_value = clip_mock
    clip_mock.write_videofile.side_effect = RuntimeError("boom")
    clip_mock.close = MagicMock()

    video_file_clip = MagicMock(return_value=clip_mock)
    monkeypatch.setattr(editor, "VideoFileClip", video_file_clip)
    monkeypatch.setattr(editor, "_apply_random_transformations", lambda c: c)

    processed = editor.process_pending()

    assert processed == 0
    video_file_clip.assert_called_once_with(str(raw_file))
    clip_mock.write_videofile.assert_called_once()
    clip_mock.close.assert_called_once()

    updated_rows = common.read_inventory().to_dicts()
    assert updated_rows[0]["status_fb"] == "pending"


def test_vfx_tool_effects_return_valid_clips(monkeypatch):
    """Test that applying effects through vfx_tool returns valid VideoClip objects."""
    from moviepy.video.io.VideoFileClip import VideoFileClip
    
    # Create a mock clip that mimics VideoFileClip behavior
    mock_clip = MagicMock(spec=VideoFileClip)
    mock_clip.w = 1920
    mock_clip.h = 1080
    mock_clip.size = (1920, 1080)
    
    # Mock vfx_tool effects to return the clip (simulating real behavior)
    mock_vfx_tool = MagicMock()
    mock_vfx_tool.mirror_x.return_value = mock_clip
    mock_vfx_tool.resize.return_value = mock_clip
    mock_vfx_tool.crop.return_value = mock_clip
    mock_vfx_tool.multiply_color.return_value = mock_clip
    mock_vfx_tool.multiply_speed.return_value = mock_clip
    
    # Patch vfx_tool in the editor module
    monkeypatch.setattr(editor, "vfx_tool", mock_vfx_tool)
    
    # Test that _apply_random_transformations returns a valid clip
    result = editor._apply_random_transformations(mock_clip)
    
    # Verify the result is a clip object (mocked)
    assert result is not None
    # Verify at least one effect was called (since the function selects 2+ random effects)
    assert (
        mock_vfx_tool.mirror_x.called
        or mock_vfx_tool.resize.called
        or mock_vfx_tool.crop.called
        or mock_vfx_tool.multiply_color.called
        or mock_vfx_tool.multiply_speed.called
    )
