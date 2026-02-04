import logging
from datetime import datetime, timezone, timedelta

import polars as pl
import pytest
from unittest.mock import patch, MagicMock
from scripts.ingestor import ingest
from scripts.exceptions import DownloadError, InventoryUpdateError

import scripts.ingestor as ingestor
import scripts.common as common


class DummyYDL:
    def __init__(self, opts, *, listing=None, download=None):
        self.opts = opts
        self._listing = listing
        self._download = download

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url, download=False):
        if download:
            return self._download
        return self._listing


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    # Build temporary project layout
    data_dir = tmp_path / "data"
    videos_dir = tmp_path / "videos"
    raw_dir = videos_dir / "raw"
    processed_dir = videos_dir / "processed"
    logs_dir = tmp_path / "logs"
    inventory_path = data_dir / "inventario_videos.parquet"
    lock_path = data_dir / "inventario.lock"

    # Patch common module paths
    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    monkeypatch.setattr(common, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(common, "RAW_DIR", raw_dir)
    monkeypatch.setattr(common, "PROCESSED_DIR", processed_dir)
    monkeypatch.setattr(common, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(common, "INVENTORY_PATH", inventory_path)
    monkeypatch.setattr(common, "LOCK_PATH", lock_path)
    monkeypatch.setattr(common, "LOG_FILE", logs_dir / "pipeline.log")

    # Also patch names imported into ingestor at module import time
    monkeypatch.setattr(ingestor, "RAW_DIR", raw_dir)
    monkeypatch.setattr(ingestor, "BASE_DIR", tmp_path)

    # Ensure dirs and inventory exist
    common.ensure_dirs()
    common.ensure_inventory()

    yield


def _to_aware(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def test_ingest_success(tmp_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    video_id = "VID123"
    source_url = "https://example.com/source"

    listing = {
        "entries": [{"id": video_id, "url": f"https://example.com/watch/{video_id}"}]
    }
    download_info = {
        "id": video_id,
        "webpage_url": f"https://example.com/watch/{video_id}",
        "title": "Test Title",
        "duration": 12,
    }

    # Ensure the downloaded file exists in RAW_DIR to satisfy glob lookup
    (common.RAW_DIR / f"{video_id}.mp4").parent.mkdir(parents=True, exist_ok=True)
    (common.RAW_DIR / f"{video_id}.mp4").touch()

    def factory(opts):
        return DummyYDL(opts, listing=listing, download=download_info)

    monkeypatch.setattr("scripts.ingestor.YoutubeDL", factory)

    # Run ingest
    ingestor.ingest(source_url)

    # Read inventory eagerly
    df = pl.read_parquet(common.INVENTORY_PATH)
    assert df.height == 1

    row = df.row(0, named=True)
    assert row["video_id"] == video_id
    assert row["status_fb"] == "pending"

    # path_local should be relative to BASE_DIR
    assert row["path_local"] == f"videos/raw/{video_id}.mp4"

    # Validate timestamps (UTC ±5s)
    created_at = _to_aware(row["created_at"]) if row["created_at"] is not None else None
    updated_at = _to_aware(row["updated_at"]) if row["updated_at"] is not None else None
    now = datetime.now(timezone.utc)
    tol = timedelta(seconds=5)

    assert created_at is not None and abs(now - created_at) <= tol
    assert updated_at is not None and abs(now - updated_at) <= tol

    # Log contains downloaded message
    assert any("Downloaded" in rec.message for rec in caplog.records)


def test_ingest_duplicate_prevention(tmp_env, monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    video_id = "VIDDUP"
    source_url = "https://example.com/source_dup"

    listing = {
        "entries": [{"id": video_id, "url": f"https://example.com/watch/{video_id}"}]
    }
    download_info = {
        "id": video_id,
        "webpage_url": f"https://example.com/watch/{video_id}",
        "title": "Dup Title",
        "duration": 20,
    }

    # Prepare download file and first successful ingest
    (common.RAW_DIR / f"{video_id}.mp4").parent.mkdir(parents=True, exist_ok=True)
    (common.RAW_DIR / f"{video_id}.mp4").touch()

    def factory_first(opts):
        return DummyYDL(opts, listing=listing, download=download_info)

    monkeypatch.setattr("scripts.ingestor.YoutubeDL", factory_first)
    ingestor.ingest(source_url)

    # Confirm one row
    df1 = pl.read_parquet(common.INVENTORY_PATH)
    assert df1.height == 1

    # Now simulate running again: listing still returns same ID
    def factory_second(opts):
        return DummyYDL(opts, listing=listing, download=download_info)

    monkeypatch.setattr("scripts.ingestor.YoutubeDL", factory_second)
    ingestor.ingest(source_url)

    # Inventory should remain with a single row
    df2 = pl.read_parquet(common.INVENTORY_PATH)
    assert df2.height == 1

    # Log should contain "No new videos found"
    assert any("No new videos found" in rec.message for rec in caplog.records)


def test_resolve_user_agent(monkeypatch):
    # Normal case: returns a non-empty string
    ua = ingestor._resolve_user_agent()
    assert isinstance(ua, str) and len(ua) > 0

    # Simulate fake_useragent failing on instantiation
    class BadUA:
        def __init__(self):
            raise RuntimeError("fail ua")

    monkeypatch.setattr(ingestor, "UserAgent", BadUA)
    ua2 = ingestor._resolve_user_agent()
    assert ua2 == ingestor.DEFAULT_USER_AGENT


@patch("scripts.ingestor.YoutubeDL")
@patch("scripts.ingestor._already_exists", return_value=False)
@patch("scripts.ingestor._append_to_inventory")
def test_ingest_success(mock_append, mock_exists, mock_ydl_class):
    """Test successful ingestion."""
    # Mock para el primer YoutubeDL (listing)
    mock_ydl_listing = MagicMock()
    mock_ydl_listing.extract_info.return_value = {
        "entries": [{"id": "test_id", "url": "http://example.com/video"}],
        "id": "test_id",
    }
    mock_ydl_listing.__enter__.return_value = mock_ydl_listing
    mock_ydl_listing.__exit__.return_value = False
    
    # Mock para el segundo YoutubeDL (download)
    mock_ydl_download = MagicMock()
    mock_ydl_download.extract_info.return_value = {
        "id": "test_id",
        "url": "http://example.com/video",
        "ext": "mp4"
    }
    mock_ydl_download.__enter__.return_value = mock_ydl_download
    mock_ydl_download.__exit__.return_value = False
    
    # Configurar el mock_ydl_class para devolver primero listing y luego download
    mock_ydl_class.side_effect = [mock_ydl_listing, mock_ydl_download]

    ingest("http://example.com/video")
    mock_append.assert_called_once()


@patch("scripts.ingestor.YoutubeDL")
@patch("scripts.ingestor._already_exists", return_value=False)
@patch("scripts.ingestor._update_inventory_status")
def test_ingest_download_error(mock_update_status, mock_exists, mock_ydl_class):
    """Test ingestion with download error."""
    # Mock para el primer YoutubeDL (listing)
    mock_ydl_listing = MagicMock()
    mock_ydl_listing.extract_info.return_value = {
        "entries": [{"id": "test_id", "url": "http://example.com/video"}],
        "id": "test_id",
    }
    mock_ydl_listing.__enter__.return_value = mock_ydl_listing
    mock_ydl_listing.__exit__.return_value = False
    
    # Mock para el segundo YoutubeDL (download) que falla
    mock_ydl_download = MagicMock()
    mock_ydl_download.extract_info.side_effect = Exception("Download failed")
    mock_ydl_download.__enter__.return_value = mock_ydl_download
    mock_ydl_download.__exit__.return_value = False
    
    # Configurar el mock_ydl_class para devolver primero listing y luego download
    mock_ydl_class.side_effect = [mock_ydl_listing, mock_ydl_download]

    with pytest.raises(DownloadError):
        ingest("http://example.com/video")


@patch("scripts.ingestor.YoutubeDL")
@patch("scripts.ingestor._already_exists", return_value=False)
@patch("scripts.ingestor._append_to_inventory")
def test_ingest_inventory_update_error(mock_append, mock_exists, mock_ydl_class):
    """Test ingestion with inventory update error."""
    # Mock para el primer YoutubeDL (listing)
    mock_ydl_listing = MagicMock()
    mock_ydl_listing.extract_info.return_value = {
        "entries": [{"id": "test_id", "url": "http://example.com/video"}],
        "id": "test_id",
    }
    mock_ydl_listing.__enter__.return_value = mock_ydl_listing
    mock_ydl_listing.__exit__.return_value = False
    
    # Mock para el segundo YoutubeDL (download)
    mock_ydl_download = MagicMock()
    mock_ydl_download.extract_info.return_value = {
        "id": "test_id",
        "url": "http://example.com/video",
        "ext": "mp4"
    }
    mock_ydl_download.__enter__.return_value = mock_ydl_download
    mock_ydl_download.__exit__.return_value = False
    
    # Configurar el mock_ydl_class para devolver primero listing y luego download
    mock_ydl_class.side_effect = [mock_ydl_listing, mock_ydl_download]
    
    # Hacer que _append_to_inventory falle
    mock_append.side_effect = Exception("Inventory update failed")

    with pytest.raises(InventoryUpdateError):
        ingest("http://example.com/video")
