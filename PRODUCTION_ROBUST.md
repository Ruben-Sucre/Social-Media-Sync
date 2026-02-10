# Production Configuration Guide - Option B (Robust)

## 🎯 Implemented Improvements

### 1. ✅ Chromium Auto-Installation
- **Dockerfile.n8n**: Browser installs automatically
- Location: `/ms-playwright/chromium*`
- No manual installation needed on container rebuild

### 2. ✅ TikTok Anti-Bot Bypass (curl_cffi)
- **Chrome impersonation** via `curl_cffi` + `yt-dlp`
- Bypasses TikTok 403 Forbidden errors
- Uses `ImpersonateTarget(client="chrome")` for requests

### 3. ✅ User-Agent Rotation
- **Pool of 12 realistic user agents** (Chrome, Firefox, Safari, Edge)
- Random selection on each scraping operation
- Reduces detection and blocking by TikTok

### 4. ✅ Selector Fallback Strategy
- **3 CSS selectors** with automatic fallback:
  1. `a[href*="/video/"]` - Primary selector
  2. `a[data-e2e="search-card-video-link"]` - Search results
  3. `div[data-e2e="search-card-desc"] a` - Description links
- Resilient to TikTok UI changes

### 5. ✅ Structured Logging
- **JSON-formatted logs** with contextual data
- Includes: timestamps, URLs, error types, progress tracking
- Easy parsing for log aggregation tools (Elasticsearch, Splunk, etc.)

### 6. ✅ Auto-Cleanup of Old Videos
- Videos with `status='ready'` older than 48 hours are automatically deleted
- Files removed from disk, status changed to `expired`
- Configurable via `--hours` parameter

### 7. ✅ Configurable Timeouts
Configure via environment variables in `docker-compose.yml`:

```yaml
environment:
  - TIKTOK_TIMEOUT=45000          # Page load timeout (ms)
  - TIKTOK_SCROLL_ATTEMPTS=3      # Number of scroll attempts
  - TIKTOK_SCROLL_WAIT_MIN=2      # Min wait between scrolls (s)
  - TIKTOK_SCROLL_WAIT_MAX=5      # Max wait between scrolls (s)
```

### 8. ✅ Improved Error Handling
- **Detailed progress tracking**: Shows N/M videos processed
- **Success rate calculation**: Percentage of successful ingests
- **Failed URLs tracking**: List of failed videos with error details
- Continues processing remaining videos on failure

### 9. ✅ Health Check Script
Run: `docker exec social-media-sync-n8n python3 /workspace/social-media-sync/scripts/health_check.py`

Checks:
- Python imports
- Playwright browser availability
- File system permissions
- Inventory access

Returns exit code 0 (healthy) or 1 (unhealthy).

### 10. ✅ Enhanced n8n Workflow
**Workflow**: `n8n-workflows/ingestor-production-robust.json`

Features:
- **Error branching**: Separate paths for success/error
- **Status checking**: IF node validates execution result
- **Structured output**: JSON-formatted metrics
- **Success rate tracking**: Calculates ingestion performance
- **Duration tracking**: Execution time measurement
- **Error alerts**: Formatted error messages (ready for webhook integration)

## 🚀 Usage

### Quick Start (CLI)

The easiest way to run the pipeline:

```bash
# Run complete pipeline (cleanup + ingestor)
./run_pipeline.sh <hashtag> <max_videos>

# Examples
./run_pipeline.sh tech 5
./run_pipeline.sh programacion 10
```

### Manual Execution

```bash
# Cleanup old ready videos (48 hours)
docker exec social-media-sync-n8n python3 -m scripts.cleanup

# Preview what would be deleted
docker exec social-media-sync-n8n python3 -m scripts.cleanup --dry-run

# Custom cleanup threshold (72 hours)
docker exec social-media-sync-n8n python3 -m scripts.cleanup --hours 72

# Run ingestor
docker exec social-media-sync-n8n python3 -c "
from scripts.ingestor import procesar_hashtag
procesar_hashtag('https://www.tiktok.com/tag/tech', max_videos=5)
"

# Run editor (process pending videos)
docker exec social-media-sync-n8n python3 -c "
from scripts.editor import procesar_pendientes
procesar_pendientes()
"

# Check inventory
docker exec social-media-sync-n8n python3 -c "
import polars as pl
df = pl.read_parquet('data/inventario_videos.parquet')
print(df.group_by('status_fb').len())
"
```

### Starting the System

```bash
# Build and start
docker compose up -d --build

# Check logs
docker compose logs -f n8n

# Verify health
docker exec social-media-sync-n8n python3 /workspace/social-media-sync/scripts/health_check.py
```

### Accessing n8n (Optional)

> **Note**: n8n UI may have connection issues in GitHub Codespaces due to WebSocket proxy limitations. Use CLI commands above as alternative.

1. Open: http://localhost:5678
2. Import workflow: `n8n-workflows/ingestor-production-robust.json`
3. Click "Execute Workflow" to test

### Monitoring

**View structured logs:**
```bash
docker compose logs n8n | grep -E 'level|event|error'
```

**Check inventory by status:**
```bash
docker exec social-media-sync-n8n python3 -c "
import polars as pl
df = pl.read_parquet('data/inventario_videos.parquet')
print(df.group_by('status_fb').len())
print(f'\\nTotal videos: {len(df)}')
"
```

**Show all video records:**
```bash
docker exec social-media-sync-n8n python3 -c "
import polars as pl
df = pl.read_parquet('data/inventario_videos.parquet')
print(df)
"
```

## 📊 Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TIKTOK_TIMEOUT` | 45000 | Page load timeout in milliseconds |
| `TIKTOK_SCROLL_ATTEMPTS` | 3 | Number of scrolls to load videos |
| `TIKTOK_SCROLL_WAIT_MIN` | 2 | Min wait between scrolls (seconds) |
| `TIKTOK_SCROLL_WAIT_MAX` | 5 | Max wait between scrolls (seconds) |
| `SKIP_WAITS` | - | Set to "1" to skip waits (testing only) |

### Cleanup Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--hours` | 48 | Delete videos older than N hours |
| `--dry-run` | false | Preview only, don't delete |

### Workflow Configuration

Edit node "Set Hashtag Config":
```json
{
  "hashtag_url": "https://www.tiktok.com/tag/your-hashtag",
  "max_videos": "5"
}
```

## 🔧 Troubleshooting

### TikTok HTTP 403 Forbidden
This is typically caused by TikTok's anti-bot protection.

```bash
# Verify curl_cffi is installed
docker exec social-media-sync-n8n python3 -c "import curl_cffi; print('curl_cffi OK')"

# Verify impersonation works
docker exec social-media-sync-n8n python3 -c "
from yt_dlp.networking.impersonate import ImpersonateTarget
print('ImpersonateTarget OK')
"
```

If not installed, rebuild the container:
```bash
docker compose down
docker compose up -d --build
```

### Chromium Not Found
```bash
# Verify installation
docker exec social-media-sync-n8n bash -c "find /ms-playwright -name 'chromium*' -type d 2>/dev/null"

# Reinstall if needed
docker exec --user root social-media-sync-n8n playwright install chromium
```

### Permission Denied Errors
```bash
# Fix permissions on host directories
chmod -R 777 videos data logs
```

### n8n "Lost Connection" in Codespaces
GitHub Codespaces proxy doesn't handle WebSockets well. Options:

1. **Use CLI** (recommended): Run `./run_pipeline.sh` instead of n8n UI
2. **Or** set SSE backend in docker-compose.yml:
```yaml
environment:
  - N8N_PUSH_BACKEND=sse
  - N8N_SECURE_COOKIE=false
```

### High Rate Limiting
Adjust timeouts to be more conservative:
```yaml
environment:
  - TIKTOK_TIMEOUT=60000              # Increase timeout
  - TIKTOK_SCROLL_WAIT_MIN=5          # Longer waits
  - TIKTOK_SCROLL_WAIT_MAX=10
```

### Import Errors
```bash
# Verify Python path
docker exec social-media-sync-n8n python3 -c "import sys; print(sys.path)"

# Test imports
docker exec social-media-sync-n8n python3 -c "from scripts.ingestor import procesar_hashtag; print('OK')"
```

## 📈 Next Steps (Optional - Option C)

To upgrade to Production-Grade (Option C):

1. **Circuit Breaker**: Pause after N consecutive failures
2. **Proxy Rotation**: Integrate proxy pool for IP rotation
3. **Webhook Notifications**: Discord/Slack/Telegram alerts
4. **Metrics Export**: Prometheus-compatible metrics endpoint
5. **Docker Health Checks**: Native Docker health monitoring
6. **Systemd Service**: Auto-restart on system reboot

## 🔐 Security Notes

- Disable n8n basic auth (`N8N_BASIC_AUTH_ACTIVE=false`) for development
- **Enable for production** with strong credentials
- Consider firewall rules to restrict port 5678 access
- Use HTTPS reverse proxy (nginx/Caddy) for production

## 📝 Log Format Example

```json
{
  "level": "INFO",
  "event": "ingest_start",
  "hashtag_url": "https://www.tiktok.com/tag/programacion",
  "max_videos": 5,
  "timestamp": "2026-02-09T12:00:00Z"
}
```

```json
{
  "level": "INFO",
  "event": "ingest_complete",
  "hashtag_url": "https://www.tiktok.com/tag/programacion",
  "videos_ingested": 4,
  "max_videos": 5,
  "success_rate": 80.0,
  "duration_seconds": 45.23,
  "failed_urls": [{"url": "...", "error": "..."}]
}
```
