#!/bin/bash
# Script para ejecutar el pipeline de ingestión de TikTok

HASHTAG="${1:-programacion}"
MAX_VIDEOS="${2:-3}"

echo "🚀 Ejecutando Pipeline de Ingestión TikTok"
echo "   Hashtag: #$HASHTAG"
echo "   Max videos: $MAX_VIDEOS"
echo ""

docker exec social-media-sync-n8n python3 -c "
from scripts.ingestor import ingest_from_hashtag
result = ingest_from_hashtag('https://www.tiktok.com/tag/$HASHTAG', max_videos=$MAX_VIDEOS)
print(f'\\n✅ Videos descargados: {result}')
"

echo ""
echo "📊 Estado del inventario:"
docker exec social-media-sync-n8n python3 -c "
import polars as pl
from pathlib import Path
inv = Path('/workspace/social-media-sync/data/inventario_videos.parquet')
if inv.exists():
    df = pl.read_parquet(str(inv))
    print(f'   Total videos: {len(df)}')
    counts = df['status_fb'].value_counts()
    print('   Por status:')
    for row in counts.iter_rows():
        print(f'      {row[0]}: {row[1]}')
else:
    print('   No hay inventario aún')
"
