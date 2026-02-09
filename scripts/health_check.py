#!/usr/bin/env python3
"""Health check script for production monitoring.

This script verifies that all critical components are functioning:
- Python imports
- Playwright browser availability
- File system permissions
- Inventory access

Exit codes:
    0: All checks passed (healthy)
    1: One or more checks failed (unhealthy)
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone


def check_imports() -> bool:
    """Verify all critical Python imports."""
    try:
        import polars
        import playwright
        import yt_dlp
        from scripts.ingestor import procesar_hashtag, ingest_from_hashtag
        from scripts.common import ensure_dirs, logger
        print("✓ All Python imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def check_playwright_browser() -> bool:
    """Verify Playwright browser is installed."""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        
        print("✓ Playwright Chromium browser available")
        return True
    except Exception as e:
        print(f"✗ Playwright browser check failed: {e}")
        return False


def check_directories() -> bool:
    """Verify critical directories exist and are writable."""
    from scripts.common import DATA_DIR, RAW_DIR, LOGS_DIR, ensure_dirs
    
    try:
        ensure_dirs()
        
        # Test write permission
        test_file = DATA_DIR / ".health_check_test"
        test_file.write_text("test")
        test_file.unlink()
        
        print(f"✓ Directories exist and writable:")
        print(f"  - DATA_DIR: {DATA_DIR}")
        print(f"  - RAW_DIR: {RAW_DIR}")
        print(f"  - LOGS_DIR: {LOGS_DIR}")
        return True
    except Exception as e:
        print(f"✗ Directory check failed: {e}")
        return False


def check_inventory() -> bool:
    """Verify inventory file is accessible."""
    try:
        from scripts.common import INVENTORY_PATH, ensure_inventory
        import polars as pl
        
        ensure_inventory()
        
        if INVENTORY_PATH.exists():
            df = pl.read_parquet(str(INVENTORY_PATH))
            print(f"✓ Inventory accessible ({len(df)} videos)")
        else:
            print("✓ Inventory initialized (empty)")
        
        return True
    except Exception as e:
        print(f"✗ Inventory check failed: {e}")
        return False


def main() -> int:
    """Run all health checks."""
    print(f"🏥 Health Check - {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    checks = [
        ("Python Imports", check_imports),
        ("Playwright Browser", check_playwright_browser),
        ("File System", check_directories),
        ("Inventory Access", check_inventory),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n[{name}]")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"✗ Unexpected error in {name}: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"✅ All checks passed ({passed}/{total})")
        return 0
    else:
        print(f"❌ Some checks failed ({passed}/{total})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
