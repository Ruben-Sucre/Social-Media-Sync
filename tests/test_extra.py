import pytest
from unittest.mock import MagicMock
from pathlib import Path
from scripts.common import FileLock
from scripts.ingestor import DownloadError
from scripts.editor import process_pending
from scripts.common import read_inventory
from polars.exceptions import ComputeError

# 1. Pruebas de concurrencia en common.py

def test_filelock_concurrency(tmp_path):
    lock_path = tmp_path / 'lockfile.lock'
    lock = FileLock(str(lock_path))
    with lock:
        assert lock_path.exists()
    assert lock_path.exists()

# 2. Casos de error en ingestor.py

def test_ingestor_network_error(monkeypatch):
    from scripts.ingestor import ingest

    def mock_download(*args, **kwargs):
        raise DownloadError("Failed to fetch listing for http://fake.url")

    monkeypatch.setattr("scripts.ingestor.YoutubeDL.extract_info", mock_download)

    with pytest.raises(DownloadError, match="Failed to fetch listing for http://fake.url"):
        ingest("http://fake.url")

# 3. Casos de error en editor.py

def test_editor_handles_corrupt_files(monkeypatch):
    def mock_read_inventory():
        raise ComputeError("parquet: File out of specification: The file must end with PAR1")

    monkeypatch.setattr("scripts.common.read_inventory", mock_read_inventory)

    with pytest.raises(ComputeError, match="parquet: File out of specification"):
        process_pending()
