# Social-Media-Sync

Sistema de sincronización y edición aleatoria de video (ingestión → edición → publicación).

## Descripción

Social-Media-Sync es un conjunto de utilidades y scripts para:
- descubrir/ingestar videos usando `yt-dlp` y registrar metadatos en un inventario Parquet,
- aplicar transformaciones aleatorias y ligeras (zoom, espejo, color, velocidad) para generar contenido único con MoviePy,
- exponer utilidades para integración con orquestadores (por ejemplo `n8n`) para publicar y marcar videos.

El proyecto está optimizado para `polars-lts-cpu` y maneja timestamps en UTC para compatibilidad y reproducibilidad.

## Tecnologías

- polars-lts-cpu (manipulación rápida de DataFrames y Parquet)
- MoviePy 2.x (edición de video)
- yt-dlp (descarga de video)
- filelock (bloqueo simple para concurrencia) 

## Instalación

### Desarrollo Local

1. Crear y activar un entorno virtual:

```bash
python -m venv .venv
. .venv/bin/activate
```

2. Instalar dependencias (runtime):

```bash
pip install -r requirements.txt
```

3. (Opcional) Instalar dependencias de desarrollo:

```bash
pip install -r requirements-dev.txt
```

Notas:
- Asegúrate de tener `ffmpeg` disponible en el sistema si ejecutas MoviePy contra videos reales (por ejemplo `sudo apt install ffmpeg`).
- Si trabajas localmente con Playwright (usado por algunas rutinas de scraping), ejecuta:

```bash
playwright install
```

El `Dockerfile.n8n` ya instala navegadores Playwright y `ffmpeg` en el contenedor, por lo que estos pasos son necesarios solo para desarrollo local fuera de Docker.

### Despliegue en VM/Producción

Para despliegue en un servidor Linux limpio (Ubuntu/Debian), consulta la [Guía de Despliegue](DEPLOYMENT.md) que incluye:

1. **Provisión automática del sistema:**
   ```bash
   sudo bash provision.sh
   ```
   Instala Python 3, FFmpeg, Docker y Docker Compose.

2. **Orquestación con n8n:**

   Este repositorio no incluye `docker-compose.yml` por seguridad. Copia `docker-compose.yml.example` a `docker-compose.yml` y crea un archivo `.env` con las variables necesarias antes de ejecutar `docker-compose up -d`.

   Ejemplo:

   ```bash
   cp docker-compose.yml.example docker-compose.yml
   # editar .env según necesidades
   docker-compose up -d
   ```

   Levanta n8n para automatizar workflows de ingestión, edición y publicación.

## Uso

- Ingestor: el módulo `scripts/ingestor.py` expone funciones para ingestión (por ejemplo `ingest_from_hashtag`) pero actualmente no tiene un entrypoint CLI `python -m scripts.ingestor`.

   Ejemplo de llamada programática rápida desde la línea de comandos:

   ```bash
   python -c "from scripts.ingestor import ingest_from_hashtag; ingest_from_hashtag('https://www.tiktok.com/tag/programacion', max_videos=1)"
   ```

   Si prefieres un CLI, puedo añadir un wrapper `if __name__ == '__main__'` en `scripts/ingestor.py` (
   dime si quieres que lo implemente).

- Editor: procesa el primer video `pending` y lo transforma/ejecuta export (este módulo sí tiene un entrypoint):

```bash
python -m scripts.editor
```

- Publicador (CLI): obtener el siguiente procesado, marcar un video como publicado o como fallido (diseñado para ser llamado por orquestadores como n8n):

```bash
python -m scripts.publicador --get-next
python -m scripts.publicador --mark-posted <VIDEO_ID>
python -m scripts.publicador --mark-failed <VIDEO_ID>
```

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
