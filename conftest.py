import sys
from pathlib import Path
import os

# Ensure the repository root is on sys.path for pytest collection/imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# During tests we skip any artificial waits/backoff to keep runs fast.
os.environ.setdefault("SKIP_WAITS", "1")
