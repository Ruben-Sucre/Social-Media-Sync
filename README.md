# Social-Media-Sync

Sistema de sincronización y edición aleatoria de video (ingestión → edición → publicación).

## Descripción

Social-Media-Sync es un conjunto de utilidades y scripts para:
- descubrir/ingestar videos de TikTok usando `yt-dlp` + `playwright` y registrar metadatos en un inventario Parquet,
- aplicar transformaciones aleatorias y ligeras (zoom, espejo, color, velocidad) para generar contenido único con MoviePy,
- exponer utilidades para integración con orquestadores (por ejemplo `n8n`) para publicar y marcar videos,
- **auto-limpieza** de videos procesados que no se publican dentro de 48 horas.

El proyecto está optimizado para `polars-lts-cpu` y maneja timestamps en UTC para compatibilidad y reproducibilidad.

## 🚀 Quick Start

```bash
# Clonar e iniciar
git clone https://github.com/Ruben-Sucre/Social-Media-Sync.git
cd Social-Media-Sync
docker compose up -d --build

# Instalar dependencias en el contenedor (primera vez)
docker exec --user root social-media-sync-n8n pip install curl_cffi
docker exec --user root social-media-sync-n8n playwright install chromium

# Ejecutar pipeline de ingestión
./run_pipeline.sh programacion 5    # Descarga 5 videos del hashtag #programacion
./run_pipeline.sh tech 3            # Descarga 3 videos del hashtag #tech

# Procesar videos (aplicar transformaciones)
docker exec social-media-sync-n8n python3 -m scripts.editor
```

## Tecnologías

- **polars-lts-cpu** - Manipulación rápida de DataFrames y Parquet
- **MoviePy 2.x** - Edición de video (zoom, mirror, color, speed)
- **yt-dlp** - Descarga de video con impersonación Chrome
- **curl_cffi** - Bypass de protección anti-bot TikTok (403)
- **Playwright** - Scraping de hashtags TikTok
- **filelock** - Bloqueo simple para concurrencia
- **n8n** - Orquestación de workflows (opcional) 

## Instalación

### Docker (Recomendado)

```bash
# Clonar repositorio
git clone https://github.com/Ruben-Sucre/Social-Media-Sync.git
cd Social-Media-Sync

# Iniciar contenedor
docker compose up -d --build

# Instalar dependencias adicionales (primera vez)
docker exec --user root social-media-sync-n8n pip install curl_cffi
docker exec --user root social-media-sync-n8n playwright install chromium
docker exec --user root social-media-sync-n8n chmod -R 777 /workspace/social-media-sync/videos /workspace/social-media-sync/data
```

### Desarrollo Local

1. Crear y activar un entorno virtual:

```bash
python -m venv .venv
. .venv/bin/activate
```

2. Instalar dependencias (runtime):

```bash
pip install -r requirements.txt
playwright install chromium
```

3. (Opcional) Instalar dependencias de desarrollo:

```bash
pip install -r requirements-dev.txt
```

**Requisitos del sistema:**
- `ffmpeg` para MoviePy: `sudo apt install ffmpeg`
- Python 3.12+

### Despliegue en VM/Producción

Para despliegue en un servidor Linux limpio (Ubuntu/Debian), consulta la [Guía de Despliegue](DEPLOYMENT.md) que incluye:

1. **Provisión automática del sistema:**
   ```bash
   sudo bash provision.sh
   ```
   Instala Python 3, FFmpeg, Docker y Docker Compose.

2. **Orquestación con n8n:**

   ```bash
   cp docker-compose.yml.example docker-compose.yml
   docker compose up -d --build
   ```

   Levanta n8n para automatizar workflows de ingestión, edición y publicación.

3. **Configuración robusta:** Ver [PRODUCTION_ROBUST.md](PRODUCTION_ROBUST.md)

## Uso

### Script de Pipeline (Recomendado)

```bash
# Sintaxis: ./run_pipeline.sh <hashtag> <max_videos>
./run_pipeline.sh programacion 5    # Descarga 5 videos de #programacion
./run_pipeline.sh python 3          # Descarga 3 videos de #python
./run_pipeline.sh tech 10           # Descarga 10 videos de #tech
```

El script automáticamente:
1. Ejecuta cleanup de videos viejos (>48h)
2. Descarga nuevos videos del hashtag
3. Muestra el estado del inventario

### Ingestor (Programático)

```bash
docker exec social-media-sync-n8n python3 -c "
from scripts.ingestor import ingest_from_hashtag
result = ingest_from_hashtag('https://www.tiktok.com/tag/programacion', max_videos=5)
print(f'Videos descargados: {result}')
"
```

### Editor (Procesar Videos)

Procesa el primer video `pending` aplicando transformaciones aleatorias:

```bash
# Procesar un video
docker exec social-media-sync-n8n python3 -m scripts.editor

# Procesar todos los pendientes
docker exec social-media-sync-n8n python3 -c "
from scripts.editor import process_pending
while process_pending() > 0: pass
"
```

### Cleanup (Auto-limpieza)

Elimina videos `ready` que no se publicaron después de N horas:

```bash
# Ver qué se borraría (dry-run)
docker exec social-media-sync-n8n python3 -m scripts.cleanup --dry-run --hours 48

# Ejecutar cleanup
docker exec social-media-sync-n8n python3 -m scripts.cleanup --hours 48
```

### Publicador (CLI)

```bash
# Obtener siguiente video listo
docker exec social-media-sync-n8n python3 -m scripts.publicador --get-next

# Marcar como publicado
docker exec social-media-sync-n8n python3 -m scripts.publicador --mark-posted <VIDEO_ID>

# Marcar como fallido
docker exec social-media-sync-n8n python3 -m scripts.publicador --mark-failed <VIDEO_ID>
```

## Estados del Inventario

| Status | Descripción |
|--------|-------------|
| `pending` | Video descargado, esperando procesamiento |
| `ready` | Video procesado, listo para publicar |
| `posted` | Video publicado exitosamente |
| `failed` | Error en descarga/procesamiento/publicación |
| `expired` | Video eliminado por auto-cleanup (>48h sin publicar) |

## Pruebas

El proyecto cuenta con una suite de tests que cubre los flujos principales.

Ejecuta todos los tests con:

```bash
pytest -v tests
```

Los tests usan `pytest` y `pytest-mock` para simular dependencias externas (MoviePy, YoutubeDL) y son rápidos y deterministas.

## Limpieza y Mantenimiento

Antes de desplegar en producción o hacer commits importantes, limpia archivos temporales y de prueba:

```bash
bash cleanup.sh
```

Este script elimina:
- Videos de prueba en `videos/raw/` y `videos/processed/`
- Logs antiguos en `logs/`
- Cache de Python (`__pycache__`, archivos `.pyc`, `.pyo`)

**Nota:** El inventario de datos (`data/*.parquet`) se conserva por defecto. Descomenta la línea correspondiente en el script si deseas limpiar también el inventario.

## Manejo de Errores

El sistema implementa un manejo de errores centralizado y explícito:

- Todas las operaciones críticas (ingestión, edición, publicación) capturan y reportan excepciones personalizadas definidas en `scripts/exceptions.py`.
- Los errores se registran en logs y el inventario se actualiza con el estado correspondiente (`failed`, etc.), permitiendo trazabilidad y recuperación.
- Los tests incluyen casos de error para validar que el sistema responde correctamente ante fallos de red, archivos corruptos o dependencias externas.

Esto garantiza que el flujo de trabajo sea resiliente y fácil de depurar ante cualquier incidente.

## n8n — integración y despliegue

1. Copia el ejemplo de Docker Compose y crea un `.env` (mínimo):

```bash
cp docker-compose.yml.example docker-compose.yml
cat > .env <<'EOF'
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=changeme
N8N_HOST=localhost
N8N_PORT=5678
GENERICS_TIMEZONE=UTC
EOF
```

2. Levanta n8n (el `Dockerfile.n8n` incluye Python y Playwright):

```bash
docker compose up -d --build
```

3. Importa `n8n-workflows/ingestor-production-robust.json` en la UI de n8n y ejecuta `Manual Trigger`.

Notas específicas del workflow:
- `Set Hashtag Config` ahora incluye `debug_set = "activo"` (variable de depuración añadida), pero el nodo de código `Run Hashtag Ingestor` solo consume `hashtag_url` y `max_videos`.
- Para inspeccionar resultados: abre la ejecución en la UI de n8n y revisa la salida del nodo `Run Hashtag Ingestor` y `Verify Inventory`.

## Depuración rápida

- Saltar esperas en pruebas/depuración:

```bash
export SKIP_WAITS=1
```

- Ver logs del contenedor n8n y del sistema:

```bash
docker compose logs -f n8n
tail -f logs/pipeline.log
```

- Comprobar inventario directamente desde Python REPL:

```bash
python -c "from scripts.common import read_inventory; print(read_inventory().tail(10))"
```

## Notas y gaps conocidos

- No existe un `.env` por defecto en el repo — crea uno a partir de `docker-compose.yml.example` antes de levantar n8n.
- `scripts/ingestor.py` no provee un entrypoint CLI; el README ahora documenta una llamada programática. Puedo añadir un wrapper CLI si lo deseas.
- `debug_set` se añadió al workflow como bandera de depuración pero actualmente no es utilizada por el nodo de código.

## Notas de diseño

- El inventario se mantiene en `data/inventario_videos.parquet` y es el registro de verdad.
- Fechas y timestamps se manejan en UTC y las columnas `created_at` y `updated_at` tienen zona horaria explícita (`UTC`).
- Se usa `filelock` para evitar condiciones de carrera cuando varios procesos actualizan el inventario.

---

Para más detalles o integraciones (Playwright, pipelines CI/CD, despliegue), dime qué priorizar y lo abordamos por sprints.
