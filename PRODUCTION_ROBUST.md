# Production Configuration Guide - Option B (Robust)

## 🎯 Implemented Improvements

### 1. ✅ Chromium Auto-Installation
- **Dockerfile.n8n**: Browser installs automatically as `node` user
- Location: `/home/node/.cache/ms-playwright/chromium*`
- No manual installation needed on container rebuild

### 2. ✅ User-Agent Rotation
- **Pool of 12 realistic user agents** (Chrome, Firefox, Safari, Edge)
- Random selection on each scraping operation
- Reduces detection and blocking by TikTok

### 3. ✅ Selector Fallback Strategy
- **3 CSS selectors** with automatic fallback:
  1. `a[href*="/video/"]` - Primary selector
  2. `a[data-e2e="search-card-video-link"]` - Search results
  3. `div[data-e2e="search-card-desc"] a` - Description links
- Resilient to TikTok UI changes

### 4. ✅ Structured Logging
- **JSON-formatted logs** with contextual data
- Includes: timestamps, URLs, error types, progress tracking
- Easy parsing for log aggregation tools (Elasticsearch, Splunk, etc.)

### 5. ✅ Configurable Timeouts
Configure via environment variables in `docker-compose.yml`:

```yaml
environment:
  - TIKTOK_TIMEOUT=45000          # Page load timeout (ms)
  - TIKTOK_SCROLL_ATTEMPTS=3      # Number of scroll attempts
  - TIKTOK_SCROLL_WAIT_MIN=2      # Min wait between scrolls (s)
  - TIKTOK_SCROLL_WAIT_MAX=5      # Max wait between scrolls (s)
```

### 6. ✅ Improved Error Handling
- **Detailed progress tracking**: Shows N/M videos processed
- **Success rate calculation**: Percentage of successful ingests
- **Failed URLs tracking**: List of failed videos with error details
- Continues processing remaining videos on failure

### 7. ✅ Health Check Script
Run: `docker exec social-media-sync-n8n python3 /workspace/social-media-sync/scripts/health_check.py`

Checks:
- Python imports
- Playwright browser availability
- File system permissions
- Inventory access

Returns exit code 0 (healthy) or 1 (unhealthy).

### 8. ✅ Enhanced n8n Workflow
**New workflow**: `ingestor-production-robust.json`

Features:
- **Error branching**: Separate paths for success/error
- **Status checking**: IF node validates execution result
- **Structured output**: JSON-formatted metrics
- **Success rate tracking**: Calculates ingestion performance
- **Duration tracking**: Execution time measurement
- **Error alerts**: Formatted error messages (ready for webhook integration)

## 🚀 Usage

### Starting the System

```bash
# Build and start
docker compose up -d --build

# Check logs
docker compose logs -f n8n

# Verify health
docker exec social-media-sync-n8n python3 /workspace/social-media-sync/scripts/health_check.py
```

### Accessing n8n

1. Open: http://localhost:5678
2. Import workflow: `n8n-workflows/ingestor-production-robust.json`
3. Click "Execute Workflow" to test

### Monitoring

**View structured logs:**
```bash
docker compose logs n8n | grep -E 'level|event|error'
```

**Check inventory:**
```bash
docker exec social-media-sync-n8n python3 -c "
import polars as pl
from pathlib import Path
df = pl.read_parquet('data/inventario_videos.parquet')
print(df.tail(10))
print(f'\\nTotal videos: {len(df)}')
print(df['status_fb'].value_counts())
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

### Workflow Configuration

Edit node "Set Hashtag Config":
```json
{
  "hashtag_url": "https://www.tiktok.com/tag/your-hashtag",
  "max_videos": "5"
}
```

## 🔧 Troubleshooting

### Chromium Not Found
```bash
# Verify installation
docker exec social-media-sync-n8n bash -c "find /home/node/.cache -name 'chromium-*' -type d"

# Reinstall if needed
docker exec -u node social-media-sync-n8n playwright install chromium
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
